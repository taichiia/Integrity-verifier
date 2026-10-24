use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};

use crate::error::{CoreError, Result};

pub type JsonMap = Map<String, Value>;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ManifestEntry {
    pub path: String,
    pub hash: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub size: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FitDocument {
    pub format_version: u32,
    pub algorithm: String,
    pub active_checklist: String,
    pub checklists: BTreeMap<String, Vec<ManifestEntry>>,
    #[serde(default)]
    pub exclude_paths: Vec<String>,
    #[serde(default)]
    pub exclude_rules: JsonMap,
    #[serde(default)]
    pub metadata: JsonMap,
}

pub fn normalize_relative_path(input: &str) -> Result<String> {
    let normalized = input.replace('\\', "/");
    if normalized.is_empty() || input.chars().any(|c| c.is_control()) {
        return Err(CoreError::Manifest(
            "path is empty or contains control characters",
        ));
    }

    let mut parts = Vec::new();
    for part in normalized.split('/') {
        match part {
            "" | "." => {}
            ".." => return Err(CoreError::Manifest("path contains parent traversal")),
            _ => parts.push(part),
        }
    }

    if parts.is_empty() {
        return Err(CoreError::Manifest("path has no file component"));
    }
    Ok(parts.join("/"))
}

pub fn canonical_python_json(value: &Value) -> String {
    let mut output = String::new();
    write_python_json(value, &mut output);
    output
}

pub fn manifest_hash(entries: &[ManifestEntry]) -> Result<String> {
    let mut values = Vec::with_capacity(entries.len());
    for entry in entries {
        if entry.path.is_empty() {
            return Err(CoreError::Manifest("entry path is empty"));
        }
        values.push(serde_json::to_value(entry)?);
    }
    values.sort_by(|left, right| {
        left.get("path")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .cmp(
                right
                    .get("path")
                    .and_then(Value::as_str)
                    .unwrap_or_default(),
            )
    });

    let canonical = canonical_python_json(&Value::Array(values));
    Ok(sha256_hex(canonical.as_bytes()))
}

impl FitDocument {
    pub fn validate(&self) -> Result<()> {
        if self.format_version != 1 {
            return Err(CoreError::UnsupportedVersion(self.format_version));
        }
        if self.algorithm.is_empty() {
            return Err(CoreError::Manifest("checksum algorithm is empty"));
        }
        if self.active_checklist.is_empty() {
            return Err(CoreError::Manifest("active checklist is empty"));
        }
        if !self.checklists.contains_key(&self.active_checklist) {
            return Err(CoreError::Manifest("active checklist does not exist"));
        }

        for (name, entries) in &self.checklists {
            if name.is_empty() {
                return Err(CoreError::Manifest("checklist name is empty"));
            }
            let mut seen = std::collections::HashSet::new();
            for entry in entries {
                let normalized = normalize_relative_path(&entry.path)?;
                if entry.hash.is_empty() {
                    return Err(CoreError::Manifest("entry hash is empty"));
                }
                if !seen.insert(normalized) {
                    return Err(CoreError::Manifest("duplicate normalized entry path"));
                }
            }
        }
        Ok(())
    }

    pub fn active_entries(&self) -> Result<&[ManifestEntry]> {
        self.checklists
            .get(&self.active_checklist)
            .map(Vec::as_slice)
            .ok_or(CoreError::Manifest("active checklist does not exist"))
    }

    pub fn active_manifest_hash(&self) -> Result<String> {
        manifest_hash(self.active_entries()?)
    }
}

fn write_python_json(value: &Value, output: &mut String) {
    match value {
        Value::Null => output.push_str("null"),
        Value::Bool(true) => output.push_str("true"),
        Value::Bool(false) => output.push_str("false"),
        Value::Number(number) => output.push_str(&number.to_string()),
        Value::String(text) => write_python_json_string(text, output),
        Value::Array(items) => {
            output.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    output.push_str(", ");
                }
                write_python_json(item, output);
            }
            output.push(']');
        }
        Value::Object(map) => {
            output.push('{');
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            for (index, key) in keys.into_iter().enumerate() {
                if index > 0 {
                    output.push_str(", ");
                }
                write_python_json_string(key, output);
                output.push_str(": ");
                write_python_json(&map[key], output);
            }
            output.push('}');
        }
    }
}

fn write_python_json_string(text: &str, output: &mut String) {
    output.push('"');
    for character in text.chars() {
        match character {
            '"' => output.push_str("\\\""),
            '\\' => output.push_str("\\\\"),
            '\u{8}' => output.push_str("\\b"),
            '\u{9}' => output.push_str("\\t"),
            '\u{a}' => output.push_str("\\n"),
            '\u{c}' => output.push_str("\\f"),
            '\u{d}' => output.push_str("\\r"),
            c if (c as u32) < 0x20 => {
                output.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => output.push(c),
        }
    }
    output.push('"');
}

pub(crate) fn sha256_hex(data: &[u8]) -> String {
    let digest = Sha256::digest(data);
    bytes_to_hex(&digest)
}

pub(crate) fn bytes_to_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(HEX[(byte >> 4) as usize] as char);
        output.push(HEX[(byte & 0x0f) as usize] as char);
    }
    output
}
