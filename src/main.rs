pub mod rocksdb;

use ::rocksdb::Options;

use crate::rocksdb::loader::{load, FileFormat};
use std::{prelude::*, path::Path};

pub fn main() {
    println!("Hello, world!");
    load(Path::new("./testdb"), &Options::default(), &[
        &Path::new("/Users/rook/workspace/hugedict/tests/resources/wdprops/art.tsv"),
        &Path::new("/Users/rook/workspace/hugedict/tests/resources/wdprops/human.tsv"),
        &Path::new("/Users/rook/workspace/hugedict/tests/resources/wdprops/e-commerce.tsv"),
    ], &FileFormat::TabSep, true);
}