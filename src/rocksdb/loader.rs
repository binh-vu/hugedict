use super::options::Options;
use crate::error::{into_pyerr, HugeDictError};
use crate::funcs::itemgetter::{itemgetter, ItemGetter};
use anyhow::Result;
use bzip2::read::MultiBzDecoder;
use flate2::read::GzDecoder;
use indicatif::{ParallelProgressIterator, ProgressBar};
use log::info;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyTuple};
use pythonize::depythonize;
use rayon::prelude::*;
use rocksdb::{
    DBWithThreadMode, IngestExternalFileOptions, Options as RocksDBOptions, SingleThreaded,
    SstFileWriter,
};
use serde::{Deserialize, Serialize};
use serde_json;
use std::ffi::OsStr;
use std::fs;
use std::io::{BufRead, BufReader, ErrorKind, Read};
use std::path::Path;
use std::path::PathBuf;

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(tag = "type")]
pub enum RecordType {
    // a binary key-value format that:
    // for each pair of key-value, has the following format
    // <key length><key><value length><value>
    #[serde(rename = "bin_kv")]
    BinaryKeyValue,

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

/// Load files into RocksDB by building SST files and ingesting them.
///
/// Raised exception when no sst files are created (i.e., no input files).
///
/// # Arguments
/// * `dbpath` - path to a RocksDB
/// * `dbopts` - options to start a RocksDB
/// * `files` - path to the files to load into RocksDB
/// * `format` - file format
/// * `compact` - compact the database after loading
pub fn load<P: AsRef<Path> + Sync>(
    dbpath: &Path,
    dbopts: &RocksDBOptions,
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
    let it = files
        .par_iter()
        .enumerate()
        .map(|(index, file)| {
            let sstfile = tempdir.join(format!("{}.sst", index));
            if build_sst_file(dbopts, file.as_ref(), &sstfile, &format)? {
                Ok(Some(sstfile))
            } else {
                Ok(None)
            }
        })
        .filter(|r| r.is_ok() && r.as_ref().unwrap().is_some())
        .map(|r| match r {
            Ok(path) => Ok(path.unwrap()),
            Err(e) => Err(e),
        });

    let sst_files_: Result<Vec<PathBuf>> = if verbose {
        let pb = ProgressBar::new(files.len() as u64);
        pb.set_message("Building SST Files");

        it.progress_with(pb).collect()
    } else {
        it.collect()
    };
    let sst_files = sst_files_?;

    if sst_files.len() == 0 {
        return Err(HugeDictError::NoFiles.into());
    }

    // ingest the sst files into RocksDB
    info!("Ingesting SST files...");
    let mut ingest_opts = IngestExternalFileOptions::default();
    ingest_opts.set_move_files(true);
    let db: DBWithThreadMode<SingleThreaded> = DBWithThreadMode::open(dbopts, dbpath)?;
    db.ingest_external_file_opts(&ingest_opts, sst_files)?;

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
    dbopts: &RocksDBOptions,
    infile: &Path,
    outfile: &Path,
    format: &FileFormat,
) -> Result<bool> {
    let stream: Box<dyn Read> = match infile.extension().and_then(OsStr::to_str) {
        Some("gz") => Box::new(GzDecoder::new(fs::File::open(infile)?)),
        Some("bz2") => Box::new(MultiBzDecoder::new(fs::File::open(infile)?)),
        _ => Box::new(fs::File::open(infile)?),
    };
    let mut reader = BufReader::new(stream);
    let mut has_record = false;

    let mut writer = SstFileWriter::create(dbopts);
    writer.open(outfile)?;

    match (&format.record_type, format.is_sorted) {
        (RecordType::BinaryKeyValue, false) => {
            let mut kvs: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();
            let mut num_buf = [0u8; 8];
            let mut buf: Vec<u8> = Vec::with_capacity(1024);

            loop {
                let mut size = read_binary_format(&mut reader, &mut num_buf, &mut buf, format)?;
                if size == -1 {
                    break;
                }
                let k: Vec<u8> = buf[..(size as usize)].into();
                size = read_binary_format(&mut reader, &mut num_buf, &mut buf, format)?;
                if size == -1 {
                    return Err(HugeDictError::FormatError {
                        format: format.clone(),
                        content: "file end before finish reading a value".to_owned(),
                    }
                    .into());
                }
                let v: Vec<u8> = buf[..size as usize].into();
                kvs.push((k, v));
            }

            kvs.sort_unstable_by(|kv1, kv2| kv1.0.cmp(&kv2.0));
            has_record = kvs.len() > 0;
            for (k, v) in kvs.iter() {
                writer.put(k, v)?;
            }
        }
        (RecordType::BinaryKeyValue, true) => {
            let mut num_buf = [0u8; 8];
            let mut buf: Vec<u8> = Vec::with_capacity(1024);

            loop {
                let mut size = read_binary_format(&mut reader, &mut num_buf, &mut buf, format)?;
                if size == -1 {
                    break;
                }
                let k: Vec<u8> = buf[..(size as usize)].into();
                size = read_binary_format(&mut reader, &mut num_buf, &mut buf, format)?;
                if size == -1 {
                    return Err(HugeDictError::FormatError {
                        format: format.clone(),
                        content: "file end before finish reading a value".to_owned(),
                    }
                    .into());
                }
                let v: Vec<u8> = buf[..size as usize].into();
                writer.put(k, v)?;
                has_record = true;
            }
        }
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
            has_record = kvs.len() > 0;
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
                has_record = true;
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
            has_record = kvs.len() > 0;
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
                has_record = true;
            }
        }
        (RecordType::Tuple2 { key, value }, false) => {
            let mut kvs: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();
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
                let v: Vec<u8> = match valuegetter.get_item(&kv.1) {
                    None => return Err(HugeDictError::ValueError(valueerror_msg.clone()).into()),
                    Some(o) => match o {
                        serde_json::Value::String(s) => s.as_bytes().to_vec(),
                        serde_json::Value::Bool(s) => vec![*s as u8],
                        // always use little endian so that the databases can move between platform without
                        // rebuilt
                        serde_json::Value::Number(s) if s.is_f64() => {
                            s.as_f64().unwrap().to_le_bytes().to_vec()
                        }
                        serde_json::Value::Number(s) if s.is_i64() => {
                            s.as_f64().unwrap().to_le_bytes().to_vec()
                        }
                        serde_json::Value::Number(s) if s.is_u64() => {
                            s.as_u64().unwrap().to_le_bytes().to_vec()
                        }
                        serde_json::Value::Null => vec![],
                        _ => serde_json::to_string(o)
                            .expect("No bug in serde_json package")
                            .as_bytes()
                            .to_vec(),
                    },
                };

                kvs.push((k, v));
                buffer.clear();
            }

