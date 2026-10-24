use std::fs;
use std::path::Path;

use crate::error::{CoreError, Result};
use crate::manifest::{FitDocument, sha256_hex};
use ed25519_dalek::{Signature, Signer, Verifier};
use reed_solomon_erasure::{ReedSolomon, galois_8};
use serde::{Deserialize, Serialize};

const MAGIC: [u8; 8] = *b"FITREC1\0";
const SIGNATURE_LENGTH: usize = 64;

#[derive(Clone, Copy, Debug)]
pub struct FitRecOptions {
    pub data_shards: u8,
    pub parity_shards: u8,
}

impl Default for FitRecOptions {
    fn default() -> Self {
        Self {
            data_shards: 8,
            parity_shards: 4,
        }
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FitRecChecklistInfo {
    pub name: String,
    pub count: usize,
    pub active: bool,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FitRecInfo {
    pub data_shards: u8,
    pub parity_shards: u8,
    pub active_checklist: String,
    pub checklists: Vec<FitRecChecklistInfo>,
}

#[derive(Clone, Debug)]
pub struct FitRecRepair {
    pub document: FitDocument,
    pub repaired_record: Vec<u8>,
    pub damaged_shards: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "snake_case")]
pub(crate) enum SignatureAlgorithm {
    Ed25519,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "snake_case")]
enum CodecAlgorithm {
    ReedSolomon,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "snake_case")]
pub(crate) struct SignatureHeader {
    pub(crate) algorithm: SignatureAlgorithm,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "snake_case")]
struct CodecHeader {
    algorithm: CodecAlgorithm,
    data_shards: u8,
    parity_shards: u8,
    shard_size: u32,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "snake_case")]
struct Header {
    format: String,
    version: u32,
    manifest_hash: String,
    document_len: u64,
    document_sha256: String,
    codec: CodecHeader,
    shard_sha256: Vec<String>,
    signature: SignatureHeader,
}

pub type SigningKey = ed25519_dalek::SigningKey;
pub type VerifyingKey = ed25519_dalek::VerifyingKey;

pub fn generate_signing_key() -> Result<SigningKey> {
    let mut secret = [0_u8; 32];
    getrandom::fill(&mut secret).map_err(|error| CoreError::Crypto(error.to_string()))?;
    let key = SigningKey::from_bytes(&secret);
    secret.fill(0);
    Ok(key)
}

pub fn generate_keypair<P: AsRef<Path>, Q: AsRef<Path>>(
    private_key_path: P,
    public_key_path: Q,
) -> Result<()> {
    let private_path = private_key_path.as_ref();
    let public_path = public_key_path.as_ref();
    if private_path == public_path {
        return Err(CoreError::Crypto(
            "private and public key paths must differ".to_string(),
        ));
    }
    if private_path.exists() {
        return Err(CoreError::Crypto(format!(
            "private key already exists: {}",
            private_path.display()
        )));
    }
    if public_path.exists() {
        return Err(CoreError::Crypto(format!(
            "public key already exists: {}",
            public_path.display()
        )));
    }

    let signing_key = generate_signing_key()?;
    let private_bytes = signing_key.to_bytes();
    fs::write(private_path, private_bytes)?;
    if let Err(error) = write_public_key(public_path, &signing_key) {
        let _ = fs::remove_file(private_path);
        return Err(error);
    }
    Ok(())
}

pub fn load_signing_key<P: AsRef<Path>>(path: P) -> Result<SigningKey> {
    let data = fs::read(path)?;
    let bytes = if data.len() == 32 {
        data
    } else {
        let text = String::from_utf8(data)
            .map_err(|_| CoreError::Crypto("private key is not raw bytes or hex".to_string()))?;
        hex::decode(text.trim())
            .map_err(|_| CoreError::Crypto("private key is not raw bytes or hex".to_string()))?
    };
    let bytes: [u8; 32] = bytes
        .try_into()
        .map_err(|_| CoreError::Crypto("private key must contain exactly 32 bytes".to_string()))?;
    Ok(SigningKey::from_bytes(&bytes))
}

pub fn write_public_key<P: AsRef<Path>>(path: P, signing_key: &SigningKey) -> Result<()> {
    let public_bytes = hex::encode(signing_key.verifying_key().to_bytes());
    fs::write(path, public_bytes)?;
    Ok(())
}

pub fn write_fitrec<P: AsRef<Path>>(
    path: P,
    document: &FitDocument,
    signing_key: &SigningKey,
    options: FitRecOptions,
) -> Result<()> {
    let record = encode_fitrec(document, signing_key, options)?;
    fs::write(path, record)?;
    Ok(())
}

pub fn load_fitrec<P: AsRef<Path>>(path: P, verifying_key: &VerifyingKey) -> Result<FitDocument> {
    let record = fs::read(path)?;
    decode_fitrec(&record, verifying_key)
}

pub fn repair_fitrec<P: AsRef<Path>, Q: AsRef<Path>>(
    record_path: P,
    verifying_key: &VerifyingKey,
    output_path: Q,
) -> Result<FitRecRepair> {
    let record = fs::read(record_path)?;
    let repair = decode_fitrec_repaired(&record, verifying_key)?;
    if repair.damaged_shards > 0 {
        fs::write(output_path, &repair.repaired_record)?;
    }
    Ok(repair)
}

