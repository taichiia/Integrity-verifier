use std::fs;
use std::io::{Seek, Write};

use fit_core::{
    FileRecoveryOptions, FitDocument, ManifestEntry, VerifyingKey, generate_signing_key, hash_file,
    load_file_recovery, recover_files, write_file_recovery, write_public_key,
};

fn document_for(directory: &std::path::Path, files: &[&str]) -> FitDocument {
    let entries = files
        .iter()
        .map(|name| ManifestEntry {
            path: (*name).to_string(),
            hash: hash_file(&directory.join(name), fit_core::HashAlgorithm::Sha256).unwrap(),
            size: Some(fs::metadata(directory.join(name)).unwrap().len()),
            status: None,
            extra: Default::default(),
        })
        .collect();
    FitDocument {
        format_version: 1,
        algorithm: "sha256".to_string(),
        active_checklist: "default".to_string(),
        checklists: [("default".to_string(), entries)].into_iter().collect(),
        exclude_paths: Vec::new(),
        exclude_rules: Default::default(),
        metadata: Default::default(),
    }
}

fn write_test_file(path: &std::path::Path, length: usize) {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).unwrap();
    }
    let data = (0..length)
        .map(|index| (index % 251) as u8)
        .collect::<Vec<_>>();
    fs::write(path, data).unwrap();
}

#[test]
fn file_parity_repairs_unknown_position_damage_to_a_copy() {
    let directory = tempfile::tempdir().unwrap();
    let target = tempfile::tempdir().unwrap();
    let output = tempfile::tempdir().unwrap();
    let source = directory.path().join("nested/alpha.bin");
    write_test_file(&source, 1024 * 1024 + 12345);
    let document = document_for(directory.path(), &["nested/alpha.bin"]);
    let signing_key = generate_signing_key().unwrap();
    let public_key = directory.path().join("recovery.pub");
    write_public_key(&public_key, &signing_key).unwrap();

    let archive = directory.path().join("recovery.fitpar");
    write_file_recovery(
        directory.path(),
        &archive,
        &document,
        &signing_key,
        FileRecoveryOptions {
            data_shards: 2,
            parity_shards: 2,
            shard_size: 64 * 1024,
            mode: fit_core::FileRecoveryMode::SingleFile,
        },
    )
    .unwrap();

    let original = VerifyingKey::from_bytes(
        &hex::decode(fs::read_to_string(&public_key).unwrap().trim())
            .unwrap()
            .try_into()
            .unwrap(),
    )
    .unwrap();

    let info = load_file_recovery(&archive, &original).unwrap();
    assert_eq!(info.file_count, 1);
    assert_eq!(info.data_shards, 2);
    assert_eq!(info.parity_shards, 2);
    assert_eq!(info.total_size, fs::metadata(&source).unwrap().len());

    let damaged = target.path().join("nested/alpha.bin");
    fs::create_dir_all(damaged.parent().unwrap()).unwrap();
    fs::copy(&source, &damaged).unwrap();
    let mut file = fs::OpenOptions::new().write(true).open(&damaged).unwrap();
    file.seek(std::io::SeekFrom::Start(777)).unwrap();
    file.write_all(&[0xa5]).unwrap();
    drop(file);

    let report = recover_files(&archive, &original, target.path(), output.path()).unwrap();
    eprintln!("repair report: {:?}", report);
    assert_eq!(report.total, 1);
    assert_eq!(report.repaired, 1);
    assert_eq!(report.failed, 0);
    assert_eq!(
        fs::read(output.path().join("nested/alpha.bin")).unwrap(),
        fs::read(&source).unwrap()
    );
}

#[test]
fn file_parity_reports_capacity_failure_without_writing_bad_data() {
    let directory = tempfile::tempdir().unwrap();
    let target = tempfile::tempdir().unwrap();
    let output = tempfile::tempdir().unwrap();
    let source = directory.path().join("alpha.bin");
    write_test_file(&source, 129 * 1024);
    let document = document_for(directory.path(), &["alpha.bin"]);
    let signing_key = generate_signing_key().unwrap();
    let public_key = directory.path().join("recovery.pub");
    write_public_key(&public_key, &signing_key).unwrap();

    let archive = directory.path().join("recovery.fitpar");
    write_file_recovery(
        directory.path(),
        &archive,
        &document,
        &signing_key,
        FileRecoveryOptions {
            data_shards: 2,
            parity_shards: 1,
            shard_size: 64 * 1024,
            mode: fit_core::FileRecoveryMode::SingleFile,
        },
    )
    .unwrap();

    let damaged = target.path().join("alpha.bin");
    fs::copy(&source, &damaged).unwrap();
    let mut file = fs::OpenOptions::new().write(true).open(&damaged).unwrap();
    for offset in [0_u64, 64 * 1024] {
        file.seek(std::io::SeekFrom::Start(offset)).unwrap();
        file.write_all(&[0x5a]).unwrap();
    }
    drop(file);

    let verifying_key = VerifyingKey::from_bytes(
        &hex::decode(fs::read_to_string(&public_key).unwrap().trim())
            .unwrap()
            .try_into()
            .unwrap(),
    )
    .unwrap();
    let report = recover_files(&archive, &verifying_key, target.path(), output.path()).unwrap();
    assert_eq!(report.failed, 1);
    assert!(report.details[0].message.contains("damaged shards"));
    assert!(!output.path().join("alpha.bin").exists());
}

