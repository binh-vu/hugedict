from functools import partial
import os
from pathlib import Path
from subprocess import Popen, check_call
import sys
from typing import List, Mapping, Tuple
import pytest
from hugedict.cachedict import CacheDict
from hugedict.hugedict.rocksdb import RocksDBDict, Options, fixed_prefix_alike
from tests.python.test_mapping import TestMutableMappingSuite
from hugedict.sqlitedict import SqliteDict


class TestSqliteDict(TestMutableMappingSuite):
    DELETE_MISSING_KEY_RAISE_ERROR = False

    @pytest.fixture
    def mapping(self, tmp_path: Path, existed_items: List[Tuple[str, str]]) -> Mapping:
        dbpath = tmp_path / f"test.sqlite"
        map = SqliteDict.str(dbpath, ser_value=str.encode, deser_value=bytes.decode)
        map["P131"] = "located in the administrative territorial entity"
        for k, v in existed_items:
            map[k] = v
        return map

    @pytest.fixture
    def size(self) -> int:
        return 7

    @pytest.fixture
    def existed_items(self) -> List[Tuple[str, str]]:
        return [
            ("P7462", "graph diameter"),
            ("P7166", "Acharts.co song ID"),
            ("P405", "taxon author"),
            ("P2842", "place of marriage"),
            ("P2937", "parliamentary term"),
            ("P7957", "Directory of Maîtres d'art"),
        ]

    @pytest.fixture
    def new_items(self) -> List[Tuple[str, str]]:
        return [
            ("P58", "screenwriter"),
            ("P106", "occupation"),
            ("P123", "publisher"),
            ("P162", "producer"),
            ("P170", "creator"),
            ("P175", "performer"),
        ]

    @pytest.fixture
    def unknown_keys(self) -> List:
        return ["Q10", 5, b"whatever", None, 123.49]

    def test_concurrent_access(self, mapping: SqliteDict):
        nkey, nvalue = "newkey", "concurrent access"
        assert nkey not in mapping

        # start a new process and write a new key
        commands = [
            "from hugedict.sqlitedict import SqliteDict",
            f"map = SqliteDict.str('{str(mapping.dbfile.absolute())}', ser_value=str.encode, deser_value=bytes.decode)",
            f"nkey = '{nkey}'",
            f"nvalue = '{nvalue}'",
            "assert nkey not in map",
            "map[nkey] = nvalue",
            "assert map[nkey] == nvalue",
        ]
        command = ";".join(commands)
        check_call([sys.executable, "-c", command])

        assert nkey in mapping
