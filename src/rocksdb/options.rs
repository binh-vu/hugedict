use pyo3::{
    exceptions::PyValueError,
    prelude::*,
    types::{PyBytes, PyString},
};
use rocksdb::{DBCompactionStyle as RocksDBCompactionStyle, Options as RocksDBOptions};
use serde::{Deserialize, Serialize};

#[derive(Debug, Copy, Clone, PartialEq, Serialize, Deserialize)]
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

/// Checkout the list of options here:
/// - https://github.com/facebook/rocksdb/blob/0e0a19832e5f1e3584590edf796abd05c484e649/include/rocksdb/options.h#L432
/// - https://github.com/facebook/rocksdb/blob/main/include/rocksdb/advanced_options.h
/// - https://docs.rs/rocksdb/latest/rocksdb/struct.Options.html
#[derive(Deserialize, Serialize)]
#[pyclass(module = "hugedict.hugedict.rocksdb")]
pub struct Options {
    pub create_if_missing: Option<bool>,
    pub max_open_files: Option<i32>,
    pub use_fsync: Option<bool>,
    pub bytes_per_sync: Option<u64>,
    // original option: ColumnFamilyOptions* OptimizeForPointLookup(uint64_t block_cache_size_mb);
    pub optimize_for_point_lookup: Option<u64>,
    pub table_cache_numshardbits: Option<i32>,
    pub max_write_buffer_number: Option<i32>,
    pub write_buffer_size: Option<usize>,
    pub target_file_size_base: Option<u64>,
    pub min_write_buffer_number_to_merge: Option<i32>,
    pub level_zero_stop_writes_trigger: Option<i32>,
    pub level_zero_slowdown_writes_trigger: Option<i32>,
    pub compaction_style: Option<DBCompactionStyle>,
    pub disable_auto_compactions: Option<bool>,
    pub max_background_jobs: Option<i32>,
    pub max_subcompactions: Option<u32>,
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
        max_subcompactions = "None"
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
        match self.compaction_style {
            Some(DBCompactionStyle::Level) => {
                opts.set_compaction_style(RocksDBCompactionStyle::Level);
            }
            Some(DBCompactionStyle::Universal) => {
                opts.set_compaction_style(RocksDBCompactionStyle::Universal);
            }
            Some(DBCompactionStyle::FIFO) => {
                opts.set_compaction_style(RocksDBCompactionStyle::Fifo);
            }
            None => {}
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
        opts
    }
}
