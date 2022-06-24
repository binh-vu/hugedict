use std::path::Path;

use crate::macros::def_pyfunction;

use super::{
    dict::RocksDBDict,
    loader,
    mrsw::{primary_db, stop_primary_db, SecondaryDB},
};
use pyo3::prelude::*;

use super::options::Options;
use pythonize::depythonize;

#[pyfunction]
pub fn load(
    dbpath: &str,
    dbopts: &Options,
    files: Vec<&str>,
    format: &PyAny,
    verbose: bool,
    compact: bool,
) -> PyResult<()> {
    loader::load(
        Path::new(dbpath),
        &dbopts.get_options(),
        &files.iter().map(|file| Path::new(file)).collect::<Vec<_>>(),
        &depythonize(format)?,
        verbose,
        compact,
    )?;

    Ok(())
}

pub(crate) fn register(py: Python<'_>, m: &PyModule) -> PyResult<()> {
    let submodule = PyModule::new(py, "rocksdb")?;

    def_pyfunction!(submodule, "hugedict.hugedict.rocksdb", load);
    def_pyfunction!(submodule, "hugedict.hugedict.rocksdb", primary_db);
    def_pyfunction!(submodule, "hugedict.hugedict.rocksdb", stop_primary_db);
    submodule.add_class::<Options>()?;
    submodule.add_class::<RocksDBDict>()?;
    submodule.add_class::<SecondaryDB>()?;

    m.add_submodule(submodule)?;

    py.import("sys")?
        .getattr("modules")?
        .set_item("hugedict.hugedict.rocksdb", submodule)?;

    Ok(())
}
