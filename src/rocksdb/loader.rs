use crate::error::HugeDictError;
use crate::funcs::itemgetter::{itemgetter, ItemGetter};
use anyhow::Result;
use bzip2::read::MultiBzDecoder;
use flate2::read::GzDecoder;
use indicatif::{ParallelProgressIterator, ProgressBar};
use log::info;
use rayon::prelude::*;
use rocksdb::{
    DBWithThreadMode, IngestExternalFileOptions, Options, SingleThreaded, SstFileWriter,
};
use serde::{Deserialize, Serialize};
use serde_json;
use std::ffi::OsStr;
use std::fs;
use std::io::{BufRead, BufReader, Read};
use std::path::Path;
use std::path::PathBuf;

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(tag = "type")]
pub enum RecordType {
    // tab separated format of serialized byte key and value
    // serialized key must not contain tab character
    // serialized value must not contain newline character such as \r\n.
    #[serde(rename = "tabsep")]
    TabSep,

    // each line is a json list of two items key and value
    #[serde(rename = "tuple2")]
    Tuple2 {
        // object's attribute contains the key, None if key is the object itself.
        key: Option<String>,
        // object's attribute contains the value, None if value is the object itself.
        value: Option<String>,
    },

    // each line is a json object
    #[serde(rename = "ndjson")]
    NDJson {
        // object's attribute contains the key, None if key is the object itself.
        key: String,
        // object's attribute contains the value, None if value is the serialized object itself.
        value: Option<String>,
    },
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct FileFormat {
    // record type including function to extract key and value a record
    pub record_type: RecordType,
    // whether the file is sorted or not.
    pub is_sorted: bool,
}

pub struct Fn {}

/// Load files into RocksDB by building SST files and ingesting them
///
/// # Arguments
/// * `dbpath` - path to a RocksDB
/// * `dbopts` - options to start a RocksDB
/// * `files` - path to the files to load into RocksDB
/// * `format` - file format
/// * `compact` - compact the database after loading
pub fn load<P: AsRef<Path> + Sync>(
    dbpath: &Path,
    dbopts: &Options,
    files: &[P],
    format: &FileFormat,
    verbose: bool,
    compact: bool,
) -> Result<()> {
    if files.len() == 0 {
        return Err(HugeDictError::NoFiles.into());
    }

    let tempdir = dbpath.join("_temporary");
    fs::create_dir_all(&tempdir)?;

    info!("Creating SST files...");

    // create sst files storing in temporary directory
    let it = files.par_iter().enumerate().map(|(index, file)| {
        let sstfile = tempdir.join(format!("{}.sst", index));
        build_sst_file(dbopts, file.as_ref(), &sstfile, &format)?;
        Ok(sstfile)
    });

    let sst_files: Result<Vec<PathBuf>> = if verbose {
        let pb = ProgressBar::new(files.len() as u64);
        pb.set_message("Building SST Files");

        it.progress_with(pb).collect()
    } else {
        it.collect()
    };

    // ingest the sst files into RocksDB
    info!("Ingesting SST files...");
    let mut ingest_opts = IngestExternalFileOptions::default();
    ingest_opts.set_move_files(true);
    let db: DBWithThreadMode<SingleThreaded> = DBWithThreadMode::open(dbopts, dbpath)?;
    db.ingest_external_file_opts(&ingest_opts, sst_files?)?;

    // compact the database
    if compact {
        info!("Compacting database...");
        db.compact_range::<&[u8], &[u8]>(None, None);
    }

    // remove temporary directory and close the database
    info!("Clean up...");
    fs::remove_dir(tempdir)?;
    drop(db);

    Ok(())
}

pub fn build_sst_file(
    dbopts: &Options,
    infile: &Path,
    outfile: &Path,
    format: &FileFormat,
) -> Result<()> {
    let stream: Box<dyn Read> = match infile.extension().and_then(OsStr::to_str) {
        Some("gz") => Box::new(GzDecoder::new(fs::File::open(infile)?)),
        Some("bz2") => Box::new(MultiBzDecoder::new(fs::File::open(infile)?)),
        _ => Box::new(fs::File::open(infile)?),
    };
    let mut reader = BufReader::new(stream);

    let mut writer = SstFileWriter::create(dbopts);
    writer.open(outfile)?;

    match (&format.record_type, format.is_sorted) {
        (RecordType::TabSep, false) => {
            let mut kvs: Vec<(String, String)> = Vec::new();
            let mut buffer = String::new();

            while reader.read_line(&mut buffer)? > 0 {
                trim_newline(&mut buffer);
                let kv: Vec<&str> = buffer.splitn(2, "\t").collect();
                if kv.len() != 2 {
                    return Err(HugeDictError::FormatError {
                        format: format.clone(),
                        content: buffer.clone(),
                    }
                    .into());
                }
                kvs.push((kv[0].into(), kv[1].into()));
                buffer.clear();
            }

            kvs.sort_unstable_by(|kv1, kv2| kv1.0.cmp(&kv2.0));
            for (k, v) in kvs.iter() {
                writer.put(k, v)?;
            }
        }
        (RecordType::TabSep, true) => {
            let mut buffer = String::new();
            while reader.read_line(&mut buffer)? > 0 {
                trim_newline(&mut buffer);
                let kv: Vec<&str> = buffer.splitn(2, "\t").collect();
                if kv.len() != 2 {
                    return Err(HugeDictError::FormatError {
                        format: format.clone(),
                        content: buffer.clone(),
                    }
                    .into());
                }
                writer.put(kv[0], kv[1])?;
                buffer.clear();
            }
        }
        (RecordType::NDJson { key, value }, false) => {
            let mut kvs: Vec<(Vec<u8>, String)> = Vec::new();
            let mut buffer = String::new();

            let keygetter = itemgetter(Some(key));
            let valuegetter = itemgetter(value.as_ref());
            let keyerror_msg = format!("{:?} not found", key);
            let valueerror_msg = format!("{:?} not found", value);

            while reader.read_line(&mut buffer)? > 0 {
                let object: serde_json::Value = serde_json::from_str(&buffer)?;
                let k = extract_key(keygetter.as_ref(), &keyerror_msg, &object)?
                    .as_ref()
                    .as_ref()
                    .into();
                let v: String = match &value {
                    None => {
                        trim_newline(&mut buffer);
                        buffer.clone()
                    }
                    Some(_) => match valuegetter.get_item(&object) {
                        None => {
                            return Err(HugeDictError::ValueError(valueerror_msg.clone()).into())
                        }
                        Some(o) => serde_json::to_string(o).expect("No bug in serde_json package"),
                    },
                };

                kvs.push((k, v));
                buffer.clear();
            }

            kvs.sort_unstable_by(|kv1, kv2| kv1.0.cmp(&kv2.0));
            for (k, v) in kvs.iter() {
                writer.put(k, v)?;
            }
        }
        (RecordType::NDJson { key, value }, true) => {
            let mut buffer = String::new();
            let keygetter = itemgetter(Some(key));
            let valuegetter = itemgetter(value.as_ref());
            let keyerror_msg = format!("{:?} not found", key);
            let valueerror_msg = format!("{:?} not found", value);

            while reader.read_line(&mut buffer)? > 0 {
                let object: serde_json::Value = serde_json::from_str(&buffer)?;
                let k: Vec<u8> = extract_key(keygetter.as_ref(), &keyerror_msg, &object)?
                    .as_ref()
                    .as_ref()
                    .into();
                match &value {
                    None => {
                        trim_newline(&mut buffer);
                        writer.put(k, &buffer)?;
                    }
                    Some(_) => match valuegetter.get_item(&object) {
                        None => {
                            return Err(HugeDictError::ValueError(valueerror_msg.clone()).into());
                        }
                        Some(o) => {
                            writer.put(
                                k,
                                serde_json::to_string(o).expect("No bug in serde_json package"),
                            )?;
                        }
                    },
                };

                buffer.clear();
            }
        }
        (RecordType::Tuple2 { key, value }, false) => {
            let mut kvs: Vec<(Vec<u8>, String)> = Vec::new();
            let mut buffer = String::new();

            let keygetter = itemgetter(key.as_ref());
            let valuegetter = itemgetter(value.as_ref());
            let keyerror_msg = format!("{:?} not found", key);
            let valueerror_msg = format!("{:?} not found", value);

            while reader.read_line(&mut buffer)? > 0 {
                let kv: (serde_json::Value, serde_json::Value) = serde_json::from_str(&buffer)?;
                let k = extract_key(keygetter.as_ref(), &keyerror_msg, &kv.0)?
                    .as_ref()
                    .as_ref()
                    .into();
                let v: String = match valuegetter.get_item(&kv.1) {
                    None => return Err(HugeDictError::ValueError(valueerror_msg.clone()).into()),
                    Some(o) => serde_json::to_string(o).expect("No bug in serde_json package"),
                };

                kvs.push((k, v));
                buffer.clear();
            }

            kvs.sort_unstable_by(|kv1, kv2| kv1.0.cmp(&kv2.0));
            for (k, v) in kvs.iter() {
                writer.put(k, v)?;
            }
        }
        (RecordType::Tuple2 { key, value }, true) => {
            let mut buffer = String::new();

            let keygetter = itemgetter(key.as_ref());
            let valuegetter = itemgetter(value.as_ref());
            let keyerror_msg = format!("{:?} not found", key);
            let valueerror_msg = format!("{:?} not found", value);

            while reader.read_line(&mut buffer)? > 0 {
                let kv: (serde_json::Value, serde_json::Value) = serde_json::from_str(&buffer)?;
                let k: Vec<u8> = extract_key(keygetter.as_ref(), &keyerror_msg, &kv.0)?
                    .as_ref()
                    .as_ref()
                    .into();
                let v: String = match valuegetter.get_item(&kv.1) {
                    None => return Err(HugeDictError::ValueError(valueerror_msg.clone()).into()),
                    Some(o) => serde_json::to_string(o).expect("No bug in serde_json package"),
                };

                writer.put(k, v)?;
                buffer.clear();
            }
        }
    }

    writer.finish()?;

    Ok(())
}

#[inline]
fn trim_newline(buffer: &mut String) {
    if buffer.ends_with("\n") {
        buffer.pop();
        if buffer.ends_with("\r") {
            buffer.pop();
        }
    }
}

#[inline]
fn extract_key<'s>(
    keygetter: &dyn ItemGetter<serde_json::Value, serde_json::Value>,
    keyerror_msg: &str,
    object: &'s serde_json::Value,
) -> Result<Box<dyn AsRef<[u8]> + 's>> {
    let k: Box<dyn AsRef<[u8]>> = match keygetter.get_item(object) {
        Some(serde_json::Value::String(k)) => Box::new(k.as_bytes()),
        Some(serde_json::Value::Number(k)) => Box::new(
            k.as_i64()
                .ok_or_else(|| {
                    HugeDictError::ValueError(format!(
                        "Key must either be string or integer. Get: {:?}",
                        k
                    ))
                })?
                .to_le_bytes(),
        ),
        None => return Err(HugeDictError::KeyError(keyerror_msg.to_owned()).into()),
        value => {
            return Err(HugeDictError::ValueError(format!(
                "Key must either be string or integer. Get: {:?}",
                value
            ))
            .into())
        }
    };
    Ok(k)
}
