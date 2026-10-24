use serde_json::Value;

use crate::manifest::JsonMap;

#[derive(Clone, Debug, Default)]
pub struct FileRules {
    pub enabled: bool,
    pub blacklist: bool,
    pub extensions: Vec<String>,
    pub folders: Vec<String>,
    pub min_size: u64,
    pub max_size: u64,
}

impl FileRules {
    pub fn from_config(config: &JsonMap) -> Self {
        Self {
            enabled: bool_field(config, "enabled").unwrap_or(false),
            blacklist: bool_field(config, "blacklist").unwrap_or(true),
            extensions: string_list(config, "extensions"),
            folders: string_list(config, "folders"),
            min_size: unsigned_field(config, "min_size").unwrap_or(0),
            max_size: unsigned_field(config, "max_size").unwrap_or(0),
        }
    }

    pub fn excludes(&self, relative_path: &str, size: u64) -> bool {
        if !self.enabled {
            return false;
        }
        if self.min_size > 0 && size < self.min_size {
            return true;
        }
        if self.max_size > 0 && size > self.max_size {
            return true;
        }

        let normalized = relative_path.replace('\\', "/");
        if !self.extensions.is_empty() {
            let hit = extension_of(&normalized)
                .map(|extension| self.extensions.contains(&extension))
                .unwrap_or(false);
            if self.blacklist && hit {
                return true;
            }
            if !self.blacklist && !hit {
                return true;
            }
        }

        if !self.folders.is_empty() {
            let hit = normalized
                .split('/')
                .filter(|part| !part.is_empty())
                .map(str::to_ascii_lowercase)
                .any(|part| self.folders.contains(&part));
            if self.blacklist && hit {
                return true;
            }
            if !self.blacklist && !hit {
                return true;
            }
        }

        false
    }

    pub fn excludes_directory(&self, name: &str) -> bool {
        self.enabled && self.blacklist && self.folders.contains(&name.to_ascii_lowercase())
    }
}

fn bool_field(config: &JsonMap, key: &str) -> Option<bool> {
    config.get(key).and_then(Value::as_bool)
}

fn unsigned_field(config: &JsonMap, key: &str) -> Option<u64> {
    config.get(key).and_then(Value::as_u64)
}

fn string_list(config: &JsonMap, key: &str) -> Vec<String> {
    config
        .get(key)
        .and_then(Value::as_array)
        .map(|values| {
            values
                .iter()
                .filter_map(Value::as_str)
                .map(|value| value.trim().trim_start_matches('.').to_ascii_lowercase())
                .filter(|value| !value.is_empty())
                .collect()
        })
        .unwrap_or_default()
}

fn extension_of(path: &str) -> Option<String> {
    let name = path.rsplit('/').next()?;
    let dot = name.rfind('.')?;
    if dot == 0 {
        return None;
    }
    Some(name[dot + 1..].to_ascii_lowercase())
}