#[test]
fn file_parity_reports_whole_file_missing_without_default_capacity() {
    let directory = tempfile::tempdir().unwrap();
    let target = tempfile::tempdir().unwrap();
    let output = tempfile::tempdir().unwrap();
    let source = directory.path().join("alpha.bin");
    write_test_file(&source, 128 * 1024);
    let document = document_for(directory.path(), &["alpha.bin"]);
    let signing_key = generate_signing_key().unwrap();
    let public_key = directory.path().join("recovery.pub");
    write_public_key(&public_key, &signing_key).unwrap();
    let archive = directory.path().join("recovery.fitpar");

    write_file_recovery(
        directory.path(),
        &archive,
        &document,
        &signing_key,
        FileRecoveryOptions {
            data_shards: 2,
            parity_shards: 1,
            shard_size: 64 * 1024,
            mode: fit_core::FileRecoveryMode::SingleFile,
        },
    )
    .unwrap();

    let verifying_key = VerifyingKey::from_bytes(
        &hex::decode(fs::read_to_string(&public_key).unwrap().trim())
            .unwrap()
            .try_into()
            .unwrap(),
    )
    .unwrap();
    let report = recover_files(&archive, &verifying_key, target.path(), output.path()).unwrap();
    assert_eq!(report.missing, 1);
    assert_eq!(report.failed, 0);
    assert!(!output.path().join("alpha.bin").exists());
}

#[test]
fn cross_file_parity_rebuilds_whole_missing_file() {
    let directory = tempfile::tempdir().unwrap();
    let target = tempfile::tempdir().unwrap();
    let output = tempfile::tempdir().unwrap();
    let alpha = directory.path().join("alpha.bin");
    let beta = directory.path().join("beta.bin");
    write_test_file(&alpha, 100 * 1024);
    write_test_file(&beta, 128 * 1024);
    let document = document_for(directory.path(), &["alpha.bin", "beta.bin"]);
    let signing_key = generate_signing_key().unwrap();
    let public_key = directory.path().join("recovery.pub");
    write_public_key(&public_key, &signing_key).unwrap();
    let archive = directory.path().join("recovery.fitpar");

    write_file_recovery(
        directory.path(),
        &archive,
        &document,
        &signing_key,
        FileRecoveryOptions {
            data_shards: 2,
            parity_shards: 1,
            shard_size: 64 * 1024,
            mode: fit_core::FileRecoveryMode::CrossFile,
        },
    )
    .unwrap();

    let verifying_key = VerifyingKey::from_bytes(
        &hex::decode(fs::read_to_string(&public_key).unwrap().trim())
            .unwrap()
            .try_into()
            .unwrap(),
    )
    .unwrap();
    fs::create_dir_all(target.path().join("")).unwrap();
    fs::copy(&beta, target.path().join("beta.bin")).unwrap();

    let info = load_file_recovery(&archive, &verifying_key).unwrap();
    assert!(matches!(info.mode, fit_core::FileRecoveryMode::CrossFile));
    let report = recover_files(&archive, &verifying_key, target.path(), output.path()).unwrap();
    assert_eq!(report.repaired, 1);
    assert_eq!(report.healthy, 1);
    assert_eq!(report.failed, 0);
    assert_eq!(
        fs::read(output.path().join("alpha.bin")).unwrap(),
        fs::read(&alpha).unwrap()
    );
}

#[test]
fn cross_file_parity_rebuilds_missing_and_truncated_lanes() {
    let directory = tempfile::tempdir().unwrap();
    let target = tempfile::tempdir().unwrap();
    let output = tempfile::tempdir().unwrap();
    let alpha = directory.path().join("alpha.bin");
    let beta = directory.path().join("beta.bin");
    write_test_file(&alpha, 100 * 1024);
    write_test_file(&beta, 128 * 1024);
    let document = document_for(directory.path(), &["alpha.bin", "beta.bin"]);
    let signing_key = generate_signing_key().unwrap();
    let public_key = directory.path().join("recovery.pub");
    write_public_key(&public_key, &signing_key).unwrap();
    let archive = directory.path().join("recovery.fitpar");

    write_file_recovery(
        directory.path(),
        &archive,
        &document,
        &signing_key,
        FileRecoveryOptions {
            data_shards: 2,
            parity_shards: 2,
            shard_size: 64 * 1024,
            mode: fit_core::FileRecoveryMode::CrossFile,
        },
    )
    .unwrap();

    let verifying_key = VerifyingKey::from_bytes(
        &hex::decode(fs::read_to_string(&public_key).unwrap().trim())
            .unwrap()
            .try_into()
            .unwrap(),
    )
    .unwrap();
    fs::write(target.path().join("beta.bin"), b"short").unwrap();

    let report = recover_files(&archive, &verifying_key, target.path(), output.path()).unwrap();
    assert_eq!(report.repaired, 2);
    assert_eq!(report.failed, 0);
    assert_eq!(
        fs::read(output.path().join("alpha.bin")).unwrap(),
        fs::read(&alpha).unwrap()
    );
    assert_eq!(
        fs::read(output.path().join("beta.bin")).unwrap(),
        fs::read(&beta).unwrap()
    );
}
