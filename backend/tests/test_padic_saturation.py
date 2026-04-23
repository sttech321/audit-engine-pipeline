from rim_os_v2 import padic_lift, PRIMES_256


def test_padic_reports_saturation_for_large_exponents():
    exps = [0] * 256
    # Force saturation on a small prime channel: p0=2, k=3 => mod=8
    exps[0] = 999

    out = padic_lift(exps, k=3)
    sat = out.get("saturation") or {}
    assert sat.get("count", 0) >= 1
    assert 0.0 < float(sat.get("fraction", 0.0)) <= 1.0


def test_padic_no_saturation_when_exps_below_modulus():
    k = 3
    exps = [0] * 256
    for i in range(256):
        mod = PRIMES_256[i] ** k
        exps[i] = max(0, int(mod) - 1)

    out = padic_lift(exps, k=k)
    sat = out.get("saturation") or {}
    assert sat.get("count") == 0
    assert float(sat.get("fraction")) == 0.0

