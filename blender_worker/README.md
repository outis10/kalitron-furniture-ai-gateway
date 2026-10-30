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
