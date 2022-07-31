.. include:: glossary.rst

Getting Started
===============

Installation
------------

|hugedict| is distributed on `PyPI <https://pypi.org/project/hugedict/>`_ so you can install with pip as below.

.. code:: hugedict

    pip install hugedict

.. note::

    Prebuilt binaries are available on Linux, Windows (x86_64), and MacOS (x86_64 and arm64). However, if you are using an uncommon platform such as ARM on Linux, prebuilt binary is not available, ``pip`` will attempt to recompile the source code automatically. In that case, please see :ref:`Install from source` for the list of prerequisite tools/libraries.

Install from source
^^^^^^^^^^^^^^^^^^^

.. admonition:: Prerequisite tools/libraries

    1. `maturin <https://github.com/PyO3/maturin>`__
    2. `Rust <https://www.rust-lang.org/>`__
    3. CMake
    4. CLang

If you are inside a virtual environment, you can install it to directly

.. code:: bash

    maturin develop -r  # -r to compile in release mode, it's optional

Otherwise, you can build a wheel and install it

.. code:: bash

    maturin build -r -o dist
    pip install dist/hugedict-*.whl

You can also consult the :source:`containers/manylinux2014_x86_64/Dockerfile` for guidance to install from scratch.

Usage
-----

1. Create a mutable mapping backed by RocksDB

.. code:: python

    from functools import partial
    from hugedict.prelude import RocksDBDict, RocksDBOptions

    # replace [str, str] for the types of keys and values you want
    # as well as deser_key, deser_value, ser_value
    mapping: MutableMapping[str, str] = RocksDBDict(
        path=dbpath,  # path (str) to db file
        options=RocksDBOptions(create_if_missing=create_if_missing),  # whether to create database if missing, check other options
        deser_key=partial(str, encoding="utf-8"),  # decode the key from memoryview
        deser_value=partial(str, encoding="utf-8"),  # decode the value from memoryview
        ser_value=str.encode,  # encode the value to bytes
        readonly=False,  # open database in read only mode
        secondary_mode=False,  # open database in secondary mode
        secondary_path=None,  # when secondary_mode is True, it's a string pointing to a directory for storing data required to operate in secondary mode
    )

2. Load huge data from files into RocksDB in parallel: `from hugedict.prelude import rocksdb_load`. This function creates SST files in parallel, ingests into the db and (optionally) compacts them.

3. Cache a function when doing parallel processing

.. code:: python

    from hugedict.prelude import Parallel

    pp = Parallel()

    @pp.cache_func("/tmp/test.db")
    def heavy_computing(seconds: float):
        time.sleep(seconds)
        return seconds * 2


    output = pp.map(heavy_computing, [0.5, 1, 0.7, 0.3, 0.6], n_processes=3)

.. note::

    If the process start method is ``fork``, then you may encounter an error when running ``pp.map`` multiple times, change the start method to ``spawn`` will solve the error. The reason is that somehow in my test, ``with Pool()`` seems to fork from previous forked processes. As fork is not safe for libraries that use locks, the ``nng`` library throws an error saying it
    is not fork re-entrant safe.

