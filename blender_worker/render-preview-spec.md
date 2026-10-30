# E17 / VIS-04/05/06 — Local material and lighting preview

Status: Reviewed for implementation; operator approval of finishes remains pending.
Parent: https://github.com/outis10/kalitron-furniture-studio/issues/174
Builds on the verified diagnostic Fusion import. This is a local preview, not
completion of the full MVP, stable identity contract, catalog or agent.

## Behavior

A versioned Blender CLI reads an imported .blend, the matching export manifest
and explicit JSON presentation configuration. Produce PNG previews and a reusable
.blend in a fresh output directory. Rendering runs outside FastAPI. No LLM needed.

Configuration separates an illustrative material library from explicit operator
assignments by role, definition or instance. Role assignments are deliberate
preview choices, never automatic inference of actual construction material.
Unassigned pieces use a clearly recorded diagnostic fallback. Preserve all source
vertices, triangles, object transforms and master source visibility. Only the
interior view temporarily hides DOOR objects; report and restore those overrides.
No hinge motion, model scaling, extra furniture, changed shelf widths or geometry
modifiers. A separately owned presentation floor is optional and recorded.

Materials use Principled BSDF and physical world scale. No external texture
download or unverified product/color matching. Nondirectional solid finishes are
supported first. Real wood requires explicit local grain metadata and validated
mapping; do not silently invent its orientation.

Scene presets provide soft area lights, neutral world lighting and cameras at
human eye height. Output perspective, front and interior previews, plus config
snapshot, source export ID, material assignment provenance, source validation
issues, per-frame timings and geometry-integrity verification. Record hardware,
engine and samples. Unknown configuration keys/roles/material references, invalid
numbers or an occupied output directory fail clearly.

## Verification

Pure-Python tests cover configuration validation, assignment precedence and
unknown material handling. Blender runtime verifies source mesh/transform hashes
before and after setup/render, confirms source visibility restoration, writes all
three previews, and records renderer/version/time. Visually review exposure,
framing, proportions and illustrative finishes on the operator's validated kitchen.
Never mark final/client-ready while finishes/grain or source omissions remain.

## Runtime verification

Completed on Blender 5.2.3 LTS / OptiX / RTX 3050 Ti Laptop GPU: three 1280x960
Cycles previews at 32 samples, saved .blend and report. Source geometry/topology/
transforms hash remained unchanged and visibility was restored. Total 341.41 s;
first perspective 273.21 s, front 21.21 s, interior 24.09 s. The first-render
preparation cost is not a production throughput benchmark. Illustrative palette
remains unconfirmed; 196 imported source bodies and the known source omission are
recorded, not corrected by rendering. 21 pure-Python worker/config tests pass.
