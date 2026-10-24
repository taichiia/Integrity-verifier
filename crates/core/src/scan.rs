use std::path::Path;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::mpsc;
use std::thread;
use std::time::UNIX_EPOCH;

use serde::{Deserialize, Serialize};
use walkdir::WalkDir;

use crate::error::{CoreError, Result};
use crate::hashing::{HashAlgorithm, hash_file};
use crate::manifest::normalize_relative_path;

const PROGRESS_EVERY: usize = 256;
const PREHASH_BATCH: usize = 64;

#[derive(Clone, Default)]
pub struct ScanOptions {
    pub cancel: Option<Arc<AtomicBool>>,
    pub progress: Option<ScanProgressCallback>,
}

pub type ScanProgressCallback = Arc<dyn Fn(usize, &str) + Send + Sync>;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ScannedFile {
    pub path: String,
    pub absolute_path: String,
    pub size: u64,
    pub modified: Option<u64>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct ScanReport {
    pub root: String,
    pub files: Vec<ScannedFile>,
    pub errors: Vec<String>,
    pub cancelled: bool,
    #[serde(default)]
    pub prehashes: Vec<PreHashEntry>,
}

#[derive(Clone)]
pub struct PreHashOptions {
    pub algorithm: HashAlgorithm,
    pub cancel: Option<Arc<AtomicBool>>,
    pub progress: Option<PreHashProgressCallback>,
}

impl Default for PreHashOptions {
    fn default() -> Self {
        Self {
            algorithm: HashAlgorithm::Sha256,
            cancel: None,
            progress: None,
        }
    }
}

pub type PreHashProgressCallback = Arc<dyn Fn(usize, usize, &str) + Send + Sync>;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PreHashEntry {
    pub path: String,
    pub absolute_path: String,
    pub algorithm: HashAlgorithm,
    pub hash: String,
    pub size: u64,
    pub modified: Option<u64>,
}

pub fn scan_and_prehash(
    root: &Path,
    scan_options: &ScanOptions,
    prehash_options: &PreHashOptions,
) -> Result<ScanReport> {
    if !root.is_dir() {
        return Err(CoreError::Io(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "scan root is not a directory",
        )));
    }

    let (sender, receiver) = mpsc::channel::<ScannedFile>();
    let walk_root = root.to_path_buf();
    let walk_cancel = scan_options.cancel.clone();
    let walk_errors = Arc::new(std::sync::Mutex::new(Vec::new()));
    let walk_cancelled = Arc::new(AtomicBool::new(false));
    let walk_cancelled_observer = walk_cancelled.clone();
    let walk_errors_observer = walk_errors.clone();
    let discovered_total = Arc::new(AtomicUsize::new(0));
    let discovered_total_observer = discovered_total.clone();

    let walker = thread::spawn(move || {
        for entry in WalkDir::new(&walk_root).sort_by_file_name() {
            if walk_cancel
                .as_ref()
                .is_some_and(|flag| flag.load(Ordering::Relaxed))
            {
                walk_cancelled_observer.store(true, Ordering::Relaxed);
                break;
            }

            let entry = match entry {
                Ok(entry) => entry,
                Err(error) => {
                    walk_errors_observer.lock().unwrap().push(error.to_string());
                    continue;
                }
            };
            if !entry.file_type().is_file() {
                continue;
            }

            let path = entry.path();
            let relative = match path.strip_prefix(&walk_root) {
                Ok(relative) => relative,
                Err(error) => {
                    walk_errors_observer
                        .lock()
                        .unwrap()
                        .push(format!("{}: {error}", path.display()));
                    continue;
                }
            };
            let relative_text = match normalize_relative_path(&relative.to_string_lossy()) {
                Ok(relative_text) => relative_text,
                Err(error) => {
                    walk_errors_observer.lock().unwrap().push(error.to_string());
                    continue;
                }
            };
            let metadata = match entry.metadata() {
                Ok(metadata) => metadata,
                Err(error) => {
                    walk_errors_observer
                        .lock()
                        .unwrap()
                        .push(format!("{}: {error}", path.display()));
                    continue;
                }
            };

            let file = ScannedFile {
                path: relative_text,
                absolute_path: path.to_string_lossy().to_string(),
                size: metadata.len(),
                modified: modified_timestamp(&metadata),
            };
            if sender.send(file).is_err() {
                break;
            }
            discovered_total_observer.fetch_add(1, Ordering::Relaxed);
        }
    });

    let mut report = ScanReport {
        root: root.to_string_lossy().to_string(),
        files: Vec::new(),
        errors: Vec::new(),
        cancelled: false,
        prehashes: Vec::new(),
    };
    let mut pending = Vec::with_capacity(PREHASH_BATCH);

    while let Ok(file) = receiver.recv() {
        report.files.push(file.clone());
        pending.push(file);
        if pending.len() < PREHASH_BATCH {
            continue;
        }
        let entries = prehash_batch(&pending, prehash_options, &discovered_total);
        report.prehashes.extend(entries.into_iter().flatten());
        pending.clear();
    }

    if !pending.is_empty() {
        let entries = prehash_batch(&pending, prehash_options, &discovered_total);
        report.prehashes.extend(entries.into_iter().flatten());
    }

    let _ = walker.join();
    report.errors.extend(walk_errors.lock().unwrap().drain(..));
    report.cancelled = walk_cancelled.load(Ordering::Relaxed);
    Ok(report)
}

