## Cascade: split into k5 (parallel) and τ (perpendicular) (RIM-402/403) — design note

### Goal (Reference Model v1.3 §6.3)
The cascade must produce **two independent objects**:
- **k5**: lattice position (parallel component)
- **τ**: phase offsets (perpendicular component)

Deriving τ from k5 (or clamping τ) violates cut-and-project faithfulness and injectivity.

### Inputs
KAG invariant bundle (see `kag_invariants.md`), assumed scale-invariant and deterministic.

For v1 we assume we have:
- `dir_mass[5]` (sums to 1)
- `dir_entropy`
- `participation`
- `index_mu/index_var/index_skew`

### Proposed deterministic split (v1)

#### k5 (parallel)
We map directional mass deviations from uniform into a signed vector:

\[
k5_d = s \cdot (P_d - 1/5)
\]

where \(s\) is a scale constant (kept as existing `scale=50.0` for now).
This makes k5 depend on *directional structure*, not on arbitrary clamped ranges.

#### τ (perpendicular phase)
We map *independent* invariant scalars into a 5-vector phase by modular reduction:

Let:
- \(u_0 = index\_mu\)
- \(u_1 = index\_var\)
- \(u_2 = index\_skew\)
- \(u_3 = dir\_entropy\)
- \(u_4 = participation\)

Then define:

\[
\tau_i = (u_i + \alpha_i) \bmod 1
\]

with fixed irrational offsets \(\alpha_i\) (constants), e.g. derived from \(\phi\):
\(\alpha_i = frac(\phi \cdot (i+1))\).

**Important**: no clamping. Only `% 1.0`.

### Acceptance criteria mapping
- Perturb k5 only: world position changes, phase stays stable (within tolerance).
- Perturb τ only: tiling phase changes, world position stable.
- Far-out values map distinctly due to modular reduction (no clamp collapse).

### Migration notes
- `compute_k5` becomes `compute_k5_and_tau(invariants, scale=...)`.
- `_tau_pentagrid_from_k5` is removed once all callers are migrated.

