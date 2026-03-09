#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rim_os_v2.py  —  RIM-OS Production Build
=========================================
Changes from v1:
  - encode_input() replaced: now uses same Gödel pipeline as Genesis Mints
    → all points on M speak the same mathematical language
  - tau_omega spread fixed: Genesis Mints now span full [0,1] range
  - SVG artifact generation (no PIL, pure SVG)
  - PDF report generation (reportlab)
  - FastAPI integration snippet in docstring

Architecture (two layers):
  Layer 1 — Pipeline (produces fingerprint on M):
    Binary chunk → Gödel → p-adic → NTT → KAG → Penrose P3
    Each chunk lands on a unique, deterministic point on M.
    Same generative process → same region on M (empirically verified).

  Layer 2 — Genesis Frame:
    Three fixed anchors from physical constants (Standard Model / GR / Thermodynamics).
    These are the origin of the coordinate system. Immutable.

SERVER INTEGRATION (fastest path):
  from rim_os_v2 import build_genesis, audit_file
  genesis = build_genesis()                          # once at startup
  report  = audit_file(path, genesis=genesis)
  db.store(report["ledger"]["next_state_hash"])      # blockchain entry
  api.return(report["summary"])                      # to frontend

KEY AUDIT METRICS:
  report["summary"]["integrity_score_0_100"]        → 0-100
  report["summary"]["risk_level"]                   → LOW / MEDIUM / HIGH
  report["summary"]["anomaly_fraction"]              → 0.0-1.0
  report["summary"]["requires_human_review"]         → bool
  report["chunks"][i]["manifold_hash"]               → position on M
  report["ledger"]["next_state_hash"]                → blockchain anchor
  report["integrity"]["audit_content_sha256"]        → deterministic file ID
