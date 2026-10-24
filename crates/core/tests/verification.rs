use std::collections::BTreeMap;
use std::fs;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use fit_core::{
    FileRules, FitDocument, ManifestEntry, VerificationOptions, normalize_relative_path,
    run_verification,
};

fn entry(path: &str, hash: &str) -> ManifestEntry {
    ManifestEntry {
        path: path.to_string(),
        hash: hash.to_string(),
        size: None,
        status: Some("ok".to_string()),
        extra: BTreeMap::new(),
    }
}

fn sha256(text: &str) -> String {
    use sha2::{Digest, Sha256};
    Sha256::digest(text.as_bytes())
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

#[test]
fn verification_reports_pass_fail_missing_and_extra() {
    let directory = tempfile::tempdir().unwrap();
    fs::write(directory.path().join("pass.txt"), b"pass").unwrap();
    fs::write(directory.path().join("fail.txt"), b"changed").unwrap();
    fs::write(directory.path().join("extra.txt"), b"extra").unwrap();
    fs::create_dir_all(directory.path().join("logs")).unwrap();
    fs::write(directory.path().join("logs/ignored.log"), b"ignored").unwrap();

    let mut checklists = BTreeMap::new();
    checklists.insert(
        "default".to_string(),
        vec![
            entry("pass.txt", &sha256("pass")),
            entry("fail.txt", &sha256("original")),
            entry("missing.txt", &sha256("missing")),
        ],
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

    let options = VerificationOptions {
        ignored_paths: vec!["logs/ignored.log".to_string()],
        ..Default::default()
    };
    let report = run_verification(&document, directory.path(), &options).unwrap();

    assert_eq!(report.total, 3);
    assert_eq!(report.passed, 1);
    assert_eq!(report.failed, 1);
    assert_eq!(report.missing, 1);
    assert_eq!(report.extra_count, 1);

    let statuses = report
        .details
        .iter()
        .map(|detail| (detail.path.as_str(), detail.status.as_str()))
        .collect::<Vec<_>>();
    assert!(statuses.contains(&("pass.txt", "pass")));
    assert!(statuses.contains(&("fail.txt", "fail")));
    assert!(statuses.contains(&("missing.txt", "missing")));
    assert!(statuses.contains(&("extra.txt", "extra")));
}

#[test]
fn ignored_path_excludes_directory_prefix() {
    let directory = tempfile::tempdir().unwrap();
    fs::write(directory.path().join("pass.txt"), b"pass").unwrap();
    fs::create_dir_all(directory.path().join(".fit-support")).unwrap();
    fs::write(
        directory.path().join(".fit-support/release.fitrec"),
        b"record",
    )
    .unwrap();

    let mut checklists = BTreeMap::new();
    checklists.insert(
        "default".to_string(),
        vec![entry("pass.txt", &sha256("pass"))],
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

    let options = VerificationOptions {
        ignored_paths: vec![".fit-support".to_string()],
        ..Default::default()
    };
    let report = run_verification(&document, directory.path(), &options).unwrap();

    assert_eq!(report.total, 1);
    assert_eq!(report.passed, 1);
    assert_eq!(report.extra_count, 0);
}

#[test]
fn exclude_rules_hide_files_and_directories() {
    let directory = tempfile::tempdir().unwrap();
    fs::write(directory.path().join("app.txt"), b"app").unwrap();
    fs::write(directory.path().join("cache.tmp"), b"cache").unwrap();
    fs::create_dir_all(directory.path().join("logs")).unwrap();
    fs::write(directory.path().join("logs/hidden.log"), b"hidden").unwrap();

    let mut checklists = BTreeMap::new();
    checklists.insert(
        "default".to_string(),
        vec![entry("app.txt", &sha256("app"))],
    );
    let mut exclude_rules = serde_json::Map::new();
    exclude_rules.insert("enabled".to_string(), serde_json::json!(true));
    exclude_rules.insert("blacklist".to_string(), serde_json::json!(true));
    exclude_rules.insert("extensions".to_string(), serde_json::json!(["tmp"]));
    exclude_rules.insert("folders".to_string(), serde_json::json!(["logs"]));
    let document = FitDocument {
        format_version: 1,
        algorithm: "sha256".to_string(),
        active_checklist: "default".to_string(),
        checklists,
        exclude_paths: Vec::new(),
        exclude_rules,
        metadata: serde_json::Map::new(),
    };

    let options = VerificationOptions {
        exclude_rules: FileRules::from_config(&document.exclude_rules),
        ..Default::default()
    };
    let report = run_verification(&document, directory.path(), &options).unwrap();

    assert_eq!(report.extra_count, 0);
    assert!(normalize_relative_path("logs/hidden.log").is_ok());
}

#[test]
fn progress_callback_can_cancel_verification() {
    let directory = tempfile::tempdir().unwrap();
    fs::write(directory.path().join("pass.txt"), b"pass").unwrap();
    fs::write(directory.path().join("fail.txt"), b"changed").unwrap();

    let mut checklists = BTreeMap::new();
    checklists.insert(
        "default".to_string(),
        vec![
            entry("pass.txt", &sha256("pass")),
            entry("fail.txt", &sha256("original")),
        ],
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

    let cancel = Arc::new(AtomicBool::new(false));
    let progress_cancel = cancel.clone();
    let options = VerificationOptions {
        cancel: Some(cancel),
        progress: Some(Arc::new(move |progress| {
            if progress.completed >= 1 {
                progress_cancel.store(true, Ordering::Relaxed);
            }
        })),
        ..Default::default()
    };
    let report = run_verification(&document, directory.path(), &options).unwrap();

    assert!(report.cancelled);
    assert!(!report.details.is_empty());
}
