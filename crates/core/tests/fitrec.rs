use ed25519_dalek::{SigningKey, VerifyingKey};
use fit_core::{
    CoreError, FitDocument, FitRecOptions, ManifestEntry, canonical_python_json, decode_fitrec,
    encode_fitrec, generate_signing_key, load_fitrec, normalize_relative_path, write_fitrec,
};
use fit_core::{decode_fitrec_repaired, repair_fitrec};
use std::collections::BTreeMap;

fn entry(path: &str, hash: &str) -> ManifestEntry {
    ManifestEntry {
        path: path.to_string(),
        hash: hash.to_string(),
        size: Some(12),
        status: Some("ok".to_string()),
        extra: BTreeMap::new(),
    }
}

fn document() -> FitDocument {
    let mut checklists = BTreeMap::new();
    checklists.insert("default".to_string(), vec![entry("a.bin", "hash-a")]);
    checklists.insert(
        "release".to_string(),
        vec![entry("app.dll", "hash-a"), entry("data.bin", "hash-b")],
    );
    FitDocument {
        format_version: 1,
        algorithm: "sha256".to_string(),
        active_checklist: "release".to_string(),
        checklists,
        exclude_paths: vec!["logs".to_string()],
        exclude_rules: serde_json::Map::new(),
        metadata: serde_json::Map::new(),
    }
}

fn encode_default(document: &FitDocument, key: &SigningKey) -> Vec<u8> {
    encode_fitrec(document, key, FitRecOptions::default()).unwrap()
}

fn body_start(record: &[u8]) -> usize {
    12 + u32::from_le_bytes(record[8..12].try_into().unwrap()) as usize
}

#[test]
fn manifest_hash_matches_python_style_canonical_json() {
    let document = document();
    let hash = document.active_manifest_hash().unwrap();
    let expected = sha256(
        "[{\"hash\": \"hash-a\", \"path\": \"app.dll\", \"size\": 12, \"status\": \"ok\"}, {\"hash\": \"hash-b\", \"path\": \"data.bin\", \"size\": 12, \"status\": \"ok\"}]",
    );
    assert_eq!(hash, expected);
}

#[test]
fn canonical_json_preserves_unicode_and_python_separators() {
    let mut object = BTreeMap::new();
    object.insert("path".to_string(), serde_json::json!("示例/文件.txt"));
    object.insert("size".to_string(), serde_json::json!(12));
    let value = serde_json::Value::Object(object.into_iter().collect());
    assert_eq!(
        canonical_python_json(&value),
        "{\"path\": \"示例/文件.txt\", \"size\": 12}"
    );
}

#[test]
fn roundtrip_and_file_helpers_succeed() {
    let document = document();
    let signing_key = generate_signing_key().unwrap();
    let verifying_key = VerifyingKey::from(&signing_key);
    let record = encode_default(&document, &signing_key);

    let decoded = decode_fitrec(&record, &verifying_key).unwrap();
    assert_eq!(decoded.active_checklist, "release");
    assert_eq!(
        decoded.active_manifest_hash().unwrap(),
        document.active_manifest_hash().unwrap()
    );

    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("release.fitrec");
    write_fitrec(&path, &document, &signing_key, FitRecOptions::default()).unwrap();
    assert_eq!(load_fitrec(&path, &verifying_key).unwrap(), decoded);
}

#[test]
fn unknown_position_damaged_shards_recover_up_to_parity_capacity() {
    let document = document();
    let signing_key = generate_signing_key().unwrap();
    let verifying_key = VerifyingKey::from(&signing_key);
    let record = encode_default(&document, &signing_key);
    let total_shards = 12;
    let parity_shards = 4;

    for damaged_index in 0..parity_shards {
        let mut damaged = record.clone();
        let body_end = damaged.len() - 64;
        let body_start = body_start(&damaged);
        let shard_size = (body_end - body_start) / total_shards;
        let index = body_start + damaged_index * shard_size;
        damaged[index] ^= 0x5a;
        let decoded = decode_fitrec(&damaged, &verifying_key).unwrap();
        assert_eq!(
            decoded.active_manifest_hash().unwrap(),
            document.active_manifest_hash().unwrap()
        );
    }
}

