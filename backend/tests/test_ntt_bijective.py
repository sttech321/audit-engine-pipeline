import random


from rim_os_v2 import _ntt_inplace, NTT_MOD


def test_ntt_inverse_recovers_input_exactly():
    rng = random.Random(12345)
    a = [rng.randrange(0, 1000) for _ in range(256)]
    orig = a[:]

    _ntt_inplace(a, invert=False)
    _ntt_inplace(a, invert=True)

    assert a == [v % NTT_MOD for v in orig]

