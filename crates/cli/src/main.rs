use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use fit_core::{
    FileRecoveryMode, FileRecoveryOptions, FitDocument, FitRecOptions, ManifestEntry, write_fitrec,
};
use serde::Deserialize;
use serde_json::Map;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct DocumentInput {
    format_version: u32,
    algorithm: String,
    active_checklist: String,
    checklists: BTreeMap<String, Vec<ManifestEntry>>,
    #[serde(default)]
    exclude_paths: Vec<String>,
    #[serde(default)]
    exclude_rules: Map<String, serde_json::Value>,
    #[serde(default)]
    metadata: Map<String, serde_json::Value>,
}

impl From<DocumentInput> for FitDocument {
    fn from(value: DocumentInput) -> Self {
        Self {
            format_version: value.format_version,
            algorithm: value.algorithm,
            active_checklist: value.active_checklist,
            checklists: value.checklists,
            exclude_paths: value.exclude_paths,
            exclude_rules: value.exclude_rules,
            metadata: value.metadata,
        }
    }
}

enum Command {
    Generate {
        input: PathBuf,
        output: PathBuf,
        private_key: PathBuf,
        public_key: PathBuf,
        source_directory: Option<PathBuf>,
        options: FitRecOptions,
        recovery: FileRecoveryOptions,
    },
    GenerateKey {
        private_key: PathBuf,
        public_key: PathBuf,
    },
}

