use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{BufReader, BufWriter, Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

use ed25519_dalek::{Signature, Signer, Verifier};
use rayon::prelude::*;
use reed_solomon_erasure::{ReedSolomon, galois_8};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::error::{CoreError, Result};
use crate::fitrec::{SignatureAlgorithm, SignatureHeader};
use crate::manifest::{FitDocument, sha256_hex};

const MAGIC: [u8; 8] = *b"FITPAR1\0";
const SIGNATURE_LENGTH: usize = 64;
const DEFAULT_SHARD_SIZE: u32 = 1024 * 1024;
const ENCODE_BATCH: usize = 4;

type FileRecoveryProgress = Arc<dyn Fn(u64, u64, &str) + Send + Sync>;
type ProgressCallback = Option<FileRecoveryProgress>;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum FileRecoveryMode {
    SingleFile,
    #[default]
    CrossFile,
    Dual,
}

#[derive(Clone, Copy, Debug)]
pub struct FileRecoveryOptions {
    pub data_shards: u8,
    pub parity_shards: u8,
    pub shard_size: u32,
    pub mode: FileRecoveryMode,
}

impl Default for FileRecoveryOptions {
    fn default() -> Self {
        Self {
            data_shards: 8,
            parity_shards: 4,
            shard_size: DEFAULT_SHARD_SIZE,
            mode: FileRecoveryMode::CrossFile,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
struct SourcePlan {
    path: String,
    hash: String,
    size: u64,
}

#[derive(Clone, Debug)]
struct SinglePlan {
    source: SourcePlan,
    parity_offset: u64,
    parity_len: u64,
    blocks: u64,
}

#[derive(Clone, Debug)]
struct CrossPlan {
    sources: Vec<SourcePlan>,
    lane_count: u16,
    block_count: u64,
    parity_offset: u64,
    parity_len: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct FileRecoveryEntry {
    pub path: String,
    pub sha256: String,
    pub size: u64,
    pub parity_offset: u64,
    pub parity_len: u64,
    pub shard_sha256: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cross_group: Option<usize>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cross_lane: Option<u16>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub cross_data_sha256: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
struct RecoveryGroup {
    parity_offset: u64,
    parity_len: u64,
    lane_count: u16,
    block_count: u64,
    parity_sha256: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
struct RecoveryHeader {
    format: String,
    version: u32,
    manifest_hash: String,
    data_shards: u8,
    parity_shards: u8,
    shard_size: u32,
    #[serde(default)]
    mode: FileRecoveryMode,
    files: Vec<FileRecoveryEntry>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    groups: Vec<RecoveryGroup>,
    signature: SignatureHeader,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileRecoveryInfo {
    pub data_shards: u8,
    pub parity_shards: u8,
    pub shard_size: u32,
    pub mode: FileRecoveryMode,
    pub file_count: usize,
    pub total_size: u64,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileRecoveryEstimate {
    pub mode: FileRecoveryMode,
    pub file_count: usize,
    pub group_count: usize,
    pub recoverable_files: usize,
    pub recoverable_ratio: f64,
    pub parity_size: u64,
    pub header_size: u64,
    pub total_size: u64,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileRecoveryDetail {
    pub path: String,
    pub status: String,
    pub message: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileRecoveryReport {
    pub total: usize,
    pub repaired: usize,
    pub healthy: usize,
    pub missing: usize,
    pub failed: usize,
    pub details: Vec<FileRecoveryDetail>,
}

pub fn load_file_recovery<P: AsRef<Path>>(
    path: P,
    verifying_key: &crate::fitrec::VerifyingKey,
) -> Result<FileRecoveryInfo> {
    let (header, _) = read_header(path, verifying_key)?;
    Ok(FileRecoveryInfo {
        data_shards: header.data_shards,
        parity_shards: header.parity_shards,
        shard_size: header.shard_size,
        mode: header.mode,
        file_count: header.files.len(),
        total_size: header.files.iter().map(|entry| entry.size).sum(),
    })
}

pub fn write_file_recovery<P: AsRef<Path>, Q: AsRef<Path>>(
    directory: P,
    output_path: Q,
    document: &FitDocument,
    signing_key: &crate::fitrec::SigningKey,
    options: FileRecoveryOptions,
) -> Result<()> {
    write_file_recovery_with_progress(
        directory,
        output_path,
        document,
        signing_key,
        options,
        None,
        None,
    )
}

fn blocks_for(size: u64, shard_size: u32) -> u64 {
    if size == 0 {
        0
    } else {
        size.div_ceil(u64::from(shard_size))
    }
}

fn source_plans(directory: &Path, document: &FitDocument) -> Result<Vec<SourcePlan>> {
    let mut plans = Vec::new();
    for entry in document.active_entries()? {
        let source_path = directory.join(&entry.path);
        let metadata = fs::metadata(&source_path)?;
        if !metadata.is_file() {
            return Err(CoreError::Manifest("recovery source is not a file"));
        }
        if entry.size.is_some_and(|size| size != metadata.len()) {
            return Err(CoreError::SourceChanged {
                path: entry.path.clone(),
                reason: "file size changed",
            });
        }
        plans.push(SourcePlan {
            path: entry.path.clone(),
            hash: entry.hash.clone(),
            size: metadata.len(),
        });
    }
    Ok(plans)
}

fn balanced_cross_groups(mut plans: Vec<SourcePlan>, data_shards: u8) -> Vec<Vec<SourcePlan>> {
    plans.sort_by(|left, right| {
        right
            .size
            .cmp(&left.size)
            .then_with(|| left.path.cmp(&right.path))
    });
    if plans.is_empty() {
        return Vec::new();
    }
    let group_count = plans.len().div_ceil(usize::from(data_shards));
    let base_size = plans.len() / group_count;
    let remainder = plans.len() % group_count;
    let mut groups = Vec::with_capacity(group_count);
    let mut cursor = 0_usize;
    for index in 0..group_count {
        let length = base_size + usize::from(index < remainder);
        groups.push(plans[cursor..cursor + length].to_vec());
        cursor += length;
    }
    groups
}

fn build_single_plans(
    sources: &[SourcePlan],
    options: &FileRecoveryOptions,
    mut offset: u64,
) -> (Vec<SinglePlan>, u64) {
    let parity_unit = u64::from(options.parity_shards) * u64::from(options.shard_size);
    let mut plans = Vec::with_capacity(sources.len());
    for source in sources {
        let blocks = blocks_for(source.size, options.shard_size);
        let parity_len = blocks * parity_unit;
        plans.push(SinglePlan {
            source: source.clone(),
            parity_offset: offset,
            parity_len,
            blocks,
        });
        offset += parity_len;
    }
    (plans, offset)
}

fn build_cross_plans(
    sources: &[SourcePlan],
    options: &FileRecoveryOptions,
    mut offset: u64,
) -> (Vec<CrossPlan>, u64) {
    let parity_unit = u64::from(options.parity_shards) * u64::from(options.shard_size);
    let mut plans = Vec::new();
    for group in balanced_cross_groups(sources.to_vec(), options.data_shards) {
        let block_count = group
            .iter()
            .map(|source| blocks_for(source.size, options.shard_size))
            .max()
            .unwrap_or(0);
        let parity_len = block_count * parity_unit;
        plans.push(CrossPlan {
            lane_count: group.len() as u16,
            sources: group,
            block_count,
            parity_offset: offset,
            parity_len,
        });
        offset += parity_len;
    }
    (plans, offset)
}

fn rough_header_size(
    file_count: usize,
    group_count: usize,
    single_hash_count: usize,
    cross_data_hash_count: usize,
    cross_parity_hash_count: usize,
) -> u64 {
    let hash_bytes = 68_u64;
    160_u64
        + 220_u64 * file_count as u64
        + 120_u64 * group_count as u64
        + hash_bytes * single_hash_count as u64
        + hash_bytes * cross_data_hash_count as u64
        + hash_bytes * cross_parity_hash_count as u64
}

pub fn estimate_file_recovery_size<P: AsRef<Path>>(
    directory: P,
    document: &FitDocument,
    options: FileRecoveryOptions,
) -> Result<FileRecoveryEstimate> {
    document.validate()?;
    validate_options(&options)?;
    let sources = source_plans(directory.as_ref(), document)?;
    let (single_plans, _) = build_single_plans(&sources, &options, 0);
    let (cross_plans, _) = build_cross_plans(&sources, &options, 0);

    let single_blocks: u64 = single_plans.iter().map(|plan| plan.blocks).sum();
    let cross_data_blocks: u64 = cross_plans
        .iter()
        .map(|plan| plan.block_count * u64::from(plan.lane_count))
        .sum();
    let cross_parity_blocks: u64 = cross_plans
        .iter()
        .map(|plan| plan.block_count * u64::from(options.parity_shards))
        .sum();
    let single_parity = single_plans.iter().map(|plan| plan.parity_len).sum::<u64>();
    let cross_parity = cross_plans.iter().map(|plan| plan.parity_len).sum::<u64>();
    let parity_size = match options.mode {
        FileRecoveryMode::SingleFile => single_parity,
        FileRecoveryMode::CrossFile => cross_parity,
        FileRecoveryMode::Dual => single_parity + cross_parity,
    };
    let (single_hashes, cross_data, cross_parity_hashes) = match options.mode {
        FileRecoveryMode::SingleFile => (single_blocks, 0, 0),
        FileRecoveryMode::CrossFile => (0, cross_data_blocks, cross_parity_blocks),
        FileRecoveryMode::Dual => (single_blocks, cross_data_blocks, cross_parity_blocks),
    };
    let recoverable_files = match options.mode {
        FileRecoveryMode::SingleFile => {
            if options.parity_shards >= options.data_shards {
                sources.len()
            } else {
                0
            }
        }
        FileRecoveryMode::CrossFile | FileRecoveryMode::Dual => cross_plans
            .iter()
            .map(|plan| usize::from(options.parity_shards).min(usize::from(plan.lane_count)))
            .sum(),
    };
    let recoverable_ratio = if sources.is_empty() {
        0.0
    } else {
        recoverable_files as f64 / sources.len() as f64
    };
    let header_size = rough_header_size(
        sources.len(),
        if matches!(
            options.mode,
            FileRecoveryMode::CrossFile | FileRecoveryMode::Dual
        ) {
            cross_plans.len()
        } else {
            0
        },
        usize::try_from(single_hashes).unwrap_or(usize::MAX),
        usize::try_from(cross_data).unwrap_or(usize::MAX),
        usize::try_from(cross_parity_hashes).unwrap_or(usize::MAX),
    );
    Ok(FileRecoveryEstimate {
        mode: options.mode,
        file_count: sources.len(),
        group_count: cross_plans.len(),
        recoverable_files,
        recoverable_ratio,
        parity_size,
        header_size,
        total_size: 12 + 64 + header_size + parity_size,
    })
}

struct BlockInput {
    shards: Vec<Vec<u8>>,
}

struct BlockOutput {
    hashes: Vec<String>,
    parity: Vec<Vec<u8>>,
}

fn encode_block_batch(
    codec: &ReedSolomon<galois_8::Field>,
    parity_shards: usize,
    blocks: Vec<BlockInput>,
    cancel: &Option<Arc<AtomicBool>>,
) -> Result<Vec<BlockOutput>> {
    blocks
        .into_par_iter()
        .map(|mut block| {
            if is_cancelled(cancel) {
                return Err(CoreError::Cancelled);
            }
            codec.encode(&mut block.shards).map_err(|error| {
                CoreError::CodecMessage(format!(
                    "file recovery RS encoding failed: {error:?}; shards={}",
                    block.shards.len()
                ))
            })?;
            let hashes = block.shards.iter().map(|shard| sha256_hex(shard)).collect();
            let parity = block.shards.split_off(block.shards.len() - parity_shards);
            Ok(BlockOutput { hashes, parity })
        })
        .collect()
}

fn read_single_block(
    source: &mut BufReader<File>,
    hasher: &mut Sha256,
    plan: &SinglePlan,
    block_index: u64,
    shard_size: usize,
    data_shards: usize,
) -> std::result::Result<(BlockInput, u64), String> {
    let mut shards = Vec::with_capacity(data_shards);
    let mut read_bytes = 0_u64;
    for data_index in 0..data_shards {
        let mut chunk = vec![0_u8; shard_size];
        let start = (block_index * data_shards as u64 + data_index as u64) * shard_size as u64;
        if start < plan.source.size {
            let wanted = std::cmp::min(shard_size as u64, plan.source.size - start) as usize;
            source
                .read_exact(&mut chunk[..wanted])
                .map_err(|error| format!("{}: {error}", plan.source.path))?;
            hasher.update(&chunk[..wanted]);
            read_bytes += wanted as u64;
        }
        shards.push(chunk);
    }
    Ok((BlockInput { shards }, read_bytes))
}

struct GeneratedSingle {
    path: String,
    parity_len: u64,
    shard_sha256: Vec<String>,
}

struct CrossLaneResult {
    path: String,
    data_sha256: Vec<String>,
}

struct GeneratedCrossGroup {
    group: RecoveryGroup,
    lanes: Vec<CrossLaneResult>,
}

fn body_writer(body_path: &Path, offset: u64) -> Result<BufWriter<File>> {
    let file = File::options().write(true).open(body_path)?;
    let mut file = file;
    file.seek(SeekFrom::Start(offset))?;
    Ok(BufWriter::with_capacity(1024 * 1024, file))
}

fn reserve_body(path: &Path, length: u64) -> Result<()> {
    File::options().write(true).open(path)?.set_len(length)?;
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn generate_single_plans(
    body_path: &Path,
    directory: &Path,
    plans: &[SinglePlan],
    options: &FileRecoveryOptions,
    codec: &ReedSolomon<galois_8::Field>,
    cancel: &Option<Arc<AtomicBool>>,
    processed: &AtomicU64,
    progress: &ProgressCallback,
    progress_total: u64,
) -> Result<Vec<GeneratedSingle>> {
    let shard_size = usize::try_from(options.shard_size)
        .map_err(|_| CoreError::Codec("shard size is too large"))?;
    let data_shards = usize::from(options.data_shards);
    let parity_shards = usize::from(options.parity_shards);

    plans
        .par_iter()
        .map(|plan| {
            if is_cancelled(cancel) {
                return Err(CoreError::Cancelled);
            }
            let source_path = directory.join(&plan.source.path);
            let mut source = BufReader::new(File::open(&source_path)?);
            let mut hasher = Sha256::new();
            let mut actual_size = 0_u64;
            let mut shard_hashes = Vec::new();

            if plan.blocks == 0 {
                if actual_size != plan.source.size {
                    return Err(CoreError::Integrity);
                }
            } else {
                let mut writer = body_writer(body_path, plan.parity_offset)?;
                let mut pending = Vec::with_capacity(ENCODE_BATCH);
                for block_index in 0..plan.blocks {
                    if is_cancelled(cancel) {
                        return Err(CoreError::Cancelled);
                    }
                    let (mut input, read_bytes) = read_single_block(
                        &mut source,
                        &mut hasher,
                        plan,
                        block_index,
                        shard_size,
                        data_shards,
                    )
                    .map_err(CoreError::CodecMessage)?;
                    for _ in 0..parity_shards {
                        input.shards.push(vec![0_u8; shard_size]);
                    }
                    actual_size += read_bytes;
                    pending.push(input);
                    if pending.len() == ENCODE_BATCH {
                        for output in encode_block_batch(
                            codec,
                            parity_shards,
                            std::mem::take(&mut pending),
                            cancel,
                        )? {
                            for shard in &output.parity {
                                writer.write_all(shard)?;
                            }
                            shard_hashes.extend(output.hashes);
                        }
                    }
                    let completed = processed.fetch_add(read_bytes, Ordering::Relaxed) + read_bytes;
                    if let Some(progress) = progress {
                        progress(
                            completed.min(progress_total),
                            progress_total,
                            &plan.source.path,
                        );
                    }
                }
                if !pending.is_empty() {
                    for output in encode_block_batch(codec, parity_shards, pending, cancel)? {
                        for shard in &output.parity {
                            writer.write_all(shard)?;
                        }
                        shard_hashes.extend(output.hashes);
                    }
                }
                writer.flush()?;
            }

            let document_hash = crate::manifest::bytes_to_hex(&hasher.finalize());
            if actual_size != plan.source.size {
                return Err(CoreError::SourceChanged {
                    path: plan.source.path.clone(),
                    reason: "file size changed while generating parity",
                });
            }
            if document_hash != plan.source.hash {
                return Err(CoreError::SourceChanged {
                    path: plan.source.path.clone(),
                    reason: "file content changed after hashing",
                });
            }
            Ok(GeneratedSingle {
                path: plan.source.path.clone(),
                parity_len: plan.parity_len,
                shard_sha256: shard_hashes,
            })
        })
        .collect()
}

#[allow(clippy::too_many_arguments)]
fn generate_cross_plans(
    body_path: &Path,
    directory: &Path,
    plans: &[CrossPlan],
    options: &FileRecoveryOptions,
    cancel: &Option<Arc<AtomicBool>>,
    processed: &AtomicU64,
    progress: &ProgressCallback,
    progress_total: u64,
) -> Result<Vec<GeneratedCrossGroup>> {
    let shard_size = usize::try_from(options.shard_size)
        .map_err(|_| CoreError::Codec("shard size is too large"))?;
    let parity_shards = usize::from(options.parity_shards);

    plans
        .par_iter()
        .map(|plan| {
            if is_cancelled(cancel) {
                return Err(CoreError::Cancelled);
            }
            let lane_count = usize::from(plan.lane_count);
            let codec = ReedSolomon::<galois_8::Field>::new(lane_count, parity_shards)
                .map_err(|_| CoreError::Codec("unable to construct cross-file RS codec"))?;
            let mut sources = Vec::with_capacity(lane_count);
            let mut hashers = Vec::with_capacity(lane_count);
            let mut actual_sizes = vec![0_u64; lane_count];
            let mut lane_hashes = vec![Vec::new(); lane_count];
            let mut parity_hashes = Vec::new();

            for source in &plan.sources {
                sources.push(BufReader::new(File::open(directory.join(&source.path))?));
                hashers.push(Sha256::new());
            }

            if plan.block_count == 0 {
                for (lane_index, source) in plan.sources.iter().enumerate() {
                    let document_hash = crate::manifest::bytes_to_hex(
                        &std::mem::take(&mut hashers[lane_index]).finalize(),
                    );
                    if source.size != 0 {
                        return Err(CoreError::SourceChanged {
                            path: source.path.clone(),
                            reason: "empty file size changed",
                        });
                    }
                    if document_hash != source.hash {
                        return Err(CoreError::SourceChanged {
                            path: source.path.clone(),
                            reason: "file content changed after hashing",
                        });
                    }
                }
            } else {
                let mut writer = body_writer(body_path, plan.parity_offset)?;
                let mut pending = Vec::with_capacity(ENCODE_BATCH);
                for block_index in 0..plan.block_count {
                    if is_cancelled(cancel) {
                        return Err(CoreError::Cancelled);
                    }
                    let mut shards = Vec::with_capacity(lane_count + parity_shards);
                    let mut batch_bytes = 0_u64;
                    for lane_index in 0..lane_count {
                        let lane = &plan.sources[lane_index];
                        let mut chunk = vec![0_u8; shard_size];
                        let start = block_index * u64::from(options.shard_size);
                        if start < lane.size {
                            let wanted =
                                std::cmp::min(shard_size as u64, lane.size - start) as usize;
                            sources[lane_index]
                                .read_exact(&mut chunk[..wanted])
                                .map_err(|error| {
                                    CoreError::CodecMessage(format!("{}: {error}", lane.path))
                                })?;
                            hashers[lane_index].update(&chunk[..wanted]);
                            actual_sizes[lane_index] += wanted as u64;
                            batch_bytes += wanted as u64;
                        }
                        shards.push(chunk);
                    }
                    for _ in 0..parity_shards {
                        shards.push(vec![0_u8; shard_size]);
                    }
                    pending.push(BlockInput { shards });
                    if pending.len() == ENCODE_BATCH {
                        for output in encode_block_batch(
                            &codec,
                            parity_shards,
                            std::mem::take(&mut pending),
                            cancel,
                        )? {
                            for shard in &output.parity {
                                writer.write_all(shard)?;
                            }
                            for (lane_index, hash) in
                                output.hashes.iter().take(lane_count).enumerate()
                            {
                                lane_hashes[lane_index].push(hash.clone());
                            }
                            parity_hashes.extend(output.hashes.iter().skip(lane_count).cloned());
                        }
                    }
                    let completed =
                        processed.fetch_add(batch_bytes, Ordering::Relaxed) + batch_bytes;
                    if let Some(progress) = progress {
                        progress(
                            completed.min(progress_total),
                            progress_total,
                            &plan.sources[0].path,
                        );
                    }
                }
                if !pending.is_empty() {
                    for output in encode_block_batch(&codec, parity_shards, pending, cancel)? {
                        for shard in &output.parity {
                            writer.write_all(shard)?;
                        }
                        for (lane_index, hash) in output.hashes.iter().take(lane_count).enumerate()
                        {
                            lane_hashes[lane_index].push(hash.clone());
                        }
                        parity_hashes.extend(output.hashes.iter().skip(lane_count).cloned());
                    }
                }
                writer.flush()?;

                for (lane_index, source) in plan.sources.iter().enumerate() {
                    let document_hash = crate::manifest::bytes_to_hex(
                        &std::mem::take(&mut hashers[lane_index]).finalize(),
                    );
                    if actual_sizes[lane_index] != source.size {
                        return Err(CoreError::SourceChanged {
                            path: source.path.clone(),
                            reason: "file size changed while generating parity",
                        });
                    }
                    if document_hash != source.hash {
                        return Err(CoreError::SourceChanged {
                            path: source.path.clone(),
                            reason: "file content changed after hashing",
                        });
                    }
                }
            }

            Ok(GeneratedCrossGroup {
                group: RecoveryGroup {
                    parity_offset: plan.parity_offset,
                    parity_len: plan.parity_len,
                    lane_count: plan.lane_count,
                    block_count: plan.block_count,
                    parity_sha256: parity_hashes,
                },
                lanes: plan
                    .sources
                    .iter()
                    .enumerate()
                    .map(|(lane_index, source)| CrossLaneResult {
                        path: source.path.clone(),
                        data_sha256: lane_hashes[lane_index].clone(),
                    })
                    .collect(),
            })
        })
        .collect()
}

pub fn write_file_recovery_with_progress<P: AsRef<Path>, Q: AsRef<Path>>(
    directory: P,
    output_path: Q,
    document: &FitDocument,
    signing_key: &crate::fitrec::SigningKey,
    options: FileRecoveryOptions,
    cancel: Option<Arc<AtomicBool>>,
    progress: ProgressCallback,
) -> Result<()> {
    document.validate()?;
    validate_options(&options)?;
    let directory = directory.as_ref();
    if !directory.is_dir() {
        return Err(CoreError::Io(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "source directory not found",
        )));
    }

    let output = output_path.as_ref();
    let temp = PathBuf::from(format!("{}.tmp-{}", output.display(), std::process::id()));
    if let Some(parent) = temp.parent() {
        fs::create_dir_all(parent)?;
    }
    File::create(&temp)?;

    let sources = source_plans(directory, document)?;
    let total = sources.iter().map(|source| source.size).sum::<u64>();
    let progress_total = match options.mode {
        FileRecoveryMode::Dual => total.saturating_mul(2),
        _ => total,
    };
    let processed = AtomicU64::new(0);
    let mut body_size = 0_u64;
    let generation = (|| -> Result<(Vec<FileRecoveryEntry>, Vec<RecoveryGroup>)> {
        let data_shards = usize::from(options.data_shards);
        let parity_shards = usize::from(options.parity_shards);
        let codec = ReedSolomon::<galois_8::Field>::new(data_shards, parity_shards)
            .map_err(|_| CoreError::Codec("unable to construct RS codec"))?;
        let mut entries = document
            .active_entries()?
            .iter()
            .map(|entry| FileRecoveryEntry {
                path: entry.path.clone(),
                sha256: entry.hash.clone(),
                size: entry.size.unwrap_or_default(),
                parity_offset: 0,
                parity_len: 0,
                shard_sha256: Vec::new(),
                cross_group: None,
                cross_lane: None,
                cross_data_sha256: Vec::new(),
            })
            .collect::<Vec<_>>();
        let mut groups = Vec::new();

        if matches!(
            options.mode,
            FileRecoveryMode::SingleFile | FileRecoveryMode::Dual
        ) {
            let (single_plans, next_offset) = build_single_plans(&sources, &options, body_size);
            reserve_body(&temp, next_offset)?;
            let generated = generate_single_plans(
                &temp,
                directory,
                &single_plans,
                &options,
                &codec,
                &cancel,
                &processed,
                &progress,
                progress_total,
            )?;
            let generated_by_path = generated
                .into_iter()
                .map(|item| (item.path.clone(), item))
                .collect::<HashMap<_, _>>();
            for (entry, plan) in entries.iter_mut().zip(&single_plans) {
                let generated = generated_by_path
                    .get(&plan.source.path)
                    .ok_or(CoreError::Malformed("generated parity is missing a source"))?;
                entry.parity_offset = plan.parity_offset;
                entry.parity_len = generated.parity_len;
                entry.shard_sha256 = generated.shard_sha256.clone();
            }
            body_size = next_offset;
        }

        if matches!(
            options.mode,
            FileRecoveryMode::CrossFile | FileRecoveryMode::Dual
        ) {
            let (cross_plans, next_offset) = build_cross_plans(&sources, &options, body_size);
            reserve_body(&temp, next_offset)?;
            let generated = generate_cross_plans(
                &temp,
                directory,
                &cross_plans,
                &options,
                &cancel,
                &processed,
                &progress,
                progress_total,
            )?;
            let lane_results = generated
                .iter()
                .flat_map(|group| group.lanes.iter())
                .map(|lane| (lane.path.clone(), lane))
                .collect::<HashMap<_, _>>();
            for entry in &mut entries {
                if let Some(lane) = lane_results.get(&entry.path) {
                    entry.cross_data_sha256 = lane.data_sha256.clone();
                }
            }
            for (group_index, generated) in generated.into_iter().enumerate() {
                for (lane_index, lane) in generated.lanes.iter().enumerate() {
                    if let Some(entry) = entries.iter_mut().find(|entry| entry.path == lane.path) {
                        entry.cross_group = Some(group_index);
                        entry.cross_lane = Some(lane_index as u16);
                    }
                }
                groups.push(generated.group);
            }
            body_size = next_offset;
        }

        for (entry, source) in entries.iter_mut().zip(&sources) {
            entry.size = source.size;
        }
        Ok((entries, groups))
    })();
    let (entries, groups) = match generation {
        Ok(value) => value,
        Err(error) => {
            let _ = fs::remove_file(&temp);
            return Err(error);
        }
    };

    let header = RecoveryHeader {
        format: "fitpar".to_string(),
        version: 2,
        manifest_hash: document.active_manifest_hash()?,
        data_shards: options.data_shards,
        parity_shards: options.parity_shards,
        shard_size: options.shard_size,
        mode: options.mode,
        files: entries,
        groups,
        signature: SignatureHeader {
            algorithm: SignatureAlgorithm::Ed25519,
        },
    };
    let header_json = serde_json::to_vec(&header)?;
    if header_json.len() > u32::MAX as usize {
        let _ = fs::remove_file(&temp);
        return Err(CoreError::Malformed("file recovery header is too large"));
    }

    let result = (|| -> Result<()> {
        if let Some(parent) = output.parent() {
            fs::create_dir_all(parent)?;
        }
        let mut final_file = BufWriter::new(File::create(output)?);
        final_file.write_all(&MAGIC)?;
        final_file.write_all(&(header_json.len() as u32).to_le_bytes())?;
        final_file.write_all(&header_json)?;
        final_file.flush()?;
        let signed_len = 8 + 4 + header_json.len();
        let mut signed_file = File::open(output)?;
        let mut signed_bytes = vec![0_u8; signed_len];
        signed_file.read_exact(&mut signed_bytes)?;
        let signature = signing_key.sign(&signed_bytes);
        final_file.write_all(&signature.to_bytes())?;

        let mut body_reader = BufReader::new(File::open(&temp)?);
        std::io::copy(&mut body_reader, &mut final_file)?;
        final_file.flush()?;
        Ok(())
    })();

    let _ = fs::remove_file(&temp);
    result
}

pub fn recover_files<P: AsRef<Path>, Q: AsRef<Path>, R: AsRef<Path>>(
    recovery_path: P,
    verifying_key: &crate::fitrec::VerifyingKey,
    target_directory: Q,
    output_directory: R,
) -> Result<FileRecoveryReport> {
    recover_files_with_progress(
        recovery_path,
        verifying_key,
        target_directory,
        output_directory,
        None,
        None,
    )
}

pub fn recover_files_with_progress<P: AsRef<Path>, Q: AsRef<Path>, R: AsRef<Path>>(
    recovery_path: P,
    verifying_key: &crate::fitrec::VerifyingKey,
    target_directory: Q,
    output_directory: R,
    cancel: Option<Arc<AtomicBool>>,
    progress: ProgressCallback,
) -> Result<FileRecoveryReport> {
    let (header, body_start) = read_header(&recovery_path, verifying_key)?;
    validate_recovery_header(&header)?;
    let target = target_directory.as_ref();
    let output = output_directory.as_ref();
    if !target.is_dir() {
        return Err(CoreError::Io(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "target directory not found",
        )));
    }
    fs::create_dir_all(output)?;
    if same_directory(target, output)? {
        return Err(CoreError::Manifest(
            "recovery output must differ from the target directory",
        ));
    }

    let entries_by_path = header
        .files
        .iter()
        .map(|entry| (entry.path.clone(), entry))
        .collect::<HashMap<_, _>>();
    let total: u64 = header.files.iter().map(|entry| entry.size).sum();
    let processed = AtomicU64::new(0);
    let archive_path = PathBuf::from(recovery_path.as_ref());
    let output_base = output.to_path_buf();
    let target_base = target.to_path_buf();
    let mut grouped_lanes = header
        .groups
        .iter()
        .map(|group| vec![None; usize::from(group.lane_count)])
        .collect::<Vec<_>>();
    for entry in &header.files {
        if let (Some(group), Some(lane)) = (entry.cross_group, entry.cross_lane)
            && let Some(lanes) = grouped_lanes.get_mut(group)
            && let Some(slot) = lanes.get_mut(usize::from(lane))
            && slot.replace(entry).is_some()
        {
            return Err(CoreError::Malformed("duplicate cross-file lane entry"));
        }
    }
    let group_lanes = grouped_lanes
        .into_iter()
        .map(|lanes| {
            lanes
                .into_iter()
                .collect::<Option<Vec<_>>>()
                .ok_or(CoreError::Malformed("cross-file group has missing lanes"))
        })
        .collect::<Result<Vec<_>>>()?;

    let details: Vec<std::result::Result<FileRecoveryDetail, String>> = header
        .files
        .par_iter()
        .map(|entry| {
            let source_path = target_base.join(&entry.path);
            if source_path.is_file() {
                let actual_hash = match crate::hashing::hash_file(
                    &source_path,
                    crate::hashing::HashAlgorithm::Sha256,
                ) {
                    Ok(hash) => hash,
                    Err(error) => {
                        return Ok(FileRecoveryDetail {
                            path: entry.path.clone(),
                            status: "failed".to_string(),
                            message: error.to_string(),
                        });
                    }
                };
                if actual_hash == entry.sha256 {
                    let completed = processed.fetch_add(entry.size, Ordering::Relaxed) + entry.size;
                    if let Some(progress) = &progress {
                        progress(completed.min(total), total, &entry.path);
                    }
                    return Ok(FileRecoveryDetail {
                        path: entry.path.clone(),
                        status: "healthy".to_string(),
                        message: "file is healthy".to_string(),
                    });
                }
            }

            if matches!(header.mode, FileRecoveryMode::CrossFile)
                || (matches!(header.mode, FileRecoveryMode::Dual) && !source_path.is_file())
            {
                recover_cross_file(
                    &archive_path,
                    &target_base,
                    &output_base,
                    entry,
                    &header,
                    body_start,
                    &group_lanes,
                    &cancel,
                    &processed,
                    &progress,
                    total,
                )
            } else {
                let single = recover_file(
                    &archive_path,
                    &target_base,
                    &output_base,
                    entry,
                    entries_by_path.get(&entry.path).copied().unwrap_or(entry),
                    &header,
                    body_start,
                    &cancel,
                    &processed,
                    &progress,
                    total,
                );
                if single.is_err() && matches!(header.mode, FileRecoveryMode::Dual) {
                    recover_cross_file(
                        &archive_path,
                        &target_base,
                        &output_base,
                        entry,
                        &header,
                        body_start,
                        &group_lanes,
                        &cancel,
                        &processed,
                        &progress,
                        total,
                    )
                } else {
                    single
                }
            }
        })
        .collect();

    let mut details = details
        .into_iter()
        .map(|result| match result {
            Ok(detail) => detail,
            Err(message) => FileRecoveryDetail {
                path: String::new(),
                status: "failed".to_string(),
                message,
            },
        })
        .collect::<Vec<_>>();
    if is_cancelled(&cancel) {
        return Err(CoreError::Cancelled);
    }
    details.sort_by(|left, right| left.path.cmp(&right.path));
    let repaired = details.iter().filter(|d| d.status == "repaired").count();
    let healthy = details.iter().filter(|d| d.status == "healthy").count();
    let missing = details.iter().filter(|d| d.status == "missing").count();
    let failed = details.iter().filter(|d| d.status == "failed").count();
    Ok(FileRecoveryReport {
        total: header.files.len(),
        repaired,
        healthy,
        missing,
        failed,
        details,
    })
}

#[allow(clippy::too_many_arguments)]
fn recover_file(
    archive_path: &Path,
    target_base: &Path,
    output_base: &Path,
    entry: &FileRecoveryEntry,
    _entry_lookup: &FileRecoveryEntry,
    header: &RecoveryHeader,
    body_start: usize,
    cancel: &Option<Arc<AtomicBool>>,
    processed: &AtomicU64,
    progress: &ProgressCallback,
    total: u64,
) -> std::result::Result<FileRecoveryDetail, String> {
    let source_path = target_base.join(&entry.path);
    let output_path = output_base.join(&entry.path);
    let mut source = if source_path.is_file() {
        Some(File::open(&source_path).map_err(|error| error.to_string())?)
    } else {
        None
    };
    if source.is_none() && usize::from(header.parity_shards) < usize::from(header.data_shards) {
        return Ok(FileRecoveryDetail {
            path: entry.path.clone(),
            status: "missing".to_string(),
            message: "file is missing and parity cannot rebuild it".to_string(),
        });
    }

    if is_cancelled(cancel) {
        return Err("cancelled".to_string());
    }

    let shard_size =
        usize::try_from(header.shard_size).map_err(|_| "shard size too large".to_string())?;
    let data_shards = usize::from(header.data_shards);
    let parity_shards = usize::from(header.parity_shards);
    let codec = ReedSolomon::<galois_8::Field>::new(data_shards, parity_shards)
        .map_err(|_| "unable to construct RS codec".to_string())?;
    let mut archive = BufReader::new(File::open(archive_path).map_err(|error| error.to_string())?);
    archive
        .seek(SeekFrom::Start(body_start as u64 + entry.parity_offset))
        .map_err(|error| error.to_string())?;

    if let Some(parent) = output_path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    if output_path.exists() {
        return Err("output file already exists".to_string());
    }
    let temp_output = PathBuf::from(format!(
        "{}.tmp-{}",
        output_path.display(),
        std::process::id()
    ));
    let mut output = BufWriter::new(File::create(&temp_output).map_err(|error| error.to_string())?);
    let mut hasher = Sha256::new();
    let mut remaining = entry.size;
    let mut block_index = 0_usize;

    loop {
        if is_cancelled(cancel) {
            let _ = fs::remove_file(&temp_output);
            return Err("cancelled".to_string());
        }

        let remaining_before = remaining;
        let mut shards = Vec::with_capacity(data_shards + parity_shards);
        let mut valid = vec![true; data_shards + parity_shards];
        for (data_index, valid_slot) in valid.iter_mut().enumerate().take(data_shards) {
            let mut chunk = vec![0_u8; shard_size];
            let mut damaged = true;
            if let Some(source) = &mut source {
                let mut filled = 0_usize;
                while filled < shard_size {
                    let read = source
                        .read(&mut chunk[filled..])
                        .map_err(|error| error.to_string())?;
                    if read == 0 {
                        break;
                    }
                    filled += read;
                }
                if remaining == 0 && data_index == 0 {
                    damaged = false;
                } else {
                    let hash_index = block_index * (data_shards + parity_shards) + data_index;
                    damaged = sha256_hex(&chunk)
                        != entry
                            .shard_sha256
                            .get(hash_index)
                            .map(String::as_str)
                            .unwrap_or_default();
                }
            }
            if damaged {
                *valid_slot = false;
            }
            shards.push(chunk);
        }
        for _ in 0..parity_shards {
            shards.push(vec![0_u8; shard_size]);
        }
        if remaining == 0 {
            break;
        }

        let hash_start = block_index * (data_shards + parity_shards);
        let parity_hashes = &entry.shard_sha256[hash_start + data_shards
            ..std::cmp::min(
                entry.shard_sha256.len(),
                hash_start + data_shards + parity_shards,
            )];
        for (parity_index, chunk) in shards.iter_mut().skip(data_shards).enumerate() {
            let mut shard = vec![0_u8; shard_size];
            archive
                .read_exact(&mut shard)
                .map_err(|error| format!("recovery archive is truncated: {error}"))?;
            *chunk = shard;
            valid[data_shards + parity_index] = sha256_hex(chunk)
                == parity_hashes
                    .get(parity_index)
                    .map(String::as_str)
                    .unwrap_or_default();
        }
        let damaged = valid.iter().filter(|valid| !**valid).count();
        if damaged > parity_shards {
            let _ = fs::remove_file(&temp_output);
            return Err(format!(
                "damaged shards {} exceed recovery capacity {}",
                damaged, parity_shards
            ));
        }
        if damaged > 0 {
            let mut reconstructions = shards
                .iter()
                .zip(&valid)
                .map(|(shard, valid)| (shard.clone(), *valid))
                .collect::<Vec<_>>();
            codec.reconstruct(&mut reconstructions).map_err(|error| {
                let _ = fs::remove_file(&temp_output);
                format!("RS reconstruction failed: {error}")
            })?;
            for (index, (shard, _valid)) in reconstructions.into_iter().enumerate() {
                let hash_index = block_index * (data_shards + parity_shards) + index;
                if sha256_hex(&shard)
                    != entry
                        .shard_sha256
                        .get(hash_index)
                        .map(String::as_str)
                        .unwrap_or_default()
                {
                    let _ = fs::remove_file(&temp_output);
                    return Err("rebuilt shard hash mismatch".to_string());
                }
                shards[index] = shard;
            }
        }

        for shard in shards.iter().take(data_shards) {
            let write_len = std::cmp::min(shard.len(), remaining as usize);
            output
                .write_all(&shard[..write_len])
                .map_err(|error| error.to_string())?;
            hasher.update(&shard[..write_len]);
            remaining -= write_len as u64;
        }
        block_index += 1;

        let completed = processed.fetch_add(
            std::cmp::min(remaining_before, (data_shards * shard_size) as u64),
            Ordering::Relaxed,
        );
        if let Some(progress) = progress {
            progress(completed.min(total), total, &entry.path);
        }
    }
    output.flush().map_err(|error| error.to_string())?;

    if crate::manifest::bytes_to_hex(&hasher.finalize()) != entry.sha256 {
        let _ = fs::remove_file(&temp_output);
        return Err("recovered file hash mismatch".to_string());
    }

    fs::rename(&temp_output, &output_path).map_err(|error| {
        let _ = fs::remove_file(&temp_output);
        error.to_string()
    })?;

    Ok(FileRecoveryDetail {
        path: entry.path.clone(),
        status: "repaired".to_string(),
        message: if source.is_some() {
            "file repaired".to_string()
        } else {
            "file rebuilt from parity".to_string()
        },
    })
}

#[allow(clippy::too_many_arguments)]
fn recover_cross_file(
    archive_path: &Path,
    target_base: &Path,
    output_base: &Path,
    entry: &FileRecoveryEntry,
    header: &RecoveryHeader,
    body_start: usize,
    group_lanes: &[Vec<&FileRecoveryEntry>],
    cancel: &Option<Arc<AtomicBool>>,
    processed: &AtomicU64,
    progress: &ProgressCallback,
    total: u64,
) -> std::result::Result<FileRecoveryDetail, String> {
    let Some(group_index) = entry.cross_group else {
        return Err("recovery entry has no cross-file group".to_string());
    };
    let Some(lane_index) = entry.cross_lane else {
        return Err("recovery entry has no cross-file lane".to_string());
    };
    let Some(group) = header.groups.get(group_index) else {
        return Err("recovery group is missing".to_string());
    };
    let Some(lanes) = group_lanes.get(group_index) else {
        return Err("recovery group is empty".to_string());
    };
    if lanes.len() != usize::from(group.lane_count) {
        return Err("recovery group lane metadata is invalid".to_string());
    }
    let Some(target_lane) = lanes.get(usize::from(lane_index)) else {
        return Err("recovery lane is missing".to_string());
    };
    if target_lane.path != entry.path || target_lane.sha256 != entry.sha256 {
        return Err("recovery lane metadata is invalid".to_string());
    }

    let shard_size =
        usize::try_from(header.shard_size).map_err(|_| "shard size too large".to_string())?;
    let data_shards = usize::from(group.lane_count);
    let parity_shards = usize::from(header.parity_shards);
    let codec = ReedSolomon::<galois_8::Field>::new(data_shards, parity_shards)
        .map_err(|_| "unable to construct RS codec".to_string())?;

    let output_path = output_base.join(&entry.path);
    if let Some(parent) = output_path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    if output_path.exists() {
        return Err("output file already exists".to_string());
    }
    let temp_output = PathBuf::from(format!(
        "{}.tmp-{}",
        output_path.display(),
        std::process::id()
    ));
    let cleanup = |message: String| {
        let _ = fs::remove_file(&temp_output);
        message
    };

    if entry.size == 0 {
        let mut output = File::create(&temp_output).map_err(|error| error.to_string())?;
        output.flush().map_err(|error| error.to_string())?;
        fs::rename(&temp_output, &output_path).map_err(|error| error.to_string())?;
        return Ok(FileRecoveryDetail {
            path: entry.path.clone(),
            status: "repaired".to_string(),
            message: "empty file rebuilt from parity".to_string(),
        });
    }

    let mut sources = Vec::with_capacity(data_shards);
    for lane in lanes {
        let source_path = target_base.join(&lane.path);
        sources.push(if source_path.is_file() {
            File::open(&source_path).ok().map(BufReader::new)
        } else {
            None
        });
    }

    let mut archive = BufReader::new(File::open(archive_path).map_err(|error| error.to_string())?);
    archive
        .seek(SeekFrom::Start(body_start as u64 + group.parity_offset))
        .map_err(|error| error.to_string())?;
    let mut output = BufWriter::new(File::create(&temp_output).map_err(|error| error.to_string())?);
    let mut hasher = Sha256::new();
    let mut remaining = entry.size;
    let mut unavailable_sources = vec![false; data_shards];

    for block_index in 0..group.block_count {
        if is_cancelled(cancel) {
            return Err(cleanup("cancelled".to_string()));
        }
        let hash_block = usize::try_from(block_index)
            .map_err(|_| cleanup("recovery block index is too large".to_string()))?;

        let mut shards = Vec::with_capacity(data_shards + parity_shards);
        let mut valid = vec![true; data_shards + parity_shards];
        for (lane_position, lane_entry) in lanes.iter().enumerate() {
            let mut chunk = vec![0_u8; shard_size];
            let start = block_index * shard_size as u64;
            if start < lane_entry.size {
                let wanted = std::cmp::min(shard_size as u64, lane_entry.size - start) as usize;
                if let Some(source) = &mut sources[lane_position] {
                    let mut filled = 0_usize;
                    let mut read_failed = false;
                    while filled < wanted {
                        match source.read(&mut chunk[filled..wanted]) {
                            Ok(0) => break,
                            Ok(count) => filled += count,
                            Err(_) => {
                                read_failed = true;
                                break;
                            }
                        }
                    }
                    if read_failed || filled != wanted {
                        unavailable_sources[lane_position] = true;
                        chunk[filled..wanted].fill(0);
                    }
                }
            }
            valid[lane_position] = !unavailable_sources[lane_position]
                && sha256_hex(&chunk)
                    == lane_entry
                        .cross_data_sha256
                        .get(hash_block)
                        .map(String::as_str)
                        .unwrap_or_default();
            shards.push(chunk);
        }

        let hash_start = hash_block * parity_shards;
        for parity_index in 0..parity_shards {
            let mut chunk = vec![0_u8; shard_size];
            archive
                .read_exact(&mut chunk)
                .map_err(|error| cleanup(format!("recovery archive is truncated: {error}")))?;
            valid[data_shards + parity_index] = sha256_hex(&chunk)
                == group
                    .parity_sha256
                    .get(hash_start + parity_index)
                    .map(String::as_str)
                    .unwrap_or_default();
            shards.push(chunk);
        }

        let damaged = valid.iter().filter(|valid| !**valid).count();
        if damaged > parity_shards {
            return Err(cleanup(format!(
                "damaged shards {} exceed cross-file recovery capacity {}",
                damaged, parity_shards
            )));
        }
        if damaged > 0 {
            let mut reconstructions = shards
                .iter()
                .zip(&valid)
                .map(|(shard, valid)| (shard.clone(), *valid))
                .collect::<Vec<_>>();
            codec
                .reconstruct(&mut reconstructions)
                .map_err(|error| cleanup(format!("RS reconstruction failed: {error}")))?;
            for (index, (shard, _valid)) in reconstructions.into_iter().enumerate() {
                let expected = if index < data_shards {
                    lanes[index].cross_data_sha256.get(hash_block)
                } else {
                    group
                        .parity_sha256
                        .get(hash_block * parity_shards + index - data_shards)
                };
                if sha256_hex(&shard) != expected.map(String::as_str).unwrap_or_default() {
                    return Err(cleanup("rebuilt shard hash mismatch".to_string()));
                }
                shards[index] = shard;
            }
        }

        let write_len = std::cmp::min(shard_size, remaining as usize);
        output
            .write_all(&shards[lane_index as usize][..write_len])
            .map_err(|error| error.to_string())?;
        hasher.update(&shards[lane_index as usize][..write_len]);
        remaining -= write_len as u64;

        let completed = processed.fetch_add(write_len as u64, Ordering::Relaxed) + write_len as u64;
        if let Some(progress) = progress {
            progress(completed.min(total), total, &entry.path);
        }
    }

    output.flush().map_err(|error| error.to_string())?;
    if crate::manifest::bytes_to_hex(&hasher.finalize()) != entry.sha256 {
        return Err(cleanup("recovered file hash mismatch".to_string()));
    }
    fs::rename(&temp_output, &output_path).map_err(|error| error.to_string())?;
    Ok(FileRecoveryDetail {
        path: entry.path.clone(),
        status: "repaired".to_string(),
        message: "file rebuilt from cross-file parity".to_string(),
    })
}

fn read_header<P: AsRef<Path>>(
    path: P,
    verifying_key: &crate::fitrec::VerifyingKey,
) -> Result<(RecoveryHeader, usize)> {
    let mut record = BufReader::new(File::open(path)?);
    let mut magic_and_len = [0_u8; 12];
    record.read_exact(&mut magic_and_len)?;
    if magic_and_len[..8] != MAGIC {
        return Err(CoreError::Malformed("bad file recovery archive"));
    }
    let header_len = u32::from_le_bytes(magic_and_len[8..12].try_into().unwrap()) as usize;
    let header_start: usize = 12;
    let header_end = header_start
        .checked_add(header_len)
        .ok_or(CoreError::Malformed("header length overflow"))?;
    let mut signed_bytes = vec![0_u8; header_end];
    signed_bytes[..12].copy_from_slice(&magic_and_len);
    record.read_exact(&mut signed_bytes[12..])?;
    let mut signature_bytes = [0_u8; SIGNATURE_LENGTH];
    record.read_exact(&mut signature_bytes)?;
    let signature = Signature::from_slice(&signature_bytes)
        .map_err(|error| CoreError::Crypto(error.to_string()))?;
    verifying_key
        .verify(&signed_bytes, &signature)
        .map_err(|_| CoreError::Signature)?;
    let mut header: RecoveryHeader =
        serde_json::from_slice(&signed_bytes[header_start..header_end])?;
    if header.version == 1 {
        header.mode = FileRecoveryMode::SingleFile;
    }
    Ok((header, header_end + SIGNATURE_LENGTH))
}

fn validate_options(options: &FileRecoveryOptions) -> Result<()> {
    if options.data_shards == 0 || options.parity_shards == 0 {
        return Err(CoreError::Codec(
            "data and parity shard counts must be greater than zero",
        ));
    }
    if usize::from(options.data_shards) + usize::from(options.parity_shards) > 255 {
        return Err(CoreError::Codec("total RS shard count must not exceed 255"));
    }
    if options.shard_size == 0 {
        return Err(CoreError::Codec("shard size must be greater than zero"));
    }
    Ok(())
}

fn validate_recovery_header(header: &RecoveryHeader) -> Result<()> {
    if header.format != "fitpar" || !matches!(header.version, 1 | 2) {
        return Err(CoreError::UnsupportedVersion(header.version));
    }
    validate_options(&FileRecoveryOptions {
        data_shards: header.data_shards,
        parity_shards: header.parity_shards,
        shard_size: header.shard_size,
        mode: header.mode,
    })?;
    let uses_cross = matches!(
        header.mode,
        FileRecoveryMode::CrossFile | FileRecoveryMode::Dual
    );
    if !uses_cross && !header.groups.is_empty() {
        return Err(CoreError::Malformed("single-file archive contains groups"));
    }
    for entry in &header.files {
        crate::manifest::normalize_relative_path(&entry.path)?;
        if header.mode != FileRecoveryMode::CrossFile
            && entry.parity_len % u64::from(header.parity_shards) != 0
        {
            return Err(CoreError::Malformed("parity length is not aligned"));
        }
    }
    if uses_cross {
        for group in &header.groups {
            if usize::from(group.lane_count) > usize::from(header.data_shards)
                || group.parity_len
                    != group.block_count
                        * u64::from(header.parity_shards)
                        * u64::from(header.shard_size)
                || group.parity_sha256.len()
                    != group.block_count as usize * usize::from(header.parity_shards)
            {
                return Err(CoreError::Malformed("invalid cross-file group"));
            }
        }
        for entry in &header.files {
            let (Some(group_index), Some(lane_index)) = (entry.cross_group, entry.cross_lane)
            else {
                return Err(CoreError::Malformed("cross-file entry is incomplete"));
            };
            let Some(group) = header.groups.get(group_index) else {
                return Err(CoreError::Malformed("cross-file group is missing"));
            };
            if usize::from(lane_index) >= usize::from(group.lane_count)
                || entry.cross_data_sha256.len() != group.block_count as usize
            {
                return Err(CoreError::Malformed("invalid cross-file entry"));
            }
        }
    }
    Ok(())
}

fn same_directory(left: &Path, right: &Path) -> Result<bool> {
    let left = left.canonicalize()?;
    let right = right.canonicalize()?;
    Ok(left == right)
}

fn is_cancelled(cancel: &Option<Arc<AtomicBool>>) -> bool {
    cancel
        .as_ref()
        .map(|flag| flag.load(Ordering::Relaxed))
        .unwrap_or(false)
}
