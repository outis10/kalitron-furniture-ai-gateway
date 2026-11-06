# E17 diagnostic Blender worker

Standalone local process for Studio [E17 #174](https://github.com/outis10/kalitron-furniture-studio/issues/174).
No FastAPI route or LLM is involved. Synchronous Blender operations run here,
outside the async web service. Contract baseline: Studio PR #175 at
93ccd0ced99488ee8cc810f805dbb1792a396c8d; this is the diagnostic VIS-01 profile,
not a final-ready implementation of VIS-02. See `pilot-spec.md`.

Requires Blender 4.2+ with Python. Executed on Blender 5.2.3 LTS: the synthetic
fixture imported 5 bodies and a real diagnostic kitchen imported 194 bodies without
worker errors. Source-to-scene fidelity still requires the operator's visual review;
the dimensional check compares the imported mesh to its manifest, not independently
to Fusion. The pure validator uses only the Python standard library.

For the Microsoft Store installation on Windows, the working command-line entry
point was `%LOCALAPPDATA%\Microsoft\WindowsApps\blender-launcher.exe`; executing
the binary directly under `Program Files\WindowsApps` may return Access denied.

## Run on Windows

Export with `KaliExportRender` in the Fusion add-in repository first, then:

```powershell
& 'C:\path\to\blender.exe' --background --factory-startup --python-exit-code 1 --python blender_worker/import_package.py -- --package 'C:\exports\KFS_RENDER_example' --output 'C:\renders\import-001'
```

Choose a new output directory every time. Output: `diagnostic.blend` and
`import-report.json`. Open the scene, select the KFS collection's objects and
frame selection (Numpad decimal). The startup cube/camera/light are ordinary
Blender defaults, outside the KFS collection; remove/hide them for visual review.
No professional render or real catalog material is claimed by this import spike.

The strict OBJ subset is intentionally parsed directly: no automatic OBJ axis
rotation, object splitting, naming heuristics or double transform. Local vertices
and world translation convert mm to meters exactly once. The worker bakes each
placement once, reverses mirrored winding and stores source IDs and the original
matrix as object properties. One body object is created for each placed body.
Hidden source instances/bodies remain present but hidden. Snapshot IDs must not
be used to apply overrides from an older export.

All references, checksums, ownership, transforms and declared mesh bounds are
validated before modifying the scene. When exporter v0.1.2 provides independent
Fusion placed-body bounds, actual world mesh vertices must match those within
1 mm before import. This detects wrong evaluated dimensions and placements.
Older packages lack that independent source check and cannot establish source fidelity.
Imported world vertices are checked within
a provisional 1 mm tolerance. Source geometry/metadata omissions remain visible
in the report; diagnostic import success does not mean source completeness.
Colors are unassigned neutral placeholders, not an approved finish.

Calling `import_package` again within a running Blender session replaces only
the collection for the same project after staging succeeds. It does not delete
other projects or decorations. CLI startup creates a fresh scene independently.

## Tests

```powershell
python -m unittest discover -s blender_worker/tests -p test_import_package.py -v
```

Synthetic shared, multi-body, nested/rotated/mirrored fixture:

```powershell
& 'C:\path\to\blender.exe' --background --factory-startup --python-exit-code 1 --python blender_worker/import_package.py -- --package blender_worker/tests/fixtures/nested-mirror --output 'C:\renders\fixture-001'
```

Expected: 3 definition meshes, 4 component instances, 5 placed body objects.
Two mirrored door bodies are present but hidden through their parent.
Source bounds span X=0..1000, Y=-400..400, Z=0..18 mm.
Check dimensions, orientation and visibility on a real kitchen module before
expanding to kitchen A, its revision and kitchen B. Persistent registry, full
finish/grain resolution, cameras, lights and rendering follow this pilot.

## Illustrative material and lighting previews

`render_preview.py` reads the imported .blend, its matching original package and
an explicit `kfs-preview/0.1` JSON configuration. See `render-preview-spec.md`.
The included white-matte preset is an **unconfirmed illustrative proposal**, not
a catalog mapping or an assertion about the operator's actual finishes.

`presets/mint-kitchen-preview.json` captures the operator's requested palette:
doors/covers mint, gola/plinth matte black, countertop white, interiors matte
white and pearl-beige walls. The numerical mint shade and its initial matte
roughness are illustrative pending visual review; they are not calibrated to
Tabylam 2VJ or any other manufacturer SKU. Unclassified parts remain diagnostic.
Project-only definition overrides stay in local configs, separate from this
reusable preset and from manufacturer catalog records.

`presets/olive-kitchen-preview.json` varies only the mint finish to an illustrative
olive matte while preserving the requested white/black/pearl-beige palette. Its
color is not calibrated to EGGER U640 ST9 or another commercial reference.

`presets/olive-kitchen-decor-preview.json` adds a small procedural potted plant
(180×180×320 mm envelope) and rounded wooden cutting board (350×240×18 mm).
See `decor-spec.md`. `decor_plan.py` checks configuration/footprints;
`decor_assets.py` checks actual countertop support, source clearance and creates
an independently owned accessory collection. Nine ray samples per prop verify
support. This is deliberately limited to flat surfaces, not arbitrary mesh packing.
Asset materials are original procedural shaders; no external texture images are
downloaded. Accessories do not receive furniture instance IDs or change Fusion
geometry. Their placement/anchor IDs and checks are included in the render report.
Rebuilding replaces only the same export's owned accessory collection; an empty
decor array clears owned props. Spanish prompt control remains future work.

```powershell
& 'C:\path\to\blender.exe' --background 'C:\renders\import-001\diagnostic.blend' --python-exit-code 1 --python blender_worker/render_preview.py -- --package 'C:\exports\KFS_RENDER_example' --config blender_worker/presets/white-matte-preview.json --output 'C:\renders\preview-001'
```

Outputs: `perspectiva.png`, `frontal.png`, `interior.png`, `presentacion.blend`,
`config.json` and `render-report.json`. The report records assignments, fallbacks,
source issues, engine/device, camera positions, hidden interior doors and timings.
Source vertices, topology and object transforms are hashed before/after rendering;
source visibility is restored before saving. The interior view hides only explicit
DOOR instances, never drawer fronts or structural parts. A separate presentation
floor and soft area lights are added. No source geometry or manufacturing model is
modified. No wood grain, external textures or material product matching is claimed.

The worker prefers available OptiX/CUDA GPU devices and otherwise uses CPU Cycles.
The first GPU render may spend time compiling kernels. A fresh output directory
is mandatory. If a job fails, its report records FAILED; partial images are not a
successful completed presentation. Render completion remains illustrative and
non-final until the operator approves finishes and source fidelity.

Test configuration and precedence without Blender:

```powershell
python -m unittest discover -s blender_worker/tests -p 'test_*.py' -v
```

## Interactive 360 pilot

Open a completed `presentacion.blend` in background mode and run
`export_interactive.py -- --output <fresh-directory>`. Outputs `kitchen.glb`,
`kitchen-no-walls.glb` and `export-report.json`. Only visible source bodies and
accessories belonging to the same snapshot are included; the source blend is
not saved. Reject scenes with multiple imported projects. Coordinates convert
once from Blender Z-up meters to glTF Y-up meters. Preserve source extras.

Use `check_interactive.py -- --glb <kitchen.glb>` with the same source blend to
verify all visible source IDs, material assignments and world vertices after
reimport (maximum coordinate error 0.01 mm). Report written beside the GLB.

For a standalone local preview, copy `interactive-viewer.html` as `index.html`
beside the GLBs and copy `@google/model-viewer@4.4.0/dist/model-viewer.min.js`
and its LICENSE from Studio's installed dependency. Serve only that directory
on 127.0.0.1 using Python http.server. No external CDN or geometry upload.
Supports orbit, zoom, auto rotation, reset and wall variants. Browser lighting
and procedural textures differ from the Cycles render; this remains illustrative.

Studio's authenticated `/visualization-preview` route opens a selected local GLB
without uploading it. Project storage and persisted result associations remain
future integration work.

Current validation, confirmed tags and pending hidden gola profiles: see
[pilot-status.md](pilot-status.md). Source-hidden bodies stay hidden in the GLB.

The renderer creates a dedicated presentation scene, linking only the matching
source collection and owned setup/accessories. It retains the original scene
without rendering its startup cube, camera, lights or other unrelated objects.
The saved blend opens in the isolated scene. `excluded_scene_objects` and
`scene_ownership_verified` in the render report make this explicit.
Run `check_presentation_scene.py -- --report <path.json>` on that saved blend
to verify the active scene contains only owned objects. This fixes the white
block previously obscuring the kitchen corner: it was Blender's startup Cube,
not source furniture or a camera distortion. The GLB already omitted the cube.

Operator accepted the corrected corner on 2026-11-05. Current validation and
remaining scope: [pilot-acceptance.md](pilot-acceptance.md).
