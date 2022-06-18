use rocksdb::{DBWithThreadMode, Options, DB};
use serde::{Deserialize, Serialize};
use std::path::Path;

/// Extracting key and value from an object.
struct KVExtractor {
    // object's attribute contains the key, None if key is the object itself.
    key: Optional<String>,
    // object's attribute contains the value, None if value is the object itself.
    value: Optional<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
enum FileFormat {
    // tab separated format of serialized byte key and value
    // serialized key must not contain tab character
    // serialized value must not contain newline character such as \r\n.
    #[serde(rename = "tabsep")]
    TabSep,

    // each line is a json object
    #[serde(rename = "ndjson")]
    NDJson(KVExtractor),

    // each line is a json list of two items key and value
    #[serde(rename = "tuple2")]
    Tuple2(KVExtractor),
}

/// Load files into RocksDB
///
/// # Arguments
/// * `dbpath` - path to a RocksDB
/// * `dbopts` - options to start a RocksDB
/// * `files` - path to the files to load into RocksDB
/// * `format` - file format
pub fn load(dbpath: &Path, dbopts: &Options, files: &[&Path], format: FileFormat, verbose: bool) {
    let db = DBWithThreadMode<MultiThreaded>::open(dbopts, dbpath);
    load_into_db(db, files, format, verbose)
}

/// Load files into RocksDB
pub fn load_into_db(db: DBWithThreadMode<MultiThreaded>, files: &[&Path], format: FileFormat, verbose: bool) {
    
}
