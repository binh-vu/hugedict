from typing import Generic, List, Mapping, MutableMapping, Tuple

import pytest


class TestMappingSuite:
    @pytest.fixture
    def mapping(self) -> Mapping:
        return {"P276": "location", "Q5": "human"}

    @pytest.fixture
    def size(self) -> int:
        return 2

    @pytest.fixture
    def existed_items(self) -> List[tuple]:
        return [("Q5", "human")]

    @pytest.fixture
    def unknown_keys(self) -> List:
        return ["Q10", 5, b"whatever"]

    def test_get(
        self,
        mapping: Mapping,
        existed_items: List[tuple],
        unknown_keys: List,
    ):
        for k, v in existed_items:
            assert mapping[k] == v
            if v is not None:
                assert mapping.get(k, None) == v
            else:
                assert mapping.get(k, 1) == v

        for k in unknown_keys:
            with pytest.raises(KeyError):
                mapping[k]

    def test_contains(
        self,
        mapping: Mapping,
        existed_items: List[tuple],
        unknown_keys: List,
    ):
        for k, v in existed_items:
            assert k in mapping

        for k in unknown_keys:
            assert k not in mapping

    def test_len(self, mapping: Mapping, size: int):
        assert len(mapping) == size

    def test_iter(self, mapping: Mapping):
        size = len(mapping)

        keys = list(iter(mapping))
        assert keys == list(mapping.keys()), "Looping order is the same"
        assert len(keys) == size, "Get all keys"
        for k in keys:
            assert k in mapping

        items = dict(mapping.items())
        assert len(items) == size, "Get all items"
        for k, v in items.items():
            assert mapping[k] == v

        values = list(mapping.values())
        assert len(values) == size, "Get all values"
        for i, (k, v) in enumerate(items.items()):
            assert values[i] == v, "Looping order is the same"


class TestMutableMappingSuite(TestMappingSuite):
    DELETE_MISSING_KEY_RAISE_ERROR = True

    @pytest.fixture
    def new_items(self) -> List[tuple]:
        return [("Q8", "happiness")]

    def test_delete(
        self,
        mapping: MutableMapping,
        existed_items: List[tuple],
        new_items: List[tuple],
        unknown_keys: List,
    ):
        size = len(mapping)

        for k in [x[0] for x in new_items] + unknown_keys:
            if self.DELETE_MISSING_KEY_RAISE_ERROR:
                with pytest.raises(KeyError):
                    del mapping[k]
            else:
                del mapping[k]
        assert size == len(mapping)

        for k, v in existed_items:
            del mapping[k]
            assert k not in mapping
        assert size == len(mapping) + len(existed_items)

    def test_pop(
        self,
        mapping: MutableMapping,
        existed_items: List[tuple],
        new_items: List[tuple],
        unknown_keys: List,
    ):
        for k in [x[0] for x in new_items] + unknown_keys:
            assert mapping.pop(k, None) == None

        for k, v in existed_items:
            if v is not None:
                assert mapping.pop(k, None) == v
            else:
                assert mapping.pop(k, 1) == v
            assert k not in mapping

    def test_set(self, mapping: MutableMapping, new_items: List[Tuple]):
        size = len(mapping)
        for k, v in new_items:
            assert k not in mapping
            mapping[k] = v
            assert k in mapping

        assert size + len(new_items) == len(mapping)
