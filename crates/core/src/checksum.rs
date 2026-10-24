use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, BufWriter, Read, Write};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::error::{CoreError, Result};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ChecksumEntry {
    pub path: String,
    pub hash: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ChecksumFile {
    pub algorithm: String,
    pub entries: Vec<ChecksumEntry>,
}

pub fn write_csv<P: AsRef<Path>>(
    path: P,
    algorithm: &str,
    entries: &[ChecksumEntry],
) -> Result<()> {
    let path = path.as_ref();
    if let Some(parent) = path.parent()
        && !parent.as_os_str().is_empty()
    {
        std::fs::create_dir_all(parent)?;
    }

    let file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(path)?;
    let mut writer = BufWriter::new(file);
    writeln!(writer, "# Algorithm: {algorithm}")?;
    writeln!(writer, "path,hash")?;
    for entry in entries {
        writeln!(
            writer,
            "{},{}",
            csv_field(&entry.path),
            csv_field(&entry.hash)
        )?;
    }
    writer.flush()?;
    Ok(())
}

pub fn write_sfv<P: AsRef<Path>>(path: P, entries: &[ChecksumEntry]) -> Result<()> {
    let path = path.as_ref();
    if let Some(parent) = path.parent()
        && !parent.as_os_str().is_empty()
    {
        std::fs::create_dir_all(parent)?;
    }

    let file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(path)?;
    let mut writer = BufWriter::new(file);
    for entry in entries {
        writeln!(writer, "{} {}", normalize_sfv_path(&entry.path), entry.hash)?;
    }
    writer.flush()?;
    Ok(())
}

pub fn read_checksum_file<P: AsRef<Path>>(
    path: P,
    fallback_algorithm: &str,
) -> Result<ChecksumFile> {
    let path = path.as_ref();
    let lower = path
        .extension()
        .and_then(|extension| extension.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    if lower == "sfv" {
        let entries = read_sfv(path)?;
        return Ok(ChecksumFile {
            algorithm: fallback_algorithm.to_string(),
            entries,
        });
    }

    read_csv(path)
}

fn read_csv<P: AsRef<Path>>(path: P) -> Result<ChecksumFile> {
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    let mut algorithm = "sha256".to_string();
    let mut entries = Vec::new();
    let mut line = String::new();
    let mut saw_header = false;

    loop {
        line.clear();
        let read = reader.read_line(&mut line)?;
        if read == 0 {
            break;
        }
        let trimmed = line.trim_end_matches(['\r', '\n']);
        if trimmed.starts_with("# Algorithm:") {
            algorithm = trimmed
                .split_once(':')
                .map(|(_, value)| value.trim().to_string())
                .unwrap_or(algorithm);
            continue;
        }
        if trimmed.starts_with('#') || trimmed.is_empty() {
            continue;
        }
        if !saw_header {
            saw_header = true;
            let fields = parse_csv_line(trimmed)?;
            if fields.first().map(String::as_str) == Some("path")
                && fields.get(1).map(String::as_str) == Some("hash")
            {
                continue;
            }
        }

        let fields = parse_csv_line(trimmed)?;
        if fields.len() < 2 {
            return Err(CoreError::Manifest("checksum CSV row is incomplete"));
        }
        entries.push(ChecksumEntry {
            path: fields[0].clone(),
            hash: fields[1].clone(),
        });
    }

    Ok(ChecksumFile { algorithm, entries })
}

fn parse_csv_line(line: &str) -> Result<Vec<String>> {
    let mut fields = Vec::new();
    let mut field = String::new();
    let mut characters = line.chars().peekable();
    let mut quoted = false;

    while let Some(character) = characters.next() {
        match character {
            '"' if field.is_empty() && !quoted => quoted = true,
            '"' if quoted => {
                if characters.peek() == Some(&'"') {
                    characters.next();
                    field.push('"');
                } else {
                    quoted = false;
                }
            }
            ',' if !quoted => fields.push(std::mem::take(&mut field)),
            character => field.push(character),
        }
    }
    if quoted {
        return Err(CoreError::Manifest(
            "checksum CSV has an unterminated field",
        ));
    }
    fields.push(field);
    Ok(fields)
}

fn csv_field(value: &str) -> String {
    if value.contains(',') || value.contains('"') || value.contains('\n') || value.contains('\r') {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.to_string()
    }
}

pub fn read_sfv<P: AsRef<Path>>(path: P) -> Result<Vec<ChecksumEntry>> {
    let file = File::open(path)?;
    let reader = BufReader::new(file);
    let mut entries = Vec::new();
    for line in reader.lines() {
        let line = line?;
        let line = line.trim();
        if line.is_empty() || line.starts_with(';') {
            continue;
        }
        let Some((name, hash)) = line.rsplit_once(' ') else {
            continue;
        };
        let name = name.trim().trim_start_matches('*');
        entries.push(ChecksumEntry {
            path: name.to_string(),
            hash: hash.trim().to_string(),
        });
    }
    Ok(entries)
}

fn normalize_sfv_path(path: &str) -> String {
    let path = path.replace('\\', "/");
    let path = path.strip_prefix("./").unwrap_or(&path);
    path.trim_start_matches('/').to_string()
}

pub fn verify_checksum_file_size<P: AsRef<Path>>(path: P, max_bytes: usize) -> Result<usize> {
    let metadata = std::fs::metadata(path)?;
    if metadata.len() > max_bytes as u64 {
        return Err(CoreError::Manifest("checksum file is too large"));
    }
    Ok(metadata.len() as usize)
}

pub fn read_binary_file<P: AsRef<Path>>(path: P, max_bytes: usize) -> Result<Vec<u8>> {
    let path = path.as_ref();
    verify_checksum_file_size(path, max_bytes)?;
    let mut data = Vec::new();
    File::open(path)?.read_to_end(&mut data)?;
    Ok(data)
}

pub fn signature_path_for(path: &Path) -> PathBuf {
    let mut name = path.file_name().map_or_else(
        || std::ffi::OsString::from("checksum.sig"),
        std::ffi::OsString::from,
    );
    name.push(".sig");
    path.with_file_name(name)
}
