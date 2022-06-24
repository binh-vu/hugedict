pub mod error;
pub mod funcs;
pub mod macros;
pub mod rocksdb;

use pyo3::{prelude::*, types::PyList};

#[pymodule]
fn hugedict(py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.setattr("__path__", PyList::empty(py))?;

    rocksdb::python::register(py, m)?;

    Ok(())
}
