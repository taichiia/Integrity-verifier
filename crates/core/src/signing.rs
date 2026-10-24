use std::path::{Path, PathBuf};

use ed25519_dalek::{Signature, Signer, Verifier, VerifyingKey};

use crate::checksum::{read_binary_file, signature_path_for};
use crate::error::{CoreError, Result};
use crate::fitrec::load_signing_key;

const MAX_CHECKSUM_FILE_BYTES: usize = 64 * 1024 * 1024;
const SIGNATURE_HEX_LENGTH: usize = 128;

pub fn sign_file<P: AsRef<Path>, Q: AsRef<Path>>(path: P, private_key_path: Q) -> Result<PathBuf> {
    let path = path.as_ref();
    let signing_key = load_signing_key(private_key_path)?;
    let data = read_binary_file(path, MAX_CHECKSUM_FILE_BYTES)?;
    let signature = signing_key.sign(&data);
    let signature_path = signature_path_for(path);
    std::fs::write(&signature_path, hex::encode(signature.to_bytes()))?;
    Ok(signature_path)
}

pub fn verify_file<P: AsRef<Path>, Q: AsRef<Path>>(path: P, public_key_path: Q) -> Result<()> {
    let path = path.as_ref();
    let public_key = std::fs::read_to_string(public_key_path)?;
    let public_key = public_key.trim().trim_start_matches("0x");
    let public_key =
        hex::decode(public_key).map_err(|error| CoreError::Crypto(error.to_string()))?;
    let public_key: [u8; 32] = public_key
        .try_into()
        .map_err(|_| CoreError::Crypto("public key must contain exactly 32 bytes".to_string()))?;
    let verifying_key = VerifyingKey::from_bytes(&public_key)
        .map_err(|error| CoreError::Crypto(error.to_string()))?;

    let signature_path = signature_path_for(path);
    let signature_hex = std::fs::read_to_string(&signature_path)?;
    if signature_hex.trim().len() != SIGNATURE_HEX_LENGTH {
        return Err(CoreError::Manifest("signature file has invalid length"));
    }
    let signature_bytes =
        hex::decode(signature_hex.trim()).map_err(|error| CoreError::Crypto(error.to_string()))?;
    let signature = Signature::from_slice(&signature_bytes)
        .map_err(|error| CoreError::Crypto(error.to_string()))?;
    let data = read_binary_file(path, MAX_CHECKSUM_FILE_BYTES)?;
    verifying_key
        .verify(&data, &signature)
        .map_err(|_| CoreError::Signature)
}