pub fn load_fitrec_info<P: AsRef<Path>>(
    path: P,
    verifying_key: &VerifyingKey,
) -> Result<FitRecInfo> {
    let record = fs::read(path)?;
    let document = decode_fitrec(&record, verifying_key)?;
    let header_len = u32::from_le_bytes(
        record[8..12]
            .try_into()
            .map_err(|_| CoreError::Malformed("header length is invalid"))?,
    ) as usize;
    let header_end = 12usize
        .checked_add(header_len)
        .ok_or(CoreError::Malformed("header length overflow"))?;
    if header_end > record.len() {
        return Err(CoreError::Malformed("header extends beyond record"));
    }
    #[derive(Deserialize)]
    struct RecoveryHeader {
        codec: CodecHeader,
    }
    let recovery: RecoveryHeader = serde_json::from_slice(&record[12..header_end])?;
    Ok(FitRecInfo {
        data_shards: recovery.codec.data_shards,
        parity_shards: recovery.codec.parity_shards,
        active_checklist: document.active_checklist.clone(),
        checklists: document
            .checklists
            .iter()
            .map(|(name, entries)| FitRecChecklistInfo {
                name: name.clone(),
                count: entries.len(),
                active: name == &document.active_checklist,
            })
            .collect(),
    })
}

pub fn encode_fitrec(
    document: &FitDocument,
    signing_key: &SigningKey,
    options: FitRecOptions,
) -> Result<Vec<u8>> {
    document.validate()?;
    let manifest_hash = document.active_manifest_hash()?;

    let data_shards = usize::from(options.data_shards);
    let parity_shards = usize::from(options.parity_shards);
    if data_shards == 0 {
        return Err(CoreError::Codec(
            "data shard count must be greater than zero",
        ));
    }
    if parity_shards == 0 {
        return Err(CoreError::Codec(
            "parity shard count must be greater than zero",
        ));
    }
    if data_shards
        .checked_add(parity_shards)
        .is_none_or(|n| n > 255)
    {
        return Err(CoreError::Codec("total RS shard count must not exceed 255"));
    }

    let document_json = serde_json::to_vec(document)?;
    let document_len = document_json.len();
    let document_sha256 = sha256_hex(&document_json);
    let shard_size = document_len.div_ceil(data_shards).max(1);
    if shard_size > u32::MAX as usize {
        return Err(CoreError::Codec("shard size exceeds format limit"));
    }

    let mut shards = vec![vec![0_u8; shard_size]; data_shards + parity_shards];
    for (shard_index, shard) in shards.iter_mut().enumerate().take(data_shards) {
        let start = shard_index * shard_size;
        let end = std::cmp::min(start + shard_size, document_len);
        if start < end {
            shard[..end - start].copy_from_slice(&document_json[start..end]);
        }
    }

    let codec = ReedSolomon::<galois_8::Field>::new(data_shards, parity_shards)
        .map_err(|_| CoreError::Codec("unable to construct RS codec"))?;
    codec
        .encode(&mut shards)
        .map_err(|_| CoreError::Codec("RS encoding failed"))?;

    let shard_hashes = shards
        .iter()
        .map(|shard| sha256_hex(shard))
        .collect::<Vec<_>>();
    let header = Header {
        format: "fitrec".to_string(),
        version: 1,
        manifest_hash,
        document_len: document_len as u64,
        document_sha256,
        codec: CodecHeader {
            algorithm: CodecAlgorithm::ReedSolomon,
            data_shards: options.data_shards,
            parity_shards: options.parity_shards,
            shard_size: shard_size as u32,
        },
        shard_sha256: shard_hashes,
        signature: SignatureHeader {
            algorithm: SignatureAlgorithm::Ed25519,
        },
    };
    let header_json = serde_json::to_vec(&header)?;
    if header_json.len() > u32::MAX as usize {
        return Err(CoreError::Malformed("header is too large"));
    }

    let mut output = Vec::with_capacity(
        8 + 4 + header_json.len() + shards.len() * shard_size + SIGNATURE_LENGTH,
    );
    output.extend_from_slice(&MAGIC);
    output.extend_from_slice(&(header_json.len() as u32).to_le_bytes());
    output.extend_from_slice(&header_json);
    let signed_bytes = output.clone();
    let signature = signing_key.sign(&signed_bytes);
    for shard in shards {
        output.extend_from_slice(&shard);
    }
    output.extend_from_slice(&signature.to_bytes());
    Ok(output)
}

pub fn decode_fitrec(record: &[u8], verifying_key: &VerifyingKey) -> Result<FitDocument> {
    Ok(decode_fitrec_repaired(record, verifying_key)?.document)
}

