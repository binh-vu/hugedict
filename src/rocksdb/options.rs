use pyo3::{
    exceptions::PyValueError,
    prelude::*,
    types::{PyBytes, PyString},
};
use rocksdb::{
    DBCompactionStyle as RocksDBCompactionStyle, DBCompressionType as RocksDBCompressionType,
    Options as RocksDBOptions, SliceTransform,
};
use serde::{Deserialize, Serialize};

use super::dict::pyser_key;

#[derive(Debug, Copy, Clone, Eq, PartialEq, Serialize, Deserialize)]
pub enum DBCompactionStyle {
    Level,
    Universal,
    FIFO,
}

impl<'s> FromPyObject<'s> for DBCompactionStyle {
    fn extract(obj: &'s PyAny) -> PyResult<Self> {
        let style = obj.downcast::<PyString>()?.to_str()?;
        match style {
            "level" => Ok(DBCompactionStyle::Level),
            "universal" => Ok(DBCompactionStyle::Universal),
            "fifo" => Ok(DBCompactionStyle::FIFO),
            _ => Err(PyErr::new::<PyValueError, _>(format!(
                "Unknown compaction style: {}",
                style
            ))),
        }
    }
}

impl From<DBCompactionStyle> for RocksDBCompactionStyle {
    fn from(style: DBCompactionStyle) -> Self {
        match style {
            DBCompactionStyle::Level => RocksDBCompactionStyle::Level,
            DBCompactionStyle::Universal => RocksDBCompactionStyle::Universal,
            DBCompactionStyle::FIFO => RocksDBCompactionStyle::Fifo,
        }
    }
}

#[derive(Debug, Copy, Clone, Eq, PartialEq, Serialize, Deserialize)]
pub enum DBCompressionType {
    None,
    Snappy,
    Zlib,
    Bz2,
    Lz4,
    Lz4hc,
    Zstd,
}

impl<'s> FromPyObject<'s> for DBCompressionType {
    fn extract(obj: &'s PyAny) -> PyResult<Self> {
        let style = obj.downcast::<PyString>()?.to_str()?;
        match style {
            "none" => Ok(DBCompressionType::None),
            "snappy" => Ok(DBCompressionType::Snappy),
            "zlib" => Ok(DBCompressionType::Zlib),
            "bz2" => Ok(DBCompressionType::Bz2),
            "lz4" => Ok(DBCompressionType::Lz4),
            "lz4hc" => Ok(DBCompressionType::Lz4hc),
            "zstd" => Ok(DBCompressionType::Zstd),
            _ => Err(PyErr::new::<PyValueError, _>(format!(
                "Unknown compression style: {}",
                style
            ))),
        }
    }
}

impl From<DBCompressionType> for RocksDBCompressionType {
    fn from(style: DBCompressionType) -> Self {
        match style {
            DBCompressionType::None => RocksDBCompressionType::None,
            DBCompressionType::Snappy => RocksDBCompressionType::Snappy,
            DBCompressionType::Zlib => RocksDBCompressionType::Zlib,
            DBCompressionType::Bz2 => RocksDBCompressionType::Bz2,
            DBCompressionType::Lz4 => RocksDBCompressionType::Lz4,
            DBCompressionType::Lz4hc => RocksDBCompressionType::Lz4hc,
            DBCompressionType::Zstd => RocksDBCompressionType::Zstd,
        }
    }
}

#[derive(Debug, Copy, Clone, Eq, PartialEq, Serialize, Deserialize)]
pub enum PrefixExtractor {
    FixedPrefixTransform(usize),
}

impl<'s> FromPyObject<'s> for PrefixExtractor {
    fn extract(obj: &'s PyAny) -> PyResult<Self> {
        match obj.getattr("type")?.downcast::<PyString>()?.to_str()? {
            "fixed_prefix" => {
                let prefix_length = obj.getattr("size")?.extract()?;
                Ok(PrefixExtractor::FixedPrefixTransform(prefix_length))
            }
            "fixed_prefix_alike" => {
                let prefix = obj.getattr("prefix")?;
                let prefix_length = pyser_key(prefix)?.as_ref().as_ref().len();
                Ok(PrefixExtractor::FixedPrefixTransform(prefix_length))
            }
            s => Err(PyErr::new::<PyValueError, _>(format!(
                "Unknown prefix extractor: {}",
                s
            ))),
        }
    }
}

