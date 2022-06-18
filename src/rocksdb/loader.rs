use rocksdb::{DBWithThreadMode, Options, DB, MultiThreaded};
use serde::{Deserialize, Serialize};
use std::ffi::OsStr;
use std::{path::Path, io::BufReader, fs::File};
use std::io::{self, BufRead};
use std::prelude::*;
use rayon::prelude::*;
use flate2::read::GzDecoder;

/// Extracting key and value from an object.
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct KVExtractor {
    // object's attribute contains the key, None if key is the object itself.
    key: Option<String>,
    // object's attribute contains the value, None if value is the object itself.
    value: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub enum FileFormat {
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
    let db: DBWithThreadMode<MultiThreaded> = DBWithThreadMode::open(dbopts, dbpath).unwrap();

    files.iter()
        .map(|file| {
            build_sst_file(file, &format);
    //         // let mut writer = SstFileWriter::create(dbopts);
    //         // writer.open(dbpath)?;

    //         // read the file
    //         match format {
    //             FileFormat::TabSep => {

    //             },
    //             _ => unimplemented! ()
    //         }
            
    //         // writer.finish()?;
        });
}

pub fn build_sst_file(file: &Path, format: &FileFormat) {
    let mut reader = match file.extension().and_then(OsStr::to_str) {
        None => unimplemented!(),
        Some("gz") => BufReader::new(GzDecoder::new(File::open(file).unwrap())),
        _ => unimplemented!(),
    };
    // let reader = if file.extension().unwrap() == "gz" {
    //     BufReader::new(GzDecoder::new(File::open(file).unwrap()))
    // } else {
    //     // BufReader::new(File::open(file).unwrap())
    //     unimplemented!()
    // };

    match format {
        FileFormat::TabSep => {
            for line0 in reader.lines() {
                let line = line0.unwrap();
                let kv = line.splitn(1, "\t");
                println!("{:?}", kv);
            }
        },
        _ => unimplemented! ()
    }
}