fn main() -> ExitCode {
    match run() {
        Ok(message) => {
            println!("{message}");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("fit-rec: {error}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<String, String> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    match parse_command(&args)? {
        Command::GenerateKey {
            private_key,
            public_key,
        } => {
            generate_keypair(&private_key, &public_key)?;
            Ok(format!("created Ed25519 keypair: {}", public_key.display()))
        }
        Command::Generate {
            input,
            output,
            private_key,
            public_key,
            source_directory,
            options,
            recovery,
        } => {
            let document = load_document(&input)?;
            let signing_key =
                fit_core::load_signing_key(&private_key).map_err(|error| error.to_string())?;
            write_fitrec(&output, &document, &signing_key, options)
                .map_err(|error| error.to_string())?;
            fit_core::write_public_key(&public_key, &signing_key)
                .map_err(|error| format!("unable to write public key: {error}"))?;

            let Some(source_directory) = source_directory else {
                return Ok(format!(
                    "created recovery record: {} (public key: {})",
                    output.display(),
                    public_key.display()
                ));
            };

            let parity_output = PathBuf::from(format!("{}.parity", output.display()));
            if parity_output == input
                || parity_output == private_key
                || parity_output == public_key
                || parity_output == output
            {
                return Err("output paths and key paths must differ".to_string());
            }

            fit_core::write_file_recovery(
                &source_directory,
                &parity_output,
                &document,
                &signing_key,
                fit_core::FileRecoveryOptions {
                    data_shards: options.data_shards,
                    parity_shards: options.parity_shards,
                    shard_size: recovery.shard_size,
                    mode: recovery.mode,
                },
            )
            .map_err(|error| format!("unable to write file recovery: {error}"))?;

            Ok(format!(
                "created recovery record: {} (parity: {}, public key: {})",
                output.display(),
                parity_output.display(),
                public_key.display()
            ))
        }
    }
}

fn parse_command(args: &[String]) -> Result<Command, String> {
    if args.first().map(String::as_str) == Some("keygen") {
        let mut private_key = None;
        let mut public_key = None;
        for pair in args[1..].chunks(2) {
            match pair {
                [flag, value] if flag == "--private" => {
                    private_key = Some(PathBuf::from(value));
                }
                [flag, value] if flag == "--public" => {
                    public_key = Some(PathBuf::from(value));
                }
                _ => return Err("keygen expects --private <path> --public <path>".to_string()),
            }
        }
        let private_key = private_key.ok_or("keygen is missing --private")?;
        let public_key = public_key.ok_or("keygen is missing --public")?;
        if private_key == public_key {
            return Err("private and public key paths must differ".to_string());
        }
        return Ok(Command::GenerateKey {
            private_key,
            public_key,
        });
    }

    if args.first().map(String::as_str) == Some("generate") {
        let mut input = None;
        let mut output = None;
        let mut private_key = None;
        let mut public_key = None;
        let mut source_directory = None;
        let mut data_shards = 16;
        let mut parity_shards = 4;
        let mut shard_size = 1024 * 1024;
        let mut mode = FileRecoveryMode::CrossFile;

        let mut index = 1;
        while index < args.len() {
            let flag = args[index].as_str();
            let Some(value) = args.get(index + 1) else {
                return Err(format!("{flag} is missing a value"));
            };
            match flag {
                "--input" => input = Some(PathBuf::from(value)),
                "--output" => output = Some(PathBuf::from(value)),
                "--private-key" => private_key = Some(PathBuf::from(value)),
                "--public-key" => public_key = Some(PathBuf::from(value)),
                "--source-directory" => source_directory = Some(PathBuf::from(value)),
                "--data-shards" => data_shards = parse_shards(flag, value)?,
                "--parity-shards" => parity_shards = parse_shards(flag, value)?,
                "--shard-size" => shard_size = parse_u32(flag, value)?,
                "--recovery-mode" => mode = parse_recovery_mode(value)?,
                _ => return Err(format!("unknown generate option: {flag}")),
            }
            index += 2;
        }

        let input = input.ok_or("generate is missing --input")?;
        let output = output.ok_or("generate is missing --output")?;
        let private_key = private_key.ok_or("generate is missing --private-key")?;
        let public_key = public_key.ok_or("generate is missing --public-key")?;
        if input == output || output == private_key || input == private_key {
            return Err("input, output and private key paths must differ".to_string());
        }
        if public_key == private_key {
            return Err("private and public key paths must differ".to_string());
        }
        if output == public_key {
            return Err("output and public key paths must differ".to_string());
        }
        if let Some(source_directory) = &source_directory {
            if !source_directory.is_dir() {
                return Err("source directory does not exist".to_string());
            }
            if input == *source_directory
                || output == *source_directory
                || private_key == *source_directory
                || public_key == *source_directory
            {
                return Err("source directory, input, output and key paths must differ".to_string());
            }
        }
        return Ok(Command::Generate {
            input,
            output,
            private_key,
            public_key,
            source_directory,
            options: FitRecOptions {
                data_shards,
                parity_shards,
            },
            recovery: FileRecoveryOptions {
                data_shards,
                parity_shards,
                shard_size,
                mode,
            },
        });
    }

    Err("usage: fit-rec generate ... | fit-rec keygen --private <path> --public <path>".to_string())
}

fn parse_shards(flag: &str, value: &str) -> Result<u8, String> {
    value
        .parse::<u8>()
        .map_err(|_| format!("{flag} must be an integer from 1 to 255"))
}

fn parse_u32(flag: &str, value: &str) -> Result<u32, String> {
    value
        .parse::<u32>()
        .map_err(|_| format!("{flag} must be an integer"))
}

fn parse_recovery_mode(value: &str) -> Result<FileRecoveryMode, String> {
    match value {
        "single" | "singleFile" => Ok(FileRecoveryMode::SingleFile),
        "cross" | "crossFile" => Ok(FileRecoveryMode::CrossFile),
        "dual" => Ok(FileRecoveryMode::Dual),
        _ => Err("recovery mode must be single, cross, or dual".to_string()),
    }
}

fn load_document(path: &Path) -> Result<FitDocument, String> {
    let data = fs::read(path).map_err(|error| format!("unable to read document: {error}"))?;
    let input: DocumentInput = serde_json::from_slice(&data)
        .map_err(|error| format!("invalid FitDocument JSON: {error}"))?;
    let document = FitDocument::from(input);
    document
        .validate()
        .map_err(|error| format!("invalid FitDocument: {error}"))?;
    Ok(document)
}

fn generate_keypair(private_path: &Path, public_path: &Path) -> Result<(), String> {
    fit_core::generate_keypair(private_path, public_path).map_err(|error| error.to_string())
}