/// Compression options. See more:
/// - http://rocksdb.org/blog/2021/05/31/dictionary-compression.html
/// - https://github.com/facebook/rocksdb/wiki/Space-Tuning
#[derive(Deserialize, Serialize, Clone, Eq, PartialEq)]
#[pyclass(module = "hugedict.hugedict.rocksdb")]
pub struct CompressionOptions {
    window_bits: i32,
    level: i32,
    strategy: i32,
    max_dict_bytes: i32,
}

#[pymethods]
impl CompressionOptions {
    #[new]
    fn new(window_bits: i32, level: i32, strategy: i32, max_dict_bytes: i32) -> Self {
        CompressionOptions {
            window_bits,
            level,
            strategy,
            max_dict_bytes,
        }
    }
}

/// Checkout the list of options here:
/// - https://github.com/facebook/rocksdb/blob/0e0a19832e5f1e3584590edf796abd05c484e649/include/rocksdb/options.h#L432
/// - https://github.com/facebook/rocksdb/blob/main/include/rocksdb/advanced_options.h
/// - https://docs.rs/rocksdb/latest/rocksdb/struct.Options.html
#[derive(Deserialize, Serialize, Clone, Eq, PartialEq)]
#[pyclass(module = "hugedict.hugedict.rocksdb")]
pub struct Options {
    #[pyo3(get, set)]
    pub create_if_missing: Option<bool>,
    #[pyo3(get, set)]
    pub max_open_files: Option<i32>,
    #[pyo3(get, set)]
    pub use_fsync: Option<bool>,
    #[pyo3(get, set)]
    pub bytes_per_sync: Option<u64>,
    // original option: ColumnFamilyOptions* OptimizeForPointLookup(uint64_t block_cache_size_mb);
    #[pyo3(get, set)]
    pub optimize_for_point_lookup: Option<u64>,
    #[pyo3(get, set)]
    pub table_cache_numshardbits: Option<i32>,
    #[pyo3(get, set)]
    pub max_write_buffer_number: Option<i32>,
    #[pyo3(get, set)]
    pub write_buffer_size: Option<usize>,
    #[pyo3(get, set)]
    pub target_file_size_base: Option<u64>,
    #[pyo3(get, set)]
    pub min_write_buffer_number_to_merge: Option<i32>,
    #[pyo3(get, set)]
    pub level_zero_stop_writes_trigger: Option<i32>,
    #[pyo3(get, set)]
    pub level_zero_slowdown_writes_trigger: Option<i32>,
    pub compaction_style: Option<DBCompactionStyle>,
    #[pyo3(get, set)]
    pub disable_auto_compactions: Option<bool>,
    #[pyo3(get, set)]
    pub max_background_jobs: Option<i32>,
    #[pyo3(get, set)]
    pub max_subcompactions: Option<u32>,
    pub compression_type: Option<DBCompressionType>,
    pub bottommost_compression_type: Option<DBCompressionType>,
    pub prefix_extractor: Option<PrefixExtractor>,
    pub compression_opts: Option<CompressionOptions>,
    pub bottommost_compression_opts: Option<CompressionOptions>,
    // in here: http://rocksdb.org/blog/2021/05/31/dictionary-compression.html
    // recommended to 100x of max_dict_bytes
    #[pyo3(get, set)]
    pub zstd_max_train_bytes: Option<i32>,
    #[pyo3(get, set)]
    pub bottommost_zstd_max_train_bytes: Option<i32>,
}

