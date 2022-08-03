pub mod container;
pub mod error;
pub mod funcs;
pub mod macros;
pub mod rocksdb;

use pyo3::{prelude::*, types::PyList};

#[pyfunction]
pub fn init_env_logger() -> PyResult<()> {
    env_logger::init();
    Ok(())
}

#[pymodule]
fn hugedict(py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.setattr("__path__", PyList::empty(py))?;

    m.add_function(wrap_pyfunction!(init_env_logger, m)?)?;
    rocksdb::python::register(py, m)?;

    Ok(())
}
