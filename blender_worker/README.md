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
validated before modifying the scene. Imported world vertices are checked within
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