#[pymethods]
impl Options {
    #[new]
    #[args(
        "*",
        create_if_missing = "None",
        max_open_files = "None",
        use_fsync = "None",
        bytes_per_sync = "None",
        optimize_for_point_lookup = "None",
        table_cache_numshardbits = "None",
        max_write_buffer_number = "None",
        write_buffer_size = "None",
        target_file_size_base = "None",
        min_write_buffer_number_to_merge = "None",
        level_zero_stop_writes_trigger = "None",
        level_zero_slowdown_writes_trigger = "None",
        compaction_style = "None",
        disable_auto_compactions = "None",
        max_background_jobs = "None",
        max_subcompactions = "None",
        compression_type = "self::DBCompressionType::Lz4",
        bottommost_compression_type = "None",
        prefix_extractor = "None",
        compression_opts = "None",
        bottommost_compression_opts = "None",
        zstd_max_train_bytes = "None",
        bottommost_zstd_max_train_bytes = "None"
    )]
    fn new(
        create_if_missing: Option<bool>,
        max_open_files: Option<i32>,
        use_fsync: Option<bool>,
        bytes_per_sync: Option<u64>,
        optimize_for_point_lookup: Option<u64>,
        table_cache_numshardbits: Option<i32>,
        max_write_buffer_number: Option<i32>,
        write_buffer_size: Option<usize>,
        target_file_size_base: Option<u64>,
        min_write_buffer_number_to_merge: Option<i32>,
        level_zero_stop_writes_trigger: Option<i32>,
        level_zero_slowdown_writes_trigger: Option<i32>,
        compaction_style: Option<DBCompactionStyle>,
        disable_auto_compactions: Option<bool>,
        max_background_jobs: Option<i32>,
        max_subcompactions: Option<u32>,
        compression_type: Option<DBCompressionType>,
        bottommost_compression_type: Option<DBCompressionType>,
        prefix_extractor: Option<PrefixExtractor>,
        compression_opts: Option<CompressionOptions>,
        bottommost_compression_opts: Option<CompressionOptions>,
        zstd_max_train_bytes: Option<i32>,
        bottommost_zstd_max_train_bytes: Option<i32>,
    ) -> Self {
        Options {
            create_if_missing: create_if_missing,
            max_open_files: max_open_files,
            use_fsync: use_fsync,
            bytes_per_sync: bytes_per_sync,
            optimize_for_point_lookup: optimize_for_point_lookup,
            table_cache_numshardbits: table_cache_numshardbits,
            max_write_buffer_number: max_write_buffer_number,
            write_buffer_size: write_buffer_size,
            target_file_size_base: target_file_size_base,
            min_write_buffer_number_to_merge: min_write_buffer_number_to_merge,
            level_zero_stop_writes_trigger: level_zero_stop_writes_trigger,
            level_zero_slowdown_writes_trigger: level_zero_slowdown_writes_trigger,
            compaction_style: compaction_style,
            disable_auto_compactions: disable_auto_compactions,
            max_background_jobs: max_background_jobs,
            max_subcompactions: max_subcompactions,
            compression_type: compression_type,
            bottommost_compression_type: bottommost_compression_type,
            prefix_extractor: prefix_extractor,
            compression_opts: compression_opts,
            bottommost_compression_opts: bottommost_compression_opts,
            zstd_max_train_bytes: zstd_max_train_bytes,
            bottommost_zstd_max_train_bytes: bottommost_zstd_max_train_bytes,
        }
    }

    fn __getstate__(&self, py: Python) -> PyResult<PyObject> {
        let encode: Vec<u8> = bincode::serialize(self).unwrap();
        Ok(PyBytes::new(py, &encode).into())
    }

    fn __setstate__(&mut self, py: Python, state: PyObject) -> PyResult<()> {
        let b = state.as_ref(py).downcast::<PyBytes>()?.as_bytes();
        let o: Options = bincode::deserialize(b).map_err(|_err| {
            PyValueError::new_err(format!("Cannot deserialize Options: corrupted state"))
        })?;

        self.create_if_missing = o.create_if_missing;
        self.max_open_files = o.max_open_files;
        self.use_fsync = o.use_fsync;
        self.bytes_per_sync = o.bytes_per_sync;
        self.optimize_for_point_lookup = o.optimize_for_point_lookup;
        self.table_cache_numshardbits = o.table_cache_numshardbits;
        self.max_write_buffer_number = o.max_write_buffer_number;
        self.write_buffer_size = o.write_buffer_size;
        self.target_file_size_base = o.target_file_size_base;
        self.min_write_buffer_number_to_merge = o.min_write_buffer_number_to_merge;
        self.level_zero_stop_writes_trigger = o.level_zero_stop_writes_trigger;
        self.level_zero_slowdown_writes_trigger = o.level_zero_slowdown_writes_trigger;
        self.compaction_style = o.compaction_style;
        self.disable_auto_compactions = o.disable_auto_compactions;
        self.max_background_jobs = o.max_background_jobs;
        self.max_subcompactions = o.max_subcompactions;
        self.compression_type = o.compression_type;
        self.bottommost_compression_type = o.bottommost_compression_type;
        self.prefix_extractor = o.prefix_extractor;
        self.compression_opts = o.compression_opts;
        self.bottommost_compression_opts = o.bottommost_compression_opts;
        Ok(())
    }
}

