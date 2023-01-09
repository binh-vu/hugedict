use crate::error::into_pyerr;

use super::options::Options;
use crate::macros::call_method;
use pyo3::{
    exceptions::{PyKeyError, PyValueError},
    prelude::*,
    types::{PyBytes, PyLong, PyString, PyTuple},
};
use rocksdb::{self, DBIteratorWithThreadMode, DBRawIteratorWithThreadMode};

#[pyclass(module = "hugedict.hugedict.rocksdb", subclass)]
pub struct RocksDBDict {
    db: rocksdb::DB,
    options: Options,
    deser_key: Py<PyAny>,
    deser_value: Py<PyAny>,
    ser_value: Py<PyAny>,
}

#[pymethods]
impl RocksDBDict {
    #[new]
    #[args(readonly = "false", secondary_mode = "false", secondary_path = "None")]
    pub fn new(
        path: &str,
        options: &Options,
        deser_key: Py<PyAny>,
        deser_value: Py<PyAny>,
        ser_value: Py<PyAny>,
        readonly: bool,
        secondary_mode: bool,
        secondary_path: Option<&str>,
    ) -> PyResult<Self> {
        let db = if readonly {
            rocksdb::DB::open_for_read_only(&options.get_options(), path, false)
                .map_err(into_pyerr)?
        } else {
            if secondary_mode {
                rocksdb::DB::open_as_secondary(
                    &options.get_options(),
                    path,
                    secondary_path.ok_or_else(|| {
                        PyValueError::new_err(
                            "secondary path must not be None when secondary_mode is True",
                        )
                    })?,
                )
                .map_err(into_pyerr)?
            } else {
                rocksdb::DB::open(&options.get_options(), path).map_err(into_pyerr)?
            }
        };

        Ok(Self {
            db,
            options: options.clone(),
            deser_key,
            deser_value,
            ser_value,
        })
    }

