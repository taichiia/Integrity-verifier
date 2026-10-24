use std::path::{Path, PathBuf};

use aes_gcm::{
    Aes256Gcm, Nonce,
    aead::{Aead, KeyInit},
};
use sha2::Sha256;

use crate::checksum::read_binary_file;
use crate::error::{CoreError, Result};

const MAX_CHECKSUM_FILE_BYTES: usize = 64 * 1024 * 1024;
const SALT_LENGTH: usize = 16;
const NONCE_LENGTH: usize = 12;
const PBKDF2_ITERATIONS: u32 = 200_000;

pub fn encrypt_file_with_password<P: AsRef<Path>, Q: AsRef<Path>>(
    path: P,
    password: &str,
    output_path: Q,
) -> Result<PathBuf> {
    if password.is_empty() {
        return Err(CoreError::Crypto(
            "encryption password is empty".to_string(),
        ));
    }
    let plaintext = read_binary_file(path, MAX_CHECKSUM_FILE_BYTES)?;
    let mut salt = [0_u8; SALT_LENGTH];
    let mut nonce = [0_u8; NONCE_LENGTH];
    getrandom::fill(&mut salt).map_err(|error| CoreError::Crypto(error.to_string()))?;
    getrandom::fill(&mut nonce).map_err(|error| CoreError::Crypto(error.to_string()))?;
    let key = derive_key_from_password(password, &salt);
    let cipher =
        Aes256Gcm::new_from_slice(&key).map_err(|error| CoreError::Crypto(error.to_string()))?;
    let ciphertext = cipher
        .encrypt(Nonce::from_slice(&nonce), plaintext.as_slice())
        .map_err(|_| CoreError::Crypto("encryption failed".to_string()))?;

    let mut payload = Vec::with_capacity(SALT_LENGTH + NONCE_LENGTH + ciphertext.len());
    payload.extend_from_slice(&salt);
    payload.extend_from_slice(&nonce);
    payload.extend_from_slice(&ciphertext);
    let output_path = output_path.as_ref().to_path_buf();
    std::fs::write(&output_path, payload)?;
    Ok(output_path)
}

pub fn decrypt_file_with_password<P: AsRef<Path>, Q: AsRef<Path>>(
    path: P,
    password: &str,
    output_path: Q,
) -> Result<PathBuf> {
    if password.is_empty() {
        return Err(CoreError::Crypto(
            "decryption password is empty".to_string(),
        ));
    }
    let payload = read_binary_file(path, MAX_CHECKSUM_FILE_BYTES)?;
    if payload.len() < SALT_LENGTH + NONCE_LENGTH {
        return Err(CoreError::Manifest("encrypted file is truncated"));
    }
    let (salt, remainder) = payload.split_at(SALT_LENGTH);
    let (nonce, ciphertext) = remainder.split_at(NONCE_LENGTH);
    let key = derive_key_from_password(password, salt);
    let cipher =
        Aes256Gcm::new_from_slice(&key).map_err(|error| CoreError::Crypto(error.to_string()))?;
    let plaintext = cipher
        .decrypt(Nonce::from_slice(nonce), ciphertext)
        .map_err(|_| CoreError::Integrity)?;
    let output_path = output_path.as_ref().to_path_buf();
    std::fs::write(&output_path, plaintext)?;
    Ok(output_path)
}

fn derive_key_from_password(password: &str, salt: &[u8]) -> [u8; 32] {
    let mut key = [0_u8; 32];
    pbkdf2::pbkdf2_hmac::<Sha256>(password.as_bytes(), salt, PBKDF2_ITERATIONS, &mut key);
    key
}
