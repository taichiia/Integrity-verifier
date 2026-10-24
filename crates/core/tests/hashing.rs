use std::fs;
use std::path::PathBuf;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicUsize};

use fit_core::{
    HashAlgorithm, HashOptions, PreHashOptions, ScanOptions, ScannedFile, hash_file, run_hashing,
    scan_and_prehash, scan_directory,
};
use sha2::{Digest, Sha256};

fn sample_files(root: &std::path::Path) -> Vec<PathBuf> {
    let first = root.join("a.txt");
    let nested = root.join("nested");
    let second = nested.join("b.txt");
    fs::create_dir_all(&nested).unwrap();
    fs::write(&first, b"alpha").unwrap();
    fs::write(&second, b"beta").unwrap();
    vec![first, second]
}

#[test]
fn scan_collects_all_files_without_applying_rules() {
    let directory = tempfile::tempdir().unwrap();
    sample_files(directory.path());
    let report = scan_directory(directory.path(), &ScanOptions::default()).unwrap();

    assert_eq!(report.files.len(), 2);
    assert!(!report.cancelled);
    assert!(report.errors.is_empty());
    let paths: Vec<_> = report.files.iter().map(|file| file.path.as_str()).collect();
    assert!(paths.contains(&"a.txt"));
    assert!(paths.contains(&"nested/b.txt"));
    assert!(report.files.iter().all(|file: &ScannedFile| file.size > 0));
}

#[test]
fn missing_scan_root_is_rejected() {
    let directory = tempfile::tempdir().unwrap();
    let missing = directory.path().join("missing");
    assert!(scan_directory(&missing, &ScanOptions::default()).is_err());
}

#[test]
fn scan_and_prehash_returns_reusable_entries() {
    let directory = tempfile::tempdir().unwrap();
    let paths = sample_files(directory.path());
    let options = PreHashOptions {
        algorithm: HashAlgorithm::Sha256,
        ..Default::default()
    };
    let report = scan_and_prehash(directory.path(), &ScanOptions::default(), &options).unwrap();

    assert_eq!(report.files.len(), 2);
    assert_eq!(report.prehashes.len(), 2);
    for file in &report.files {
        let entry = report
            .prehashes
            .iter()
            .find(|entry| entry.path == file.path)
            .unwrap();
        assert_eq!(entry.size, file.size);
        assert_eq!(entry.modified, file.modified);
        assert_eq!(
            entry.hash,
            hash_file(&directory.path().join(&file.path), HashAlgorithm::Sha256,).unwrap()
        );
    }
    assert!(paths.iter().all(|path| path.is_file()));
}

#[test]
fn hash_algorithms_and_parallel_results_are_stable() {
    let directory = tempfile::tempdir().unwrap();
    let paths = sample_files(directory.path());
    let expected_sha256 = {
        let mut hasher = Sha256::new();
        hasher.update(b"alpha");
        hasher
            .finalize()
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>()
    };

    assert_eq!(
        hash_file(&paths[0], HashAlgorithm::Sha256).unwrap(),
        expected_sha256
    );
    assert_eq!(
        hash_file(&paths[0], HashAlgorithm::Sha512).unwrap().len(),
        128
    );
    assert_eq!(hash_file(&paths[0], HashAlgorithm::Md5).unwrap().len(), 32);

    let results = run_hashing(&paths, HashAlgorithm::Sha256, &HashOptions::default());
    assert_eq!(results.len(), paths.len());
    assert!(results.iter().all(|result| result.error.is_empty()));
    assert_eq!(results[0].hash, expected_sha256);
}

#[test]
fn hash_progress_and_cancel_are_reported() {
    let directory = tempfile::tempdir().unwrap();
    let paths = sample_files(directory.path());
    let progress = Arc::new(AtomicUsize::new(0));
    let observer = progress.clone();
    let options = HashOptions {
        progress: Some(Arc::new(move |completed, total, path| {
            observer.store(completed, std::sync::atomic::Ordering::Relaxed);
            assert!(completed <= total);
            assert!(!path.is_empty());
        })),
        ..Default::default()
    };
    run_hashing(&paths, HashAlgorithm::Sha256, &options);
    assert_eq!(
        progress.load(std::sync::atomic::Ordering::Relaxed),
        paths.len()
    );

    let cancelled = Arc::new(AtomicBool::new(true));
    let options = HashOptions {
        cancel: Some(cancelled),
        ..Default::default()
    };
    let results = run_hashing(&paths, HashAlgorithm::Sha256, &options);
    assert!(results.iter().all(|result| result.error == "cancelled"));
}