    #[getter]
    fn options(&self) -> PyResult<Options> {
        Ok(self.options.clone())
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
        let mut ptr = extend_lifetime_raw_it(Box::new(slf.db.raw_iterator()));
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
        let mut ptr = extend_lifetime_raw_it(Box::new(slf.db.raw_iterator()));
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
        let mut ptr = extend_lifetime_raw_it(Box::new(slf.db.raw_iterator()));
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

    #[args(default = "None")]
    fn get(&self, py: Python, key: &PyAny, default: Option<Py<PyAny>>) -> PyResult<Py<PyAny>> {
        let dft = default.unwrap_or(py.None());
        convert_key!(self.impl_get_default(py ; key ; dft))
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

    fn update_cache(slf: PyRef<'_, Self>, py: Python, obj: &PyAny) -> PyResult<Py<PyAny>> {
        let this: Py<RocksDBDict> = slf.into();
        let cache_dict = PyModule::import(py, "hugedict.cachedict")?
            .getattr("CacheDict")?
            .call1(PyTuple::new(py, [this]))?;

        cache_dict.call_method1("update_cache", PyTuple::new(py, [obj]))?;
        Ok(cache_dict.into())
    }

    fn _put(&self, key: &PyBytes, value: &PyBytes) -> PyResult<()> {
        self.db
            .put(key.as_bytes(), value.as_bytes())
            .map_err(into_pyerr)
    }

    fn _get(&self, py: Python, key: &PyBytes) -> PyResult<Py<PyBytes>> {
        match self.db.get_pinned(key.as_bytes()).map_err(into_pyerr)? {
            None => Err(PyKeyError::new_err(PyObject::from(key))),
            Some(value) => Ok(PyBytes::new(py, value.as_ref()).into()),
        }
    }

    fn _multi_get(&self, py: Python, keys: Vec<&PyBytes>) -> PyResult<Vec<Option<Py<PyBytes>>>> {
        let mut values = Vec::with_capacity(keys.len());
        let it = keys.into_iter().map(|k| k.as_bytes());

        for item in self.db.multi_get(it) {
            let value = match item.map_err(into_pyerr)? {
                None => None,
                Some(value) => Some(PyBytes::new(py, value.as_ref()).into()),
            };
            values.push(value);
        }
        Ok(values)
    }

    // fn _multi_get_str(
    //     &self,
    //     py: Python,
    //     keys: Vec<&PyBytes>,
    // ) -> PyResult<Vec<Option<Py<PyString>>>> {
    //     let mut values = Vec::with_capacity(keys.len());
    //     let it = keys.into_iter().map(|k| k.as_bytes());

    //     for item in self.db.multi_get(it) {
    //         let value = match item.map_err(into_pyerr)? {
    //             None => None,
    //             Some(value) => Some(PyString::new(py, std::str::from_utf8(&value)?)),
    //         };
    //         values.push(value);
    //     }
    //     Ok(values)
    // }

    /// Retrieves a RocksDB property's value and cast it to an integer.
    ///
    /// Full list of properties that return int values could be find [here](https://github.com/facebook/rocksdb/blob/08809f5e6cd9cc4bc3958dd4d59457ae78c76660/include/rocksdb/db.h#L428-L634).
    fn get_int_property(&self, name: &str) -> PyResult<Option<u64>> {
        self.db.property_int_value(name).map_err(into_pyerr)
    }

    /// Seek to the first key that matches the *entire* prefix. From
    /// there, the itereator will continue to read pairs as long as the
    /// prefix extracted from `key` matches the prefix extracted from `prefix`.
    ///
    /// Note: for this function to always iterate over keys that match the *entire*
    /// prefix, set options.prefix_extractor to the length of the prefix.
    fn seek_keys(
        slf: PyRef<'_, Self>,
        py: Python,
        prefix: &PyAny,
    ) -> PyResult<Py<DBPrefixKeyIterator>> {
        let ptr = extend_lifetime_it(Box::new(
            slf.db.prefix_iterator(pyser_key(prefix)?.as_ref().as_ref()),
        ));
        let deser_key = slf.deser_key.clone_ref(py);

        let it = DBPrefixKeyIterator {
            db: slf.into(),
            deser_key,
            it: ptr,
        };
        Ok(Py::new(py, it)?)
    }

    /// Seek to the first key that matches the *entire* prefix. From
    /// there, the itereator will continue to read pairs as long as the
    /// prefix extracted from `key` matches the prefix extracted from `prefix`.
    ///
    /// Note: for this function to always iterate over keys that match the *entire*
    /// prefix, set options.prefix_extractor to the length of the prefix.
    fn seek_items(
        slf: PyRef<'_, Self>,
        py: Python,
        prefix: &PyAny,
    ) -> PyResult<Py<DBPrefixItemIterator>> {
        let ptr = extend_lifetime_it(Box::new(
            slf.db.prefix_iterator(pyser_key(prefix)?.as_ref().as_ref()),
        ));
        let deser_key = slf.deser_key.clone_ref(py);
        let deser_value = slf.deser_value.clone_ref(py);

        let it = DBPrefixItemIterator {
            db: slf.into(),
            deser_key,
            deser_value,
            it: ptr,
        };
        Ok(Py::new(py, it)?)
    }

    #[args(start = "None", end = "None")]
    fn compact(&self, start: Option<&PyAny>, end: Option<&PyAny>) -> PyResult<()> {
        match (start, end) {
            (None, None) => self.db.compact_range::<&[u8], &[u8]>(None, None),
            (Some(start), None) => self
                .db
                .compact_range::<&[u8], &[u8]>(Some(pyser_key(start)?.as_ref().as_ref()), None),
            (None, Some(end)) => self
                .db
                .compact_range::<&[u8], &[u8]>(None, Some(pyser_key(end)?.as_ref().as_ref())),
            (Some(start), Some(end)) => self.db.compact_range::<&[u8], &[u8]>(
                Some(pyser_key(start)?.as_ref().as_ref()),
                Some(pyser_key(end)?.as_ref().as_ref()),
            ),
        }

        Ok(())
    }

    fn try_catch_up_with_primary(&self) -> PyResult<()> {
        self.db.try_catch_up_with_primary().map_err(into_pyerr)
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
        default: Py<PyAny>,
    ) -> PyResult<Py<PyAny>> {
        match self.db.get_pinned(key.as_ref()).map_err(into_pyerr)? {
            None => Ok(default),
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
///
/// It creates a memoryview object pointing to `val`'s memory. Then invoke a deserializer that directly
/// use the memoryview object to restore Python object. If the deserializer is implemented correctly, it
/// won't store the memoryview object, so the memoryview object is gone and we don't have unsafe memory access.
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
pub fn extend_lifetime_raw_it(
    x: Box<DBRawIteratorWithThreadMode<'_, rocksdb::DB>>,
) -> Box<DBRawIteratorWithThreadMode<'static, rocksdb::DB>> {
    unsafe {
        Box::from_raw(
            Box::into_raw(x) as usize as *mut DBRawIteratorWithThreadMode<'static, rocksdb::DB>
        )
    }
}

pub fn extend_lifetime_it(
    x: Box<DBIteratorWithThreadMode<'_, rocksdb::DB>>,
) -> Box<DBIteratorWithThreadMode<'static, rocksdb::DB>> {
    unsafe {
        Box::from_raw(
            Box::into_raw(x) as usize as *mut DBIteratorWithThreadMode<'static, rocksdb::DB>
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
struct DBPrefixKeyIterator {
    it: Box<DBIteratorWithThreadMode<'static, rocksdb::DB>>,
    deser_key: Py<PyAny>,
    db: Py<RocksDBDict>,
}

#[pymethods]
impl DBPrefixKeyIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>, py: Python) -> PyResult<Option<PyObject>> {
        match slf.it.next() {
            None => Ok(None),
            Some((k, _v)) => {
                let next = pydeser_value(k, &slf.deser_key, py)?;
                Ok(Some(next))
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

#[pyclass(module = "hugedict.hugedict.rocksdb")]
#[allow(unused)]
struct DBPrefixItemIterator {
    it: Box<DBIteratorWithThreadMode<'static, rocksdb::DB>>,
    deser_key: Py<PyAny>,
    deser_value: Py<PyAny>,
    db: Py<RocksDBDict>,
}

#[pymethods]
impl DBPrefixItemIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>, py: Python) -> PyResult<Option<(PyObject, PyObject)>> {
        match slf.it.next() {
            None => Ok(None),
            Some((k, v)) => {
                let key = pydeser_value(k, &slf.deser_key, py)?;
                let value = pydeser_value(v, &slf.deser_value, py)?;
                Ok(Some((key, value)))
            }
        }
    }
}