pub fn prehash_files(files: &[ScannedFile], options: &PreHashOptions) -> Vec<Option<PreHashEntry>> {
    let total = Arc::new(AtomicUsize::new(files.len()));
    prehash_batch(files, options, &total)
}

pub fn scan_directory(root: &Path, options: &ScanOptions) -> Result<ScanReport> {
    if !root.is_dir() {
        return Err(CoreError::Io(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "scan root is not a directory",
        )));
    }

    let mut report = ScanReport {
        root: root.to_string_lossy().to_string(),
        files: Vec::new(),
        errors: Vec::new(),
        cancelled: false,
        prehashes: Vec::new(),
    };
    let completed = AtomicUsize::new(0);

    for entry in WalkDir::new(root).sort_by_file_name() {
        if is_cancelled(options) {
            report.cancelled = true;
            return Ok(report);
        }
        let entry = match entry {
            Ok(entry) => entry,
            Err(error) => {
                report.errors.push(error.to_string());
                continue;
            }
        };
        if !entry.file_type().is_file() {
            continue;
        }

        let path = entry.path();
        let relative = path
            .strip_prefix(root)
            .map_err(|error| CoreError::Io(std::io::Error::other(error.to_string())))?;
        let relative_text = normalize_relative_path(&relative.to_string_lossy())?;
        let metadata = entry.metadata().map_err(|error| {
            CoreError::Io(std::io::Error::other(format!(
                "{}: {error}",
                path.display()
            )))
        })?;

        report.files.push(ScannedFile {
            path: relative_text,
            absolute_path: path.to_string_lossy().to_string(),
            size: metadata.len(),
            modified: modified_timestamp(&metadata),
        });

        let completed = completed.fetch_add(1, Ordering::Relaxed) + 1;
        if completed.is_multiple_of(PROGRESS_EVERY)
            && let Some(progress) = &options.progress
        {
            progress(completed, &report.files[completed - 1].path);
        }
    }

    Ok(report)
}

fn prehash_batch(
    files: &[ScannedFile],
    options: &PreHashOptions,
    total: &Arc<AtomicUsize>,
) -> Vec<Option<PreHashEntry>> {
    use rayon::prelude::*;

    let completed = Arc::new(AtomicUsize::new(0));
    files
        .par_iter()
        .map(|file| {
            if is_prehash_cancelled(options) {
                return None;
            }

            let result = hash_file(Path::new(&file.absolute_path), options.algorithm).ok();
            let completed = completed.fetch_add(1, Ordering::Relaxed) + 1;
            if let Some(progress) = &options.progress {
                progress(completed, total.load(Ordering::Relaxed), &file.path);
            }
            result.map(|hash| PreHashEntry {
                path: file.path.clone(),
                absolute_path: file.absolute_path.clone(),
                algorithm: options.algorithm,
                hash,
                size: file.size,
                modified: file.modified,
            })
        })
        .collect()
}

pub fn modified_timestamp(metadata: &std::fs::Metadata) -> Option<u64> {
    metadata
        .modified()
        .ok()?
        .duration_since(UNIX_EPOCH)
        .ok()
        .map(|duration| duration.as_millis() as u64)
}

fn is_cancelled(options: &ScanOptions) -> bool {
    options
        .cancel
        .as_ref()
        .map(|flag| flag.load(Ordering::Relaxed))
        .unwrap_or(false)
}

fn is_prehash_cancelled(options: &PreHashOptions) -> bool {
    options
        .cancel
        .as_ref()
        .map(|flag| flag.load(Ordering::Relaxed))
        .unwrap_or(false)
}
