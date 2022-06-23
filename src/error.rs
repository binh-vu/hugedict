use crate::rocksdb::loader::FileFormat;
use pyo3::PyErr;
use thiserror::Error;

/// Represent possible errors returned by this library.
#[derive(Error, Debug)]
pub enum HugeDictError {
    #[error("No files provided")]
    NoFiles,

    /// When file is not in the expected format.
    #[error(
        "Content is not in the expected format: {format:?}. The invalid content is: {content:?}"
    )]
    FormatError { format: FileFormat, content: String },

    #[error("Invalid file format: {0}")]
    InvalidFormat(&'static str),

    #[error("KeyError: {0}")]
    KeyError(String),

    #[error("ValueError: {0}")]
    ValueError(String),

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

    /// PyO3 error
    #[error(transparent)]
    PyErr(#[from] pyo3::PyErr),

    #[error("NNG (Messaging Library) Error: {0}")]
    NNGError(nng::Error),

    /// Error due to incorrect NNG's usage (e.g., implementing multi-read single-write paradigm).
    #[error("IPC Impl Error: {0}")]
    IPCImplError(String),
}

pub fn into_pyerr<E: Into<HugeDictError>>(err: E) -> PyErr {
    let hderr = err.into();
    if let HugeDictError::PyErr(e) = hderr {
        e
    } else {
        let anyerror: anyhow::Error = hderr.into();
        anyerror.into()
    }
}
