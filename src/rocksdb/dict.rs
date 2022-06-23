use crate::error::into_pyerr;

use super::options::Options;
use crate::macros::call_method;
use pyo3::{
    exceptions::PyKeyError,
    prelude::*,
    types::{PyBytes, PyLong, PyString, PyTuple},
};
use rocksdb::{self, DBRawIteratorWithThreadMode};

#[pyclass(module = "hugedict.hugedict.rocksdb", subclass)]
pub struct RocksDBDict {
    db: rocksdb::DB,
    deser_key: Py<PyAny>,
    deser_value: Py<PyAny>,
    ser_value: Py<PyAny>,
}

#[pymethods]
impl RocksDBDict {
    #[new]
    #[args(readonly = "false")]
    pub fn new(
        path: &str,
        options: &Options,
        deser_key: Py<PyAny>,
        deser_value: Py<PyAny>,
        ser_value: Py<PyAny>,
        readonly: bool,
    ) -> PyResult<Self> {
        let db = if readonly {
            rocksdb::DB::open_for_read_only(&options.get_options(), path, false)
                .map_err(into_pyerr)?
        } else {
            rocksdb::DB::open(&options.get_options(), path).map_err(into_pyerr)?
        };

        Ok(Self {
            db,
            deser_key,
            deser_value,
            ser_value,
        })
    }

    #[getter]
    fn deser_value(&self) -> PyResult<Py<PyAny>> {
        Ok(self.deser_value.clone())
    }

    #[getter]
    fn ser_value(&self) -> PyResult<Py<PyAny>> {
        Ok(self.ser_value.clone())
    }

    fn __getitem__(&self, py: Python, key: &PyAny) -> PyResult<Py<PyAny>> {
        convert_key!(self.impl_get(py ; key ; key))
    }

    fn __setitem__(&self, py: Python, key: &PyAny, value: &PyAny) -> PyResult<()> {
        convert_key!(self.impl_set(py; key; value))
    }

    fn __delitem__(&self, key: &PyAny) -> PyResult<()> {
        convert_key!(self.impl_del(;key;))
    }

    fn __iter__(slf: PyRef<'_, Self>, py: Python) -> PyResult<Py<DBKeyIterator>> {
        RocksDBDict::keys(slf, py)
    }

    fn __len__(&self) -> PyResult<usize> {
        let mut it = self.db.raw_iterator();
        let mut len = 0;

        it.seek_to_first();
        while it.valid() {
            len += 1;
            it.next();
        }

        return Ok(len);
    }

    fn __contains__(&self, key: &PyAny) -> PyResult<bool> {
        convert_key!(self.impl_contains(; key ;))
    }

    fn keys(slf: PyRef<'_, Self>, py: Python) -> PyResult<Py<DBKeyIterator>> {
        let mut ptr = extend_lifetime(Box::new(slf.db.raw_iterator()));
        ptr.as_mut().seek_to_first();
        let deser_key = slf.deser_key.clone_ref(py);
        let it = DBKeyIterator {
            db: slf.into(),
            deser_key,
            it: ptr,
        };
        Ok(Py::new(py, it)?)
    }

    fn values(slf: PyRef<'_, Self>, py: Python) -> PyResult<Py<DBValueIterator>> {
        let mut ptr = extend_lifetime(Box::new(slf.db.raw_iterator()));
        ptr.as_mut().seek_to_first();
        let deser_value = slf.deser_value.clone_ref(py);
        let it = DBValueIterator {
            db: slf.into(),
            it: ptr,
            deser_value,
        };
        Ok(Py::new(py, it)?)
    }

    fn items(slf: PyRef<'_, Self>, py: Python) -> PyResult<Py<DBItemIterator>> {
        let mut ptr = extend_lifetime(Box::new(slf.db.raw_iterator()));
        ptr.as_mut().seek_to_first();
        let deser_key = slf.deser_key.clone_ref(py);
        let deser_value = slf.deser_value.clone_ref(py);
        let it = DBItemIterator {
            db: slf.into(),
            it: ptr,
            deser_key,
            deser_value,
        };
        Ok(Py::new(py, it)?)
    }

    fn get(&self, py: Python, key: &PyAny, default: &PyAny) -> PyResult<Py<PyAny>> {
        convert_key!(self.impl_get_default(py ; key ; default))
    }

    fn pop(&self, py: Python, key: &PyAny, default: &PyAny) -> PyResult<Py<PyAny>> {
        convert_key!(self.impl_pop(py ; key ; default))
    }