pub fn decode_fitrec_repaired(record: &[u8], verifying_key: &VerifyingKey) -> Result<FitRecRepair> {
    let minimum_len = MAGIC.len() + 4 + SIGNATURE_LENGTH;
    if record.len() < minimum_len || record[..8] != MAGIC {
        return Err(CoreError::Malformed("bad magic or truncated record"));
    }

    let header_len_bytes = &record[8..12];
    let header_len = u32::from_le_bytes(header_len_bytes.try_into().unwrap()) as usize;
    let header_start: usize = 12;
    let header_end = header_start
        .checked_add(header_len)
        .ok_or(CoreError::Malformed("header length overflow"))?;
    if header_end > record.len() {
        return Err(CoreError::Malformed("header extends beyond record"));
    }

    let signature_start = record.len().checked_sub(SIGNATURE_LENGTH).unwrap();
    if header_end > signature_start {
        return Err(CoreError::Malformed("header extends into record body"));
    }
    let signature_bytes = &record[signature_start..];
    let signature = Signature::from_slice(signature_bytes)
        .map_err(|error| CoreError::Crypto(error.to_string()))?;
    let signed_bytes = &record[..header_end];
    verifying_key
        .verify(signed_bytes, &signature)
        .map_err(|_| CoreError::Signature)?;

    let header: Header = serde_json::from_slice(&record[header_start..header_end])?;
    if header.format != "fitrec" || header.version != 1 {
        return Err(CoreError::UnsupportedVersion(header.version));
    }
    let data_shards = usize::from(header.codec.data_shards);
    let parity_shards = usize::from(header.codec.parity_shards);
    if data_shards == 0 || parity_shards == 0 || data_shards + parity_shards > 255 {
        return Err(CoreError::Codec("invalid RS shard configuration"));
    }
    if header.shard_sha256.len() != data_shards + parity_shards {
        return Err(CoreError::Malformed(
            "shard hash count does not match codec",
        ));
    }

    let shard_size = header.codec.shard_size as usize;
    let shard_count = data_shards + parity_shards;
    let body_len = data_shards
        .checked_mul(shard_size)
        .and_then(|len| len.checked_add(parity_shards.checked_mul(shard_size)?))
        .ok_or(CoreError::Malformed("shard body length overflow"))?;
    if body_len != signature_start - header_end {
        return Err(CoreError::Malformed("shard body length mismatch"));
    }

    let mut shards: Vec<Vec<u8>> = Vec::with_capacity(shard_count);
    for index in 0..shard_count {
        let start = header_end + index * shard_size;
        shards.push(record[start..start + shard_size].to_vec());
    }

    let mut damaged_shards = 0;
    let mut repaired: Option<Vec<u8>> = None;
    let damaged = shards
        .iter()
        .zip(&header.shard_sha256)
        .enumerate()
        .filter(|(_, (shard, expected))| sha256_hex(shard) != expected.as_str())
        .map(|(index, _)| index)
        .collect::<Vec<_>>();
    if damaged.len() > parity_shards {
        return Err(CoreError::InsufficientShards {
            damaged: damaged.len(),
            capacity: parity_shards,
        });
    }

    if !damaged.is_empty() {
        let codec = ReedSolomon::<galois_8::Field>::new(data_shards, parity_shards)
            .map_err(|_| CoreError::Codec("unable to construct RS codec"))?;
        let mut reconstructions = shards
            .iter()
            .enumerate()
            .map(|(index, shard)| (shard.clone(), !damaged.contains(&index)))
            .collect::<Vec<_>>();
        codec
            .reconstruct(&mut reconstructions)
            .map_err(|_| CoreError::Codec("RS reconstruction failed"))?;
        shards = reconstructions
            .into_iter()
            .map(|(shard, _)| shard)
            .collect();
        for (index, shard) in shards.iter().take(shard_count).enumerate() {
            if sha256_hex(shard) != header.shard_sha256[index] {
                return Err(CoreError::Integrity);
            }
        }

        let mut repaired_record = Vec::with_capacity(record.len());
        repaired_record.extend_from_slice(&record[..header_end]);
        for shard in &shards {
            repaired_record.extend_from_slice(shard);
        }
        repaired_record.extend_from_slice(&record[signature_start..]);
        damaged_shards = damaged.len();
        repaired = Some(repaired_record);
    }

    let document_len = header.document_len as usize;
    if document_len > data_shards * shard_size {
        return Err(CoreError::Malformed(
            "document length exceeds shard capacity",
        ));
    }
    let mut document_json = Vec::with_capacity(document_len);
    for shard in shards.iter().take(data_shards) {
        let remaining = document_len - document_json.len();
        document_json.extend_from_slice(&shard[..std::cmp::min(shard_size, remaining)]);
        if document_json.len() >= document_len {
            break;
        }
    }
    if document_json.len() != document_len || sha256_hex(&document_json) != header.document_sha256 {
        return Err(CoreError::Integrity);
    }

    let document: FitDocument = serde_json::from_slice(&document_json)?;
    document.validate()?;
    if document.active_manifest_hash()? != header.manifest_hash {
        return Err(CoreError::Integrity);
    }
    Ok(FitRecRepair {
        document,
        repaired_record: repaired.unwrap_or_else(|| record.to_vec()),
        damaged_shards,
    })
}
