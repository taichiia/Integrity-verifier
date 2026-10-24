use std::cell::RefCell;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::time::Duration;

use digest::Output;
use md5::Md5;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256, Sha512};

use crate::error::Result;

const READ_CHUNK: usize = 1024 * 1024;
const PROGRESS_EVERY: usize = 16;

thread_local! {
    static READ_BUFFER: RefCell<Vec<u8>> = RefCell::new(vec![0_u8; READ_CHUNK]);
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HashAlgorithm {
    Sha256,
    Sha512,
    Md5,
}

#[derive(Clone, Default)]
pub struct HashOptions {
    pub cancel: Option<Arc<AtomicBool>>,
    pub pause: Option<Arc<AtomicBool>>,
    pub progress: Option<HashProgressCallback>,
}

pub type HashProgressCallback = Arc<dyn Fn(usize, usize, &str) + Send + Sync>;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HashResult {
    pub path: String,
    pub hash: String,
    pub error: String,
}

pub fn hash_file(path: &Path, algorithm: HashAlgorithm) -> Result<String> {
    let mut file = File::open(path)?;
    READ_BUFFER.with_borrow_mut(|buffer| match algorithm {
        HashAlgorithm::Sha256 => Ok(bytes_to_hex(&hash_with_digest::<Sha256>(
            &mut file, buffer,
        )?)),
        HashAlgorithm::Sha512 => Ok(bytes_to_hex(&hash_with_digest::<Sha512>(
            &mut file, buffer,
        )?)),
        HashAlgorithm::Md5 => Ok(bytes_to_hex(&hash_with_digest::<Md5>(&mut file, buffer)?)),
    })
}

fn hash_with_digest<H: Digest>(file: &mut File, buffer: &mut [u8]) -> Result<Output<H>> {
    let mut hasher = H::new();
    loop {
        let read = file.read(buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(hasher.finalize())
}

pub fn run_hashing(
    paths: &[PathBuf],
    algorithm: HashAlgorithm,
    options: &HashOptions,
) -> Vec<HashResult> {
    let completed = Arc::new(AtomicUsize::new(0));
    paths
        .par_iter()
        .map(|path| {
            wait_while_paused(options);
            let result = if is_cancelled(options) {
                HashResult {
                    path: path.to_string_lossy().to_string(),
                    hash: String::new(),
                    error: "cancelled".to_string(),
                }
            } else {
                match hash_file(path, algorithm) {
                    Ok(hash) => HashResult {
                        path: path.to_string_lossy().to_string(),
                        hash,
                        error: String::new(),
                    },
                    Err(error) => HashResult {
                        path: path.to_string_lossy().to_string(),
                        hash: String::new(),
                        error: error.to_string(),
                    },
                }
            };

            let completed = completed.fetch_add(1, Ordering::Relaxed) + 1;
            if (completed.is_multiple_of(PROGRESS_EVERY) || completed == paths.len())
                && let Some(progress) = &options.progress
            {
                progress(completed, paths.len(), &result.path);
            }
            result
        })
        .collect()
}

fn is_cancelled(options: &HashOptions) -> bool {
    options
        .cancel
        .as_ref()
        .map(|flag| flag.load(Ordering::Relaxed))
        .unwrap_or(false)
}

fn wait_while_paused(options: &HashOptions) {
    while !is_cancelled(options) && is_paused(options) {
        std::thread::sleep(Duration::from_millis(50));
    }
}

fn is_paused(options: &HashOptions) -> bool {
    options
        .pause
        .as_ref()
        .map(|flag| flag.load(Ordering::Relaxed))
        .unwrap_or(false)
}

fn bytes_to_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(HEX[(byte >> 4) as usize] as char);
        output.push(HEX[(byte & 0x0f) as usize] as char);
    }
    output
}