            kvs.sort_unstable_by(|kv1, kv2| kv1.0.cmp(&kv2.0));
            has_record = kvs.len() > 0;
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
                let v: Vec<u8> = match valuegetter.get_item(&kv.1) {
                    None => return Err(HugeDictError::ValueError(valueerror_msg.clone()).into()),
                    Some(o) => match o {
                        serde_json::Value::String(s) => s.as_bytes().to_vec(),
                        serde_json::Value::Bool(s) => vec![*s as u8],
                        // always use little endian so that the databases can move between platform without
                        // rebuilt
                        serde_json::Value::Number(s) if s.is_f64() => {
                            s.as_f64().unwrap().to_le_bytes().to_vec()
                        }
                        serde_json::Value::Number(s) if s.is_i64() => {
                            s.as_f64().unwrap().to_le_bytes().to_vec()
                        }
                        serde_json::Value::Number(s) if s.is_u64() => {
                            s.as_u64().unwrap().to_le_bytes().to_vec()
                        }
                        serde_json::Value::Null => vec![],
                        _ => serde_json::to_string(o)
                            .expect("No bug in serde_json package")
                            .as_bytes()
                            .to_vec(),
                    },
                };

                writer.put(k, v)?;
                buffer.clear();
                has_record = true;
            }
        }
    }

    if has_record {
        writer.finish()?;
    } else {
        fs::remove_file(outfile)?;
    }
    Ok(has_record)
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

