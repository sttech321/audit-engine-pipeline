## KAG invariants (RIM-401) — design note

### Goal (Reference Model v1.2 §5)
KAG is **not** a projection or a statistical decomposition. It is a **distillation to invariants**:
scale-invariant, directionally meaningful descriptors of the microscope body (Gödel→p-adic→NTT),
with redundancy removed.

This note defines a concrete invariant set that is:
- **Deterministic**
- **Scale-invariant** (multiplying the spectrum by a constant does not change invariants)
- **Stable** under small perturbations (no discontinuous thresholds)
- **Low-dimensional** enough for downstream cut-and-project

### Input
After RIM-302, we have the full 256-point NTT spectrum over GF(998244353). We derive a
non-negative magnitude vector \(m \in \mathbb{R}_{\ge 0}^{256}\) by signed-magnitude folding:
`m[i] = min(a[i], MOD - a[i])`.

### Proposed invariants (v1)
We treat the spectrum as a distribution by normalizing to a probability simplex:

\[
p_i = \frac{m_i + \epsilon}{\sum_j (m_j + \epsilon)}
\]

with a small fixed \(\epsilon\) (e.g. \(10^{-12}\)) to avoid zero-division.

Then compute:

1) **Directional moments over 5 residue classes**  
Map index \(i\) to a direction bucket \(d = i \bmod 5\). (This is the minimal 5-way symmetry
proxy available without introducing arbitrary geometry at this stage.)

\[
P_d = \sum_{i: i \bmod 5 = d} p_i
\]

This yields a 5-vector \(P \in [0,1]^5\), \(\sum P_d = 1\).

2) **Entropy of direction distribution** (scale-invariant)

\[
H_5(P) = -\sum_d P_d \log P_d \,/\, \log 5
\]

3) **Participation ratio** (effective support size, scale-invariant)

\[
PR(p) = \frac{(\sum_i p_i)^2}{\sum_i p_i^2} = \frac{1}{\sum_i p_i^2}
\]

Normalize to \([0,1]\) by `PR/256`.

4) **Low-order spectrum “shape” moments** (scale-invariant)
Compute the first 3 centralized moments of the index distribution weighted by \(p_i\):
mean \(\mu\), variance \(\sigma^2\), skewness \(\gamma\). These are invariant to magnitude scale.

### Output object
The invariant bundle (example):
- `dir_mass[5]` (the \(P_d\) vector)
- `dir_entropy` (0..1)
- `participation` (0..1)
- `index_mu` (0..255 normalized to 0..1)
- `index_var` (normalized)
- `index_skew` (bounded)

### Why this matches the model “enough” (and what it is not)
This is a **first implementable invariant family** that satisfies scale-invariance and determinism.
It is not claimed to be the final Freedman‑Mulligan / Vanherreweghe formalization; it is a
concrete stepping stone that removes the current non-invariant 8×8 additive decomposition.

### Acceptance criteria mapping
- Scale invariance test: scaling `m` by constant leaves invariants unchanged (within tolerance).
- Stability: small perturbations to `m` produce small changes in invariants (no hard thresholds).

### Next note dependencies
This invariant set must feed the cascade split (RIM-402) and trajectory aggregation (RIM-404).

