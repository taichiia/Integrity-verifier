use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    prepare_verifier_payload();
    tauri_build::build();
}

fn prepare_verifier_payload() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let target_dir = env::var_os("CARGO_TARGET_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            manifest_dir
                .parent()
                .expect("builder manifest parent")
                .parent()
                .expect("workspace root")
                .join("target")
        });
    let verifier = target_dir.join("release").join("fit-verifier.exe");
    let payload = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR")).join("verifier.exe");

    if verifier.is_file() {
        fs::copy(&verifier, &payload).expect("copy verifier payload");
    } else {
        fs::write(&payload, []).expect("write empty verifier payload");
    }

    println!("cargo:rerun-if-changed={}", verifier.display());
}