#[inline]
fn read_binary_format<'s>(
    reader: &'s mut BufReader<Box<dyn Read>>,
    num_buf: &mut [u8; 8],
    buf: &mut Vec<u8>,
    format: &FileFormat,
) -> Result<i64> {
    let size = match reader.read_exact(num_buf) {
        Ok(()) => u64::from_le_bytes(num_buf.clone()),
        Err(error) => {
            if error.kind() == ErrorKind::UnexpectedEof {
                return Ok(-1);
            }

            return Err(HugeDictError::FormatError {
                format: format.clone(),
                content: "expect an u64 number of 8 bytes to specify the key/value size".to_owned(),
            }
            .into());
        }
    };

    buf.clear();

    let nread = reader.take(size).read_to_end(buf)?;
    if (nread as u64) != size {
        return Err(HugeDictError::FormatError {
            format: format.clone(),
            content: format!(
                "file end before finish reading a key/value of {} bytes",
                size
            ),
        }
        .into());
    }

    Ok(size as i64)
}

#[pyfunction(name = "load")]
pub fn py_load(
    dbpath: &str,
    dbopts: &Options,
    files: Vec<&str>,
    format: &PyAny,
    verbose: bool,
    compact: bool,
) -> PyResult<()> {
    load(
        Path::new(dbpath),
        &dbopts.get_options(),
        &files.iter().map(|file| Path::new(file)).collect::<Vec<_>>(),
        &depythonize(format)?,
        verbose,
        compact,
    )?;

    Ok(())
}

#[pyfunction(name = "build_sst_file")]
pub fn py_build_sst_file(
    dbopts: &Options,
    outfile: &str,
    input_generator: &PyAny,
) -> PyResult<bool> {
    let opts = dbopts.get_options();
    let mut writer = SstFileWriter::create(&opts);
    let mut has_record = false;
    writer.open(outfile).map_err(into_pyerr)?;

    loop {
        let output = input_generator.call0()?;
        if output.is_none() {
            break;
        }

        let kv = output.downcast::<PyTuple>()?;
        let k = kv.get_item(0)?.downcast::<PyBytes>()?;
        let v = kv.get_item(1)?.downcast::<PyBytes>()?;

        writer.put(k.as_bytes(), v.as_bytes()).map_err(into_pyerr)?;
        has_record = true;
    }

    if has_record {
        writer.finish().map_err(into_pyerr)?;
    } else {
        fs::remove_file(outfile)?;
    }
    Ok(has_record)
}

#[pyfunction(name = "ingest_sst_files")]
pub fn py_ingest_sst_files(
    dbpath: &str,
    dbopts: &Options,
    sst_files: Vec<String>,
    compact: bool,
) -> PyResult<()> {
    // ingest the sst files into RocksDB
    info!("Ingesting SST files...");
    let opts = dbopts.get_options();
    let mut ingest_opts = IngestExternalFileOptions::default();
    ingest_opts.set_move_files(true);
    let db: DBWithThreadMode<SingleThreaded> =
        DBWithThreadMode::open(&opts, dbpath).map_err(into_pyerr)?;
    db.ingest_external_file_opts(&ingest_opts, sst_files)
        .map_err(into_pyerr)?;

    // compact the database
    if compact {
        info!("Compacting database...");
        db.compact_range::<&[u8], &[u8]>(None, None);
    }

    drop(db);
    Ok(())
}
