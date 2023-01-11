from functools import partial
from pathlib import Path
from typing import List, Mapping, Tuple
import pytest
from hugedict.cachedict import CacheDict
from hugedict.hugedict.rocksdb import RocksDBDict, Options, fixed_prefix_alike
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

    def test_update_cache1(
        self,
        mapping: RocksDBDict,
        existed_items: List[tuple],
        new_items: List[Tuple[str, str]],
    ):
        mcache = mapping.cache()
        assert isinstance(mcache, CacheDict)

        for k, v in existed_items:
            assert k in mapping
            assert k in mcache

        mcache.update_cache(new_items)

        for k, v in new_items:
            assert k not in mapping
            assert k in mcache

    def test_has_properties(self, mapping: RocksDBDict):
        assert hasattr(mapping, "deser_value")
        assert hasattr(mapping, "ser_value")

    def test_estimate_num_keys(self, mapping: RocksDBDict):
        # we create database from scratch, we haven't update/delete any key so the
        # estimation should be correct
        assert mapping.get_int_property("rocksdb.estimate-num-keys") == len(mapping)

    def test__put(self, mapping: RocksDBDict, new_items: List[tuple]):
        for k, v in new_items:
            mapping._put(k.encode(), v.encode())

        for k, v in new_items:
            assert mapping[k] == v

    def test_open_readonly(
        self, wdprops: Path, existed_items: List[tuple], new_items: List[tuple]
    ):
        db = RocksDBDict(
            str(wdprops),
            Options(),
            deser_key=partial(str, encoding="utf-8"),
            deser_value=partial(str, encoding="utf-8"),
            ser_value=str.encode,
            readonly=True,
        )

        for k, v in existed_items:
            assert db[k] == v

        # writing to db in readonly mode is not allowed
        for k, v in new_items:
            with pytest.raises(RuntimeError):
                db[k] = v

    def test_open_secondary_mode(
        self,
        wdprops: Path,
        tmp_path: Path,
        existed_items: List[tuple],
        new_items: List[tuple],
    ):
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

    def test_seek_iterators(self, wdprops: Path):
        deser_key = partial(str, encoding="utf-8")
        deser_value = partial(str, encoding="utf-8")
        ser_value = str.encode

        get_db = lambda opts: RocksDBDict(
            str(wdprops),
            opts,
            deser_key=deser_key,
            deser_value=deser_value,
            ser_value=ser_value,
        )

        # default opts without prefix_extractor will also yield keys not matched the entired prefix
        db = get_db(Options())

        prefix_counter = 0
        nonprefix_counter = 0

        subitems = dict(db.seek_items("P7"))
        for k in db.seek_keys("P7"):
            if k.startswith("P7"):
                prefix_counter += 1
            else:
                nonprefix_counter += 1
            assert k in subitems and subitems.pop(k) == db[k]

        assert len(subitems) == 0
        assert prefix_counter > 0
        assert nonprefix_counter > 0
        assert prefix_counter + nonprefix_counter < len(db)

        del db

        # get correct results with prefix_extractor
        db = get_db(
            Options(
                prefix_extractor=fixed_prefix_alike(
                    type="fixed_prefix_alike", prefix="P7"
                )
            )
        )
        prefix_counter = 0
        subitems = dict(db.seek_items("P7"))
        for k in db.seek_keys("P7"):
            assert k.startswith("P7")
            prefix_counter += 1
            assert k in subitems and subitems.pop(k) == db[k]
        assert prefix_counter > 0
        assert len(subitems) == 0
