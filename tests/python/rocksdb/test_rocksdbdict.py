from functools import partial
from pathlib import Path
from typing import Generic, List, Mapping, Tuple
import pytest
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