impl Options {
    pub fn get_options(&self) -> RocksDBOptions {
        let mut opts = RocksDBOptions::default();
        if let Some(create_if_missing) = self.create_if_missing {
            opts.create_if_missing(create_if_missing);
        }
        if let Some(max_open_files) = self.max_open_files {
            opts.set_max_open_files(max_open_files);
        }
        if let Some(use_fsync) = self.use_fsync {
            opts.set_use_fsync(use_fsync);
        }
        if let Some(bytes_per_sync) = self.bytes_per_sync {
            opts.set_bytes_per_sync(bytes_per_sync);
        }
        if let Some(optimize_for_point_lookup) = self.optimize_for_point_lookup {
            opts.optimize_for_point_lookup(optimize_for_point_lookup);
        }
        if let Some(table_cache_numshardbits) = self.table_cache_numshardbits {
            opts.set_table_cache_num_shard_bits(table_cache_numshardbits);
        }
        if let Some(max_write_buffer_number) = self.max_write_buffer_number {
            opts.set_max_write_buffer_number(max_write_buffer_number);
        }
        if let Some(write_buffer_size) = self.write_buffer_size {
            opts.set_write_buffer_size(write_buffer_size);
        }
        if let Some(target_file_size_base) = self.target_file_size_base {
            opts.set_target_file_size_base(target_file_size_base);
        }
        if let Some(min_write_buffer_number_to_merge) = self.min_write_buffer_number_to_merge {
            opts.set_min_write_buffer_number_to_merge(min_write_buffer_number_to_merge);
        }
        if let Some(level_zero_stop_writes_trigger) = self.level_zero_stop_writes_trigger {
            opts.set_level_zero_stop_writes_trigger(level_zero_stop_writes_trigger);
        }
        if let Some(level_zero_slowdown_writes_trigger) = self.level_zero_slowdown_writes_trigger {
            opts.set_level_zero_slowdown_writes_trigger(level_zero_slowdown_writes_trigger);
        }
        if let Some(compaction_style) = self.compaction_style {
            opts.set_compaction_style(compaction_style.into());
        }
        if let Some(disable_auto_compactions) = self.disable_auto_compactions {
            opts.set_disable_auto_compactions(disable_auto_compactions);
        }
        if let Some(max_background_jobs) = self.max_background_jobs {
            opts.set_max_background_jobs(max_background_jobs);
        }
        if let Some(max_subcompactions) = self.max_subcompactions {
            opts.set_max_subcompactions(max_subcompactions);
        }
        if let Some(compression_type) = self.compression_type {
            opts.set_compression_type(compression_type.into());
        }
        if let Some(bottommost_compression_type) = self.bottommost_compression_type {
            opts.set_bottommost_compression_type(bottommost_compression_type.into());
        }
        if let Some(prefix_extractor) = self.prefix_extractor {
            match prefix_extractor {
                PrefixExtractor::FixedPrefixTransform(len) => {
                    let extractor = SliceTransform::create_fixed_prefix(len);
                    opts.set_prefix_extractor(extractor);
                }
            }
        }
        if let Some(compression_opts) = &self.compression_opts {
            opts.set_compression_options(
                compression_opts.window_bits,
                compression_opts.level,
                compression_opts.strategy,
                compression_opts.max_dict_bytes,
            );
        }
        if let Some(compression_opts) = &self.bottommost_compression_opts {
            opts.set_bottommost_compression_options(
                compression_opts.window_bits,
                compression_opts.level,
                compression_opts.strategy,
                compression_opts.max_dict_bytes,
                true,
            );
        }
        if let Some(zstd_max_train_bytes) = self.zstd_max_train_bytes {
            opts.set_zstd_max_train_bytes(zstd_max_train_bytes);
        }
        if let Some(bottommost_zstd_max_train_bytes) = self.bottommost_zstd_max_train_bytes {
            opts.set_bottommost_zstd_max_train_bytes(bottommost_zstd_max_train_bytes, true);
        }

        opts
    }
}
