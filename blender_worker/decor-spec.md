# E17 — First procedural presentation accessories

Status: Reviewed for implementation; visual approval pending.
Parent: https://github.com/outis10/kalitron-furniture-studio/issues/174

The operator authorized one small potted plant and one cutting board, added in
Blender separately from the real furniture. Keep the last olive/white/black
palette. No Fusion edits, ComfyUI image edits, external assets or LLM integration.

## Deterministic library and placement

Version two original procedural assets: `potted_plant_v1` and `cutting_board_v1`.
Dimensions are configured in mm and converted to Blender meters once. A strict
optional `decor` array selects asset, ID, size, rotation and a supported placement
preset. Unknown assets/options and invalid sizes fail before scene mutation.

Select a visible COUNTERTOP surface automatically. Proposed footprints must fit
within its bounds with clearance, be supported by actual upward-facing mesh hits,
and avoid overlap with other accessories and visible source objects. Fail clearly
instead of placing unsupported/floating/intersecting props. The first presets
use the longest countertop, plant toward its back/right and board toward its
front/left, leaving the remainder clear. This is not general-purpose packing.

Place all generated objects in an owned decor collection with distinct metadata,
anchor body/instance IDs, transforms, dimensions and procedural-library version.
Rebuilding the same export replaces only that owned decoration after staging
succeeds; never delete source furniture or unrelated scene objects.

## Acceptance

- Pure tests cover mm placement, rotated footprint fitting, pair overlap, too-small
  surfaces and invalid configuration. Real Blender validates mesh support and
  source-object clearance before creating props.
- Render all three views with coherent light/shadows and no source visibility edits
  beyond the existing recorded interior-door override.
- Hash all source mesh/topology/transforms before/after rendering as usual.
- Report props and support checks; save the editable scene and a fresh output.
- Human review checks scale, contact, material appearance and uncluttered placement.
- Future Spanish prompts must translate to these reviewed operations/configs,
  not arbitrary generated Python. No prompt-driven agent is claimed yet.

## Workstation result

Blender 5.2.3 LTS rendered all three accessory views in 53.47 s. Both props passed
nine support samples and conservative source-clearance checks. The 196 source
bodies retained identical geometry/topology/transforms and restored visibility.
Two consecutive rebuilds retained exactly two accessory roots and 25 total decor
objects, without duplicates or source changes. 30 pure worker/config/placement
tests pass. Operator visual approval of the accessories remains pending.
