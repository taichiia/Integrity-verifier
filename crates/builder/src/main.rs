#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[path = "commands.rs"]
mod commands;

use commands::*;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            scan_directory,
            cancel_scan,
            filter_files,
            calculate_hashes,
            cancel_hashing,
            toggle_hash_pause,
            hash_file_command,
            generate_keypair_command,
            generate_fitrec_command,
            estimate_file_recovery_command,
            write_checksum_file,
            read_checksum_file,
            encrypt_checksum_file,
            decrypt_checksum_file,
            sign_checksum_file,
            verify_checksum_file,
            locate_verifier,
            prepare_support_directory,
            pack_native_verifier,
            verify_document,
            cancel_verification,
            save_project,
            load_project,
            pick_directory,
            pick_file,
            pick_files,
            pick_save_file,
        ])
        .manage(BuilderState::default())
        .run(tauri::generate_context!())
        .expect("error while running Tauri builder");
}
