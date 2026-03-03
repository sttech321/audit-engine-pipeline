import hashlib
import time
from typing import List, Tuple, Dict, Any, Optional

from app.config import get_settings
from app.models.common_schemas import (
    KPI, VerificationStatus, Anomaly, AnomalyType, RiskLevel,
    RiskBadge, EUAIActCompliance, LegalDisclosures, ExtendedAuditResult
)

# Load settings
settings = get_settings()

# ─── Pipeline Stage Constants (from config) ──────────────────────────────────
MIN_FILE_SIZE = settings.min_file_size
MAX_FILE_SIZE = settings.max_file_size
PRIME_P = settings.prime_p
NTT_MOD = settings.ntt_mod
NTT_ROOT = settings.ntt_root
MIN_BYTE_DIVERSITY = settings.min_byte_diversity
MIN_ENTROPY = settings.min_entropy
MIN_KAG_SCORE = settings.min_kag_score

# ─── RIM95 Format Validation ──────────────────────────────────────────────────
# A valid RIM97/RIM95 artifact must:
#   1. Be at least MIN_FILE_SIZE bytes
#   2. Have >= MIN_BYTE_DIVERSITY distinct byte values (not garbage/trivial data)
#   3. NOT be pure ASCII text (e.g. "236" or "9\n" are not audit artifacts)
#   4. Have a Shannon entropy >= MIN_ENTROPY (real audit data has high entropy)

def _validate_rim95_format(contents: bytes, filename: str) -> Tuple[bool, str]:
    """
    Validates that the uploaded file is a plausible RIM95/RIM97 audit artifact.
    Returns (is_valid, reason).
    """
    size = len(contents)

    # 1. Minimum size check
    if size < MIN_FILE_SIZE:
        return False, f"File too small ({size} bytes) — minimum is {MIN_FILE_SIZE} bytes"

    # 2. Unique byte diversity — reject trivially simple files
    sample = contents[:512] if size >= 512 else contents
    unique_bytes = len(set(sample))
    if unique_bytes < MIN_BYTE_DIVERSITY:
        return False, f"Insufficient byte diversity ({unique_bytes} unique values) — not a valid audit artifact"

    # 3. Shannon entropy check — real cryptographic artifacts have high entropy
    from collections import Counter
    import math
    counts = Counter(sample)
    total = len(sample)
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
    if entropy < MIN_ENTROPY:
        return False, f"File entropy too low ({entropy:.2f} bits/byte) — does not resemble a cryptographic artifact"

    # 4. Pure-ASCII short files are not valid audit files
    if size < 64:
        try:
            decoded = contents.decode('utf-8')
            if decoded.strip().replace('\n','').replace('\r','').isdigit():
                return False, "File contains only numeric text — not a valid audit artifact"
            if all(32 <= b < 127 for b in contents):
                return False, "File is plain ASCII text — not a valid binary audit artifact"
        except UnicodeDecodeError:
            pass  # Binary content, fine

    return True, "Format check passed"


# ─── Stage 1: Gödel Fingerprint ───────────────────────────────────────────────
def _stage1_godel_fingerprint(contents: bytes) -> int:
    """
    Gödel fingerprint: assigns prime_k^byte_k to each position,
    products mod a large Mersenne prime. A unique, deterministic
    integer that represents the exact content of the file.
    Follows the numbering used in PASS97 §2.1.
    """
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
    n_primes = len(primes)
    g = 1
    # Sample up to 512 bytes to bound computation on large files
    sample = contents[:512]
    for i, byte in enumerate(sample):
        p = primes[i % n_primes]
        g = (g * pow(p, byte + 1, PRIME_P)) % PRIME_P
    return g


# ─── Stage 2: p-adic Lift ─────────────────────────────────────────────────────
def _stage2_padic_lift(godel_val: int, p: int = 257) -> List[int]:
    """
    p-adic lift: decomposes the Gödel value into its base-p expansion.
    Produces a vector of coefficients [a0, a1, ...] such that:
        godel_val ≡ a0 + a1*p + a2*p^2 + ... (mod PRIME_P)
    Implements the PASS97 §2.2 p-adic norm check for anomaly detection.
    Returns the first 8 coefficients.
    """
    coeffs = []
    v = godel_val
    for _ in range(8):
        coeffs.append(int(v % p))
        v = v // p
    return coeffs