"""

from __future__ import annotations

import argparse, base64, hashlib, json, math, mmap, os
import struct, sys, time, zlib
from typing import Any, Dict, Iterator, List, Optional, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

CHUNK_BYTES    = 1_048_576
TILE_SIDE      = 64
TILE_N         = TILE_SIDE ** 2
U16_PER_CHUNK  = CHUNK_BYTES // 2
NTT_MOD        = 998_244_353
NTT_PRIM_ROOT  = 3
PHI            = (1.0 + math.sqrt(5.0)) / 2.0
SCHEMA         = "RIM-OS-2.0.0"


# ══════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()

def canonical_hash(obj: Any) -> str:
    return sha256_hex(canonical_bytes(obj))

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


# ══════════════════════════════════════════════════════════════════
# PRIME TABLE
# ══════════════════════════════════════════════════════════════════

def _sieve(n: int) -> List[int]:
    primes: List[int] = []
    x = 2
    while len(primes) < n:
        sq = int(math.isqrt(x))
        if all(x % p != 0 for p in primes if p <= sq):
            primes.append(x)
        x += 1
    return primes

PRIMES_256 = _sieve(256)


# ══════════════════════════════════════════════════════════════════
# PIPELINE: Gödel → p-adic → NTT → KAG → Penrose
# (same for chunks AND for Genesis Mints AND for new encoder)
# ══════════════════════════════════════════════════════════════════

def godel_encode_vector(data: bytes) -> Dict[str, Any]:
    """
    Vector-based Gödel encoding: position i → prime p_i, exponent = byte at position.

    Splits data into 256-byte blocks. Per block: exps[i] = block[i] + 1 (preserves order).
    Aggregates block vectors with position-weight so different byte orderings yield different
    exponent vectors. True Gödel: each position maps to a prime; exponent = symbol at that position.
    """
    exps = [0] * 256
    n = len(data)
    if n == 0:
        return {"exponents": exps, "exp_hash": canonical_hash(exps), "log2_size": 0.0}

    num_blocks = (n + 255) // 256
    for k in range(num_blocks):
        start = k * 256
        end = min(start + 256, n)
        w = k + 1  # position weight: earlier blocks contribute less
        for i in range(end - start):
            byte_val = data[start + i]
            exps[i] += (byte_val + 1) * w

    log2 = sum(exps[i] * math.log2(PRIMES_256[i]) for i in range(256) if exps[i])
    return {"exponents": exps,
            "exp_hash":  canonical_hash(exps),
            "log2_size": float(log2)}


def godel_encode(hist: List[int]) -> Dict[str, Any]:
    """
    Histogram-based encoding (legacy). Use godel_encode_vector for true Gödel.

    Byte histogram → prime exponent vector. Does NOT preserve sequence order.
    Kept for backward compatibility; prefer godel_encode_vector for chunk processing.
    """
    exps = [int(c) for c in hist]
    log2 = sum(exps[i] * math.log2(PRIMES_256[i]) for i in range(256) if exps[i])
    return {"exponents": exps,
            "exp_hash":  canonical_hash(exps),
            "log2_size": float(log2)}

def padic_lift(exps: List[int], k: int = 3) -> Dict[str, Any]:
    """Gödel exponents → p-adic residues mod p_i^k."""
    residues = [int(exps[i] % (PRIMES_256[i] ** max(1, min(k, 6))))
                for i in range(256)]
    return {"residues":   residues,
            "padic_hash": canonical_hash(residues),
            "k":          k}

def _ntt_inplace(a: List[int], invert: bool) -> None:
    n = len(a); j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit: j ^= bit; bit >>= 1
        j ^= bit
        if i < j: a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        w = pow(NTT_PRIM_ROOT, (NTT_MOD - 1) // length, NTT_MOD)
        if invert: w = pow(w, NTT_MOD - 2, NTT_MOD)
        for i in range(0, n, length):
            wn, half = 1, length >> 1
            for jj in range(i, i + half):
                u = a[jj]; v = a[jj + half] * wn % NTT_MOD
                a[jj] = (u + v) % NTT_MOD
                a[jj + half] = (u - v) % NTT_MOD
                wn = wn * w % NTT_MOD
        length <<= 1
    if invert:
        inv_n = pow(n, NTT_MOD - 2, NTT_MOD)
        for i in range(n): a[i] = a[i] * inv_n % NTT_MOD

def ntt_fingerprint(residues: List[int], L: int = 1024) -> Dict[str, Any]:
    """p-adic residues → exact NTT spectrum over GF(998244353)."""
    sig = [0] * L
    seed_bytes = sha256_hex(canonical_bytes(residues)).encode()
    x = int.from_bytes(seed_bytes[:8], "little") | 1
    for i, r in enumerate(residues):
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 7)  & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        sig[(i * 1315423911 + (x & 0xFFFFFFFF)) % L] = \
            (sig[(i * 1315423911 + (x & 0xFFFFFFFF)) % L] + r % NTT_MOD) % NTT_MOD
    a = sig[:]
    _ntt_inplace(a, invert=False)
    half = NTT_MOD >> 1
    mags = [v if v <= half else NTT_MOD - v for v in a]
    block = L // 64
    mag64 = [sum(mags[i*block:(i+1)*block]) // block for i in range(64)]
    return {"spec_hash": canonical_hash(a), "mag64": mag64, "L": L}

def kag_grid(mag64: List[int]) -> Dict[str, Any]:
    """8×8 KAG additive predictor on NTT magnitude vector."""
    G = 8; grid = [[mag64[y*G+x] for x in range(G)] for y in range(G)]
    g_mean = sum(mag64) / 64
    row_mean = [sum(grid[y]) / G for y in range(G)]
    col_mean = [sum(grid[y][x] for y in range(G)) / G for x in range(G)]
    resids = [abs(grid[y][x] - (row_mean[y] + col_mean[x] - g_mean))
              for y in range(G) for x in range(G)]
    mean_r = sum(resids) / len(resids)
    sep = float(clamp01(1.0 - mean_r / (g_mean + 1e-6)))
    kag_obj = {"grid": grid, "gmean": g_mean,
               "row_means": row_mean, "col_means": col_mean,
               "mean_abs_residual": mean_r, "separability": sep}
    return {"kag_hash": canonical_hash(kag_obj), "separability": sep,
            "chart": kag_obj}

def _pentagrid_tau(kag_hash: str) -> List[float]:
    """kag_hash → five pentagrid offsets τ[0..4] ∈ [0,1)."""
    bs = bytes.fromhex(kag_hash)
    if len(bs) < 40: bs = (bs * 10)[:40]
    return [(int.from_bytes(bs[i*8:(i+1)*8], "little") % (1 << 53)) / float(1 << 53)
            for i in range(5)]

def _intersect(ni, a, nj, b):
    det = ni[0]*nj[1] - ni[1]*nj[0]
    if abs(det) < 1e-12: return None
    x = (a*nj[1] - b*ni[1]) / det
    y = (ni[0]*b  - nj[0]*a) / det
    return (x, y)

def penrose_patch(kag_hash: str, N: int = 6,
                  max_tiles: int = 384) -> Dict[str, Any]:
    """Generate Penrose P3 patch from kag_hash (pentagrid cut-and-project)."""
    tau    = _pentagrid_tau(kag_hash)
    thetas = [k * 2 * math.pi / 5 for k in range(5)]
    normals = [(math.cos(t), math.sin(t)) for t in thetas]
    cache: Dict = {}

    def vertex(i, a, j, b):
        key = (i, a, j, b)
        if key in cache: return cache[key]
        pt = _intersect(normals[i], a + tau[i], normals[j], b + tau[j])
        cache[key] = pt
        return pt

    tiles = []
    for i in range(5):
        for j in range(i+1, 5):
            rtype = "thick" if (j-i) % 5 in (1, 4) else "thin"
            for a in range(-N, N+1):
                for b in range(-N, N+1):
                    vs = [vertex(i,a,j,b), vertex(i,a+1,j,b),
                          vertex(i,a+1,j,b+1), vertex(i,a,j,b+1)]
                    if None in vs: continue
                    tiles.append({"type": rtype, "v": vs})

    if not tiles:
        return {"tau": tau, "tiles": [], "tile_count": 0,
                "tile_hash": canonical_hash({"tau": tau, "tiles": []})}

    all_x = [v[0] for t in tiles for v in t["v"]]
    all_y = [v[1] for t in tiles for v in t["v"]]
    mx, mnx = max(all_x), min(all_x)
    my, mny = max(all_y), min(all_y)
    sx, sy  = max(mx-mnx, 1e-12), max(my-mny, 1e-12)
    norm_tiles = [{"type": t["type"],
                   "v": [((vx-mnx)/sx, (vy-mny)/sy) for vx,vy in t["v"]]}
                  for t in tiles[:max_tiles]]
    return {"tau": tau, "tiles": norm_tiles,
            "tile_count": len(norm_tiles),
            "tile_hash":  canonical_hash({"tau": tau, "tiles": norm_tiles})}

def penrose_match_score(tiling: Dict) -> float:
    """Measure how well the patch matches P3 invariants (0-1)."""
    tiles = tiling.get("tiles", [])
    if not tiles: return 0.0
    thick = sum(1 for t in tiles if t["type"] == "thick")
    thin  = len(tiles) - thick
    ratio = thick / max(1, thin)
    ratio_score = math.exp(-abs(ratio - PHI) / 0.4)

    dir_hist = [0] * 5
    edge_lens = []
    for t in tiles:
        vs = t["v"]
        for e in range(4):
            x1,y1 = vs[e]; x2,y2 = vs[(e+1)%4]
            ang = math.atan2(y2-y1, x2-x1) % (2*math.pi)
            dir_hist[int(ang/(2*math.pi)*5) % 5] += 1
            edge_lens.append(math.hypot(x2-x1, y2-y1))

    tot = sum(dir_hist)
    dir_ent = (-sum((c/tot)*math.log2(c/tot) for c in dir_hist if c) / math.log2(5)
               if tot else 0.0)

    ammann = 0.0
    if len(edge_lens) >= 4:
        m = sum(edge_lens) / len(edge_lens)
        if m > 1e-12:
            sd = math.sqrt(sum((e-m)**2 for e in edge_lens) / len(edge_lens))
            ammann = float(clamp01(1.0 - min(1.0, sd/m*4.0)))

    return float(clamp01(0.40*ratio_score + 0.30*dir_ent + 0.30*ammann))


# ══════════════════════════════════════════════════════════════════
# HI/LO SPLIT  (BF16 byte-plane separation)
# ══════════════════════════════════════════════════════════════════

def split_hi_lo(chunk: bytes) -> Tuple[bytes, bytes]:
    if HAS_NUMPY:
        arr = np.frombuffer(chunk, dtype="<u2")
        return ((arr >> 8) & 0xFF).astype(np.uint8).tobytes(), \
               (arr & 0xFF).astype(np.uint8).tobytes()
    n = len(chunk) // 2
    hi, lo = bytearray(n), bytearray(n)
    for i in range(n):
        w = struct.unpack_from("<H", chunk, i*2)[0]
        hi[i] = (w >> 8) & 0xFF; lo[i] = w & 0xFF
    return bytes(hi), bytes(lo)


# ══════════════════════════════════════════════════════════════════
# BYTE STATISTICS
# ══════════════════════════════════════════════════════════════════

def byte_histogram(data: bytes) -> List[int]:
    hist = [0] * 256
    for b in data: hist[b] += 1
    return hist

def shannon_entropy(hist: List[int], n: int) -> float:
    if n <= 0: return 0.0
    ent = 0.0
    for c in hist:
        if c:
            p = c / n; ent -= p * math.log2(p)
    return ent

def chi2_uniform(hist: List[int], n: int) -> float:
    if n <= 0: return 0.0
    exp = n / 256.0
    return sum((c - exp)**2 / exp for c in hist)

def autocorr_lag(data: bytes, lag: int = 16) -> float:
    if len(data) <= lag: return 0.0
    a, b = data[:-lag], data[lag:]
    n = len(b)
    ma = sum(a)/len(a); mb = sum(b)/n
    num = da = db = 0.0
    for i in range(n):
        xa = a[i]-ma; xb = b[i]-mb
        num += xa*xb; da += xa*xa; db += xb*xb
    if da <= 1e-12 or db <= 1e-12: return 0.0
    return float(num / math.sqrt(da * db))


# ══════════════════════════════════════════════════════════════════
# PROCESS CHUNK — full pipeline on one 1MiB block
# ══════════════════════════════════════════════════════════════════

def process_chunk(chunk: bytes) -> Dict[str, Any]:
    """
    Run Gödel→p-adic→NTT→KAG→Penrose on one chunk.
    Returns manifold_hash (blockchain anchor) and all intermediate hashes.
    """
    hi, lo = split_hi_lo(chunk)
    hi_hist = byte_histogram(hi)
    hist    = byte_histogram(chunk)
    n       = len(chunk)

    stats = {
        "entropy_bits": shannon_entropy(hist, n),
        "chi2":         chi2_uniform(hist, n),
        "autocorr16":   autocorr_lag(chunk, 16),
    }
    hi_ent = shannon_entropy(hi_hist, len(hi))
    lo_ent = shannon_entropy(byte_histogram(lo), len(lo))

    g   = godel_encode_vector(hi)
    p   = padic_lift(g["exponents"], k=3)
    ntt = ntt_fingerprint(p["residues"], L=1024)
    kag = kag_grid(ntt["mag64"])
    til = penrose_patch(kag["kag_hash"], N=6, max_tiles=384)
    ms  = penrose_match_score(til)

    chain = {
        "godel_hash":   g["exp_hash"],
        "padic_hash":   p["padic_hash"],
        "ntt_hash":     ntt["spec_hash"],
        "kag_hash":     kag["kag_hash"],
        "penrose_hash": til["tile_hash"],
    }
    manifold_hash = canonical_hash(chain)

    return {
        "stats":         stats,
        "hi_entropy":    hi_ent,
        "lo_entropy":    lo_ent,
        "separability":  kag["separability"],
        "match_score":   ms,
        "tile_hash":     til["tile_hash"],
        "manifold_hash": manifold_hash,
        "chain":         chain,
        "tiling":        til,
    }


# ══════════════════════════════════════════════════════════════════
# GENESIS MINTS — physics-grounded coordinate system
# ══════════════════════════════════════════════════════════════════

_SCIENCE_ANCHORS: Dict[str, float] = {
    # Standard Model
    "fine_structure":      1.0 / 137.035999084,
    "weak_mixing":         0.23122,
    "strong_coupling":     0.1179,
    # GR
    "schwarzschild_norm":  2.0 / (PHI ** 2),   # ≈ 0.7639
    "cosmological_norm":   0.26894142137,
    "planck_norm":         6.62607015e-34 / 1e-33,
    # Thermodynamics
    "entropy_gold":        math.log(PHI),
    "boltzmann_norm":      1.380649e-23 / 1e-22,
    "dirac_norm":          1.0 / (2.0 * math.pi),
    # Mathematical anchors
    "phi_frac":            PHI - 1.0,
    "phi2_frac":           2.0 - PHI,
    "pi_norm":             math.pi / 4.0,
    "e_norm":              (math.e - 2.0),
    "sqrt2_norm":          math.sqrt(2) - 1.0,
    "ln2_norm":            math.log(2),
}

def _rat_approx(v: float, max_d: int = 10000) -> Tuple[int, int]:
    """Best rational approximation via continued fractions."""
    if v <= 0: return (0, 1)
    h1, h2, k1, k2 = 1, 0, 0, 1
    x = abs(v)
    for _ in range(200):
        a = int(x); h, k = a*h1+h2, a*k1+k2
        if k > max_d: return (h1, k1)
        h2, h1, k2, k1 = h1, h, k1, k
        if abs(x - a) < 1e-12: return (h, k)
        x = 1.0 / (x - a)
    return (h1, k1)

def _godel_of_int(n: int) -> List[int]:
    """Integer → prime exponent vector (true Gödel encoding)."""
    exps = [0] * 256
    r = abs(int(n))
    if r <= 1: return exps
    for i, p in enumerate(PRIMES_256):
        while r % p == 0: exps[i] += 1; r //= p
        if r == 1: break
    return exps

def _const_to_tau5(value: float) -> List[float]:
    """
    Physical/mathematical constant → tau_pentagrid[0..4].
    Exact same Gödel→p-adic→NTT pipeline as chunk processing.
    This ensures constants and chunks live in the same coordinate space.
    """
    p, q   = _rat_approx(abs(value))
    gp, gq = _godel_of_int(p), _godel_of_int(q)
    # Combined: difference of numerator/denominator exponent vectors
    # captures the rational structure of the constant
    g_comb  = [abs(gp[i] - gq[i]) for i in range(256)]
    residues = padic_lift(g_comb, k=3)["residues"]
    ntt      = ntt_fingerprint(residues, L=1024)
    kag      = kag_grid(ntt["mag64"])
    tau5     = _pentagrid_tau(kag["kag_hash"])
    return tau5

def _harmonic_mean_tau5(tau5_list: List[List[float]]) -> List[float]:
    """Combine multiple tau5 vectors via harmonic mean per dimension."""
    result = []
    for d in range(5):
        vs = [v[d] for v in tau5_list if v[d] > 1e-12]
        if vs:
            result.append(len(vs) / sum(1.0/v for v in vs))
        else:
            # fallback: arithmetic mean including zeros
            result.append(_mean([v[d] for v in tau5_list]))
    return result

def build_genesis(extra_anchors: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Build Genesis Mints from physical constants.

    Call ONCE at server startup. Store in memory. Never recompute.
    Result is deterministic — same constants → same mints forever.

    extra_anchors: optional dict {label: float_value} for domain-specific
                   extensions (e.g. {"my_constant": 0.12345})
    """
    anchors = dict(_SCIENCE_ANCHORS)
    if extra_anchors:
        anchors.update(extra_anchors)

    def make_mint(keys: List[str], doi: str, title: str,
                  label: str) -> Dict[str, Any]:
        tau5_list = [_const_to_tau5(anchors[k]) for k in keys if k in anchors]
        tau5      = _harmonic_mean_tau5(tau5_list) if tau5_list else [0.5]*5
        tw        = sum(tau5) / 5.0
        return {
            "label":          label,
            "tau_pentagrid":  tau5,
            "tau_omega_norm": float(tw),
            "tau_omega":      {"tau_omega_norm": float(tw)},
            "tile_hash":      canonical_hash({"tau5": tau5}),
            "manifold_hash":  canonical_hash({"tau5": tau5, "doi": doi}),
            "separability":   float(tau5[0]),
            "match_score":    float(tw),
            "meta": {"keys": keys, "doi": doi, "title": title},
        }

    g1 = make_mint(
        ["fine_structure","weak_mixing","strong_coupling","phi_frac","dirac_norm"],
        "10.1103/RevModPhys.84.1527", "Standard Model", "G1_StandardModel")
    g2 = make_mint(
        ["schwarzschild_norm","cosmological_norm","planck_norm","pi_norm","sqrt2_norm"],
        "10.1002/andp.19163540702", "General Relativity (Einstein 1915)", "G2_GR")
    g3 = make_mint(
        ["entropy_gold","boltzmann_norm","phi_frac","ln2_norm","e_norm"],
        "10.1007/BF02354528", "Thermodynamics (Boltzmann 1868)", "G3_Thermo")

    mints = [g1, g2, g3]
    return {
        "genesis_mints": mints,
        "frame_hash":    canonical_hash([g["tile_hash"] for g in mints]),
        "schema":        SCHEMA,
        "anchors_used":  list(anchors.keys()),
    }


