use anyhow::Result;
use rocksdb::{Options, DB};
use std::{ffi::OsStr, fs, path::Path};
use tempfile::tempdir;

use hugedict::rocksdb::loader::*;

#[test]
fn load_tabsep_unsorted() -> Result<()> {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/resources/wdprops");
    let mut files = vec![];

    for file in fs::read_dir(&dir)? {
        let path = file?.path();
        if path.extension().and_then(OsStr::to_str).unwrap_or("") != "tsv" {
            continue;
        }
        files.push(path);
    }

    let dir = tempdir()?;
    let dbpath = dir.path();

    let mut opts = Options::default();
    opts.create_if_missing(true);

    load(
        dbpath,
        &opts,
        files.as_slice(),
        &FileFormat {
            record_type: RecordType::TabSep,
            is_sorted: false,
        },
        true,
        true,
    )?;

    let db = DB::open(&opts, dbpath)?;
    assert_eq!(
        "illustrator",
        String::from_utf8(db.get("P110")?.unwrap_or(vec![]))?
    );
    assert_eq!(
        "votes received",
        String::from_utf8(db.get("P1111")?.unwrap_or(vec![]))?
    );

    Ok(())
}

#[test]
fn load_empty_file_ok() -> Result<()> {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/resources/universities");
    let mut files = vec![];

    for file in fs::read_dir(&dir)? {
        let path = file?.path();
        if path.extension().and_then(OsStr::to_str).unwrap_or("") != "tsv" {
            continue;
        }
        files.push(path);
    }

    let dir = tempdir()?;
    let dbpath = dir.path();

    let mut opts = Options::default();
    opts.create_if_missing(true);

    load(
        dbpath,
        &opts,
        files.as_slice(),
        &FileFormat {
            record_type: RecordType::TabSep,
            is_sorted: false,
        },
        true,
        true,
    )?;

    let db = DB::open(&opts, dbpath)?;
    assert_eq!(
        "university of southern california",
        String::from_utf8(db.get("usc")?.unwrap_or(vec![]))?
    );
    assert_eq!(
        "university of california, los angeles",
        String::from_utf8(db.get("ucla")?.unwrap_or(vec![]))?
    );

    Ok(())
}
