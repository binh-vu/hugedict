use crate::{container::Container, macros::def_pyfunction};

use super::options::{CompressionOptions, Options};
use super::{
    dict::RocksDBDict,
    loader::{py_build_sst_file, py_ingest_sst_files, py_load},
    mrsw::{primary_db, stop_primary_db, SecondaryDB},
};
use pyo3::prelude::*;
use pyo3::type_object::PyTypeObject;

pub(crate) fn register(py: Python<'_>, m: &PyModule) -> PyResult<()> {
    let submodule = PyModule::new(py, "rocksdb")?;

    def_pyfunction!(submodule, "hugedict.hugedict.rocksdb", py_load);
    def_pyfunction!(submodule, "hugedict.hugedict.rocksdb", py_build_sst_file);
    def_pyfunction!(submodule, "hugedict.hugedict.rocksdb", py_ingest_sst_files);
    def_pyfunction!(submodule, "hugedict.hugedict.rocksdb", primary_db);
    def_pyfunction!(submodule, "hugedict.hugedict.rocksdb", stop_primary_db);

    submodule.add_class::<Options>()?;
    submodule.add_class::<CompressionOptions>()?;
    submodule.add_class::<RocksDBDict>()?;
    submodule.add_class::<SecondaryDB>()?;
    submodule.add("PrefixExtractor", Container::type_object(py))?;
    submodule.add("fixed_prefix", Container::type_object(py))?;
    submodule.add("fixed_prefix_alike", Container::type_object(py))?;

    m.add_submodule(submodule)?;

    py.import("sys")?
        .getattr("modules")?
        .set_item("hugedict.hugedict.rocksdb", submodule)?;

    Ok(())
}
