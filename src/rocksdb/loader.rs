use crate::error::HugeDictError;
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
use std::ffi::OsStr;
use std::fs;
use std::io::{BufRead, BufReader, Read};
use std::path::Path;
use std::path::PathBuf;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub enum FileType {
    // tab separated format of serialized byte key and value
    // serialized key must not contain tab character
    // serialized value must not contain newline character such as \r\n.
    #[serde(rename = "tabsep")]
    TabSep,

    // each line is a json object
    #[serde(rename = "ndjson")]
    NDJson,

    // each line is a json list of two items key and value
    #[serde(rename = "tuple2")]
    Tuple2,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct FileFormat {
    pub filetype: FileType,
    // whether the file is sorted or not.
    pub is_sorted: bool,
    // object's attribute contains the key, None if key is the object itself.
    pub key: Option<String>,
    // object's attribute contains the value, None if value is the object itself.
    pub value: Option<String>,
}

/// Load files into RocksDB
///
/// # Arguments
/// * `dbpath` - path to a RocksDB
/// * `dbopts` - options to start a RocksDB
/// * `files` - path to the files to load into RocksDB
/// * `format` - file format
/// * `compact` - compact the database after loading
pub fn load<'s>(
    dbpath: &Path,
    dbopts: &Options,
    files: &[&'s Path],
    format: &FileFormat,
    verbose: bool,
    compact: bool,
) -> Result<()> {
    let tempdir = dbpath.join("_temporary");
    fs::create_dir_all(&tempdir)?;

    info!("Creating SST files...");

    // create sst files storing in temporary directory
    let it = files.par_iter().enumerate().map(|(index, file)| {
        let sstfile = tempdir.join(format!("{}.sst", index));
        build_sst_file(dbopts, file, &sstfile, &format)?;
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

    match (&format.filetype, format.is_sorted) {
        (FileType::TabSep, false) => {
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
        (FileType::TabSep, true) => {
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
                writer.put(kv[0], kv[1])?
            }
        }
        _ => unimplemented!(),
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
