import tempfile

from rim_os_v2 import audit_file, build_genesis


def test_file_level_position_is_order_sensitive(tmp_path):
    # Build a small file with two "chunks" of different bytes, then reorder them.
    a = bytes(range(64))
    b = bytes(range(63, -1, -1))
    p1 = tmp_path / "ab.bin"
    p2 = tmp_path / "ba.bin"
    p1.write_bytes(a + b)
    p2.write_bytes(b + a)

    g = build_genesis()

    r1 = audit_file(str(p1), genesis=g, max_chunks=2)
    r2 = audit_file(str(p2), genesis=g, max_chunks=2)

    mp1 = r1.get("map_position") or {}
    mp2 = r2.get("map_position") or {}
    assert mp1.get("k5") != mp2.get("k5")
