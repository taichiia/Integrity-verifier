use thiserror::Error;

pub type Result<T> = std::result::Result<T, CoreError>;

#[derive(Debug, Error)]
pub enum CoreError {
    #[error("malformed FIT recovery record: {0}")]
    Malformed(&'static str),
    #[error("unsupported FIT recovery record version: {0}")]
    UnsupportedVersion(u32),
    #[error("signature verification failed")]
    Signature,
    #[error("document integrity check failed")]
    Integrity,
    #[error("RS recovery capacity exceeded: {damaged} damaged shards, capacity is {capacity}")]
    InsufficientShards { damaged: usize, capacity: usize },
    #[error("invalid manifest entry: {0}")]
    Manifest(&'static str),
    #[error("invalid RS configuration: {0}")]
    Codec(&'static str),
    #[error("{0}")]
    CodecMessage(String),
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("crypto error: {0}")]
    Crypto(String),
    #[error("cancelled")]
    Cancelled,
    #[error("unsupported hash algorithm: {0}")]
    UnsupportedAlgorithm(String),
}
