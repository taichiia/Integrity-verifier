use std::fs;

use fit_builder::commands::{
    CryptoArgs, PackArgs, ProjectDocument, decrypt_checksum_file, encrypt_checksum_file,
    ensure_within_base, filter_files, load_project, pack_native_verifier, read_checksum_file,
    save_project, validate_path_string, write_checksum_file,
};
use fit_core::ScannedFile;
use serde_json::json;

#[test]
fn path_validation_resolves_relative_and_rejects_traversal() {
    assert!(validate_path_string("").is_err());
    let relative = validate_path_string("relative/path").unwrap();
    assert!(relative.is_absolute());
    assert!(relative.ends_with("relative/path"));
    assert!(validate_path_string("C:/base/../secret").is_err());
    assert!(validate_path_string("C:/base\0hidden").is_err());
    assert!(validate_path_string("C:/base/ok").is_ok());
}

#[test]
fn path_validation_accepts_pasted_absolute_paths() {
    assert!(validate_path_string(" E:/测试临时文件夹 ").is_ok());
    assert!(validate_path_string("\"E:/测试临时文件夹\"").is_ok());
    assert!(validate_path_string("“E:/测试临时文件夹”").is_ok());
    assert!(validate_path_string("E：/测试临时文件夹").is_ok());
}

#[test]
fn hash_paths_must_stay_inside_selected_base() {
    let directory = tempfile::tempdir().unwrap();
    let inside = directory.path().join("inside.txt");
    let outside = directory.path().parent().unwrap().join("outside.txt");
    fs::write(&inside, b"inside").unwrap();
    fs::write(&outside, b"outside").unwrap();

    assert!(ensure_within_base(&inside, directory.path()).is_ok());
    assert!(ensure_within_base(&outside, directory.path()).is_err());
}

#[test]
fn filter_files_uses_core_rules() {
    let files = vec![
        ScannedFile {
            path: "keep.txt".to_string(),
            absolute_path: "C:/base/keep.txt".to_string(),
            size: 10,
            modified: None,
        },
        ScannedFile {
            path: "cache.tmp".to_string(),
            absolute_path: "C:/base/cache.tmp".to_string(),
            size: 10,
            modified: None,
        },
    ];
    let rules = json!({
        "enabled": true,
        "blacklist": true,
        "extensions": ["tmp"],
        "folders": [],
        "min_size": 0,
        "max_size": 0
    })
    .as_object()
    .unwrap()
    .clone();
    let kept = filter_files(fit_builder::commands::FilterArgs { files, rules }).unwrap();
    assert_eq!(kept.len(), 1);
    assert_eq!(kept[0].path, "keep.txt");
}

#[test]
fn project_save_and_load_roundtrip() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("project.fitbuilder");
    let mut project = ProjectDocument {
        base_directory: directory.path().to_string_lossy().to_string(),
        ..Default::default()
    };
    project.entries.push(fit_core::ManifestEntry {
        path: "app.dll".to_string(),
        hash: "hash".to_string(),
        size: Some(12),
        status: Some("ok".to_string()),
        extra: Default::default(),
    });
    save_project(path.to_string_lossy().to_string(), project).unwrap();

    let loaded = load_project(path.to_string_lossy().to_string()).unwrap();
    assert_eq!(loaded.version, 1);
    assert_eq!(loaded.entries.len(), 1);
    assert_eq!(loaded.entries[0].path, "app.dll");
}

#[test]
fn project_rejects_traversal_entries() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("bad.fitbuilder");
    let mut project = ProjectDocument::default();
    project.entries.push(fit_core::ManifestEntry {
        path: "../secret.txt".to_string(),
        hash: "hash".to_string(),
        size: Some(1),
        status: Some("ok".to_string()),
        extra: Default::default(),
    });
    let error = save_project(path.to_string_lossy().to_string(), project)
        .expect_err("traversal should be rejected");
    assert!(error.contains("invalid project entry"));
}

#[test]
fn checksum_file_commands_roundtrip() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("checksums.csv");
    let entries = vec![fit_core::ChecksumEntry {
        path: "a.txt".to_string(),
        hash: "hash".to_string(),
    }];
    write_checksum_file(fit_builder::commands::WriteChecksumArgs {
        path: path.to_string_lossy().to_string(),
        format: "csv".to_string(),
        algorithm: "sha256".to_string(),
        entries,
    })
    .unwrap();

    let loaded = read_checksum_file(path.to_string_lossy().to_string()).unwrap();
    assert_eq!(loaded.algorithm, "sha256");
    assert_eq!(loaded.entries.len(), 1);
}

#[test]
fn native_verifier_pack_copies_runtime_files() {
    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("source");
    let output = directory.path().join("package");
    fs::create_dir_all(&source).unwrap();
    fs::write(source.join("fit-verifier.exe"), b"verifier").unwrap();
    fs::write(source.join("release.fitrec"), b"record").unwrap();
    fs::write(source.join("release.fitrec.pub"), b"public").unwrap();
    fs::write(source.join("checksums.csv"), b"path,hash\na.txt,hash\n").unwrap();
    fs::write(source.join("checksums.csv.sig"), b"signature").unwrap();

    let packaged = pack_native_verifier(PackArgs {
        output_directory: output.to_string_lossy().to_string(),
        record_path: source.join("release.fitrec").to_string_lossy().to_string(),
        checksum_path: Some(source.join("checksums.csv").to_string_lossy().to_string()),
        verifier_path: source
            .join("fit-verifier.exe")
            .to_string_lossy()
            .to_string(),
    })
    .unwrap();

    let packaged = std::path::Path::new(&packaged);
    assert!(packaged.join("fit-verifier.exe").is_file());
    assert!(packaged.join(".fit-support/release.fitrec").is_file());
    assert!(packaged.join(".fit-support/release.fitrec.pub").is_file());
    assert!(packaged.join(".fit-support/checksums.csv").is_file());
    assert!(packaged.join(".fit-support/checksums.csv.sig").is_file());
}