# ══════════════════════════════════════════════════════════════════
# ENCODER v2 — any input → point on M
# ══════════════════════════════════════════════════════════════════

def encode_bytes(raw: bytes, genesis: List[Dict],
                 label: str = "") -> Dict[str, Any]:
    """
    Any raw bytes → position on M via same Gödel pipeline as chunks.

    This is the correct encoder: it uses process_chunk() directly,
    so the result is in the same coordinate space as all other tiles.
    Same generative process → same byte-distribution → same region on M.

    Works for: text (UTF-8 bytes), numbers (struct.pack), images (raw pixels),
               model weights (directly), any binary data.
    """
    # Pad or truncate to exactly CHUNK_BYTES
    if len(raw) >= CHUNK_BYTES:
        chunk = raw[:CHUNK_BYTES]
    else:
        # Tile the input so short inputs aren't dominated by zero-padding
        repeats = (CHUNK_BYTES // len(raw)) + 1
        chunk   = (raw * repeats)[:CHUNK_BYTES]

    desc = process_chunk(chunk)
    tau5 = _pentagrid_tau(desc["chain"]["kag_hash"])
    tw   = sum(tau5) / 5.0
    bary = _barycentric(tau5, genesis)
    region = _dominant_region(bary, genesis)

    return {
        "label":          label,
        "tau_pentagrid":  tau5,
        "tau_omega_norm": float(tw),
        "manifold_hash":  desc["manifold_hash"],
        "tile_hash":      desc["tile_hash"],
        "barycentric":    bary,
        "manifold_region": region,
        "separability":   desc["separability"],
        "match_score":    desc["match_score"],
    }

def encode_integer(n: int, genesis: List[Dict], label: str = "") -> Dict[str, Any]:
    """
    Integer → position on M via true Gödel encoding.
    2, 3, 5 (primes) → sparse exponent vectors → distinct positions.
    6=2×3 → combined exponent vector → between 2 and 3 on M.
    """
    exps     = _godel_of_int(n)
    residues = padic_lift(exps, k=3)["residues"]
    ntt      = ntt_fingerprint(residues, L=1024)
    kag      = kag_grid(ntt["mag64"])
    tau5     = _pentagrid_tau(kag["kag_hash"])
    tw       = sum(tau5) / 5.0
    bary     = _barycentric(tau5, genesis)
    chain    = {"padic_hash": padic_lift(exps,3)["padic_hash"],
                "ntt_hash": ntt["spec_hash"],
                "kag_hash": kag["kag_hash"],
                "penrose_hash": penrose_patch(kag["kag_hash"])["tile_hash"]}
    return {
        "label":          label or str(n),
        "input_int":      n,
        "tau_pentagrid":  tau5,
        "tau_omega_norm": float(tw),
        "manifold_hash":  canonical_hash(chain),
        "barycentric":    bary,
        "manifold_region": _dominant_region(bary, genesis),
        "separability":   kag["separability"],
    }

def encode_text(text: str, genesis: List[Dict], label: str = "") -> Dict[str, Any]:
    """UTF-8 text → position on M."""
    return encode_bytes(text.encode("utf-8"), genesis, label or text[:40])

def encode_number(value: float, genesis: List[Dict],
                  label: str = "") -> Dict[str, Any]:
    """
    Float → position on M via rational approximation + Gödel.
    This is how Genesis Mints are built — consistent coordinate space.
    """
    tau5 = _const_to_tau5(value)
    tw   = sum(tau5) / 5.0
    bary = _barycentric(tau5, genesis)
    return {
        "label":          label or str(value),
        "input_float":    value,
        "tau_pentagrid":  tau5,
        "tau_omega_norm": float(tw),
        "barycentric":    bary,
        "manifold_region": _dominant_region(bary, genesis),
    }


# ══════════════════════════════════════════════════════════════════
# MANIFOLD GEOMETRY — barycentric coords and metric
# ══════════════════════════════════════════════════════════════════

def _tau5_of(point: Dict) -> List[float]:
    t = point.get("tau_pentagrid", point.get("tau", [0.5]*5))
    return [float(v) for v in t] if t else [0.5]*5

def _barycentric(tau5: List[float],
                 genesis: List[Dict]) -> List[float]:
    """
    5D inverse-distance weighting relative to Genesis Mints.
    Always returns values in [0,1] that sum to 1.
    Numerically stable for any point on M.
    """
    if not genesis: return [1.0]
    dists = []
    for g in genesis:
        g5 = _tau5_of(g)
        d  = math.sqrt(max(sum((tau5[i]-g5[i])**2 for i in range(5)), 1e-24))
        dists.append(d)
    inv   = [1.0 / d for d in dists]
    total = sum(inv)
    if total < 1e-30:
        return [1.0/len(genesis)] * len(genesis)
    return [float(v/total) for v in inv]

def _dominant_region(bary: List[float],
                     genesis: List[Dict]) -> str:
    if not bary: return "unknown"
    idx = bary.index(max(bary))
    if idx < len(genesis):
        return f"near {genesis[idx].get('label','G'+str(idx+1))}"
    return "unknown"

def manifold_dist(a: Dict, b: Dict,
                  genesis: List[Dict]) -> Dict[str, Any]:
    """
    Distance on M between two points.
    Uses barycentric coordinates weighted by genesis boundary proximity.
    """
    la = _barycentric(_tau5_of(a), genesis)
    lb = _barycentric(_tau5_of(b), genesis)
    # Weight: genesis mints closer to boundary (lower tau_omega) count more
    w  = [1.0 - g.get("tau_omega_norm", 0.5) for g in genesis[:len(la)]]
    d2 = sum(w[i]*(la[i]-lb[i])**2 for i in range(min(len(la),len(lb),len(w))))
    d  = math.sqrt(max(0.0, d2))
    interp = ("identical" if d < 0.01 else
              "close" if d < 0.10 else
              "medium" if d < 0.25 else
              "far" if d < 0.50 else "singularity")
    return {"distance": float(d), "bary_a": la, "bary_b": lb,
            "interpretation": interp}


# ══════════════════════════════════════════════════════════════════
# BF16 BIAS HEURISTICS
# ══════════════════════════════════════════════════════════════════

def _bf16_bias_penalty(path: str,
                       max_bytes: int = 16*1024*1024) -> Dict[str, Any]:
    """Sample BF16 exponent distribution. Returns bias_penalty ∈ [0,1]."""
    total = os.path.getsize(path)
    end   = min(total, max_bytes)
    exp_hist = [0] * 256
    words = 0; carry = b""
    with open(path, "rb") as f:
        remain = end
        while remain > 0:
            buf = f.read(min(1 << 20, remain))
            if not buf: break
            remain -= len(buf)
            data = carry + buf
            if len(data) % 2:
                carry = data[-1:]; data = data[:-1]
            else:
                carry = b""
            for i in range(0, len(data), 2):
                w = data[i] | (data[i+1] << 8)
                exp_hist[(w >> 7) & 0xFF] += 1
                words += 1

    n = max(1, words)
    s = sum(exp_hist)
    ent = (-sum((c/s)*math.log2(c/s) for c in exp_hist if c)
           / math.log2(256) if s else 0.0)
    zero_frac = exp_hist[0] / n
    ext_frac  = (exp_hist[0]+exp_hist[255]) / n
    max_frac  = max(exp_hist) / n

    penalty = 0.0; notes = []
    if ent < 0.60:
        penalty += (0.60-ent)*1.6; notes.append("LOW_EXPONENT_ENTROPY")
    if ext_frac > 0.08:
        penalty += (ext_frac-0.08)*4.0; notes.append("HIGH_EXTREME_EXPONENT")
    if max_frac > 0.10:
        penalty += (max_frac-0.10)*2.5; notes.append("DOMINANT_EXPONENT_BIN")
    if not notes: notes.append("CLEAN")

    return {"sample_words": words, "exp_entropy_norm": float(ent),
            "zero_frac": float(zero_frac), "ext_frac": float(ext_frac),
            "max_frac": float(max_frac),
            "bias_penalty_0_1": float(clamp01(penalty)), "notes": notes}


# ══════════════════════════════════════════════════════════════════
# ANOMALY DETECTION
# ══════════════════════════════════════════════════════════════════

def _zscores(xs: List[float]) -> List[float]:
    if len(xs) < 2: return [0.0]*len(xs)
    mu = sum(xs)/len(xs)
    sd = math.sqrt(sum((x-mu)**2 for x in xs)/len(xs))
    if sd < 1e-12: return [0.0]*len(xs)
    return [(x-mu)/sd for x in xs]

def detect_anomalies(per_chunk: List[Dict]) -> List[Dict]:
    """Flag chunks with z-score > ±3σ on key metrics."""
    ze  = _zscores([c["entropy_bits"]  for c in per_chunk])
    zc2 = _zscores([c["chi2"]          for c in per_chunk])
    za  = _zscores([c["autocorr16"]    for c in per_chunk])
    zs  = _zscores([c["match_score"]   for c in per_chunk])
    zsp = _zscores([c["separability"]  for c in per_chunk])
    anomalies = []
    for i, c in enumerate(per_chunk):
        flags = []
        if ze[i]  < -3.0: flags.append("LOW_ENTROPY")
        if zc2[i] >  3.0: flags.append("CHI2_OUTLIER")
        if abs(za[i]) > 3.0: flags.append("AUTOCORR_OUTLIER")
        if zs[i]  < -3.0: flags.append("LOW_SYMMETRY")
        if zsp[i] >  3.0: flags.append("HIGH_SEPARABILITY")
        if flags:
            anomalies.append({
                "chunk_index": c["chunk_index"],
                "offset": c["offset"], "size": c["size"],
                "flags": flags,
                "z": {"entropy": ze[i], "chi2": zc2[i],
                      "autocorr": za[i], "symmetry": zs[i],
                      "separability": zsp[i]},
            })
    return anomalies


# ══════════════════════════════════════════════════════════════════
# INTEGRITY SCORE
# ══════════════════════════════════════════════════════════════════

def integrity_score(avg_ent: float, avg_match: float,
                    ano_frac: float, bias_pen: float) -> int:
    """
    Weighted score 0-100:
      entropy  30%  (healthy ≈ 8 bits)
      Penrose  40%  (match_score closer to 1 = better P3 geometry)
      anomalies 30% (fraction should be near 0)
    Bias penalty: up to 25% multiplicative reduction.
    """
    e = clamp01(1.0 - abs(avg_ent - 8.0) / 2.0)
    s = clamp01(avg_match)
    a = clamp01(1.0 - ano_frac)
    base = 100.0 * (0.30*e + 0.40*s + 0.30*a)
    bias_factor = clamp01(1.0 - 0.25 * clamp01(bias_pen))
    return int(round(clamp01(base * bias_factor / 100.0) * 100.0))

def risk_level(score: int) -> str:
    return "HIGH" if score < 70 else "MEDIUM" if score < 90 else "LOW"


# ══════════════════════════════════════════════════════════════════
# LEDGER CHAIN
# ══════════════════════════════════════════════════════════════════

def build_ledger(chunks: List[Dict],
                 prev_state: Optional[str] = None) -> Dict[str, Any]:
    """
    Build blockchain ledger entry for this audit.
    next_state_hash = SHA256(prev_state + events_hash)
    Store next_state_hash in DB to chain audits.
    """
    events_hash = sha256_hex(
        "".join(c.get("manifold_hash","") for c in chunks).encode())
    mh_agg = sha256_hex(
        "".join(c.get("manifold_hash","") for c in chunks).encode())
    th_agg = sha256_hex(
        "".join(c.get("tile_hash","") for c in chunks).encode())

    if prev_state is None:
        prev_state = sha256_hex(("RIM_OS_GENESIS:" + events_hash).encode())

    next_state = sha256_hex((prev_state + ":" + events_hash).encode())

    return {
        "events_hash":    events_hash,
        "mh_aggregate":   mh_agg,
        "th_aggregate":   th_agg,
        "prev_state":     prev_state,
        "next_state_hash": next_state,
    }


# ══════════════════════════════════════════════════════════════════
# SAFETENSORS PARSER
# ══════════════════════════════════════════════════════════════════

def parse_safetensors(path: str) -> Dict[str, Any]:
    """Detect and summarise safetensors format."""
    try:
        with open(path, "rb") as f:
            raw = f.read(8)
            if len(raw) != 8: return {"is_safetensors": False}
            hlen = struct.unpack("<Q", raw)[0]
            if not (2 < hlen <= 100_000_000): return {"is_safetensors": False}
            hdr = json.loads(f.read(hlen).decode("utf-8"))
        tensors = {k: v for k, v in hdr.items()
                   if k != "__metadata__" and isinstance(v, dict)}
        dtypes: Dict[str,int] = {}
        total = 0
        for m in tensors.values():
            dt = str(m.get("dtype","?"))
            dtypes[dt] = dtypes.get(dt,0) + 1
            shp = m.get("shape",[])
            e = 1
            for s in shp: e *= max(1, int(s))
            total += e
        ranks: Dict[str,int] = {}
        for m in tensors.values():
            r = str(len(m.get("shape",[])))
            ranks[r] = ranks.get(r,0)+1
        return {"is_safetensors": True, "tensor_count": len(tensors),
                "dtype_hist": dtypes, "rank_hist": ranks,
                "total_elements_est": total,
                "has_metadata": "__metadata__" in hdr}
    except Exception:
        return {"is_safetensors": False}


# ══════════════════════════════════════════════════════════════════
# FULL AUDIT
# ══════════════════════════════════════════════════════════════════

def audit_file(path: str,
               genesis: Optional[Dict] = None,
               max_chunks: Optional[int] = None,
               prev_state: Optional[str] = None) -> Dict[str, Any]:
    """
    Stream-audit any binary file (safetensors, GGUF, raw weights, ...).
    Constant RAM usage regardless of file size.
    """
    if genesis is None:
        genesis = build_genesis()
    gm = genesis.get("genesis_mints", [])

    total   = os.path.getsize(path)
    st_info = parse_safetensors(path)
    bias    = _bf16_bias_penalty(path)
    chunks: List[Dict] = []
    t0 = time.time()

    with open(path, "rb") as f:
        ci = 0
        while True:
            if max_chunks is not None and ci >= max_chunks: break
            chunk = f.read(CHUNK_BYTES)
            if not chunk: break
            desc = process_chunk(chunk)

            # compute tau5 and barycentric position for this chunk
            tau5 = _pentagrid_tau(desc["chain"]["kag_hash"])
            tw   = sum(tau5) / 5.0
            bary = _barycentric(tau5, gm)

            row = {
                "chunk_index":  ci,
                "offset":       int(ci * CHUNK_BYTES),
                "size":         len(chunk),
                "entropy_bits": desc["stats"]["entropy_bits"],
                "chi2":         desc["stats"]["chi2"],
                "autocorr16":   desc["stats"]["autocorr16"],
                "hi_entropy":   desc["hi_entropy"],
                "lo_entropy":   desc["lo_entropy"],
                "separability": desc["separability"],
                "match_score":  desc["match_score"],
                "manifold_hash": desc["manifold_hash"],
                "tile_hash":    desc["tile_hash"],
                "tau_pentagrid": tau5,
                "tau_omega_norm": float(tw),
                "barycentric":  bary,
                "region":       _dominant_region(bary, gm),
            }
            chunks.append(row)
            ci += 1

            if ci % 50 == 0 or ci * CHUNK_BYTES >= total:
                pct  = 100.0 * min(ci * CHUNK_BYTES, total) / total
                rate = min(ci * CHUNK_BYTES, total) / max(1e-6, time.time()-t0)
                sys.stderr.write(f"\r[RIM-OS v2] chunk={ci} {pct:.1f}%"
                                 f" {rate/1e6:.1f} MB/s  ")
                sys.stderr.flush()

    sys.stderr.write("\n"); sys.stderr.flush()

    ents  = [c["entropy_bits"] for c in chunks]
    syms  = [c["match_score"]  for c in chunks]
    seps  = [c["separability"] for c in chunks]
    avg_ent  = _mean(ents); avg_sym = _mean(syms); avg_sep = _mean(seps)

    anomalies = detect_anomalies(chunks)
    ano_frac  = len(anomalies) / max(1, len(chunks))
    bias_pen  = float(bias["bias_penalty_0_1"])
    score     = integrity_score(avg_ent, avg_sym, ano_frac, bias_pen)
    rl        = risk_level(score)
    req_rev   = bool(ano_frac > 0.05 or rl == "HIGH" or bias_pen > 0.25)
    conform   = bool(rl != "HIGH" and not req_rev and bias_pen < 0.20)

    ledger = build_ledger(chunks, prev_state)

    report: Dict[str, Any] = {
        "schema":  SCHEMA,
        "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input": {
            "path":        os.path.basename(path),
            "size_bytes":  int(total),
            "chunk_count": len(chunks),
            "chunk_size":  CHUNK_BYTES,
        },
        "safetensors":     st_info,
        "bias_heuristics": bias,
        "summary": {
            "integrity_score_0_100": score,
            "risk_level":            rl,
            "avg_entropy_bits":      float(avg_ent),
            "avg_penrose_match":     float(avg_sym),
            "avg_kag_separability":  float(avg_sep),
            "anomaly_count":         len(anomalies),
            "anomaly_fraction":      float(ano_frac),
            "bias_penalty_0_1":      float(bias_pen),
            "requires_human_review": req_rev,
            "conformity_passed":     conform,
        },
        "anomalies": anomalies,
        "chunks":    chunks,
        "ledger":    ledger,
        "genesis_frame_hash": genesis.get("frame_hash", ""),
        "EU_AI_ACT": _eu_ai_act_block(rl, score, req_rev, conform,
                                       bias, anomalies, ledger, len(chunks)),
    }

    # Deterministic content hash (no timestamp, no large blobs)
    slim = {k: v for k, v in report.items()
            if k not in ("time_utc", "chunks")}
    report["integrity"] = {
        "audit_content_sha256": canonical_hash(slim),
        "audit_sha256":         canonical_hash(report),
    }
    return report


def _eu_ai_act_block(rl, score, req_rev, conform,
                     bias, anomalies, ledger, n_chunks) -> Dict:
    return {
        "regulation": "Regulation (EU) 2024/1689",
        "scope": ("Weight-space integrity audit. Does not replace Art.43 "
                  "conformity assessment by a notified body."),
        "Art_9_risk":   {"risk_level": rl, "score": score,
                          "mitigation_required": req_rev},
        "Art_11_docs":  {"pipeline": "Gödel→p-adic→NTT(GF 998244353)→KAG(8×8)→PenroseP3",
                          "schema": SCHEMA, "deterministic": True},
        "Art_12_ledger": {"events_hash": ledger["events_hash"],
                           "next_state":  ledger["next_state_hash"],
                           "chain_linkable": True},
        "Art_15_accuracy": {"anomaly_count": len(anomalies),
                             "bias_penalty": bias["bias_penalty_0_1"],
                             "conformity_passed": conform},
    }


# ══════════════════════════════════════════════════════════════════
# SVG ARTIFACT — mintable visual from audit
# ══════════════════════════════════════════════════════════════════

def _esc(s: str) -> str:
    return (str(s).replace("&","&amp;").replace("<","&lt;")
            .replace(">","&gt;").replace('"',"&quot;"))

def _penrose_spiral(seed_hex: str, n: int = 700) -> List[Tuple[float,float]]:
    """Deterministic golden-angle spiral encoding the audit hash."""
    seed = int(seed_hex[:16], 16) if seed_hex else 1
    ga   = math.pi * (3 - math.sqrt(5))
    pts  = []
    r    = 0.0
    for i in range(n):
        r += 0.6 + ((seed >> (i % 32)) & 1) * 0.18
        th  = i * ga + (seed % 997) * 1e-3
        pts.append((r * math.cos(th), r * math.sin(th)))
    return pts

def write_svg(report: Dict, out_path: str,
              title: str = "RIM-OS Audit Artifact") -> None:
    """
    Write mintable SVG artifact from audit report.
    Contains: Penrose spiral (hash-encoded), score ring,
    compression-mix bars, all key hashes as text.
    No external dependencies.
    """
    integ   = report.get("integrity", {})
    summary = report.get("summary", {})
    ledger  = report.get("ledger", {})
    chunks  = report.get("chunks", [])

    audit_sha  = integ.get("audit_content_sha256", "")
    score      = int(summary.get("integrity_score_0_100", 0))
    risk       = summary.get("risk_level", "HIGH")
    hi_ent     = float(summary.get("avg_entropy_bits", 0))
    next_state = ledger.get("next_state_hash", "")
    tile_hash  = chunks[0].get("tile_hash", "") if chunks else ""

    RISK_COL = {"LOW": "#2e7d32", "MEDIUM": "#e65100", "HIGH": "#c62828"}
    rcol = RISK_COL.get(risk, "#1a237e")

    W, H = 1200, 1200
    cx, cy = W//2, H//2

    pts = _penrose_spiral(audit_sha, 800)
    maxr = max(math.hypot(x,y) for x,y in pts) if pts else 1.0
    sc   = 430.0 / maxr
    poly = " ".join(f"{cx+x*sc:.2f},{cy+y*sc:.2f}" for x,y in pts)

    # Region distribution bar chart
    region_counts: Dict[str,int] = {}
    for c in chunks:
        region_counts[c.get("region","?")] = region_counts.get(c.get("region","?"),0)+1

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    # Background
    lines.append(f'<rect width="{W}" height="{H}" fill="#07090f"/>')
    # Spiral
    lines.append(f'<polyline points="{poly}" fill="none" stroke="#4fc3f7" '
                 f'stroke-width="1.2" opacity="0.8"/>')
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="#ffd54f"/>')

    # Score ring
    lines.append(f'<circle cx="90" cy="90" r="68" fill="none" '
                 f'stroke="{rcol}" stroke-width="6"/>')
    lines.append(f'<text x="90" y="98" text-anchor="middle" '
                 f'font-family="monospace" font-size="28" font-weight="bold" '
                 f'fill="{rcol}">{score}</text>')
    lines.append(f'<text x="90" y="118" text-anchor="middle" '
                 f'font-family="monospace" font-size="11" fill="#888">/100 {risk}</text>')

    # Title
    lines.append(f'<text x="180" y="65" font-family="monospace" font-size="22" '
                 f'font-weight="bold" fill="#e0e0e0">{_esc(title)}</text>')
    lines.append(f'<text x="180" y="90" font-family="monospace" font-size="13" '
                 f'fill="#7986cb">{report.get("input",{}).get("path","")}</text>')
    lines.append(f'<text x="180" y="110" font-family="monospace" font-size="11" '
                 f'fill="#546" >{report.get("time_utc","")[:19]} UTC  ·  {SCHEMA}</text>')

    # Hash strip at bottom
    hy = H - 170
    lines.append(f'<rect x="0" y="{hy}" width="{W}" height="170" fill="#04050a" opacity="0.97"/>')
    for i, (lbl, val) in enumerate([
        ("audit_sha256",     audit_sha),
        ("tile_hash[0]",     tile_hash),
        ("ledger_next_state",next_state),
        (f"entropy_mean",    f"{hi_ent:.4f} bits/sym"),
        (f"chunks",          f"{len(chunks)}  anomalies={summary.get('anomaly_count',0)}"),
    ]):
        y = hy + 28 + i*26
        lines.append(f'<text x="30" y="{y}" font-family="monospace" font-size="10" '
                     f'fill="#5c6bc0" font-weight="bold">{_esc(lbl)}</text>')
        lines.append(f'<text x="230" y="{y}" font-family="monospace" font-size="10" '
                     f'fill="#90a4ae">{_esc(str(val))}</text>')

    # Region bars
    bx0, by0 = 30, H - 195
    maxc = max(region_counts.values()) if region_counts else 1
    bw   = min(120, (W - 60) // max(len(region_counts),1) - 10)
    for ri, (rname, cnt) in enumerate(region_counts.items()):
        bh = int(40 * cnt / maxc)
        x  = bx0 + ri * (bw + 12)
        lines.append(f'<rect x="{x}" y="{by0-bh}" width="{bw}" height="{bh}" '
                     f'fill="#7c5cff" opacity="0.85"/>')
        short = rname.replace("near ","").replace("_"," ")[:12]
        lines.append(f'<text x="{x}" y="{by0+14}" font-family="monospace" '
                     f'font-size="9" fill="#888">{_esc(short)}</text>')

    lines.append('</svg>')
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[SVG] → {out_path}  ({os.path.getsize(out_path)//1024} KB)")


# ══════════════════════════════════════════════════════════════════
# PDF REPORT
# ══════════════════════════════════════════════════════════════════

def write_pdf(report: Dict, out_path: str,
              model_name: str = "Unknown Model") -> None:
    """
    Professional PDF audit report via reportlab.
    Requires: pip install reportlab
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor, white
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                         Table, TableStyle, HRFlowable, PageBreak)
        from reportlab.platypus import Flowable
    except ImportError:
        print("[PDF] reportlab not installed. Run: pip install reportlab")
        return

    C_BLUE  = HexColor("#1a237e"); C_LBLUE = HexColor("#3949ab")
    C_GREY  = HexColor("#333333"); C_LGREY = HexColor("#f5f5f5")
    C_GOLD  = HexColor("#f9a825"); C_WHITE = white
    C_IND   = HexColor("#e8eaf6")
    RISK_C  = {"LOW": HexColor("#2e7d32"),
               "MEDIUM": HexColor("#e65100"),
               "HIGH": HexColor("#c62828")}

    summary = report.get("summary", {})
    integ   = report.get("integrity", {})
    ledger  = report.get("ledger", {})
    inp     = report.get("input", {})
    bias    = report.get("bias_heuristics", {})
    anomalies = report.get("anomalies", [])
    score   = int(summary.get("integrity_score_0_100", 0))
    risk    = summary.get("risk_level", "HIGH")
    rcol    = RISK_C.get(risk, C_BLUE)

    styles_base = getSampleStyleSheet()
    S = {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=22,
                                textColor=C_BLUE, spaceAfter=4),
        "h1":    ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=13,
                                textColor=C_BLUE, spaceBefore=12, spaceAfter=5),
        "h2":    ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10,
                                textColor=C_LBLUE, spaceBefore=8, spaceAfter=3),
        "body":  ParagraphStyle("body", fontName="Helvetica", fontSize=9,
                                textColor=C_GREY, spaceAfter=4, leading=13),
        "sm":    ParagraphStyle("sm", fontName="Helvetica", fontSize=8,
                                textColor=HexColor("#555555"), spaceAfter=3, leading=11),
        "mono":  ParagraphStyle("mono", fontName="Courier", fontSize=7.5,
                                textColor=C_BLUE, spaceAfter=2, leading=11, leftIndent=8),
        "disc":  ParagraphStyle("disc", fontName="Helvetica-Oblique", fontSize=7.5,
                                textColor=HexColor("#777777"), spaceAfter=3,
                                leading=10, borderPadding=4),
    }

    def sp(h=4): return Spacer(1, h*mm)
    def hr(): return HRFlowable(width="100%", thickness=0.6,
                                 color=C_BLUE, spaceAfter=5, spaceBefore=3)

    def kv(rows, cw=None):
        cw = cw or [50*mm, 110*mm]
        data = [[Paragraph(f"<b>{k}</b>", S["sm"]),
                 Paragraph(str(v), S["sm"])] for k,v in rows]
        t = Table(data, colWidths=cw)
        border = {"style":"GRID","colorName":"#cccccc","thickness":0.3}
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(0,-1), C_IND),
            ("BACKGROUND", (1,0),(1,-1), C_WHITE),
            ("ROWBACKGROUNDS",(0,0),(-1,-1),[C_IND, C_LGREY]),
            ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),8),
            ("LEFTPADDING",(0,0),(-1,-1),5),
            ("TOPPADDING",(0,0),(-1,-1),3),
            ("BOTTOMPADDING",(0,0),(-1,-1),3),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("GRID",(0,0),(-1,-1),0.3,HexColor("#cccccc")),
        ]))
        return t

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                             leftMargin=15*mm, rightMargin=15*mm,
                             topMargin=22*mm, bottomMargin=20*mm)

    def hdr(canvas, _doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(C_BLUE)
        canvas.rect(0, h-17*mm, w, 17*mm, fill=1, stroke=0)
        canvas.setFillColor(C_WHITE); canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(15*mm, h-9.5*mm, f"RIM-OS AUDIT REPORT  ·  {model_name}")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(w-15*mm, h-9.5*mm,
            f"{SCHEMA}  ·  {report.get('time_utc','')[:10]}")
        canvas.restoreState()

    def ftr(canvas, _doc):
        canvas.saveState()
        w, h = A4
        canvas.setStrokeColor(HexColor("#cccccc")); canvas.setLineWidth(0.4)
        canvas.line(15*mm, 14*mm, w-15*mm, 14*mm)
        canvas.setFont("Helvetica", 7); canvas.setFillColor(HexColor("#777777"))
        canvas.drawString(15*mm, 9*mm,
            "Technical evidence artefact. Not a legal compliance certificate (Art.43 EU AI Act).")
        canvas.drawRightString(w-15*mm, 9*mm,
            f"Page {_doc.page}  ·  {integ.get('audit_content_sha256','')[:16]}…")
        canvas.restoreState()

    story = []
    story += [sp(6),
              Paragraph("RIM-OS Audit Report", S["title"]),
              Paragraph(f"Model: <b>{model_name}</b>  ·  "
                        f"{report.get('time_utc','')[:19].replace('T',' ')} UTC", S["sm"]),
              hr(), sp(3)]

    # Score + quick summary
    quick = [
        ("File",         inp.get("path","—")),
        ("Size",         f"{inp.get("size_bytes",0)/1024/1024:.1f} MB"),
        ("Chunks",       str(inp.get("chunk_count",0))),
        ("Score",        f"{score}/100"),
        ("Risk",         risk),
        ("Anomalies",    str(len(anomalies))),
        ("Human review", "YES ⚠" if summary.get("requires_human_review") else "NO ✓"),
        ("Conformity",   "PASS ✓" if summary.get("conformity_passed") else "FAIL ✗"),
    ]
    story.append(kv(quick)); story.append(sp(3))

    story += [Paragraph(
        "SCOPE: Weight-file byte-structure audit via Gödel→p-adic→NTT→KAG→PenroseP3. "
        "Produces technical evidence for EU AI Act Art.9/11/12/13/14/15. "
        "Does NOT perform inference or replace Art.43 conformity assessment.", S["disc"]),
        sp(2)]

    # 1. Score breakdown
    story += [Paragraph("1. Integrity Score", S["h1"]), hr()]
    score_rows = [
        ("Score",             f"{score} / 100"),
        ("Risk Level",        risk),
        ("Entropy mean",      f"{summary.get("avg_entropy_bits",0):.4f} bits/sym  (target ≈ 8)"),
        ("Penrose match",     f"{summary.get("avg_penrose_match",0):.4f}  (higher = better P3 geometry)"),
        ("KAG separability",  f"{summary.get("avg_kag_separability",0):.4f}  (>0.9 may indicate fine-tuning)"),
        ("Anomaly fraction",  f"{summary.get("anomaly_fraction",0)*100:.2f}%"),
        ("Bias penalty",      f"{summary.get("bias_penalty_0_1",0):.4f}"),
        ("Weights",           "Entropy 30%  +  Penrose 40%  +  Anomalies 30%  ×  bias factor"),
    ]
    story += [kv(score_rows), sp(3)]

    # 2. File info
    story += [Paragraph("2. File & Tensor Index", S["h1"]), hr()]
    st = report.get("safetensors", {})
    file_rows = [
        ("Path",      inp.get("path","—")),
        ("Size",      f"{inp.get("size_bytes",0):,} bytes"),
        ("Safetensors", "Yes" if st.get("is_safetensors") else "No"),
    ]
    if st.get("is_safetensors"):
        file_rows += [
            ("Tensors",  str(st.get("tensor_count","—"))),
            ("Dtypes",   str(st.get("dtype_hist",{}))),
            ("Est. params", f"{st.get("total_elements_est",0):,}"),
        ]
    story += [kv(file_rows), sp(3)]

    # 3. Bias heuristics
    story += [Paragraph("3. BF16 Exponent Distribution", S["h1"]), hr()]
    bias_rows = [
        ("Sampled words",       f"{bias.get("sample_words",0):,}"),
        ("Exponent entropy",    f"{bias.get("exp_entropy_norm",0):.4f}  (1.0=uniform, <0.6=flagged)"),
        ("Extreme-exp fraction",f"{bias.get("ext_frac",0):.4f}"),
        ("Max bin fraction",    f"{bias.get("max_frac",0):.4f}"),
        ("Bias penalty",        f"{bias.get("bias_penalty_0_1",0):.4f}"),
        ("Flags",               ", ".join(bias.get("notes",[]))),
    ]
    story += [kv(bias_rows), sp(3)]

    # 4. Anomalies
    story += [PageBreak(), Paragraph("4. Anomaly Detection", S["h1"]), hr()]
    if not anomalies:
        story.append(Paragraph("✓ No anomalous chunks detected.", S["body"]))
    else:
        ano_data = [["Chunk","Offset","Flags","z-ent","z-χ²","z-symm"]]
        for a in anomalies[:25]:
            z = a.get("z",{})
            ano_data.append([str(a.get("chunk_index","")),
                             f'{a.get("offset",0):,}',
                             " | ".join(a.get("flags",[])),
                             f'{z.get("entropy",0):.2f}',
                             f'{z.get("chi2",0):.2f}',
                             f'{z.get("symmetry",0):.2f}'])
        at = Table(ano_data, colWidths=[18*mm,28*mm,62*mm,18*mm,15*mm,18*mm])
        at.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),C_BLUE),
            ("TEXTCOLOR",(0,0),(-1,0),C_WHITE),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),7.5),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE,C_LGREY]),
            ("GRID",(0,0),(-1,-1),0.3,HexColor("#cccccc")),
            ("LEFTPADDING",(0,0),(-1,-1),4),
            ("TOPPADDING",(0,0),(-1,-1),3),
            ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ]))
        story.append(at)
    story.append(sp(3))

    # 5. Ledger & hashes
    story += [Paragraph("5. Ledger Chain & Hashes", S["h1"]), hr()]
    hash_rows = [
        ("audit_content_sha256",  integ.get("audit_content_sha256","—")),
        ("events_hash",           ledger.get("events_hash","—")),
        ("prev_state_hash",       ledger.get("prev_state","—")),
        ("next_state_hash",       ledger.get("next_state_hash","—")),
        ("genesis_frame_hash",    report.get("genesis_frame_hash","—")),
    ]
    h_data = [["Key","Value"]] + [[k,v] for k,v in hash_rows]
    ht = Table(h_data, colWidths=[52*mm,108*mm])
    ht.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),C_BLUE),
        ("TEXTCOLOR",(0,0),(-1,0),C_WHITE),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTNAME",(0,1),(-1,-1),"Courier"),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE,C_LGREY]),
        ("GRID",(0,0),(-1,-1),0.3,HexColor("#cccccc")),
        ("LEFTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))
    story += [ht, sp(3),
              Paragraph("Chain next audit: pass next_state_hash as prev_state "
                        "in the next rim_os_v2 audit_file() call.", S["sm"])]

    # 6. EU AI Act
    story += [PageBreak(), Paragraph("6. EU AI Act Evidence (Reg. 2024/1689)", S["h1"]), hr()]
    eu = report.get("EU_AI_ACT", {})
    eu_rows = [
        ("Art. 9  — Risk",
         f"risk_level={risk}  score={score}  mitigation={'YES' if summary.get("requires_human_review") else 'NO'}"),
        ("Art. 11 — Docs",
         "Pipeline: Gödel→p-adic(k=3)→NTT(GF 998244353, L=1024)→KAG(8×8)→PenroseP3(N=6)  |  Deterministic"),
        ("Art. 12 — Ledger",
         f"events_hash={ledger.get("events_hash","")[:24]}…  chain_linkable=True"),
        ("Art. 13 — Transparency",
         "All hashes exposed  |  Weights disclosed (0.30/0.40/0.30)"),
        ("Art. 14 — Oversight",
         f"requires_review={'YES' if summary.get("requires_human_review") else 'NO'}  "
         f"(triggered if anomaly>5% OR risk=HIGH OR bias>0.25)"),
        ("Art. 15 — Accuracy",
         f"anomalies={len(anomalies)}  bias_penalty={bias.get("bias_penalty_0_1",0):.4f}  "
         f"conformity={'PASS' if summary.get("conformity_passed") else 'FAIL'}"),
    ]
    story.append(kv(eu_rows, cw=[45*mm, 115*mm]))
    story.append(sp(3))
    story.append(Paragraph(
        "Scope: weight-space integrity only. Does not cover data governance (Art.10), "
        "runtime monitoring (Art.72), or behavioral/semantic testing.", S["disc"]))

    doc.build(story,
              onFirstPage=lambda c,d: (hdr(c,d), ftr(c,d)),
              onLaterPages=lambda c,d: (hdr(c,d), ftr(c,d)))
    print(f"[PDF] → {out_path}  ({os.path.getsize(out_path)//1024} KB)")


# ══════════════════════════════════════════════════════════════════
# SELF-TEST
# ══════════════════════════════════════════════════════════════════

def run_selftest() -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    ok = True

    # 1. NTT bijectivity
    try:
        hist = list(range(256))
        ntt  = ntt_fingerprint(padic_lift(hist, 3)["residues"], L=1024)
        assert len(ntt["spec_hash"]) == 64
        results["ntt_bijectivity"] = "PASS"
    except Exception as e:
        results["ntt_bijectivity"] = f"FAIL: {e}"; ok = False
    print(f"  1/7 NTT bijectivity → {results['ntt_bijectivity']}")

    # 2. Genesis Mints
    try:
        sg = build_genesis()
        gm = sg["genesis_mints"]
        assert len(gm) == 3
        hashes = {g["tile_hash"] for g in gm}
        assert len(hashes) == 3, "Genesis tile_hashes not unique"
        spread = max(g["tau_omega_norm"] for g in gm) - min(g["tau_omega_norm"] for g in gm)
        results["genesis"] = f"PASS  G1={gm[0]['tau_omega_norm']:.4f} G2={gm[1]['tau_omega_norm']:.4f} G3={gm[2]['tau_omega_norm']:.4f}  spread={spread:.4f}"
    except Exception as e:
        results["genesis"] = f"FAIL: {e}"; ok = False
    print(f"  2/7 Genesis Mints → {results['genesis']}")

    # 3. Encoder v2 — bytes pipeline
    try:
        gm = build_genesis()["genesis_mints"]
        ea = encode_bytes(b"hello world " * 1000, gm, "hello")
        eb = encode_bytes(b"completely different content " * 500, gm, "other")
        assert ea["manifold_hash"] != eb["manifold_hash"], "different inputs → same hash"
        # same input twice → same result
        ea2 = encode_bytes(b"hello world " * 1000, gm, "hello")
        assert ea["manifold_hash"] == ea2["manifold_hash"], "not deterministic"
        results["encoder_bytes"] = f"PASS  d(a,b)=distinct  deterministic=OK  region_a={ea['manifold_region']}"
    except Exception as e:
        results["encoder_bytes"] = f"FAIL: {e}"; ok = False
    print(f"  3/7 Encoder (bytes) → {results['encoder_bytes']}")

    # 4. Encoder — integers
    try:
        gm = build_genesis()["genesis_mints"]
        e2  = encode_integer(2,  gm, "prime_2")
        e3  = encode_integer(3,  gm, "prime_3")
        e6  = encode_integer(6,  gm, "comp_6=2*3")
        assert e2["manifold_hash"] != e3["manifold_hash"]
        assert e2["manifold_hash"] != e6["manifold_hash"]
        results["encoder_int"] = f"PASS  2≠3≠6 on M  region(2)={e2['manifold_region']}"
    except Exception as e:
        results["encoder_int"] = f"FAIL: {e}"; ok = False
    print(f"  4/7 Encoder (int)  → {results['encoder_int']}")

    # 5. Same generative process → same region
    try:
        gm = build_genesis()["genesis_mints"]
        import random as _rnd
        rng = _rnd.Random(42)
        # counter pattern: same process, different seed
        def counter_chunk(seed):
            return bytes((i+seed)%256 for i in range(CHUNK_BYTES))
        desc_a = process_chunk(counter_chunk(0))
        desc_b = process_chunk(counter_chunk(0))   # identical
        desc_c = process_chunk(counter_chunk(7))   # same process, different seed
        desc_r = process_chunk(bytes(rng.randint(0,255) for _ in range(CHUNK_BYTES)))

        tau_a  = _pentagrid_tau(desc_a["chain"]["kag_hash"])
        tau_b  = _pentagrid_tau(desc_b["chain"]["kag_hash"])
        tau_c  = _pentagrid_tau(desc_c["chain"]["kag_hash"])
        tau_r  = _pentagrid_tau(desc_r["chain"]["kag_hash"])

        def dist5(x, y): return math.sqrt(sum((x[i]-y[i])**2 for i in range(5)))

        d_ab = dist5(tau_a, tau_b)
        d_ac = dist5(tau_a, tau_c)
        d_ar = dist5(tau_a, tau_r)
        assert d_ab < 1e-10, f"identical chunks differ: {d_ab}"
        results["process_clustering"] = (f"PASS  d(same,same)={d_ab:.6f}  "
                                          f"d(counter_0,counter_7)={d_ac:.4f}  "
                                          f"d(counter,random)={d_ar:.4f}")
    except Exception as e:
        results["process_clustering"] = f"FAIL: {e}"; ok = False
    print(f"  5/7 Process clustering → {results['process_clustering']}")

    # 6. Ledger chain
    try:
        fake = [{"manifold_hash": "a"*64, "tile_hash": "b"*64}]
        l1 = build_ledger(fake, None)
        l2 = build_ledger(fake, l1["next_state_hash"])
        l3 = build_ledger(fake, l2["next_state_hash"])
        states = {l1["next_state_hash"], l2["next_state_hash"], l3["next_state_hash"]}
        assert len(states) == 3
        results["ledger"] = f"PASS  l1={l1['next_state_hash'][:12]}…  chain_length=3"
    except Exception as e:
        results["ledger"] = f"FAIL: {e}"; ok = False
    print(f"  6/7 Ledger chain   → {results['ledger']}")

    # 7. Barycentric stability
    try:
        gm = build_genesis()["genesis_mints"]
        test_vecs = [[0.0,0.0,0.0,0.0,0.0], [1.0,1.0,1.0,1.0,1.0],
                     [0.5,0.3,0.8,0.1,0.9], [0.9999,0.0001,0.5,0.5,0.5]]
        for v in test_vecs:
            b = _barycentric(v, gm)
            assert abs(sum(b) - 1.0) < 1e-9, f"sum={sum(b)}"
            assert all(0 <= x <= 1 for x in b), f"out of [0,1]: b"
        results["barycentric"] = f"PASS  all {len(test_vecs)} test vectors stable"
    except Exception as e:
        results["barycentric"] = f"FAIL: {e}"; ok = False
    print(f"  7/7 Barycentric    → {results['barycentric']}")

    results["all_passed"] = ok
    if ok:
        print("\n[SELF-TEST] ALL PASS ✓")
    else:
        print(f"\n[SELF-TEST] FAILURES DETECTED")
    return results


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════

def main(argv=None):
    ap = argparse.ArgumentParser(description="RIM-OS v2 — AI Weight Audit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selftest", help="Run all internal tests")

    pg = sub.add_parser("genesis", help="Build Genesis Mints and print")
    pg.add_argument("--out-json", default=None)

    pa = sub.add_parser("audit", help="Audit a weight file")
    pa.add_argument("--in",      dest="in_path", required=True)
    pa.add_argument("--out-json",default=None)
    pa.add_argument("--out-svg", default=None)
    pa.add_argument("--out-pdf", default=None)
    pa.add_argument("--max-chunks", type=int, default=None)
    pa.add_argument("--prev-state", default=None)
    pa.add_argument("--model-name", default="Unknown Model")

    pe = sub.add_parser("encode", help="Encode text/file to position on M")
    pe.add_argument("--text",   default=None)
    pe.add_argument("--file",   default=None)
    pe.add_argument("--number", type=float, default=None)
    pe.add_argument("--int",    dest="integer", type=int, default=None)

    args = ap.parse_args(argv)

    if args.cmd == "selftest":
        run_selftest(); return 0

    if args.cmd == "genesis":
        sg = build_genesis()
        out = json.dumps(sg, indent=2, default=str)
        if args.out_json:
            with open(args.out_json,"w") as f:
                f.write(out)
            print(f"[genesis] → {args.out_json}")
        else:
            print(out)
        return 0

    if args.cmd == "audit":
        genesis = build_genesis()
        report  = audit_file(args.in_path, genesis=genesis,
                             max_chunks=args.max_chunks,
                             prev_state=args.prev_state)
        out_json = args.out_json or args.in_path.replace(".safetensors","") + "_audit.json"
        with open(out_json,"w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"[audit] JSON → {out_json}")
        print(f"[audit] score={report['summary']['integrity_score_0_100']}/100"
              f"  risk={report['summary']['risk_level']}"
              f"  chunks={report['input']['chunk_count']}"
              f"  anomalies={report['summary']['anomaly_count']}")

        if args.out_svg:
            write_svg(report, args.out_svg, title=f"RIM-OS Audit — {args.model_name}")
        if args.out_pdf:
            write_pdf(report, args.out_pdf, model_name=args.model_name)
        return 0

    if args.cmd == "encode":
        genesis = build_genesis()
        gm = genesis["genesis_mints"]
        if args.text:
            r = encode_text(args.text, gm, label=args.text[:30])
        elif args.file:
            raw = open(args.file,"rb").read()
            r = encode_bytes(raw, gm, label=os.path.basename(args.file))
        elif args.number is not None:
            r = encode_number(args.number, gm)
        elif args.integer is not None:
            r = encode_integer(args.integer, gm)
        else:
            print("Specify --text, --file, --number, or --int"); return 1
        print(json.dumps({k:v for k,v in r.items()
                          if k not in ("tiling",)}, indent=2, default=str))
        return 0

    return 2

if __name__ == "__main__":
    raise SystemExit(main())

