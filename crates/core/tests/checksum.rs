use fit_core::{ChecksumEntry, read_checksum_file, sign_file, verify_file, write_csv, write_sfv};
use std::fs;

fn entries() -> Vec<ChecksumEntry> {
    vec![
        ChecksumEntry {
            path: "plain.txt".to_string(),
            hash: "hash-one".to_string(),
        },
        ChecksumEntry {
            path: "comma,path.txt".to_string(),
            hash: "hash,two".to_string(),
        },
        ChecksumEntry {
            path: "nested/path.txt".to_string(),
            hash: "hash-three".to_string(),
        },
    ]
}

#[test]
fn csv_roundtrip_preserves_quoted_paths() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("checksums.csv");
    write_csv(&path, "sha256", &entries()).unwrap();

    let loaded = read_checksum_file(&path, "md5").unwrap();
    assert_eq!(loaded.algorithm, "sha256");
    assert_eq!(loaded.entries, entries());
}

#[test]
fn sfv_roundtrip_preserves_relative_paths() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("checksums.sfv");
    write_sfv(&path, &entries()).unwrap();

    let loaded = read_checksum_file(&path, "sha256").unwrap();
    assert_eq!(loaded.algorithm, "sha256");
    assert_eq!(loaded.entries, entries());
}

#[test]
fn checksum_file_signs_and_verifies() {
    let directory = tempfile::tempdir().unwrap();
    let checksum_path = directory.path().join("checksums.csv");
    let private_key = directory.path().join("checksum.key");
    let public_key = directory.path().join("checksum.key.pub");
    write_csv(&checksum_path, "sha256", &entries()).unwrap();

    fit_core::generate_keypair(&private_key, &public_key).unwrap();
    let signature_path = sign_file(&checksum_path, &private_key).unwrap();
    assert_eq!(signature_path, directory.path().join("checksums.csv.sig"));
    verify_file(&checksum_path, &public_key).unwrap();

    let tampered = fs::read_to_string(&checksum_path).unwrap() + "\nextra.txt,hash\n";
    fs::write(&checksum_path, tampered).unwrap();
    assert!(verify_file(&checksum_path, &public_key).is_err());
}