#[test]
fn native_verifier_pack_autodetects_adjacent_binary() {
    let directory = tempfile::tempdir().unwrap();
    let output = directory.path().join("package");
    fs::create_dir_all(&output).unwrap();
    fs::write(output.join("fit-verifier.exe"), b"verifier").unwrap();
    fs::write(output.join("release.fitrec"), b"record").unwrap();
    fs::write(output.join("release.fitrec.pub"), b"public").unwrap();

    let packaged = pack_native_verifier(PackArgs {
        output_directory: output.to_string_lossy().to_string(),
        record_path: output.join("release.fitrec").to_string_lossy().to_string(),
        verifier_path: String::new(),
        checksum_path: None,
    })
    .unwrap();

    assert!(
        std::path::Path::new(&packaged)
            .join("fit-verifier.exe")
            .is_file()
    );
    assert!(
        std::path::Path::new(&packaged)
            .join(".fit-support/release.fitrec")
            .is_file()
    );
}

#[test]
fn native_verifier_pack_rejects_random_binary() {
    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("source");
    let output = directory.path().join("package");
    fs::create_dir_all(&source).unwrap();
    fs::write(source.join("not-verifier.exe"), b"random").unwrap();
    fs::write(source.join("release.fitrec"), b"record").unwrap();
    fs::write(source.join("release.fitrec.pub"), b"public").unwrap();

    let result = pack_native_verifier(PackArgs {
        output_directory: output.to_string_lossy().to_string(),
        record_path: source.join("release.fitrec").to_string_lossy().to_string(),
        verifier_path: source
            .join("not-verifier.exe")
            .to_string_lossy()
            .to_string(),
        checksum_path: None,
    });

    assert!(
        result
            .unwrap_err()
            .contains("not a FIT verifier executable")
    );
}

#[cfg(windows)]
#[allow(clippy::permissions_set_readonly_false)]
#[test]
fn native_verifier_pack_uses_fallback_when_destination_is_readonly() {
    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("source");
    let output = directory.path().join("package");
    fs::create_dir_all(&source).unwrap();
    fs::create_dir_all(&output).unwrap();
    fs::write(source.join("fit-verifier.exe"), b"new verifier").unwrap();
    fs::write(output.join("fit-verifier.exe"), b"old verifier").unwrap();
    fs::write(output.join("release.fitrec"), b"record").unwrap();
    fs::write(output.join("release.fitrec.pub"), b"public").unwrap();

    let destination = output.join("fit-verifier.exe");
    let mut permissions = fs::metadata(&destination).unwrap().permissions();
    permissions.set_readonly(true);
    fs::set_permissions(&destination, permissions).unwrap();

    let packaged = pack_native_verifier(PackArgs {
        output_directory: output.to_string_lossy().to_string(),
        record_path: output.join("release.fitrec").to_string_lossy().to_string(),
        verifier_path: source
            .join("fit-verifier.exe")
            .to_string_lossy()
            .to_string(),
        checksum_path: None,
    })
    .unwrap();

    let packaged = std::path::Path::new(&packaged);
    assert!(packaged.join("fit-verifier (1).exe").is_file());
    assert!(packaged.join(".fit-support/release.fitrec").is_file());
    assert!(packaged.join(".fit-support/release.fitrec.pub").is_file());

    let mut permissions = fs::metadata(&destination).unwrap().permissions();
    permissions.set_readonly(false);
    fs::set_permissions(&destination, permissions).unwrap();
}

#[test]
fn checksum_file_encryption_commands_roundtrip() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("checksums.csv");
    let encrypted = directory.path().join("checksums.csv.enc");
    let decrypted = directory.path().join("checksums.csv.decoded");
    let plaintext = b"path,hash\na.txt,hash\n";
    fs::write(&path, plaintext).unwrap();

    encrypt_checksum_file(CryptoArgs {
        path: path.to_string_lossy().to_string(),
        output_path: encrypted.to_string_lossy().to_string(),
        password: "test-password".to_string(),
    })
    .unwrap();
    assert!(encrypted.is_file());

    decrypt_checksum_file(CryptoArgs {
        path: encrypted.to_string_lossy().to_string(),
        output_path: decrypted.to_string_lossy().to_string(),
        password: "test-password".to_string(),
    })
    .unwrap();
    assert_eq!(fs::read(&decrypted).unwrap(), plaintext);

    let error = decrypt_checksum_file(CryptoArgs {
        path: encrypted.to_string_lossy().to_string(),
        output_path: directory
            .path()
            .join("wrong.csv")
            .to_string_lossy()
            .to_string(),
        password: "wrong".to_string(),
    })
    .expect_err("wrong password should fail");
    assert!(error.contains("checksum decryption failed"));
}
