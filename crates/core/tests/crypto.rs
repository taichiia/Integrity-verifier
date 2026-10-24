use std::fs;

const PASSWORD: &str = "correct horse battery staple";

#[test]
fn password_encryption_roundtrip() {
    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("checksums.csv");
    let encrypted = directory.path().join("checksums.csv.enc");
    let decrypted = directory.path().join("checksums.decoded.csv");
    let plaintext = b"path,hash\nnested/file.txt,abc\n";

    fs::write(&source, plaintext).unwrap();
    fit_core::encrypt_file_with_password(&source, PASSWORD, &encrypted).unwrap();

    let payload = fs::read(&encrypted).unwrap();
    assert_ne!(payload, plaintext);
    assert!(payload.len() > plaintext.len());

    fit_core::decrypt_file_with_password(&encrypted, PASSWORD, &decrypted).unwrap();
    assert_eq!(fs::read(&decrypted).unwrap(), plaintext);
}

#[test]
fn encrypted_files_use_unique_salt_and_nonce() {
    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("checksums.csv");
    let first = directory.path().join("first.enc");
    let second = directory.path().join("second.enc");
    fs::write(&source, b"path,hash\nfile.txt,abc\n").unwrap();

    fit_core::encrypt_file_with_password(&source, PASSWORD, &first).unwrap();
    fit_core::encrypt_file_with_password(&source, PASSWORD, &second).unwrap();

    let first = fs::read(&first).unwrap();
    let second = fs::read(&second).unwrap();
    assert_ne!(first[..16], second[..16]);
    assert_ne!(first[16..28], second[16..28]);
}

#[test]
fn empty_and_wrong_passwords_are_rejected() {
    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("checksums.csv");
    let encrypted = directory.path().join("checksums.csv.enc");
    let output = directory.path().join("checksums.decoded.csv");
    fs::write(&source, b"path,hash\nfile.txt,abc\n").unwrap();

    assert!(fit_core::encrypt_file_with_password(&source, "", &encrypted).is_err());
    fit_core::encrypt_file_with_password(&source, PASSWORD, &encrypted).unwrap();
    assert!(fit_core::decrypt_file_with_password(&encrypted, "", &output).is_err());

    let error = fit_core::decrypt_file_with_password(&encrypted, "wrong", &output)
        .expect_err("wrong password should fail");
    assert!(matches!(error, fit_core::CoreError::Integrity));
    assert!(!output.exists());
}