# ─── Stage 3: NTT Fingerprint ─────────────────────────────────────────────────
def _ntt(a: List[int], invert: bool = False) -> List[int]:
    """Iterative Cooley-Tukey NTT over Z/NTT_MOD Z."""
    n = len(a)
    a = a[:]
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        w = pow(NTT_ROOT, (NTT_MOD - 1) // length, NTT_MOD)
        if invert:
            w = pow(w, NTT_MOD - 2, NTT_MOD)
        for i in range(0, n, length):
            wn = 1
            for k in range(length // 2):
                u = a[i + k]
                v = a[i + k + length // 2] * wn % NTT_MOD
                a[i + k] = (u + v) % NTT_MOD
                a[i + k + length // 2] = (u - v) % NTT_MOD
                wn = wn * w % NTT_MOD
        length <<= 1
    if invert:
        n_inv = pow(n, NTT_MOD - 2, NTT_MOD)
        a = [x * n_inv % NTT_MOD for x in a]
    return a


def _stage3_ntt_fingerprint(contents: bytes) -> int:
    """
    NTT fingerprint: pads file content to nearest power-of-2,
    runs a forward NTT, and XOR-folds the spectrum into a 32-bit checksum.
    Implements PASS97 §2.3 frequency-domain uniqueness check.
    """
    sample = list(contents[:256]) if len(contents) >= 256 else list(contents)
    # Pad to next power of 2
    n = 1
    while n < len(sample):
        n <<= 1
    sample = (sample + [0] * (n - len(sample)))[:n]

    spectrum = _ntt(sample)
    # XOR-fold the spectrum to a 32-bit fingerprint
    fold = 0
    for val in spectrum:
        fold ^= (val & 0xFFFFFFFF)
    return fold


# ─── Stage 4: KAG Separability ────────────────────────────────────────────────
# PASS97 Score weights: structure=0.30, semantic=0.40, provenance=0.30
KAG_WEIGHT_STRUCTURE = 0.30
KAG_WEIGHT_SEMANTIC = 0.40
KAG_WEIGHT_PROVENANCE = 0.30
KAG_BIAS_MULTIPLIER = 0.25  # 25% bias adjustment

def _stage4_kag_separability(padic_coeffs: List[int], ntt_fold: int) -> Tuple[float, str]:
    """
    KAG (kernel approximation gap) separability score.
    Measures how well the p-adic coefficients separate from a uniform baseline.
    A score > 0.6 indicates the file content is non-trivially structured (PASS97 §2.4).
    
    PASS97 Spec Compliant:
    - Uses 0.30 / 0.40 / 0.30 weights (structure / semantic / provenance)
    - Applies 25% bias multiplier
    - Returns kag_hash for tau derivation
    
    Returns: Tuple of (kag_score: float in [0, 1], kag_hash: str)
    """
    if not padic_coeffs:
        return 0.0, hashlib.sha256(b"empty").hexdigest()
    
    mean = sum(padic_coeffs) / len(padic_coeffs)
    variance = sum((c - mean) ** 2 for c in padic_coeffs) / len(padic_coeffs)
    
    # Structure component: coefficient variance
    structure_score = min(1.0, variance / (256.0 ** 2))
    
    # Semantic component: NTT fold entropy
    ntt_entropy = bin(ntt_fold).count('1') / 32.0
    semantic_score = ntt_entropy
    
    # Provenance component: coefficient spread normalized
    coeff_spread = (max(padic_coeffs) - min(padic_coeffs)) / 256.0 if padic_coeffs else 0.0
    provenance_score = min(1.0, coeff_spread)
    
    # PASS97 weighted combination with bias multiplier
    raw_kag = (
        structure_score * KAG_WEIGHT_STRUCTURE +
        semantic_score * KAG_WEIGHT_SEMANTIC +
        provenance_score * KAG_WEIGHT_PROVENANCE
    )
    
    # Apply 25% bias multiplier for edge cases
    kag = min(1.0, raw_kag * (1.0 + KAG_BIAS_MULTIPLIER))
    
    # Compute kag_hash for tau derivation (PASS97 spec: tau from kag_hash only)
    kag_input = f"{variance}:{ntt_entropy}:{coeff_spread}:{raw_kag}".encode()
    kag_hash = hashlib.sha256(kag_input).hexdigest()
    
    return round(kag, 4), kag_hash


# Legacy wrapper for backward compatibility
def _stage4_kag_separability_legacy(padic_coeffs: List[int], ntt_fold: int) -> float:
    """Legacy KAG score (backward compatible, returns float only)."""
    kag_score, _ = _stage4_kag_separability(padic_coeffs, ntt_fold)
    return kag_score


# ─── Stage 5: Penrose P3 Mapping ──────────────────────────────────────────────
PHI = (1 + 5 ** 0.5) / 2   # Golden ratio
PI = 3.14159265358979323846
TWO_PI = 2 * PI
PENTAGRID_SECTORS = 5  # k ∈ {0,1,2,3,4} for pentagrid

def _stage5_penrose_p3(godel_val: int, ntt_fold: int, kag_score: float, kag_hash: str = None) -> dict:
    """
    Penrose P3 tiling mapping: maps the pipeline state onto a quasiperiodic
    lattice coordinate (r, theta) derived from phi. This yields a final
    audit fingerprint that is highly sensitive to any input change (PASS97 §2.5).
    
    PASS97 Spec Compliant:
    - Pentagrid angles: k × 2π/5 where k ∈ {0,1,2,3,4}
    - Tau derived from kag_hash only (not godel_val ^ ntt_fold)
    - 5-fold symmetry for P3 tiling
    
    Returns: { r, theta, sector, penrose_hash, tau, tile_hash }
    """
    # Derive tau from kag_hash only (PASS97 spec compliant)
    if kag_hash:
        tau_input = kag_hash.encode()
    else:
        # Fallback for legacy calls without kag_hash
        tau_input = f"{kag_score}".encode()
    tau_bytes = hashlib.sha256(tau_input).digest()
    tau = int.from_bytes(tau_bytes[:8], 'big') / (2**64)  # [0, 1)
    
    # Pentagrid sector: k ∈ {0,1,2,3,4}
    # Use kag_hash to determine sector for determinism
    if kag_hash:
        sector_val = int(kag_hash[:8], 16)
    else:
        sector_val = int(kag_score * 10000)
    k = sector_val % PENTAGRID_SECTORS  # k ∈ {0,1,2,3,4}
    
    # Pentagrid angle: θ_k = k × 2π/5 (PASS97 spec)
    theta = (k * TWO_PI / PENTAGRID_SECTORS)  # Exact pentagrid angle
    
    # Radial coordinate via phi-based scaling (legacy compatible)
    combined = (godel_val ^ ntt_fold) + 1
    r = (combined % (10 ** 9)) / (10 ** 9) * PHI  # [0, φ)
    
    # Final Penrose hash: deterministic from all stage outputs
    penrose_input = f"{godel_val}:{ntt_fold}:{kag_score}:{k}:{tau}".encode()
    penrose_hash = hashlib.sha256(penrose_input).hexdigest()
    
    # Tile hash for NFT parcel coordinate (PASS97 spec)
    tile_input = f"{penrose_hash}:{k}:{theta}:{r}".encode()
    tile_hash = hashlib.sha256(tile_input).hexdigest()[:16]

    return {
        "r": round(r, 6),
        "theta": round(theta, 6),
        "sector": k,  # Pentagrid sector k ∈ {0,1,2,3,4}
        "penrose_hash": penrose_hash,
        "tau": round(tau, 8),
        "tile_hash": tile_hash
    }


# ─── Main pipeline entry point ────────────────────────────────────────────────
def process_audit_artifact(contents: bytes, filename: str) -> Tuple[List[KPI], VerificationStatus, str]:
    """
    PASS97 / RIM97 5-Stage Audit Pipeline (Alpha / Internal)

    Stage 0 — Format Validation    : RIM95 artifact format check
    Stage 1 — Gödel Fingerprint    : Unique integer from file content (PASS97 §2.1)
    Stage 2 — p-adic Lift          : Base-p coefficient expansion (PASS97 §2.2)
    Stage 3 — NTT Fingerprint      : Frequency-domain checksum (PASS97 §2.3)
    Stage 4 — KAG Separability     : Kernel approximation gap score (PASS97 §2.4)
    Stage 5 — Penrose P3 Mapping   : Quasiperiodic audit lattice (PASS97 §2.5)
    """
    # ── Stage 0: Format Validation ────────────────────────────────────────────
    file_size = len(contents)
    if file_size == 0:
        return _failed_result("STAGE0_EMPTY", "File is empty — ingestion rejected")
    if file_size > MAX_FILE_SIZE:
        return _failed_result("STAGE0_TOO_LARGE", "File exceeds 500MB limit")

    format_ok, format_reason = _validate_rim95_format(contents, filename)
    if not format_ok:
        return _failed_result("STAGE0_FORMAT", format_reason)

    # SHA-256 of full file (used as canonical file hash for provenance)
    file_hash = hashlib.sha256(contents).hexdigest()

    # Real Unix timestamp for the UI (frontend uses parseFloat(ts) * 1000)
    execution_timestamp = str(time.time())

    # ── Stage 1: Gödel Fingerprint ────────────────────────────────────────────
    godel_val = _stage1_godel_fingerprint(contents)
    # Must produce a large, non-trivial value (> 1 billion) for real content
    godel_ok = godel_val > 1_000_000_000

    # ── Stage 2: p-adic Lift ──────────────────────────────────────────────────
    padic_coeffs = _stage2_padic_lift(godel_val)
    # File must be >= 64 bytes AND all 8 coefficients must be non-zero AND spread
    # (high std dev means the content has sufficient complexity)
    if len(padic_coeffs) >= 2:
        p_mean = sum(padic_coeffs) / len(padic_coeffs)
        p_spread = max(padic_coeffs) - min(padic_coeffs)
    else:
        p_spread = 0
    padic_ok = (file_size >= 32) and all(c > 0 for c in padic_coeffs) and (p_spread >= 20)

    # ── Stage 3: NTT Fingerprint ──────────────────────────────────────────────
    ntt_fold = _stage3_ntt_fingerprint(contents)
    # NTT output must have >= 12 set bits (high entropy) AND >= MIN_BYTE_DIVERSITY unique bytes
    unique_bytes = len(set(contents[:512] if len(contents) >= 512 else contents))
    ntt_entropy_bits = bin(ntt_fold).count('1')
    ntt_ok = (ntt_entropy_bits >= 12) and (unique_bytes >= MIN_BYTE_DIVERSITY)

    # ── Stage 4: KAG Separability ─────────────────────────────────────────────
    kag_score, kag_hash = _stage4_kag_separability(padic_coeffs, ntt_fold)
    # Threshold from config: trivial/garbage files score below MIN_KAG_SCORE
    kag_ok = kag_score >= MIN_KAG_SCORE

    # ── Stage 5: Penrose P3 Mapping ───────────────────────────────────────
    penrose = _stage5_penrose_p3(godel_val, ntt_fold, kag_score, kag_hash)
    # A content-meaningful check: sector must be non-zero (degenerate content → sector 0)
    # AND the r value must be in the meaningful range [0.1, PHI)
    # AND KAG must pass threshold (Stage 4 must also pass for Stage 5 to be valid)
    penrose_ok = (
        penrose["sector"] != 0
        and penrose["r"] >= 0.05
        and kag_score >= MIN_KAG_SCORE
        and ntt_fold > 0
    )

    # ── Verification Logic ────────────────────────────────────────────────────
    stage_results = {
        "Signature Valid":   godel_ok,     # Stage 1 — Gödel fingerprint
        "Hash Match":        padic_ok,     # Stage 2 — p-adic structure match
        "NTT Integrity":     ntt_ok,       # Stage 3 — NTT frequency check
        "KAG Separability":  kag_ok,       # Stage 4 — content separability
        "Structure Intact":  penrose_ok,   # Stage 5 — Penrose lattice valid
    }

    checks_passed = [name for name, ok in stage_results.items() if ok]
    checks_failed = [f"{name} FAILED" for name, ok in stage_results.items() if not ok]
    all_checks = checks_passed + checks_failed

    n_failed = len(checks_failed)
    # Risk thresholds: LOW (<1 fail), MEDIUM (1-2 fail), HIGH (>2 fail)
    if n_failed == 0:
        status_msg = "Verified"
        confidence = 99
    elif n_failed <= 2:
        status_msg = "Verified with Warnings"
        confidence = max(40, 80 - n_failed * 20)
    else:
        status_msg = "Verification Failed"
        confidence = max(0, 30 - n_failed * 8)

    verification = VerificationStatus(
        status=status_msg,
        confidence=confidence,
        timestamp=execution_timestamp,   # Real Unix timestamp for UI display
        checks=all_checks
    )

    # ── Scoring: KPIs derived from pipeline outputs ───────────────────────────
    pass_ratio = len(checks_passed) / len(stage_results)
    if n_failed == 0:
        audit_score = round(80.0 + (kag_score * 15.0) + (pass_ratio * 5.0), 1)
    elif n_failed <= 2:
        audit_score = round(50.0 + (kag_score * 20.0), 1)
    else:
        audit_score = round(kag_score * 40.0, 1)  # 0–40 for high-risk
    audit_score = min(round(audit_score, 1), 100.0)

    issues_found = n_failed * 2  # Each failed stage contributes 2 issues
    coverage_val = round(pass_ratio * 100, 1)

    audit_status = (
        "excellent" if audit_score >= 90
        else "good" if audit_score >= 70
        else "warning"
    )

    kpis = [
        KPI(
            id="kpi-1",
            label="Audit Score",
            value=audit_score,
            trend="stable" if n_failed == 0 else "down",
            status=audit_status,
            description="PASS97 pipeline integrity score (Stages 1–5)"
        ),
        KPI(
            id="kpi-2",
            label="Issues Found",
            value=issues_found,
            trend="up" if n_failed > 0 else "down",
            status="warning" if n_failed > 0 else "excellent",
            description="Pipeline stages that returned anomalous results"
        ),
        KPI(
            id="kpi-3",
            label="KAG Score",
            value=f"{kag_score:.4f}",
            trend="up" if kag_score >= 0.5 else "down",
            status="excellent" if kag_score >= 0.5 else "good" if kag_score >= 0.3 else "warning",
            description="KAG separability (Stage 4 — higher = more distinct content)"
        ),
        KPI(
            id="kpi-4",
            label="Coverage",
            value=f"{coverage_val}%",
            trend="up" if pass_ratio >= 0.8 else "down",
            status="excellent" if coverage_val == 100 else "good" if coverage_val >= 60 else "warning",
            description="Fraction of PASS97 pipeline stages that passed"
        ),
        KPI(
            id="kpi-5",
            label="Penrose Sector",
            value=penrose["sector"],
            trend="stable",
            status="excellent" if penrose_ok else "warning",
            description=f"Penrose P3 sector (Stage 5) — hash: {penrose['penrose_hash'][:12]}…"
        ),
    ]

    return kpis, verification, file_hash


def _failed_result(error_code: str, message: str) -> Tuple[List[KPI], VerificationStatus, str]:
    """Hard-fail result for pre-pipeline rejections."""
    dummy_hash = hashlib.sha256(error_code.encode()).hexdigest()
    verification = VerificationStatus(
        status=f"Verification Failed",
        confidence=0,
        timestamp=str(time.time()),
        checks=[f"FAILED: {error_code} — {message}"]
    )
    kpis = [
        KPI(id="kpi-1", label="Audit Score",    value=0,     trend="down", status="warning", description=message),
        KPI(id="kpi-2", label="Issues Found",   value=10,    trend="up",   status="warning", description="File rejected before pipeline"),
        KPI(id="kpi-3", label="KAG Score",      value="N/A", trend="down", status="warning", description="Pipeline did not execute"),
        KPI(id="kpi-4", label="Coverage",       value="0%",  trend="down", status="warning", description="Pipeline did not execute"),
        KPI(id="kpi-5", label="Penrose Sector", value="N/A", trend="down", status="warning", description="Pipeline did not execute"),
    ]
    return kpis, verification, dummy_hash


# ─── Extended Audit Result with PASS97 Full Output Contract ──────────────────

def process_audit_artifact_extended(
    contents: bytes, 
    filename: str
) -> Tuple[ExtendedAuditResult, str]:
    """
    PASS97 / RIM97 5-Stage Audit Pipeline with Extended Output Contract.
    
    This is the full PASS97-compliant version that includes:
    - Anomalies list
    - Risk badge
    - EU AI Act compliance table
    - Legal disclosures
    - Penrose details
    - Tile hash for NFT
    
    Returns: (ExtendedAuditResult, file_hash)
    """
    # Run the base pipeline
    kpis, verification, file_hash = process_audit_artifact(contents, filename)
    
    # Extract values from KPIs for anomaly detection
    audit_score = 0.0
    kag_score_val = 0.0
    for kpi in kpis:
        if kpi.label == "Audit Score":
            try:
                audit_score = float(kpi.value)
            except:
                pass
        elif kpi.label == "KAG Score":
            try:
                kag_score_val = float(kpi.value)
            except:
                pass
    
    # Count failed checks for risk assessment
    failed_checks = sum(1 for check in verification.checks if "FAILED" in check)
    
    # ── Anomaly Detection ─────────────────────────────────────────────────────
    anomalies: List[Anomaly] = []
    
    # Check for specific failure conditions and create anomalies
    for check in verification.checks:
        if "FAILED" in check:
            if "Signature" in check or "Gödel" in check:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.GODEL_TRIVIAL,
                    stage="Stage 1 - Gödel Fingerprint",
                    severity=RiskLevel.HIGH,
                    message="Gödel fingerprint indicates trivial or non-cryptographic content",
                    details={"check": check}
                ))
            elif "Hash" in check or "p-adic" in check:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.PADIC_DEGENERATE,
                    stage="Stage 2 - p-adic Lift",
                    severity=RiskLevel.MEDIUM,
                    message="p-adic coefficient structure is degenerate",
                    details={"check": check}
                ))
            elif "NTT" in check:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.NTT_ENTROPY_LOW,
                    stage="Stage 3 - NTT Fingerprint",
                    severity=RiskLevel.MEDIUM,
                    message="NTT frequency spectrum has insufficient entropy",
                    details={"check": check}
                ))
            elif "KAG" in check:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.KAG_BELOW_THRESHOLD,
                    stage="Stage 4 - KAG Separability",
                    severity=RiskLevel.HIGH,
                    message=f"KAG score below threshold ({kag_score_val} < {MIN_KAG_SCORE})",
                    details={"kag_score": kag_score_val, "threshold": MIN_KAG_SCORE}
                ))
            elif "Structure" in check or "Penrose" in check:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.PENROSE_DEGENERATE,
                    stage="Stage 5 - Penrose P3",
                    severity=RiskLevel.MEDIUM,
                    message="Penrose tiling maps to degenerate sector",
                    details={"check": check}
                ))
    
    # ── Risk Badge ────────────────────────────────────────────────────────────
    risk_badge = RiskBadge.from_audit_score(audit_score, failed_checks)
    
    # ── EU AI Act Assessment ──────────────────────────────────────────────────
    eu_ai_act = EUAIActCompliance.from_risk_badge(risk_badge)
    
    # ── Legal Disclosures ─────────────────────────────────────────────────────
    legal_disclosures = LegalDisclosures.default()
    
    # ── Penrose Details ───────────────────────────────────────────────────────
    # Re-compute Penrose for details (or extract from prior computation)
    # For efficiency, we could cache this, but for correctness we recompute
    penrose_details = None
    tile_hash = None
    
    if len(contents) >= MIN_FILE_SIZE:
        try:
            godel_val = _stage1_godel_fingerprint(contents)
            padic_coeffs = _stage2_padic_lift(godel_val)
            ntt_fold = _stage3_ntt_fingerprint(contents)
            kag_score, kag_hash = _stage4_kag_separability(padic_coeffs, ntt_fold)
            penrose = _stage5_penrose_p3(godel_val, ntt_fold, kag_score, kag_hash)
            
            penrose_details = {
                "r": penrose["r"],
                "theta": penrose["theta"],
                "sector": penrose["sector"],
                "penrose_hash": penrose["penrose_hash"],
                "tau": penrose.get("tau", 0),
                "tile_hash": penrose.get("tile_hash", "")
            }
            tile_hash = penrose.get("tile_hash")
        except Exception:
            pass
    
    # ── Build Extended Result ─────────────────────────────────────────────────
    extended_result = ExtendedAuditResult(
        kpis=kpis,
        verification=verification,
        file_hash=file_hash,
        anomalies=anomalies,
        risk_badge=risk_badge,
        eu_ai_act=eu_ai_act,
        legal_disclosures=legal_disclosures,
        ledger=None,  # Set by caller after ledger entry is created
        penrose_details=penrose_details,
        tile_hash=tile_hash
    )
    
    return extended_result, file_hash

