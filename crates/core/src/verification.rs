use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

use rayon::prelude::*;
use serde::Serialize;
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

use crate::error::{CoreError, Result};
use crate::manifest::{FitDocument, normalize_relative_path};
use crate::rules::FileRules;

const READ_CHUNK: usize = 1024 * 1024;
const PROGRESS_EVERY: usize = 16;

thread_local! {
    static READ_BUFFER: std::cell::RefCell<Vec<u8>> =
        std::cell::RefCell::new(vec![0_u8; READ_CHUNK]);
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct VerificationProgress {
    pub completed: usize,
    pub total: usize,
    pub passed: usize,
    pub failed: usize,
    pub missing: usize,
    pub extra: usize,
}

pub type ProgressCallback = Arc<dyn Fn(VerificationProgress) + Send + Sync>;

#[derive(Clone, Debug, Serialize)]
pub struct VerificationDetail {
    pub path: String,
    pub status: String,
    pub expected: String,
    pub actual: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct VerificationReport {
    pub total: usize,
    pub passed: usize,
    pub failed: usize,
    pub missing: usize,
    pub extra_count: usize,
    pub cancelled: bool,
    pub details: Vec<VerificationDetail>,
    pub errors: Vec<String>,
}

#[derive(Clone, Default)]
pub struct VerificationOptions {
    pub exclude_paths: Vec<PathBuf>,
    pub exclude_rules: FileRules,
    pub ignored_paths: Vec<String>,
    pub self_exe: Option<PathBuf>,
    pub cancel: Option<Arc<AtomicBool>>,
    pub progress: Option<ProgressCallback>,
}

struct HashTask {
    detail_index: usize,
    relative_path: String,
    full_path: PathBuf,
    expected: String,
}

pub fn run_verification(
    document: &FitDocument,
    target_dir: &Path,
    options: &VerificationOptions,
) -> Result<VerificationReport> {
    if !document.algorithm.eq_ignore_ascii_case("sha256") {
        return Err(CoreError::UnsupportedAlgorithm(document.algorithm.clone()));
    }
    if !target_dir.is_dir() {
        return Err(CoreError::Io(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "target directory not found",
        )));
    }

    let entries = document.active_entries()?;
    let mut details: Vec<Option<VerificationDetail>> = Vec::with_capacity(entries.len());
    details.resize_with(entries.len(), || None);

    let mut manifest_indices = HashMap::with_capacity(entries.len());
    let mut manifest_paths = HashSet::with_capacity(entries.len());
    for (index, entry) in entries.iter().enumerate() {
        let normalized = normalize_relative_path(&entry.path)?;
        manifest_indices.insert(normalized.clone(), index);
        manifest_paths.insert(normalized);
    }

    let ignored_paths = options
        .ignored_paths
        .iter()
        .filter_map(|path| normalize_relative_path(path).ok())
        .map(|path| path.to_ascii_lowercase())
        .collect::<Vec<_>>();

    let target = target_dir.canonicalize().map_err(CoreError::Io)?;
    let absolute_excludes = options
        .exclude_paths
        .iter()
        .filter(|path| !path.as_os_str().is_empty())
        .map(|path| {
            path.canonicalize()
                .unwrap_or_else(|_| path.to_path_buf())
                .to_string_lossy()
                .to_ascii_lowercase()
        })
        .collect::<HashSet<_>>();
    let self_exe = options.self_exe.as_ref().map(|path| {
        path.canonicalize()
            .unwrap_or_else(|_| path.to_path_buf())
            .to_string_lossy()
            .to_ascii_lowercase()
    });

    let mut errors = Vec::new();
    let mut extras = Vec::new();
    let mut tasks = Vec::new();
    let completed = Arc::new(AtomicUsize::new(0));
    let passed_count = Arc::new(AtomicUsize::new(0));
    let failed_count = Arc::new(AtomicUsize::new(0));
    let known_missing = entries.len().saturating_sub(tasks.len());
    let known_extra = extras.len();

    let mut walker = WalkDir::new(&target).sort_by_file_name().into_iter();
    while let Some(result) = walker.next() {
        if is_cancelled(options) {
            break;
        }
        let entry = match result {
            Ok(entry) => entry,
            Err(error) => {
                errors.push(error.to_string());
                continue;
            }
        };
        let path = entry.path();
        let is_dir = entry.file_type().is_dir();
        let full_key = path.to_string_lossy().to_ascii_lowercase();

        if is_dir {
            let name = entry.file_name().to_string_lossy().to_string();
            let relative_dir = path
                .strip_prefix(&target)
                .ok()
                .and_then(|relative| normalize_relative_path(&relative.to_string_lossy()).ok())
                .map(|value| value.to_ascii_lowercase());
            if options.exclude_rules.excludes_directory(&name)
                || relative_dir.is_some_and(|relative| {
                    ignored_paths.iter().any(|ignored| {
                        relative == *ignored || relative.starts_with(&format!("{ignored}/"))
                    })
                })
                || absolute_excludes.contains(&full_key)
            {
                walker.skip_current_dir();
                continue;
            }
            continue;
        }

        if !entry.file_type().is_file() {
            continue;
        }
        if self_exe.as_deref() == Some(full_key.as_str()) {
            continue;
        }
        if absolute_excludes.contains(&full_key) {
            continue;
        }

        let relative = path
            .strip_prefix(&target)
            .map_err(|error| CoreError::Io(std::io::Error::other(error.to_string())))?;
        let relative = relative.to_string_lossy().replace('\\', "/");
        let normalized = normalize_relative_path(&relative)?;
        if ignored_paths.iter().any(|ignored| {
            let normalized_lower = normalized.to_ascii_lowercase();
            normalized_lower == *ignored || normalized_lower.starts_with(&format!("{ignored}/"))
        }) {
            continue;
        }
        if manifest_paths.contains(&normalized) {
            let index = manifest_indices[&normalized];
            let entry = &entries[index];
            tasks.push(HashTask {
                detail_index: index,
                relative_path: entry.path.clone(),
                full_path: path.to_path_buf(),
                expected: entry.hash.clone(),
            });
        } else if options.exclude_rules.excludes(
            &relative,
            entry.metadata().map(|meta| meta.len()).unwrap_or(0),
        ) {
            continue;
        } else {
            extras.push(VerificationDetail {
                path: relative,
                status: "extra".to_string(),
                expected: String::new(),
                actual: String::new(),
            });
        }
    }

    let hashed = tasks
        .par_iter()
        .map(|task| {
            if is_cancelled(options) {
                return None;
            }
            let result = match hash_file(&task.full_path, options) {
                Ok(actual) => {
                    let status = if actual == task.expected {
                        passed_count.fetch_add(1, Ordering::Relaxed);
                        "pass"
                    } else {
                        failed_count.fetch_add(1, Ordering::Relaxed);
                        "fail"
                    };
                    Some((
                        task.detail_index,
                        VerificationDetail {
                            path: task.relative_path.clone(),
                            status: status.to_string(),
                            expected: task.expected.clone(),
                            actual,
                        },
                    ))
                }
                Err(error) => {
                    failed_count.fetch_add(1, Ordering::Relaxed);
                    Some((
                        task.detail_index,
                        VerificationDetail {
                            path: task.relative_path.clone(),
                            status: "error".to_string(),
                            expected: task.expected.clone(),
                            actual: error,
                        },
                    ))
                }
            };

            let completed = completed.fetch_add(1, Ordering::Relaxed) + 1;
            if (completed.is_multiple_of(PROGRESS_EVERY) || completed == tasks.len())
                && let Some(progress) = &options.progress
            {
                progress(VerificationProgress {
                    completed,
                    total: entries.len(),
                    passed: passed_count.load(Ordering::Relaxed),
                    failed: failed_count.load(Ordering::Relaxed),
                    missing: known_missing,
                    extra: known_extra,
                });
            }
            result
        })
        .collect::<Vec<_>>();

    let cancelled = is_cancelled(options);

    let mut passed = 0;
    let mut failed = 0;
    for item in hashed.into_iter().flatten() {
        let (index, detail) = item;
        match detail.status.as_str() {
            "pass" => passed += 1,
            "fail" | "error" => failed += 1,
            _ => {}
        }
        details[index] = Some(detail);
    }

    let mut missing = 0;
    for (index, entry) in entries.iter().enumerate() {
        if details[index].is_none() && !cancelled {
            missing += 1;
            details[index] = Some(VerificationDetail {
                path: entry.path.clone(),
                status: "missing".to_string(),
                expected: entry.hash.clone(),
                actual: String::new(),
            });
        }
    }

    let mut all_details = details.into_iter().flatten().collect::<Vec<_>>();
    all_details.extend(extras);
    let extra_count = all_details
        .iter()
        .filter(|detail| detail.status == "extra")
        .count();

    Ok(VerificationReport {
        total: entries.len(),
        passed,
        failed,
        missing,
        extra_count,
        details: all_details,
        errors,
        cancelled,
    })
}

fn hash_file(path: &Path, options: &VerificationOptions) -> std::result::Result<String, String> {
    let mut file = File::open(path).map_err(|error| error.to_string())?;
    READ_BUFFER.with_borrow_mut(|buffer| {
        let mut hasher = Sha256::new();
        loop {
            if is_cancelled(options) {
                return Err("已取消".to_string());
            }
            let read = file.read(buffer).map_err(|error| error.to_string())?;
            if read == 0 {
                break;
            }
            hasher.update(&buffer[..read]);
        }
        let digest = hasher.finalize();
        Ok(crate::manifest::bytes_to_hex(&digest))
    })
}

fn is_cancelled(options: &VerificationOptions) -> bool {
    options
        .cancel
        .as_ref()
        .map(|flag| flag.load(Ordering::Relaxed))
        .unwrap_or(false)
}