    fn cache(slf: PyRef<'_, Self>, py: Python) -> PyResult<Py<PyAny>> {
        let this: Py<RocksDBDict> = slf.into();
        Ok(PyModule::import(py, "hugedict.cachedict")?
            .getattr("CacheDict")?
            .call1(PyTuple::new(py, [this]))?
            .into())
    }

    fn _put(&self, key: &PyBytes, value: &PyBytes) -> PyResult<()> {
        self.db
            .put(key.as_bytes(), value.as_bytes())
            .map_err(into_pyerr)
    }

    fn compact(&self) -> PyResult<()> {
        self.db.compact_range::<&[u8], &[u8]>(None, None);
        Ok(())
    }
}

impl RocksDBDict {
    #[inline]
    fn impl_get<K: AsRef<[u8]>>(
        &self,
        py: Python,
        key: K,
        original_key: &PyAny,
    ) -> PyResult<Py<PyAny>> {
        match self.db.get_pinned(key.as_ref()).map_err(into_pyerr)? {
            None => Err(PyKeyError::new_err(PyObject::from(original_key))),
            Some(value) => Ok(pydeser_value(value, &self.deser_value, py)?),
        }
    }

    #[inline]
    fn impl_set<K: AsRef<[u8]>>(&self, py: Python, key: K, value: &PyAny) -> PyResult<()> {
        let k = key.as_ref();
        let v = self.ser_value.call1(py, PyTuple::new(py, [value]))?;
        let vb = v.as_ref(py).downcast::<PyBytes>()?.as_bytes();
        Ok(self.db.put(k, vb).map_err(into_pyerr)?)
    }

    #[inline]
    fn impl_del<K: AsRef<[u8]>>(&self, key: K) -> PyResult<()> {
        Ok(self.db.delete(key.as_ref()).map_err(into_pyerr)?)
    }

    #[inline]
    fn impl_contains<K: AsRef<[u8]>>(&self, key: K) -> PyResult<bool> {
        Ok(self
            .db
            .get_pinned(key.as_ref())
            .map_err(into_pyerr)?
            .is_some())
    }

    #[inline]
    fn impl_get_default<K: AsRef<[u8]>>(
        &self,
        py: Python,
        key: K,
        default: &PyAny,
    ) -> PyResult<Py<PyAny>> {
        match self.db.get_pinned(key.as_ref()).map_err(into_pyerr)? {
            None => Ok(default.into()),
            Some(value) => Ok(pydeser_value(value, &self.deser_value, py)?),
        }
    }

    #[inline]
    fn impl_pop<K: AsRef<[u8]>>(&self, py: Python, key: K, default: &PyAny) -> PyResult<Py<PyAny>> {
        let k = key.as_ref();
        match self.db.get_pinned(k).map_err(into_pyerr)? {
            None => Ok(default.into()),
            Some(value) => {
                let res = Ok(pydeser_value(value, &self.deser_value, py)?);
                self.db.delete(k).map_err(into_pyerr)?;
                res
            }
        }
    }
}

/// Convert key (in python) to bytes
#[inline]
pub fn pyser_key<'s>(obj: &'s PyAny) -> PyResult<Box<dyn AsRef<[u8]> + 's>> {
    if let Ok(k) = obj.downcast::<PyString>() {
        return Ok(Box::new(k.to_str()?.as_bytes()));
    }

    if let Ok(k) = obj.downcast::<PyBytes>() {
        return Ok(Box::new(k.as_bytes()));
    }

    if let Ok(k) = obj.downcast::<PyLong>() {
        return Ok(Box::new(k.extract::<i64>()?.to_le_bytes()));
    }

    if obj.is_none() {
        return Ok(Box::new([]));
    }

    Err(PyKeyError::new_err(format!(
        "Key must be a string, bytes, integer or None. Got type: {}",
        obj.get_type().name()?
    )))
}

