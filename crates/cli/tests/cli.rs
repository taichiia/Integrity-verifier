use std::fs;
use std::path::PathBuf;
use std::process::{Command, Output};

use fit_core::{HashAlgorithm, VerifyingKey, hash_file, load_fitrec};
use serde_json::json;

fn binary() -> PathBuf {
    env!("CARGO_BIN_EXE_fit-rec").into()
}

fn run(args: &[&str]) -> Output {
    Command::new(binary())
        .args(args)
        .output()
        .expect("fit-rec should launch")
}

fn assert_success(output: &Output, label: &str) {
    assert!(
        output.status.success(),
        "{label} failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn keygen_and_generation_create_verifiable_record() {
    let directory = tempfile::tempdir().unwrap();
    let private_key = directory.path().join("fitrec.key");
    let source_public_key = directory.path().join("fitrec.pub");
    let input = directory.path().join("document.json");
    let record = directory.path().join("release.fitrec");
    let public_key = directory.path().join("release.fitrec.pub");

    assert_success(
        &run(&[
            "keygen",
            "--private",
            private_key.to_str().unwrap(),
            "--public",
            source_public_key.to_str().unwrap(),
        ]),
        "keygen",
    );

    fs::write(
        &input,
        json!({
            "format_version": 1,
            "algorithm": "sha256",
            "active_checklist": "release",
            "checklists": {
                "release": [
                    {"path": "app.dll", "hash": "hash-a", "size": 12, "status": "ok"}
                ]
            },
            "exclude_paths": ["logs"]
        })
        .to_string(),
    )
    .unwrap();

    assert_success(
        &run(&[
            "generate",
            "--input",
            input.to_str().unwrap(),
            "--output",
            record.to_str().unwrap(),
            "--private-key",
            private_key.to_str().unwrap(),
            "--public-key",
            public_key.to_str().unwrap(),
            "--data-shards",
            "8",
            "--parity-shards",
            "4",
        ]),
        "generate",
    );

    let public_hex = fs::read_to_string(&public_key).unwrap();
    let public_bytes: [u8; 32] = hex::decode(public_hex.trim()).unwrap().try_into().unwrap();
    let verifying_key = VerifyingKey::from_bytes(&public_bytes).unwrap();
    let document = load_fitrec(&record, &verifying_key).unwrap();
    assert_eq!(document.active_checklist, "release");
    assert_eq!(document.exclude_paths, vec!["logs".to_string()]);
}

#[test]
fn invalid_document_is_rejected() {
    let directory = tempfile::tempdir().unwrap();
    let private_key = directory.path().join("key");
    fs::write(&private_key, [7_u8; 32]).unwrap();
    let input = directory.path().join("bad.json");
    let record = directory.path().join("bad.fitrec");
    let public_key = directory.path().join("bad.pub");
    fs::write(
        &input,
        json!({
            "format_version": 1,
            "algorithm": "sha256",
            "active_checklist": "missing",
            "checklists": {}
        })
        .to_string(),
    )
    .unwrap();

    let output = run(&[
        "generate",
        "--input",
        input.to_str().unwrap(),
        "--output",
        record.to_str().unwrap(),
        "--private-key",
        private_key.to_str().unwrap(),
        "--public-key",
        public_key.to_str().unwrap(),
    ]);
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("active checklist"));
    assert!(!record.exists());
}

#[test]
fn generation_with_source_directory_creates_file_recovery() {
    let directory = tempfile::tempdir().unwrap();
    let private_key = directory.path().join("fitrec.key");
    let public_key = directory.path().join("release.fitrec.pub");
    let input = directory.path().join("document.json");
    let record = directory.path().join("release.fitrec");
    let parity = directory.path().join("release.fitrec.parity");
    let source = directory.path().join("source");
    fs::create_dir_all(&source).unwrap();
    fs::write(source.join("app.dll"), b"recovered payload").unwrap();

    assert_success(
        &run(&[
            "keygen",
            "--private",
            private_key.to_str().unwrap(),
            "--public",
            directory.path().join("key.pub").to_str().unwrap(),
        ]),
        "keygen",
    );

    let hash = hash_file(&source.join("app.dll"), HashAlgorithm::Sha256).unwrap();
    fs::write(
        &input,
        json!({
            "format_version": 1,
            "algorithm": "sha256",
            "active_checklist": "release",
            "checklists": {
                "release": [
                    {"path": "app.dll", "hash": hash, "size": 17, "status": "ok"}
                ]
            }
        })
        .to_string(),
    )
    .unwrap();

    assert_success(
        &run(&[
            "generate",
            "--input",
            input.to_str().unwrap(),
            "--output",
            record.to_str().unwrap(),
            "--private-key",
            private_key.to_str().unwrap(),
            "--public-key",
            public_key.to_str().unwrap(),
            "--source-directory",
            source.to_str().unwrap(),
            "--data-shards",
            "2",
            "--parity-shards",
            "2",
        ]),
        "generate parity",
    );

    assert!(record.is_file());
    assert!(parity.is_file());
    assert!(parity.metadata().unwrap().len() > 0);

    let public_hex = fs::read_to_string(&public_key).unwrap();
    let public_bytes: [u8; 32] = hex::decode(public_hex.trim()).unwrap().try_into().unwrap();
    let verifying_key = VerifyingKey::from_bytes(&public_bytes).unwrap();
    let info = fit_core::load_file_recovery(&parity, &verifying_key).unwrap();
    assert_eq!(info.file_count, 1);
    assert_eq!(info.total_size, 17);
}

#[test]
fn key_overwrite_is_rejected() {
    let directory = tempfile::tempdir().unwrap();
    let private_key = directory.path().join("key");
    let public_key = directory.path().join("pub");
    fs::write(&public_key, "existing").unwrap();

    let output = run(&[
        "keygen",
        "--private",
        private_key.to_str().unwrap(),
        "--public",
        public_key.to_str().unwrap(),
    ]);
    assert!(!output.status.success());
    assert!(!private_key.exists());
}
