import math

from rim_os_v2 import kag_invariants


def test_kag_invariants_scale_invariant_under_magnitude_scaling():
    # Build two spectra with identical shape but different scale.
    base = [0] * 256
    for i in range(256):
        base[i] = (i * 17) % 1000

    inv_a = kag_invariants(base)["invariants"]
    scaled = [v * 5 for v in base]
    inv_b = kag_invariants(scaled)["invariants"]

    # Should match closely because invariants normalize to probabilities.
    for k in ("dir_mass",):
        for x, y in zip(inv_a[k], inv_b[k]):
            assert abs(x - y) < 1e-9
    for k in ("dir_entropy", "participation", "index_mu", "index_var"):
        assert abs(inv_a[k] - inv_b[k]) < 1e-9


def test_kag_invariants_are_stable_under_small_perturbation():
    base = [0] * 256
    for i in range(256):
        base[i] = (i * 31) % 997
    inv_a = kag_invariants(base)["invariants"]

    pert = base[:]
    pert[10] += 1
    inv_b = kag_invariants(pert)["invariants"]

    # No discontinuity: changes should be small.
    assert abs(inv_a["dir_entropy"] - inv_b["dir_entropy"]) < 1e-3
    assert abs(inv_a["index_mu"] - inv_b["index_mu"]) < 1e-3

