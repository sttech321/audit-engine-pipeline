# RIM-OS Reference Model — v1.2 → v1.3 amendment

This file records the textual amendment to be applied to
`RIM-OS_Reference_Model_v1_2.docx`. The `.docx` itself is maintained
outside this repository; this markdown is the source of truth for the
amendment so that the change is reviewable in version control alongside
the implementation change in `backend/rim_os_v2.py`.

To apply: bump the title-page version from **v1.2** to **v1.3**, add the
changelog entry below, and replace the body of §8.4 with the replacement
text below. Save and re-file the document.

---

## Title page

```
Version: v1.3
```
(was `v1.2`)

## Changelog (add at top of document, above §1)

> **v1.3 — §8.4 amendment (Option 3: absolute positions).**
> Removes the small-amplitude position drift previously described in
> §8.4. Positions on the manifold are now absolute: prior commits are
> not displaced by later ones. The wave / convergence behaviour
> previously expressed as drift is reframed as resonance in the
> register (§10). Verification is correspondingly cheaper and fully
> reproducible against the Genesis anchors. Mass-homologous injection
> attacks are addressed at the deployment layer (§13), not by drift
> dynamics.
>
> Implementation: the `RIM-501: amplitude-bounded convergence` block in
> `audit_file` (backend/rim_os_v2.py) has been removed. `chain_seed`
> remains an accepted parameter and continues to be threaded to the
> SVG render seed (RIM-203-FINAL) and stored per block as
> `chain_seed_at_commit`; it no longer perturbs `k5`, `world_x`,
> `world_y`, `tau_vectors`, `barycentric`, `manifold_hash`, or
> `tile_hash`. Regression coverage:
> `backend/tests/test_relational_preservation.py::test_position_independent_of_chain_seed`.

## Replacement body for §8.4

> ### §8.4 Convergence as resonance, not deformation.
>
> The seed converges. Each new commit refines it. But prior commits
> are not displaced by later ones — their positions on the manifold
> are determined entirely by the deterministic pipeline run against
> the Genesis anchors. New commits do not drift old ones.
>
> The wave effect is realised in the register (§10), not in the
> chain. When a new commit is added, the geometric positions of
> prior commits do not change, but the network of structural
> relationships between them grows: every new commit potentially
> resonates with prior commits whose KAG invariants share its
> character, and that resonance is readable through the register
> API as barycentric similarity.
>
> This is what makes verification cheap and reproducible: the
> position of any commit can be recomputed at any time by running
> the pipeline against the Genesis anchors, with the same result
> regardless of how the chain has grown since.
>
> Mass-homologous injection attacks — an adversary committing many
> near-identical artifacts to dominate a region — are prevented at
> the deployment layer (§13), not by drift dynamics. Specifically:
> rate limits, authentication, and structural-similarity detection
> in the register API are the means by which homologous commit
> streams are recognised and throttled.

---

## In-repo follow-ups (already applied as part of this commit)

- `docs/design/cascade.md` — header citation updated from "Reference Model v1.2 §6.3" to "Reference Model v1.3 §6.3".
- `docs/design/kag_invariants.md` — header citation updated from "Reference Model v1.2 §5" to "Reference Model v1.3 §5".
- `backend/rim_os_v2.py::audit_file` — drift block removed; replaced by a
  comment block citing v1.3 §8.4 (Option 3) explaining that `chain_seed`
  is accepted for API stability but does not influence `map_position`.
- `backend/tests/test_relational_preservation.py` — the
  `test_amplitude_bound_same_input_seed_variation_is_small` test (which
  permitted up to 0.25 of drift) is replaced by
  `test_position_independent_of_chain_seed`, which asserts that
  `map_position` is bit-identical across `chain_seed="seedA"`,
  `chain_seed="seedB"`, and `chain_seed=None` for the same input.
