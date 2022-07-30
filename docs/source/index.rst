.. include:: glossary.rst

.. hugedict documentation master file, created by
   sphinx-quickstart on Tue Jul 26 21:56:56 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

|hugedict| documentation
====================================

|hugedict| provides a drop-in replacement for dictionary objects that are too big to fit in memory. |hugedict|'s dictionary-like objects implement :py:class:`typing.Mapping` and :py:class:`typing.MutableMapping` interfaces using key-value databases (e.g., RocksDB) as the underlying storage. Moreover, they are friendly with Python's multiprocessing.

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   getting-started
   api

.. toctree::
   :maxdepth: 1
   :hidden: 
   :caption: Development

   development
   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
