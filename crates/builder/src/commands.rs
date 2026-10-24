use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use fit_core::{
    FileRecoveryMode, FileRecoveryOptions, FileRules, FitDocument, HashAlgorithm, HashOptions,
    ManifestEntry, ScanOptions, ScannedFile, VerificationOptions, estimate_file_recovery_size,
    generate_keypair, hash_file, load_signing_key, modified_timestamp, prehash_files, run_hashing,
    run_verification, scan_directory as scan_directory_core, write_file_recovery_with_progress,
    write_fitrec, write_public_key,
};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use tauri::{Emitter, State};
use tauri_plugin_dialog::DialogExt;

const MAX_PATH_LENGTH: usize = 4096;
const PREHASH_BACKGROUND_BATCH: usize = 64;

fn default_project_shard_size() -> u32 {
    1024 * 1024
}

#[derive(Clone, Default)]
pub struct BuilderState {
    scan_cancel: Arc<AtomicBool>,
    prehash_cancel: Arc<AtomicBool>,
    prehash_generation: Arc<AtomicU64>,
    hash_cancel: Arc<AtomicBool>,
    hash_pause: Arc<AtomicBool>,
    verify_cancel: Arc<AtomicBool>,
    prehash_cache: Arc<Mutex<HashMap<PathBuf, fit_core::PreHashEntry>>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ScanArgs {
    pub root_path: String,
    #[serde(default)]
    pub prehash: bool,
    pub algorithm: HashAlgorithm,
}

#[derive(Debug, Deserialize)]
pub struct FilterArgs {
    pub files: Vec<ScannedFile>,
    pub rules: Map<String, Value>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HashArgs {
    pub base_path: String,
    pub paths: Vec<String>,
    pub algorithm: HashAlgorithm,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HashRunReport {
    pub results: Vec<fit_core::HashResult>,
    pub reused: usize,
    pub total: usize,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KeyPairArgs {
    pub private_key_path: String,
    pub public_key_path: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FitRecArgs {
    pub document: FitDocument,
    pub source_directory: String,
    pub output_path: String,
    pub private_key_path: String,
    pub data_shards: u8,
    pub parity_shards: u8,
    #[serde(default = "default_project_shard_size")]
    pub shard_size: u32,
    #[serde(default)]
    pub mode: FileRecoveryMode,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VerifyArgs {
    pub document: FitDocument,
    pub target_path: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EstimateRecoveryArgs {
    pub document: FitDocument,
    pub source_directory: String,
    pub data_shards: u8,
    pub parity_shards: u8,
    pub shard_size: u32,
    pub mode: FileRecoveryMode,
}

fn file_recovery_options(args: &FitRecArgs) -> Result<FileRecoveryOptions, String> {
    if args.shard_size == 0 {
        return Err("shard size must be greater than zero".to_string());
    }
    Ok(FileRecoveryOptions {
        data_shards: args.data_shards,
        parity_shards: args.parity_shards,
        shard_size: args.shard_size,
        mode: args.mode,
    })
}

#[tauri::command]
pub async fn estimate_file_recovery_command(args: EstimateRecoveryArgs) -> Result<Value, String> {
    let source_directory = validate_existing_directory(&args.source_directory)?;
    args.document
        .validate()
        .map_err(|error| format!("invalid document: {error}"))?;
    let fit_args = FitRecArgs {
        document: args.document.clone(),
        source_directory: args.source_directory.clone(),
        output_path: String::new(),
        private_key_path: String::new(),
        data_shards: args.data_shards,
        parity_shards: args.parity_shards,
        shard_size: args.shard_size,
        mode: args.mode,
    };
    let options = file_recovery_options(&fit_args)?;
    let document_source = source_directory.clone();
    tauri::async_runtime::spawn_blocking(move || {
        estimate_file_recovery_size(&document_source, &args.document, options)
            .map_err(|error| format!("recovery estimate failed: {error}"))
    })
    .await
    .map_err(|error| format!("estimate task failed: {error}"))?
    .and_then(|estimate| {
        serde_json::to_value(estimate)
            .map_err(|error| format!("estimate serialization failed: {error}"))
    })
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct ProjectDocument {
    pub version: u8,
    pub base_directory: String,
    pub algorithm: HashAlgorithm,
    pub files: Vec<ScannedFile>,
    pub entries: Vec<ManifestEntry>,
    pub checklists: BTreeMap<String, Vec<ManifestEntry>>,
    pub active_checklist: String,
    pub exclude_paths: Vec<String>,
    pub exclude_rules: Map<String, Value>,
    pub fitrec_private_key_path: String,
    pub data_shards: u8,
    pub parity_shards: u8,
    #[serde(default = "default_project_shard_size")]
    pub shard_size: u32,
    pub recovery_mode: FileRecoveryMode,
    pub project_name: String,
    pub checksum_output_path: String,
    pub checksum_format: String,
    pub private_key_path: String,
    pub signature_algorithm: String,
    pub verifier_title: String,
    pub verifier_icon_path: String,
    pub verifier_version: String,
    pub verifier_company: String,
    pub verifier_copyright: String,
    pub verifier_path_rule: String,
    pub verifier_subfolder: String,
    pub verifier_custom_template: String,
    pub verifier_embed_encrypted: bool,
    pub verifier_enable_signature_verify: bool,
    pub verifier_enable_antidebug: bool,
    pub verifier_enable_antisanbox: bool,
}

impl Default for ProjectDocument {
    fn default() -> Self {
        let mut checklists = BTreeMap::new();
        checklists.insert("default".to_string(), Vec::new());
        Self {
            version: 1,
            base_directory: String::new(),
            algorithm: HashAlgorithm::Sha256,
            files: Vec::new(),
            entries: Vec::new(),
            checklists,
            active_checklist: "default".to_string(),
            exclude_paths: Vec::new(),
            exclude_rules: Map::new(),
            fitrec_private_key_path: String::new(),
            data_shards: 16,
            parity_shards: 4,
            shard_size: 1024 * 1024,
            recovery_mode: FileRecoveryMode::CrossFile,
            project_name: "Untitled".to_string(),
            checksum_output_path: String::new(),
            checksum_format: "csv".to_string(),
            private_key_path: String::new(),
            signature_algorithm: "Ed25519".to_string(),
            verifier_title: "File Integrity Verifier".to_string(),
            verifier_icon_path: String::new(),
            verifier_version: "1.0.0.0".to_string(),
            verifier_company: String::new(),
            verifier_copyright: String::new(),
            verifier_path_rule: "current_dir".to_string(),
            verifier_subfolder: String::new(),
            verifier_custom_template: String::new(),
            verifier_embed_encrypted: true,
            verifier_enable_signature_verify: true,
            verifier_enable_antidebug: false,
            verifier_enable_antisanbox: false,
        }
    }
}

#[tauri::command]
pub async fn scan_directory(
    app: tauri::AppHandle,
    state: State<'_, BuilderState>,
    args: ScanArgs,
) -> Result<fit_core::ScanReport, String> {
    let root = validate_existing_directory(&args.root_path)?;
    state.prehash_cancel.store(true, Ordering::Relaxed);
    let generation = state.prehash_generation.fetch_add(1, Ordering::Relaxed) + 1;
    state.scan_cancel.store(false, Ordering::Relaxed);
    state.prehash_cache.lock().unwrap().clear();
    let cancel = state.scan_cancel.clone();
    let progress_app = app.clone();
    let scan_progress_app = progress_app.clone();
    let options = ScanOptions {
        cancel: Some(cancel.clone()),
        progress: Some(Arc::new(move |count, path| {
            let _ = scan_progress_app.emit(
                "builder-scan-progress",
                json!({"stage": "scan", "count": count, "path": path}),
            );
        })),
    };
    let scan = scan_directory_core(&root, &options);
    let report = tauri::async_runtime::spawn_blocking(move || scan)
        .await
        .map_err(|error| format!("scan task failed: {error}"))?
        .map_err(|error| format!("scan failed: {error}"))?;

    if args.prehash && !report.cancelled {
        let files = report.files.clone();
        let total_files = files.len();
        let prehash_completed = Arc::new(AtomicU64::new(0));
        let prehash_progress_count = prehash_completed.clone();
        let prehash_app = app.clone();
        let prehash_cancel = state.prehash_cancel.clone();
        let prehash_generation = state.prehash_generation.clone();
        let prehash_cache = state.prehash_cache.clone();
        prehash_cancel.store(false, Ordering::Relaxed);
        let prehash_options = fit_core::PreHashOptions {
            algorithm: args.algorithm,
            cancel: Some(prehash_cancel.clone()),
            progress: Some(Arc::new(move |_completed, _total, path| {
                let completed = prehash_progress_count.fetch_add(1, Ordering::Relaxed) + 1;
                let _ = prehash_app.emit(
                    "builder-scan-progress",
                    json!({
                        "stage": "prehash",
                        "completed": completed,
                        "total": total_files,
                        "path": path
                    }),
                );
            })),
        };

        tauri::async_runtime::spawn_blocking(move || {
            let mut files = files;
            files.reverse();
            for batch in files.chunks(PREHASH_BACKGROUND_BATCH) {
                if prehash_cancel.load(Ordering::Relaxed)
                    || prehash_generation.load(Ordering::Relaxed) != generation
                {
                    return;
                }
                let entries = prehash_files(batch, &prehash_options);
                if prehash_cancel.load(Ordering::Relaxed)
                    || prehash_generation.load(Ordering::Relaxed) != generation
                {
                    return;
                }
                let mut cache = prehash_cache.lock().unwrap();
                if prehash_generation.load(Ordering::Relaxed) != generation {
                    return;
                }
                for entry in entries.into_iter().flatten() {
                    let key = PathBuf::from(&entry.absolute_path)
                        .canonicalize()
                        .unwrap_or_else(|_| PathBuf::from(&entry.absolute_path));
                    cache.insert(key, entry);
                }
            }
            let _ = app.emit(
                "builder-scan-progress",
                json!({
                    "stage": "prehashDone",
                    "completed": total_files,
                    "total": total_files,
                    "path": ""
                }),
            );
        });
    }

    Ok(report)
}

#[tauri::command]
pub fn cancel_scan(state: State<'_, BuilderState>) {
    state.scan_cancel.store(true, Ordering::Relaxed);
    state.prehash_cancel.store(true, Ordering::Relaxed);
}

#[tauri::command]
pub fn filter_files(args: FilterArgs) -> Result<Vec<ScannedFile>, String> {
    let rules = FileRules::from_config(&args.rules);
    Ok(args
        .files
        .into_iter()
        .filter(|file| !rules.excludes(&file.path, file.size))
        .collect())
}

#[tauri::command]
pub async fn calculate_hashes(
    app: tauri::AppHandle,
    state: State<'_, BuilderState>,
    args: HashArgs,
) -> Result<HashRunReport, String> {
    let base = validate_existing_directory(&args.base_path)?;
    let canonical_base = base
        .canonicalize()
        .map_err(|error| format!("unable to resolve base directory: {error}"))?;
    let mut paths = Vec::with_capacity(args.paths.len());
    for raw_path in args.paths {
        let path = PathBuf::from(raw_path);
        let canonical = path
            .canonicalize()
            .map_err(|_error| format!("file does not exist: {}", path.display()))?;
        if !canonical.is_file() {
            return Err(format!("file does not exist: {}", canonical.display()));
        }
        if !canonical.starts_with(&canonical_base) {
            return Err(format!(
                "path is outside the selected base directory: {}",
                canonical.display()
            ));
        }
        paths.push(canonical);
    }

    let mut results = Vec::with_capacity(paths.len());
    let mut uncached_paths = Vec::new();
    let mut uncached_positions = Vec::new();
    state.prehash_cancel.store(true, Ordering::Relaxed);
    for (position, canonical) in paths.iter().enumerate() {
        if let Some(hash) = cached_prehash(&state, canonical, args.algorithm) {
            results.push(fit_core::HashResult {
                path: canonical.to_string_lossy().to_string(),
                hash,
                error: String::new(),
            });
        } else {
            results.push(fit_core::HashResult {
                path: canonical.to_string_lossy().to_string(),
                hash: String::new(),
                error: String::from("pending"),
            });
            uncached_paths.push(canonical.clone());
            uncached_positions.push(position);
        }
    }

    state.hash_cancel.store(false, Ordering::Relaxed);
    state.hash_pause.store(false, Ordering::Relaxed);
    let cancel = state.hash_cancel.clone();
    let pause = state.hash_pause.clone();
    let progress_app = app.clone();
    let options = HashOptions {
        cancel: Some(cancel),
        pause: Some(pause),
        progress: Some(Arc::new(move |completed, total, path| {
            let _ = progress_app.emit(
                "builder-hash-progress",
                json!({"completed": completed, "total": total, "path": path}),
            );
        })),
    };
    let uncached_results = run_hashing(&uncached_paths, args.algorithm, &options);
    for (position, result) in uncached_positions.into_iter().zip(uncached_results) {
        results[position] = result;
    }

    let reused = results.len() - uncached_paths.len();
    Ok(HashRunReport {
        results,
        reused,
        total: paths.len(),
    })
}

fn cached_prehash(state: &BuilderState, path: &Path, algorithm: HashAlgorithm) -> Option<String> {
    let metadata = fs::metadata(path).ok()?;
    let modified = modified_timestamp(&metadata);
    let cache = state.prehash_cache.lock().unwrap();
    let entry = cache.get(path)?;
    if entry.algorithm == algorithm && entry.size == metadata.len() && entry.modified == modified {
        Some(entry.hash.clone())
    } else {
        None
    }
}

#[tauri::command]
pub fn cancel_hashing(state: State<'_, BuilderState>) {
    state.hash_cancel.store(true, Ordering::Relaxed);
}

#[tauri::command]
pub fn toggle_hash_pause(state: State<'_, BuilderState>) -> bool {
    let paused = !state.hash_pause.load(Ordering::Relaxed);
    state.hash_pause.store(paused, Ordering::Relaxed);
    paused
}

#[tauri::command]
pub fn hash_file_command(path: String, algorithm: HashAlgorithm) -> Result<String, String> {
    let path = validate_existing_file(&path)?;
    hash_file(&path, algorithm).map_err(|error| format!("hash failed: {error}"))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WriteChecksumArgs {
    pub path: String,
    pub format: String,
    pub algorithm: String,
    pub entries: Vec<fit_core::ChecksumEntry>,
}

#[tauri::command]
pub fn write_checksum_file(args: WriteChecksumArgs) -> Result<(), String> {
    let path = validate_writable_path(&args.path)?;
    if args.entries.is_empty() {
        return Err("cannot write an empty checksum file".to_string());
    }
    match args.format.as_str() {
        "csv" => fit_core::write_csv(&path, &args.algorithm, &args.entries),
        "sfv" => fit_core::write_sfv(&path, &args.entries),
        _ => Err(fit_core::CoreError::Manifest(
            "unsupported checksum file format",
        )),
    }
    .map_err(|error| format!("checksum file write failed: {error}"))
}

#[tauri::command]
pub fn read_checksum_file(path: String) -> Result<fit_core::ChecksumFile, String> {
    let path = validate_existing_file(&path)?;
    fit_core::read_checksum_file(&path, "sha256")
        .map_err(|error| format!("checksum file load failed: {error}"))
}

#[tauri::command]
pub fn sign_checksum_file(path: String, private_key_path: String) -> Result<String, String> {
    let path = validate_existing_file(&path)?;
    let private_key = validate_existing_file(&private_key_path)?;
    fit_core::sign_file(&path, &private_key)
        .map(|signature_path| signature_path.to_string_lossy().to_string())
        .map_err(|error| format!("checksum signing failed: {error}"))
}

#[tauri::command]
pub fn verify_checksum_file(path: String, public_key_path: String) -> Result<(), String> {
    let path = validate_existing_file(&path)?;
    let public_key = validate_existing_file(&public_key_path)?;
    fit_core::verify_file(&path, &public_key)
        .map_err(|error| format!("checksum signature verification failed: {error}"))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CryptoArgs {
    pub path: String,
    pub output_path: String,
    pub password: String,
}

#[tauri::command]
pub fn encrypt_checksum_file(args: CryptoArgs) -> Result<String, String> {
    let path = validate_existing_file(&args.path)?;
    let output_path = validate_writable_path(&args.output_path)?;
    if path == output_path {
        return Err("output path must differ from the checksum file".to_string());
    }
    fit_core::encrypt_file_with_password(&path, &args.password, &output_path)
        .map(|output| output.to_string_lossy().to_string())
        .map_err(|error| format!("checksum encryption failed: {error}"))
}

#[tauri::command]
pub fn decrypt_checksum_file(args: CryptoArgs) -> Result<String, String> {
    let path = validate_existing_file(&args.path)?;
    let output_path = validate_writable_path(&args.output_path)?;
    if path == output_path {
        return Err("output path must differ from the encrypted file".to_string());
    }
    fit_core::decrypt_file_with_password(&path, &args.password, &output_path)
        .map(|output| output.to_string_lossy().to_string())
        .map_err(|error| format!("checksum decryption failed: {error}"))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PackArgs {
    pub output_directory: String,
    pub record_path: String,
    pub verifier_path: String,
}

const BUILTIN_VERIFIER: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/verifier.exe"));
const BUILTIN_VERIFIER_MARKER: &str = "builtin-verifier";

#[tauri::command]
pub fn pack_native_verifier(args: PackArgs) -> Result<String, String> {
    let output = validate_writable_path(&args.output_directory)
        .map_err(|error| format!("output directory: {error}"))?;
    let record = validate_existing_file(&args.record_path)
        .map_err(|error| format!("recovery record: {error}"))?;
    std::fs::create_dir_all(&output)
        .map_err(|error| format!("unable to create output directory: {error}"))?;
    let verifier = if args.verifier_path.is_empty() || args.verifier_path == BUILTIN_VERIFIER_MARKER
    {
        find_verifier_binary(&output).or_else(|_| write_builtin_verifier(&output))?
    } else {
        let verifier = validate_existing_file(&args.verifier_path)?;
        if !is_verifier_binary(&verifier) {
            return Err("selected file is not a FIT verifier executable".to_string());
        }
        verifier
    };
    let public_key = PathBuf::from(format!("{}.pub", record.to_string_lossy()));
    if !public_key.is_file() {
        return Err(format!(
            "record public key not found: {}",
            public_key.display()
        ));
    }

    let verifier_name = verifier
        .file_name()
        .ok_or_else(|| "invalid verifier binary".to_string())?;
    let record_name = record
        .file_name()
        .ok_or_else(|| "invalid record file".to_string())?;
    let public_key_name = public_key
        .file_name()
        .ok_or_else(|| "invalid public key file".to_string())?;
    let recovery = PathBuf::from(format!("{}.parity", record.to_string_lossy()));
    let recovery_name = recovery
        .file_name()
        .ok_or_else(|| "invalid recovery archive".to_string())?;

    let final_verifier = copy_if_needed(&verifier, &output.join(verifier_name), "verifier")?;
    copy_if_needed(&record, &output.join(record_name), "record")?;
    copy_if_needed(&public_key, &output.join(public_key_name), "public key")?;
    if recovery.is_file() {
        copy_if_needed(&recovery, &output.join(recovery_name), "recovery archive")?;
    }
    Ok(final_verifier
        .parent()
        .unwrap_or(&output)
        .to_string_lossy()
        .to_string())
}

#[tauri::command]
pub fn locate_verifier() -> Result<Option<String>, String> {
    let current_exe = std::env::current_exe().ok();
    if let Ok(verifier) = find_verifier_binary_with(Path::new(""), current_exe.as_deref()) {
        return Ok(Some(verifier.to_string_lossy().to_string()));
    }
    Ok(has_builtin_verifier().then(|| BUILTIN_VERIFIER_MARKER.to_string()))
}

fn has_builtin_verifier() -> bool {
    !BUILTIN_VERIFIER.is_empty()
}

fn write_builtin_verifier(output: &Path) -> Result<PathBuf, String> {
    if !has_builtin_verifier() {
        return Err(
            "verifier binary not found and Builder was built without an embedded verifier"
                .to_string(),
        );
    }
    let destination = output.join("FileIntegrityVerifierRust.exe");
    std::fs::write(&destination, BUILTIN_VERIFIER)
        .map_err(|error| format!("unable to write embedded verifier: {error}"))?;
    Ok(destination)
}

fn copy_if_needed(source: &Path, destination: &Path, label: &str) -> Result<PathBuf, String> {
    if source == destination || files_equal(source, destination) {
        return Ok(destination.to_path_buf());
    }

    match std::fs::copy(source, destination) {
        Ok(_) => Ok(destination.to_path_buf()),
        Err(error) if error.raw_os_error() == Some(5) => {
            for index in 1..=9 {
                let fallback = sibling_numbered_path(destination, index);
                if fallback == source {
                    continue;
                }
                if fallback.is_file() {
                    if files_equal(source, &fallback) {
                        return Ok(fallback);
                    }
                    continue;
                }
                if std::fs::copy(source, &fallback).is_ok() {
                    return Ok(fallback);
                }
            }
            Err(format!(
                "unable to copy {label}: access denied. Close any program using {}, choose another output directory, or check folder permissions.",
                destination.display()
            ))
        }
        Err(error) => Err(format!("unable to copy {label}: {error}")),
    }
}

fn files_equal(source: &Path, destination: &Path) -> bool {
    if !destination.is_file() {
        return false;
    }
    let Ok(source_bytes) = std::fs::read(source) else {
        return false;
    };
    let Ok(destination_bytes) = std::fs::read(destination) else {
        return false;
    };
    source_bytes == destination_bytes
}

fn sibling_numbered_path(path: &Path, index: u32) -> PathBuf {
    let file_name = path
        .file_name()
        .map(|name| name.to_string_lossy().to_string())
        .unwrap_or_else(|| "file".to_string());
    let (stem, extension) = match file_name.rsplit_once('.') {
        Some((stem, extension)) if !stem.is_empty() => (stem, Some(extension)),
        _ => (file_name.as_str(), None),
    };
    let name = match extension {
        Some(extension) => format!("{stem} ({index}).{extension}"),
        None => format!("{stem} ({index})"),
    };
    path.with_file_name(name)
}

fn is_verifier_binary(path: &Path) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| {
            let name = name.to_ascii_lowercase();
            name == "fit-verifier.exe" || name == "fileintegrityverifierrust.exe"
        })
}

fn find_verifier_binary(output: &Path) -> Result<PathBuf, String> {
    let current_exe = std::env::current_exe().ok();
    find_verifier_binary_with(output, current_exe.as_deref())
}

fn find_verifier_binary_with(output: &Path, current_exe: Option<&Path>) -> Result<PathBuf, String> {
    let candidates = [
        output.join("fit-verifier.exe"),
        output.join("FileIntegrityVerifierRust.exe"),
    ];
    let mut candidates = candidates.into_iter().collect::<Vec<_>>();

    if let Some(exe) = current_exe
        && let Some(exe_dir) = exe.parent()
    {
        candidates.push(exe_dir.join("fit-verifier.exe"));
        candidates.push(exe_dir.join("FileIntegrityVerifierRust.exe"));
        candidates.push(exe_dir.join("../release/fit-verifier.exe"));
        candidates.push(exe_dir.join("../output/FileIntegrityVerifierRust.exe"));
    }

    if let Ok(current_dir) = std::env::current_dir() {
        candidates.push(current_dir.join("target/release/fit-verifier.exe"));
        candidates.push(current_dir.join("output/FileIntegrityVerifierRust.exe"));
    }

    candidates
        .into_iter()
        .find(|candidate| candidate.is_file())
        .ok_or_else(|| {
            "verifier binary not found. Run python build.py --rust or place FileIntegrityVerifierRust.exe next to Builder"
                .to_string()
        })
}

#[tauri::command]
pub fn generate_keypair_command(args: KeyPairArgs) -> Result<(), String> {
    let private_key = validate_writable_path(&args.private_key_path)?;
    let public_key = validate_writable_path(&args.public_key_path)?;
    if private_key == public_key {
        return Err("private and public key paths must differ".to_string());
    }
    generate_keypair(&private_key, &public_key)
        .map_err(|error| format!("key generation failed: {error}"))
}

#[tauri::command]
pub async fn generate_fitrec_command(
    app: tauri::AppHandle,
    args: FitRecArgs,
) -> Result<String, String> {
    let output = validate_writable_path(&args.output_path)?;
    let source_directory = validate_existing_directory(&args.source_directory)?;
    if args.document.algorithm != "sha256" {
        return Err("fitrec generation requires the sha256 algorithm".to_string());
    }
    let recovery_options = file_recovery_options(&args)?;
    let private_key = validate_existing_file(&args.private_key_path)?;
    if output == private_key {
        return Err("output and private key paths must differ".to_string());
    }
    let public_key = PathBuf::from(format!("{}.pub", output.to_string_lossy()));
    if public_key == private_key {
        return Err("public key and private key paths must differ".to_string());
    }
    args.document
        .validate()
        .map_err(|error| format!("invalid document: {error}"))?;
    let output_text = output.to_string_lossy().to_string();

    tauri::async_runtime::spawn_blocking(move || {
        let signing_key = load_signing_key(&private_key)
            .map_err(|error| format!("private key failed: {error}"))?;
        let recovery_path = PathBuf::from(format!("{}.parity", output.to_string_lossy()));
        let progress_app = app.clone();
        write_fitrec(
            &output,
            &args.document,
            &signing_key,
            fit_core::FitRecOptions {
                data_shards: args.data_shards,
                parity_shards: args.parity_shards,
            },
        )
        .map_err(|error| format!("record generation failed: {error}"))?;
        write_file_recovery_with_progress(
            &source_directory,
            &recovery_path,
            &args.document,
            &signing_key,
            FileRecoveryOptions {
                data_shards: recovery_options.data_shards,
                parity_shards: recovery_options.parity_shards,
                shard_size: recovery_options.shard_size,
                mode: recovery_options.mode,
            },
            None,
            Some(Arc::new(move |completed, total, path| {
                let _ = progress_app.emit(
                    "builder-file-recovery-progress",
                    json!({"completed": completed, "total": total, "path": path}),
                );
            })),
        )
        .map_err(|error| format!("file recovery generation failed: {error}"))?;
        write_public_key(&public_key, &signing_key)
            .map_err(|error| format!("public key generation failed: {error}"))?;
        Ok(output_text)
    })
    .await
    .map_err(|error| format!("record task failed: {error}"))?
}

#[tauri::command]
pub async fn verify_document(
    app: tauri::AppHandle,
    state: State<'_, BuilderState>,
    args: VerifyArgs,
) -> Result<Value, String> {
    let target = validate_existing_directory(&args.target_path)?;
    args.document
        .validate()
        .map_err(|error| format!("invalid document: {error}"))?;

    state.verify_cancel.store(false, Ordering::Relaxed);
    let cancel = state.verify_cancel.clone();
    let progress_app = app.clone();
    let options = VerificationOptions {
        exclude_paths: args
            .document
            .exclude_paths
            .iter()
            .map(PathBuf::from)
            .collect(),
        exclude_rules: FileRules::from_config(&args.document.exclude_rules),
        ignored_paths: args.document.exclude_paths.clone(),
        self_exe: std::env::current_exe().ok(),
        cancel: Some(cancel),
        progress: Some(Arc::new(move |progress| {
            let _ = progress_app.emit("builder-verify-progress", json!(progress));
        })),
    };
    let document = args.document;
    let report = tauri::async_runtime::spawn_blocking(move || {
        run_verification(&document, &target, &options)
    })
    .await
    .map_err(|error| format!("verification task failed: {error}"))?
    .map_err(|error| format!("verification failed: {error}"))?;
    serde_json::to_value(report).map_err(|error| format!("report serialization failed: {error}"))
}

#[tauri::command]
pub fn cancel_verification(state: State<'_, BuilderState>) {
    state.verify_cancel.store(true, Ordering::Relaxed);
}

#[tauri::command]
pub fn save_project(path: String, project: ProjectDocument) -> Result<(), String> {
    let path = validate_writable_path(&path)?;
    if project.version != 1 {
        return Err("unsupported project version".to_string());
    }
    project
        .entries
        .iter()
        .chain(project.checklists.values().flatten())
        .try_for_each(|entry| {
            fit_core::normalize_relative_path(&entry.path)
                .map(|_| ())
                .map_err(|error| format!("invalid project entry: {error}"))
        })?;
    let data = serde_json::to_vec_pretty(&project)
        .map_err(|error| format!("project serialization failed: {error}"))?;
    fs::write(&path, data).map_err(|error| format!("project save failed: {error}"))
}

#[tauri::command]
pub fn load_project(path: String) -> Result<ProjectDocument, String> {
    let path = validate_existing_file(&path)?;
    let data = fs::read(&path).map_err(|error| format!("project load failed: {error}"))?;
    let mut project: ProjectDocument =
        serde_json::from_slice(&data).map_err(|error| format!("invalid project file: {error}"))?;
    if project.version != 1 {
        return Err(format!("unsupported project version: {}", project.version));
    }
    if project.active_checklist.is_empty() {
        project.active_checklist = "default".to_string();
    }
    project.checklists.entry("default".to_string()).or_default();
    Ok(project)
}

#[tauri::command]
pub fn pick_directory(app: tauri::AppHandle) -> Option<String> {
    app.dialog()
        .file()
        .blocking_pick_folder()
        .map(|path| path.to_string())
}

#[tauri::command]
pub fn pick_file(app: tauri::AppHandle) -> Option<String> {
    app.dialog()
        .file()
        .blocking_pick_file()
        .map(|path| path.to_string())
}

#[tauri::command]
pub fn pick_files(app: tauri::AppHandle) -> Option<Vec<String>> {
    app.dialog()
        .file()
        .blocking_pick_files()
        .map(|paths| paths.iter().map(|path| path.to_string()).collect())
}

#[tauri::command]
pub fn pick_save_file(
    app: tauri::AppHandle,
    name: String,
    extensions: Vec<String>,
) -> Option<String> {
    let mut dialog = app.dialog().file().set_file_name(&name);
    let extension_refs: Vec<&str> = extensions.iter().map(String::as_str).collect();
    dialog = dialog.add_filter("FIT file", &extension_refs);
    dialog.blocking_save_file().map(|path| path.to_string())
}

pub fn validate_path_string(value: &str) -> Result<PathBuf, String> {
    let value = normalize_path_input(value);
    if value.is_empty() {
        return Err("path must not be empty".to_string());
    }
    if value.len() > MAX_PATH_LENGTH {
        return Err("path is too long".to_string());
    }
    if value.chars().any(char::is_control) {
        return Err("path contains control characters".to_string());
    }
    let path = PathBuf::from(value.into_owned());
    if path
        .components()
        .any(|component| component == Component::ParentDir)
    {
        return Err("path must not contain parent traversal".to_string());
    }

    if path.is_absolute() {
        Ok(path)
    } else if path.has_root() || matches!(path.components().next(), Some(Component::Prefix(_))) {
        Err("path must be absolute".to_string())
    } else {
        let current_dir = std::env::current_dir()
            .map_err(|error| format!("unable to resolve current directory: {error}"))?;
        Ok(current_dir.join(path))
    }
}

fn normalize_path_input(value: &str) -> std::borrow::Cow<'_, str> {
    let trimmed = value.trim();
    let unquoted = if trimmed.len() >= 2
        && (trimmed.starts_with('"') && trimmed.ends_with('"')
            || trimmed.starts_with('“') && trimmed.ends_with('”'))
    {
        let mut chars = trimmed.chars();
        chars.next();
        chars.next_back();
        chars.as_str()
    } else {
        trimmed
    };

    let mut chars = unquoted.chars();
    if let (Some(first), Some(second)) = (chars.next(), chars.next())
        && first.is_ascii_alphabetic()
        && second == '：'
    {
        return std::borrow::Cow::Owned(format!("{first}:{}", chars.as_str()));
    }

    std::borrow::Cow::Borrowed(unquoted)
}

pub fn validate_existing_directory(value: &str) -> Result<PathBuf, String> {
    let path = validate_path_string(value)?;
    if !path.is_dir() {
        return Err(format!("directory does not exist: {}", path.display()));
    }
    Ok(path)
}

pub fn validate_existing_file(value: &str) -> Result<PathBuf, String> {
    let path = validate_path_string(value)?;
    if !path.is_file() {
        return Err(format!("file does not exist: {}", path.display()));
    }
    Ok(path)
}

pub fn validate_writable_path(value: &str) -> Result<PathBuf, String> {
    let path = validate_path_string(value)?;
    if let Some(parent) = path.parent()
        && !parent.exists()
    {
        return Err(format!(
            "parent directory does not exist: {}",
            parent.display()
        ));
    }
    Ok(path)
}

#[allow(dead_code)]
pub fn ensure_within_base(path: &Path, base: &Path) -> Result<(), String> {
    let path = path
        .canonicalize()
        .map_err(|error| format!("unable to resolve path {}: {error}", path.display()))?;
    let base = base
        .canonicalize()
        .map_err(|error| format!("unable to resolve base {}: {error}", base.display()))?;
    if !path.starts_with(&base) {
        return Err(format!(
            "path is outside the selected base directory: {}",
            path.display()
        ));
    }
    Ok(())
}
