use std::collections::HashMap;

use pyo3::{exceptions::PyAttributeError, prelude::*, types::PyDict};

/// A general container to store attributes
#[pyclass(subclass)]
pub struct Container {
    attrs: HashMap<String, Py<PyAny>>,
}

#[pymethods]
impl Container {
    #[new]
    #[args(kwargs = "**")]
    fn new(kwargs: Option<&PyDict>) -> PyResult<Container> {
        match kwargs {
            None => Ok(Self {
                attrs: HashMap::new(),
            }),
            Some(x) => {
                let mut attrs: HashMap<String, Py<PyAny>> = HashMap::new();
                for (k, v) in x.iter() {
                    attrs.insert(k.extract()?, v.into());
                }

                Ok(Self { attrs })
            }
        }
    }

    fn __getattr__(&self, name: &str) -> PyResult<&Py<PyAny>> {
        self.attrs
            .get(name)
            .ok_or_else(|| PyAttributeError::new_err(name.to_owned()))
    }
}
