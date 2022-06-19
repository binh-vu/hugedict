pub mod error;
pub mod rocksdb;

use ::rocksdb::Options;

use crate::rocksdb::loader::{load, FileFormat, FileType};
use anyhow::{Context, Result};
use std::{path::Path, prelude::*};

pub fn run() -> Result<()> {
    env_logger::init();

    let mut opts = Options::default();
    opts.create_if_missing(true);

    load(
        Path::new("/workspace/hugedict/testdb"),
        &opts,
        &[
            &Path::new("/workspace/hugedict/tests/resources/wdprops/art.tsv"),
            &Path::new("/workspace/hugedict/tests/resources/wdprops/human.tsv"),
            &Path::new("/workspace/hugedict/tests/resources/wdprops/e-commerce.tsv"),
        ],
        &FileFormat {
            filetype: FileType::TabSep,
            is_sorted: true,
            key: None,
            value: None,
        },
        true,
        true,
    )
    .context("unable to load files into db")?;

    Ok(())
}

pub fn main() {
    if let Err(err) = run() {
        eprintln!("Error: {:#?}", err);
        std::process::exit(1);
    }
}
