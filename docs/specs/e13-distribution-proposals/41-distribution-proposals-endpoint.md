# E13 Issue 41: `POST /api/v1/distribution/proposals` — Zoning + Width Packing

Status: Draft
Issue: #41
Epic: #39
Contract: [40-distribution-proposal-contract.md](40-distribution-proposal-contract.md)
Studio: outis10/kalitron-furniture-studio#125

## Goal

Generate 2–3 distinct, plausible distributions that fit the measured walls,
combining LLM reasoning for **what goes where** with a deterministic packer for
**exact widths**.

## Pipeline

1. **Geometry prep (deterministic):** free segments per wall and row
   (between corners, doors, columns, full-height obstacles), service points
   (water/drain/gas), window/beam/hood bands for the upper row, and — when
   `allowFreestanding` and the room is closed — the room polygon and the
   free floor area where an island/peninsula keeps `aisle.warningMm`.
2. **Zoning (LLM):** given segments, services, interview and library summary,
   choose distinct zoning strategies (e.g. sink under window vs. on wall B;
   fridge at run end; island/peninsula only if the room and interview allow it),
   and for each an ordered intent per run
   (`[FILLER, DRAWER_BASE, SINK_BASE, DISHWASHER, …]`) with rough widths.
   Output validated against a JSON schema; invalid output → one retry.
3. **Width packing (deterministic):** for each run, choose widths from
   `allowedWidthsMm` that fit the segment exactly with fillers ≤
   `maxFillerMm`, keeping sink/cooking modules over their service points when
   possible (small search / DP over allowed widths).
4. **Distinctness:** drop near-duplicate proposals.
5. **Repair:** if `previousIssues` is present, include them in the zoning
   prompt and prefer changes on the affected walls.

The gateway does **not** implement the full Studio rule set (to avoid a third
engine); Studio validates authoritatively. The packer only guarantees fit and
allowed widths.

## Acceptance Criteria

- [ ] Returns `count` proposals (or fewer with a warning if the room allows only one).
- [ ] Every run fits its segment exactly (packer invariant, unit-tested).
- [ ] Only library codes and allowed widths are used (unit-tested).
- [ ] Islands/peninsulas proposed only when `allowFreestanding` and aisles ≥ `aisle.warningMm` (unit-tested).
- [ ] Prompt version recorded in `rawExtraction`.
- [ ] 400/502/504 as per contract; never 500 for bad LLM output.

## Test Plan

- Unit: geometry prep, packer (exact fit, filler limits, service alignment), schema validation of LLM output with fixtures.
- API tests with mocked LLM.

## Open Questions

- [ ] Model choice/cost per call; target latency (Studio timeout 180 s).
- [ ] Upper row: propose always, or only when the interview asks for it?
