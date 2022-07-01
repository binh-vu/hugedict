from functools import partial
from pathlib import Path
from typing import Generic, List, Mapping, Tuple
import pytest
from hugedict.cachedict import CacheDict
from hugedict.hugedict.rocksdb import RocksDBDict, Options
from tests.python.test_mapping import TestMutableMappingSuite


class TestRocksDBDict(TestMutableMappingSuite):
    DELETE_MISSING_KEY_RAISE_ERROR = False

    @pytest.fixture
    def mapping(self, wdprops: Path) -> Mapping:
        return RocksDBDict(
            str(wdprops),
            Options(),
            deser_key=partial(str, encoding="utf-8"),
            deser_value=partial(str, encoding="utf-8"),
            ser_value=str.encode,
        )

    @pytest.fixture
    def size(self) -> int:
        return 171

    @pytest.fixture
    def existed_items(self) -> List[tuple]:
        return [
            ("P7462", "graph diameter"),
            ("P7166", "Acharts.co song ID"),
            ("P405", "taxon author"),
            ("P2842", "place of marriage"),
            ("P2937", "parliamentary term"),
            ("P7957", "Directory of Maîtres d'art"),
        ]

    @pytest.fixture
    def new_items(self) -> List[tuple]:
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
        return ["Q10", 5, b"whatever", None]

    def test_cache(
        self,
        mapping: RocksDBDict,
        existed_items: List[tuple],
        new_items: List[tuple],
        unknown_keys: List,
    ):
        mcache = mapping.cache()
        assert isinstance(mcache, CacheDict)

        for k, v in existed_items:
            assert k in mapping
            assert k in mcache

        for k in [x[0] for x in new_items] + unknown_keys:
            assert k not in mapping
            assert k not in mcache

    def test_has_properties(self, mapping: RocksDBDict):
        assert hasattr(mapping, "deser_value")
        assert hasattr(mapping, "ser_value")

    def test__put(self, mapping: RocksDBDict, new_items: List[tuple]):
        for k, v in new_items:
            mapping._put(k.encode(), v.encode())

        for k, v in new_items:
            assert mapping[k] == v

    def test_open_readonly(self, wdprops: Path, existed_items: List[tuple], new_items: List[tuple]):
        db = RocksDBDict(
            str(wdprops),
            Options(),
            deser_key=partial(str, encoding="utf-8"),
            deser_value=partial(str, encoding="utf-8"),
            ser_value=str.encode,
            readonly=True
        )

        for k, v in existed_items:
            assert db[k] == v

        # writing to db in readonly mode is not allowed
        for k, v in new_items:
            with pytest.raises(RuntimeError):
                db[k] = v

    def test_open_secondary_mode(self, wdprops: Path, tmp_path: Path, existed_items: List[tuple], new_items: List[tuple]):
        primary_db = RocksDBDict(
            str(wdprops),
            Options(),
            deser_key=partial(str, encoding="utf-8"),
            deser_value=partial(str, encoding="utf-8"),
            ser_value=str.encode,
        )

        secondary_db = RocksDBDict(
            str(wdprops),
            Options(),
            deser_key=partial(str, encoding="utf-8"),
            deser_value=partial(str, encoding="utf-8"),
            ser_value=str.encode,
            secondary_mode=True,
            secondary_path=str(tmp_path),
        )

        # writing to secondary db is not allowed
        for k, v in new_items:
            with pytest.raises(RuntimeError):
                secondary_db[k] = v

        # but writing to the primary db is okay
        for k, v in new_items:
            primary_db[k] = v

        # the new key is not available in the secondary db until we try to catch up
        for k, v in new_items:
            assert k not in secondary_db
        secondary_db.try_catch_up_with_primary()
        for k, v in new_items:
            assert secondary_db[k] == v