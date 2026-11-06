# E17 / VIS-01 diagnostic import

Status: Implementing; first real import visually reviewed, broader kitchen MVP pending.
Parent: https://github.com/outis10/kalitron-furniture-studio/issues/174
Contract: Studio PR #175, commit 93ccd0ced99488ee8cc810f805dbb1792a396c8d.

Import the Fusion diagnostic-pilot/0.1 package (kfs-render/1.0 envelope) in a
separate local Blender process. Validate references, hashes, ownership, local
and world bounds, units, matrix convention and IDs before scene mutation.
Package vertices are local mm, placements world mm; Blender vertices are world
meters after one application of the matrix. Preserve mirrored winding, source
visibility and body-to-piece association. Do not infer finishes from roles.

Use a staging collection and only replace the same project's previous collection
after import succeeds. Preserve unrelated scene objects. Save a new diagnostic
.blend and JSON report; refuse to overwrite an existing output directory.
The importer uses synchronous functions because it runs outside the FastAPI
service; no web endpoints or asynchronous render job protocol are introduced.

Acceptance: nested/rotated, reflected, shared and multi-body fixture imports;
invalid units, IDs, references, checksums and matrices are rejected. Pure Python
tests validate the package; a real Blender smoke test must additionally verify
five placed bodies, meter-scale bounds, visibility and reimport without duplicates.
No final-ready export, catalog resolution, registry, worker service, LLM or
finished commercial render is claimed. Manual kitchen A/B validation follows.

## Verified local import

The operator's corrected v0.1.2 export imported 196 body placements under Blender
5.2.3 LTS with 196 independent placed Fusion-bound checks passing. The operator
reviewed orientation and shelf widths positively. A known source body failed
tessellation and remains recorded as omitted. The next illustrative material and
camera work is scoped separately in `render-preview-spec.md`; full final-ready
finishes, kitchen B and revision-matching acceptance remain pending.
