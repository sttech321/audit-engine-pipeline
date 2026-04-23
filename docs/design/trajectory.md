## File-level trajectory aggregation (RIM-404) — design note

### Goal (Reference Model §2 bijectivity; Ticket RIM-404)
File-level position must be **order-sensitive**. A simple arithmetic mean over chunks is not
injective with respect to chunk order.

We need a deterministic `combine(state, chunk)` update that:
- Depends on chunk index order
- Is stable (doesn't explode with chunk count)
- Preserves determinism

### Proposed state (v1)
Maintain a 5D state vector `S ∈ ℝ^5` and a 5D phase state `T ∈ [0,1)^5`.

Initialization:
- `S0 = [0,0,0,0,0]`
- `T0 = [0.5]*5`

### Combine rule (v1)
For chunk i with `(k5_i, tau_i)`:

1) Update position state:
\[
S_{i+1} = rot(S_i, \theta_i) + \beta_i \cdot k5_i
\]

- `rot(·)` is a fixed mixing rotation in 5D implemented as a circulant linear transform
  (cheap, deterministic, reversible enough for injectivity-in-practice).
- `θ_i` depends on i (e.g. `θ_i = (i+1) * 2π/φ mod 2π`) to enforce order sensitivity.
- `β_i` is a deterministic weight (e.g. `β_i = 1 + i/16` capped) to prevent early/late domination.

2) Update phase state:
\[
T_{i+1} = (T_i + \gamma \cdot tau_i + \delta_i) \bmod 1
\]

Where `δ_i` is an index-dependent offset vector (irrational-based), and γ a small constant.

### Output mapping
After processing all chunks:
- `file_k5 = normalize(S_n)` into a target scale (existing `scale=50` convention).
- `file_tau = T_n`
- world position uses `file_k5`

### Acceptance criteria mapping
- Reordering chunks changes `(file_k5, file_tau)`.
- Identical file re-run gives identical outputs.

### Notes
This v1 combine rule is a deterministic “trajectory hash” over the chunk stream, expressed in
continuous 5D. If later work requires stronger injectivity proofs, we can replace the rotation
with an explicitly invertible integer matrix over a bounded ring.

