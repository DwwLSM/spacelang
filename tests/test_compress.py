import pytest

from spacelang.compress import pack_bytes, pack_file, unpack_bytes, unpack_file
from spacelang.errors import EncodingError


def test_space_roundtrip_through_gzip(tmp_path):
    source = b" " * 10000 + b"\n" + b" " * 5000 + b"\n"
    compressed = pack_bytes(source)
    assert unpack_bytes(compressed) == source
    assert len(compressed) < len(source) * 0.05

    source_path = tmp_path / "program.sp"
    packed_path = tmp_path / "program.spz"
    unpacked_path = tmp_path / "copy.sp"
    source_path.write_bytes(source)
    pack_file(source_path, packed_path)
    unpack_file(packed_path, unpacked_path)
    assert unpacked_path.read_bytes() == source


def test_unpack_rejects_invalid_gzip():
    with pytest.raises(EncodingError):
        unpack_bytes(b"not gzip")