#[test]
fn over_capacity_damage_fails_explicitly() {
    let document = document();
    let signing_key = generate_signing_key().unwrap();
    let verifying_key = VerifyingKey::from(&signing_key);
    let record = encode_default(&document, &signing_key);
    let mut damaged = record;
    let body_end = damaged.len() - 64;
    let body_start = body_start(&damaged);
    let shard_size = (body_end - body_start) / 12;
    for damaged_index in 0..5 {
        let index = body_start + damaged_index * shard_size;
        damaged[index] ^= 0xa5;
    }

    match decode_fitrec(&damaged, &verifying_key) {
        Err(CoreError::InsufficientShards { damaged, capacity }) => {
            assert_eq!((damaged, capacity), (5, 4));
        }
        other => panic!("expected explicit recovery failure, got {other:?}"),
    }
}

#[test]
fn damaged_shards_recover_to_a_repaired_copy() {
    let document = document();
    let signing_key = generate_signing_key().unwrap();
    let verifying_key = VerifyingKey::from(&signing_key);
    let original = encode_default(&document, &signing_key);
    let total_shards = 12;

    let mut damaged = original.clone();
    let body_end = damaged.len() - 64;
    let body_start = body_start(&damaged);
    let shard_size = (body_end - body_start) / total_shards;
    damaged[body_start + 3 * shard_size] ^= 0x5a;

    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("damaged.fitrec");
    let output = directory.path().join("repaired.fitrec");
    std::fs::write(&source, &damaged).unwrap();

    let repair = repair_fitrec(&source, &verifying_key, &output).unwrap();
    assert_eq!(repair.damaged_shards, 1);
    assert_eq!(
        decode_fitrec_repaired(&repair.repaired_record, &verifying_key)
            .unwrap()
            .document,
        document
    );
    assert_eq!(load_fitrec(&output, &verifying_key).unwrap(), document);
    assert_ne!(std::fs::read(&output).unwrap(), damaged);
    assert_eq!(std::fs::read(&source).unwrap(), damaged);
}

#[test]
fn healthy_record_repair_does_not_create_a_copy() {
    let document = document();
    let signing_key = generate_signing_key().unwrap();
    let verifying_key = VerifyingKey::from(&signing_key);
    let original = encode_default(&document, &signing_key);

    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("healthy.fitrec");
    let output = directory.path().join("unused.fitrec");
    std::fs::write(&source, &original).unwrap();

    let repair = repair_fitrec(&source, &verifying_key, &output).unwrap();
    assert_eq!(repair.damaged_shards, 0);
    assert_eq!(repair.repaired_record, original);
    assert!(!output.exists());
}

#[test]
fn wrong_public_key_is_rejected() {
    let document = document();
    let signing_key = generate_signing_key().unwrap();
    let record = encode_default(&document, &signing_key);
    let other_key = generate_signing_key().unwrap();
    let other_verifying_key = VerifyingKey::from(&other_key);

    assert!(matches!(
        decode_fitrec(&record, &other_verifying_key),
        Err(CoreError::Signature)
    ));
}

#[test]
fn malformed_records_fail_safely() {
    let document = document();
    let signing_key = generate_signing_key().unwrap();
    let verifying_key = VerifyingKey::from(&signing_key);
    let record = encode_default(&document, &signing_key);

    let mut bad_magic = record.clone();
    bad_magic[0] = b'X';
    assert!(decode_fitrec(&bad_magic, &verifying_key).is_err());

    let mut truncated = record.clone();
    truncated.truncate(record.len() - 20);
    assert!(decode_fitrec(&truncated, &verifying_key).is_err());

    let mut replaced = record.clone();
    let body_end = replaced.len() - 64;
    replaced[12] ^= 1;
    replaced[body_end - 1] ^= 1;
    assert!(decode_fitrec(&replaced, &verifying_key).is_err());
}

#[test]
fn paths_are_rejected_for_traversal_and_duplicates_are_detected() {
    assert!(matches!(
        normalize_relative_path("a\\b/../c.txt"),
        Err(CoreError::Manifest("path contains parent traversal"))
    ));

    let mut checklists = BTreeMap::new();
    checklists.insert(
        "default".to_string(),
        vec![entry("same.txt", "hash"), entry("same.txt", "hash")],
    );
    let document = FitDocument {
        format_version: 1,
        algorithm: "sha256".to_string(),
        active_checklist: "default".to_string(),
        checklists,
        exclude_paths: Vec::new(),
        exclude_rules: serde_json::Map::new(),
        metadata: serde_json::Map::new(),
    };
    assert!(document.validate().is_err());
}

fn sha256(data: &str) -> String {
    use sha2::{Digest, Sha256};
    let digest = Sha256::digest(data.as_bytes());
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}
