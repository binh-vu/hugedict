from hugedict.hugedict.rocksdb import CompressionOptions


def test_compression_options_to_dict():
    assert CompressionOptions(
        window_bits=-14, level=6, strategy=0, max_dict_bytes=16 * 1024
    ).to_dict() == {
        "window_bits": -14,
        "level": 6,
        "strategy": 0,
        "max_dict_bytes": 16 * 1024,
    }