/// Converting the key from PyAny to &[u8] to use with RocksDB. Hence, we are
/// using a macro to avoid typing the same extraction every time we need to use a key.
///
/// Note: this can make the code much bigger. There is a new function pyser_key that
/// return Box<dyn AsRef<[u8]>>.
macro_rules! convert_key {
    ($self:ident.$fn:ident ( $($args0:expr),* ; $key:ident ; $($args1:expr),* ) ) => {{
        if let Ok(k) = $key.downcast::<PyString>() {
            return call_method!( $self.$fn ( $($args0)* ; k.to_str()?.as_bytes() ; $($args1)* ));
        }

        if let Ok(k) = $key.downcast::<PyBytes>() {
            return call_method!( $self.$fn($($args0)* ; k.as_bytes() ; $($args1)*));
        }

        if let Ok(k) = $key.downcast::<PyLong>() {
            return call_method!( $self.$fn($($args0)* ; &k.extract::<i64>()?.to_le_bytes() ; $($args1)*));
        }

        if $key.is_none() {
            return call_method!( $self.$fn ( $($args0)* ; &[] ; $($args1)* ));
        }

        Err(PyKeyError::new_err(format!("Key must be a string, bytes, integer or None. Got type: {}", $key.get_type().name()?)))
    }};
}

pub(crate) use convert_key;

/// Deserialize a value from bytes without copying it twice.
#[inline]
pub fn pydeser_value<V: AsRef<[u8]>>(val: V, deser: &Py<PyAny>, py: Python) -> PyResult<Py<PyAny>> {
    let v = unsafe {
        let p = val.as_ref();
        let mv = pyo3::ffi::PyMemoryView_FromMemory(
            p.as_ptr() as *mut i8,
            p.len() as isize,
            pyo3::ffi::PyBUF_READ,
        );
        PyObject::from_owned_ptr(py, mv)
    };

    deser.call1(py, PyTuple::new(py, [v]))
}

/// Unsafe! Extending the lifetime of rocksdb raw iterator to static.
///
/// To ensure the lifetime of the iterator is valid, it must be use together with a reference of DB instance, so that if
/// the struct holding an DB instance is dropped, the DB instance would be dropped.
/// More information can see DBKeyiterator.
/// Note: since the iterator after extending loss the connection with the DB instance, you must ensure
/// the iterator is dropped before the DB instance (the default dropped order is the declaration order).
pub fn extend_lifetime(
    x: Box<DBRawIteratorWithThreadMode<'_, rocksdb::DB>>,
) -> Box<DBRawIteratorWithThreadMode<'static, rocksdb::DB>> {
    unsafe {
        Box::from_raw(
            Box::into_raw(x) as usize as *mut DBRawIteratorWithThreadMode<'static, rocksdb::DB>
        )
    }
}

/// Careful with the declaration order! The iterator must be declared before the DB instance to ensure it is dropped before.
#[pyclass(module = "hugedict.hugedict.rocksdb")]
#[allow(unused)]
struct DBKeyIterator {
    it: Box<DBRawIteratorWithThreadMode<'static, rocksdb::DB>>,
    deser_key: Py<PyAny>,
    db: Py<RocksDBDict>,
}

#[pymethods]
impl DBKeyIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>, py: Python) -> PyResult<Option<PyObject>> {
        match slf.it.key() {
            None => Ok(None),
            Some(k) => {
                let next = pydeser_value(k, &slf.deser_key, py)?;
                slf.it.next();
                return Ok(Some(next));
            }
        }
    }
}

#[pyclass(module = "hugedict.hugedict.rocksdb")]
#[allow(unused)]
struct DBValueIterator {
    it: Box<DBRawIteratorWithThreadMode<'static, rocksdb::DB>>,
    deser_value: Py<PyAny>,
    db: Py<RocksDBDict>,
}

#[pymethods]
impl DBValueIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>, py: Python) -> PyResult<Option<PyObject>> {
        match slf.it.value() {
            None => Ok(None),
            Some(v) => {
                let next = pydeser_value(v, &slf.deser_value, py)?;
                slf.it.next();
                Ok(Some(next))
            }
        }
    }
}

#[pyclass(module = "hugedict.hugedict.rocksdb")]
#[allow(unused)]
struct DBItemIterator {
    it: Box<DBRawIteratorWithThreadMode<'static, rocksdb::DB>>,
    deser_key: Py<PyAny>,
    deser_value: Py<PyAny>,
    db: Py<RocksDBDict>,
}

#[pymethods]
impl DBItemIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>, py: Python) -> PyResult<Option<(PyObject, PyObject)>> {
        match (slf.it.key(), slf.it.value()) {
            (None, None) => Ok(None),
            (Some(k), Some(v)) => {
                let key = pydeser_value(k, &slf.deser_key, py)?;
                let value = pydeser_value(v, &slf.deser_value, py)?;
                slf.it.next();
                Ok(Some((key, value)))
            }
            _ => unreachable!(),
        }
    }
}
