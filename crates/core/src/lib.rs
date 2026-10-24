pub mod checksum;
pub mod crypto;
pub mod error;
pub mod file_recovery;
pub mod fitrec;
pub mod hashing;
pub mod manifest;
pub mod rules;
pub mod scan;
pub mod signing;
pub mod verification;

pub use checksum::{
    ChecksumEntry, ChecksumFile, read_checksum_file, read_sfv, write_csv, write_sfv,
};
pub use crypto::{decrypt_file_with_password, encrypt_file_with_password};
pub use error::{CoreError, Result};
pub use file_recovery::{
    FileRecoveryDetail, FileRecoveryEntry, FileRecoveryEstimate, FileRecoveryInfo,
    FileRecoveryMode, FileRecoveryOptions, FileRecoveryReport, estimate_file_recovery_size,
    load_file_recovery, recover_files, recover_files_with_progress, write_file_recovery,
    write_file_recovery_with_progress,
};
pub use fitrec::{
    FitRecInfo, FitRecOptions, FitRecRepair, SigningKey, VerifyingKey, decode_fitrec,
    decode_fitrec_repaired, encode_fitrec, generate_keypair, generate_signing_key, load_fitrec,
    load_fitrec_info, load_signing_key, repair_fitrec, write_fitrec, write_public_key,
};
pub use hashing::{HashAlgorithm, HashOptions, HashResult, hash_file, run_hashing};
pub use manifest::{
    FitDocument, ManifestEntry, canonical_python_json, manifest_hash, normalize_relative_path,
};
pub use rules::FileRules;
pub use scan::{
    PreHashEntry, PreHashOptions, ScanOptions, ScanReport, ScannedFile, modified_timestamp,
    prehash_files, scan_and_prehash, scan_directory,
};
pub use signing::{sign_file, verify_file};
pub use verification::{
    VerificationDetail, VerificationOptions, VerificationProgress, VerificationReport,
    run_verification,
};
