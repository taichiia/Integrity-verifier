use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use serde_json::{Value, json};
use tauri::{Emitter, State};
use tauri_plugin_dialog::DialogExt;

use fit_core::{
    FileRules, VerificationOptions, VerifyingKey, generate_keypair, load_file_recovery,
    load_fitrec, load_fitrec_info, recover_files_with_progress,
    repair_fitrec as repair_fitrec_core, run_verification,
};

struct AppState {
    cancel: Arc<AtomicBool>,
    recovery_cancel: Arc<AtomicBool>,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct RecordBundle {
    root_path: String,
    record_path: String,
    public_key_path: String,
    recovery_path: Option<String>,
}

fn discover_record_bundle_in(root: &Path) -> Result<Option<RecordBundle>, String> {
    let support = root.join(".fit-support");
    if !support.is_dir() {
        return Ok(None);
    }

    let mut records = Vec::new();
    let entries =
        fs::read_dir(&support).map_err(|error| format!("无法读取 .fit-support: {error}"))?;
    for entry in entries {
        let entry = entry.map_err(|error| format!("无法读取 .fit-support: {error}"))?;
        let path = entry.path();
        if path.is_file()
            && path
                .extension()
                .and_then(|value| value.to_str())
                .is_some_and(|value| value.eq_ignore_ascii_case("fitrec"))
        {
            records.push(path);
        }
    }
    records.sort();
    if records.is_empty() {
        return Ok(None);
    }
    if records.len() > 1 {
        return Err(".fit-support 中包含多个 .fitrec，请手动选择".to_string());
    }

    let record = records.remove(0);
    let public_key = PathBuf::from(format!("{}.pub", record.to_string_lossy()));
    if !public_key.is_file() {
        return Err(format!("缺少校验记录公钥: {}", public_key.display()));
    }
    let recovery = PathBuf::from(format!("{}.parity", record.to_string_lossy()));
    Ok(Some(RecordBundle {
        root_path: root.to_string_lossy().to_string(),
        record_path: record.to_string_lossy().to_string(),
        public_key_path: public_key.to_string_lossy().to_string(),
        recovery_path: recovery
            .is_file()
            .then(|| recovery.to_string_lossy().to_string()),
    }))
}

#[tauri::command]
fn discover_record_bundle() -> Result<Option<RecordBundle>, String> {
    let current_exe = std::env::current_exe().ok();
    if let Some(exe_dir) = current_exe.as_ref().and_then(|path| path.parent())
        && let Some(bundle) = discover_record_bundle_in(exe_dir)?
    {
        return Ok(Some(bundle));
    }

    let current_dir = std::env::current_dir().unwrap_or_default();
    discover_record_bundle_in(&current_dir)
}

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct VerifyArgs {
    record_path: String,
    target_path: String,
    public_key_path: String,
    checklist_name: Option<String>,
}

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct RecoveryArgs {
    recovery_path: String,
    target_path: String,
    output_path: String,
    public_key_path: String,
}

#[tauri::command]
async fn verify_record(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    args: VerifyArgs,
) -> Result<serde_json::Value, String> {
    let record_path = PathBuf::from(args.record_path);
    let target_path = PathBuf::from(args.target_path);
    let public_key_path = PathBuf::from(args.public_key_path);

    let verifying_key = load_verifying_key(&public_key_path)?;

    let mut document = load_fitrec(&record_path, &verifying_key)
        .map_err(|error| format!("校验记录加载失败: {error}"))?;
    if let Some(checklist_name) = &args.checklist_name
        && !checklist_name.is_empty()
    {
        if !document.checklists.contains_key(checklist_name) {
            return Err(format!("checklist does not exist: {checklist_name}"));
        }
        document.active_checklist = checklist_name.clone();
        document
            .validate()
            .map_err(|error| format!("invalid document: {error}"))?;
    }

    let exclude_rules = FileRules::from_config(&document.exclude_rules);
    let exclude_paths = document
        .exclude_paths
        .iter()
        .map(PathBuf::from)
        .collect::<Vec<_>>();
    let cancel = state.cancel.clone();
    cancel.store(false, Ordering::Relaxed);
    let progress_app = app.clone();
    let options = VerificationOptions {
        exclude_paths: exclude_paths.clone(),
        exclude_rules,
        ignored_paths: document.exclude_paths.clone(),
        self_exe: std::env::current_exe().ok(),
        cancel: Some(cancel),
        progress: Some(Arc::new(move |progress| {
            let _ = progress_app.emit("verification-progress", json!(progress));
        })),
    };

    let report = tauri::async_runtime::spawn_blocking(move || {
        run_verification(&document, &target_path, &options)
    })
    .await
    .map_err(|error| format!("验证任务失败: {error}"))?
    .map_err(|error| format!("验证失败: {error}"))?;

    Ok(json!(report))
}

#[tauri::command]
fn inspect_fitrec(
    record_path: PathBuf,
    public_key_path: PathBuf,
) -> Result<serde_json::Value, String> {
    let verifying_key = load_verifying_key(&public_key_path)?;
    let info = load_fitrec_info(&record_path, &verifying_key)
        .map_err(|error| format!("校验记录加载失败: {error}"))?;
    serde_json::to_value(info).map_err(|error| format!("校验记录信息序列化失败: {error}"))
}

#[tauri::command]
fn inspect_file_recovery(
    recovery_path: PathBuf,
    public_key_path: PathBuf,
) -> Result<serde_json::Value, String> {
    if recovery_path.as_os_str().is_empty() {
        return Err("请选择恢复档案".to_string());
    }
    let verifying_key = load_verifying_key(&public_key_path)?;
    let info = load_file_recovery(&recovery_path, &verifying_key)
        .map_err(|error| format!("恢复档案读取失败: {error}"))?;
    serde_json::to_value(info).map_err(|error| format!("恢复档案信息序列化失败: {error}"))
}

fn load_verifying_key(path: &PathBuf) -> Result<VerifyingKey, String> {
    let key_bytes = fs::read(path).map_err(|error| format!("无法读取公钥: {error}"))?;
    let key_text = String::from_utf8_lossy(&key_bytes);
    let mut key_hex = key_text.trim().to_string();
    if key_hex.starts_with("0x") {
        key_hex = key_hex[2..].to_string();
    }
    let public_key =
        hex::decode(key_hex).map_err(|error| format!("公钥不是有效的 hex: {error}"))?;
    let public_key: [u8; 32] = public_key
        .try_into()
        .map_err(|_| "公钥长度必须是 32 字节".to_string())?;
    VerifyingKey::from_bytes(&public_key).map_err(|error| format!("公钥解析失败: {error}"))
}

#[tauri::command]
async fn recover_files(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    args: RecoveryArgs,
) -> Result<serde_json::Value, String> {
    if args.recovery_path.is_empty() {
        return Err("请选择恢复档案".to_string());
    }
    if args.target_path.is_empty() {
        return Err("请选择目标目录".to_string());
    }
    if args.output_path.is_empty() {
        return Err("请选择恢复输出目录".to_string());
    }

    let verifying_key = load_verifying_key(&PathBuf::from(&args.public_key_path))?;
    state.recovery_cancel.store(false, Ordering::Relaxed);
    let cancel = state.recovery_cancel.clone();
    let progress_app = app.clone();
    let report = tauri::async_runtime::spawn_blocking(move || {
        recover_files_with_progress(
            PathBuf::from(args.recovery_path),
            &verifying_key,
            PathBuf::from(args.target_path),
            PathBuf::from(args.output_path),
            Some(cancel),
            Some(Arc::new(move |completed, total, path| {
                let _ = progress_app.emit(
                    "recovery-progress",
                    json!({"completed": completed, "total": total, "path": path}),
                );
            })),
        )
    })
    .await
    .map_err(|error| format!("恢复任务失败: {error}"))?
    .map_err(|error| format!("文件恢复失败: {error}"))?;
    serde_json::to_value(report).map_err(|error| format!("恢复结果序列化失败: {error}"))
}

#[tauri::command]
async fn repair_fitrec(
    record_path: PathBuf,
    public_key_path: PathBuf,
    output_path: PathBuf,
) -> Result<serde_json::Value, String> {
    if record_path == output_path {
        return Err("修复副本不能覆盖原始记录".to_string());
    }
    if output_path.as_os_str().is_empty() {
        return Err("请选择修复副本保存路径".to_string());
    }
    let verifying_key = load_verifying_key(&public_key_path)?;
    let output = output_path.to_string_lossy().to_string();
    let repair = tauri::async_runtime::spawn_blocking(move || {
        repair_fitrec_core(record_path, &verifying_key, output_path)
    })
    .await
    .map_err(|error| format!("修复任务失败: {error}"))?
    .map_err(|error| format!("校验记录修复失败: {error}"))?;

    Ok(json!({
        "repaired": repair.damaged_shards > 0,
        "damagedShards": repair.damaged_shards,
        "output": if repair.damaged_shards > 0 { output } else { String::new() },
    }))
}

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct KeyPairArgs {
    private_key_path: String,
    public_key_path: String,
}

#[tauri::command]
fn generate_keypair_command(args: KeyPairArgs) -> Result<(), String> {
    if args.private_key_path.is_empty() || args.public_key_path.is_empty() {
        return Err("private and public key paths must not be empty".to_string());
    }
    let private_key = PathBuf::from(&args.private_key_path);
    let public_key = PathBuf::from(&args.public_key_path);
    if private_key == public_key {
        return Err("private and public key paths must differ".to_string());
    }
    generate_keypair(&private_key, &public_key)
        .map_err(|error| format!("key generation failed: {error}"))
}

#[tauri::command]
fn cancel_verification(state: State<'_, AppState>) {
    state.cancel.store(true, Ordering::Relaxed);
}

#[tauri::command]
fn cancel_recovery(state: State<'_, AppState>) {
    state.recovery_cancel.store(true, Ordering::Relaxed);
}

#[tauri::command]
fn save_report(app: tauri::AppHandle, report: serde_json::Value) -> Result<Option<String>, String> {
    let selected = app
        .dialog()
        .file()
        .add_filter("Report", &["json", "csv"])
        .blocking_save_file();
    let Some(selected) = selected else {
        return Ok(None);
    };
    let path = selected
        .into_path()
        .map_err(|error| format!("无法解析保存路径: {error}"))?;
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .map(str::to_ascii_lowercase)
        .unwrap_or_else(|| "json".to_string());

    let content = if extension == "csv" {
        report_to_csv(&report).into_bytes()
    } else {
        serde_json::to_vec_pretty(&report).map_err(|error| format!("无法序列化报告: {error}"))?
    };
    fs::write(&path, content).map_err(|error| format!("无法写入报告: {error}"))?;
    Ok(Some(path.to_string_lossy().to_string()))
}

fn report_to_csv(report: &serde_json::Value) -> String {
    let mut output = String::from("status,path,expected,actual\r\n");
    if let Some(details) = report.get("details").and_then(serde_json::Value::as_array) {
        for detail in details {
            let status = detail.get("status").and_then(Value::as_str).unwrap_or("");
            let path = detail.get("path").and_then(Value::as_str).unwrap_or("");
            let expected = detail.get("expected").and_then(Value::as_str).unwrap_or("");
            let actual = detail.get("actual").and_then(Value::as_str).unwrap_or("");
            output.push_str(&format!(
                "{},{},{},{}\r\n",
                csv_field(status),
                csv_field(path),
                csv_field(expected),
                csv_field(actual)
            ));
        }
    }
    output
}

fn csv_field(value: &str) -> String {
    if value.contains(',') || value.contains('"') || value.contains('\n') || value.contains('\r') {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.to_string()
    }
}

#[tauri::command]
fn pick_directory(app: tauri::AppHandle) -> Option<String> {
    app.dialog()
        .file()
        .blocking_pick_folder()
        .map(|path| path.to_string())
}

#[tauri::command]
fn pick_file(app: tauri::AppHandle) -> Option<String> {
    app.dialog()
        .file()
        .blocking_pick_file()
        .map(|path| path.to_string())
}

#[tauri::command]
fn pick_save_file(app: tauri::AppHandle, name: String, extensions: Vec<String>) -> Option<String> {
    let mut dialog = app.dialog().file().set_file_name(&name);
    let extension_refs: Vec<&str> = extensions.iter().map(String::as_str).collect();
    dialog = dialog.add_filter("Ed25519 key", &extension_refs);
    dialog.blocking_save_file().map(|path| path.to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            verify_record,
            discover_record_bundle,
            inspect_fitrec,
            repair_fitrec,
            inspect_file_recovery,
            recover_files,
            cancel_verification,
            cancel_recovery,
            save_report,
            pick_directory,
            pick_file,
            pick_save_file,
            generate_keypair_command
        ])
        .manage(AppState {
            cancel: Arc::new(AtomicBool::new(false)),
            recovery_cancel: Arc::new(AtomicBool::new(false)),
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
