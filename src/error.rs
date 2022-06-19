use crate::rocksdb::loader::FileFormat;
use thiserror::Error;

/// Represent possible errors returned by this library.
#[derive(Error, Debug)]
pub enum HugeDictError {
    /// When file is not in the expected format.
    #[error(
        "Content is not in the expected format: {format:?}. The invalid content is: {content:?}"
    )]
    FormatError { format: FileFormat, content: String },

    // #[error("File is not in the expected format")]
    // FormatError,
    /// Represents a failure to read from input.
    #[error("Read error")]
    ReadError { source: std::io::Error },

    /// Represents all RocksDB errors.
    #[error("Rocksdb Error: {0}")]
    RocksDBError(#[from] rocksdb::Error),

    /// Represents all other cases of `std::io::Error`.
    #[error(transparent)]
    IOError(#[from] std::io::Error),
}
