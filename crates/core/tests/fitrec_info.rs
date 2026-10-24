use fit_core::{FitRecOptions, VerifyingKey, generate_signing_key, load_fitrec_info, write_fitrec};
use std::collections::BTreeMap;

#[test]
fn fitrec_info_reports_recovery_configuration() {
    let mut checklists = BTreeMap::new();
    checklists.insert("default".to_string(), Vec::new());
    let document = fit_core::FitDocument {
        format_version: 1,
        algorithm: "sha256".to_string(),
        active_checklist: "default".to_string(),
        checklists,
        exclude_paths: Vec::new(),
        exclude_rules: serde_json::Map::new(),
        metadata: serde_json::Map::new(),
    };
    let signing_key = generate_signing_key().unwrap();
    let verifying_key = VerifyingKey::from(&signing_key);
    let directory = tempfile::tempdir().unwrap();
    let record = directory.path().join("release.fitrec");
    write_fitrec(&record, &document, &signing_key, FitRecOptions::default()).unwrap();

    let info = load_fitrec_info(&record, &verifying_key).unwrap();
    assert_eq!(info.data_shards, 8);
    assert_eq!(info.parity_shards, 4);
    assert_eq!(info.active_checklist, "default");
    assert_eq!(info.checklists.len(), 1);
}
