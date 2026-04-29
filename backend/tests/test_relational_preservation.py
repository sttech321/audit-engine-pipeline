import random

import pytest

from rim_os_v2 import _ntt_inplace, NTT_MOD, process_chunk, build_genesis, audit_file


def test_injectivity_one_bit_pairs():
    rng = random.Random(123)
    for _ in range(1000):
        data = bytearray(rng.randbytes(64))
        bit = rng.randrange(64 * 8)
        data2 = bytearray(data)
        data2[bit // 8] ^= (1 << (bit % 8))

        h1 = process_chunk(bytes(data)).get("manifold_hash")
        h2 = process_chunk(bytes(data2)).get("manifold_hash")
        assert h1 != h2


def test_determinism_same_input_same_output():
    data = bytes(range(64))
    r1 = process_chunk(data)
    r2 = process_chunk(data)
    assert r1.get("k5") == r2.get("k5")
    assert r1.get("tau_pentagrid") == r2.get("tau_pentagrid")


def test_ntt_bijectivity_inverse_recovers():
    a = [i % 97 for i in range(256)]
    orig = a[:]
    _ntt_inplace(a, invert=False)
    _ntt_inplace(a, invert=True)
    assert a == [v % NTT_MOD for v in orig]


def test_order_sensitivity_positions_differ(tmp_path):
    g = build_genesis()
    a = bytes(range(64))
    b = bytes(range(63, -1, -1))
    p1 = tmp_path / "ab.bin"
    p2 = tmp_path / "ba.bin"
    p1.write_bytes(a + b)
    p2.write_bytes(b + a)
    r1 = audit_file(str(p1), genesis=g, max_chunks=2, chain_seed="seed0")
    r2 = audit_file(str(p2), genesis=g, max_chunks=2, chain_seed="seed0")
    assert (r1.get("map_position") or {}).get("k5") != (r2.get("map_position") or {}).get("k5")


def test_position_independent_of_chain_seed(tmp_path):
    """Reference Model v1.3 §8.4 (Option 3): positions on the manifold are
    absolute. The same input audited under different chain_seed values must
    produce a bit-identical map_position. chain_seed is still accepted by
    audit_file (it is threaded to downstream SVG rendering and stored as
    chain_seed_at_commit on the chain block), but it must not influence k5,
    world_x, world_y, tau_vectors, barycentric, manifold_hash, or tile_hash.
    """
    g = build_genesis()
    p = tmp_path / "x.bin"
    p.write_bytes(bytes(range(128)))
    r1 = audit_file(str(p), genesis=g, max_chunks=1, chain_seed="seedA")
    r2 = audit_file(str(p), genesis=g, max_chunks=1, chain_seed="seedB")
    r3 = audit_file(str(p), genesis=g, max_chunks=1, chain_seed=None)
    mp1 = r1.get("map_position") or {}
    mp2 = r2.get("map_position") or {}
    mp3 = r3.get("map_position") or {}
    assert mp1 == mp2
    assert mp1 == mp3
    for key in ("k5", "tau_vectors", "world_x", "world_y",
                "barycentric", "manifold_hash", "tile_hash"):
        assert mp1.get(key) == mp2.get(key) == mp3.get(key), (
            f"map_position[{key!r}] varied across chain_seeds: "
            f"{mp1.get(key)!r} vs {mp2.get(key)!r} vs {mp3.get(key)!r}"
        )

