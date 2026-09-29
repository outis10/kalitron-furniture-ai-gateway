---
epic: E13
title: AI distribution proposals from validated site measurement
status: Draft
issues: "#40 #41 #42"
studio_epic: "outis10/kalitron-furniture-studio#118"
---

# E13 — AI distribution proposals

Status: Draft
Epic: #39
Studio epic: outis10/kalitron-furniture-studio#118 (distribution model, rules, editor)
Background: outis10/kalitron-furniture-studio#104 (E12 site measurement)

## Role change

The gateway **no longer reads measurements** (E12 formal-croquis issues
#31–#38 were closed). Measurements arrive in Studio as structured, validated
data from the KFS-APP mobile app. The gateway's new role in this flow is to
**propose 2–3 kitchen distributions** (which modules go on each wall) from:

- the validated site measurement,
- the client interview (KitchenSpec, style, chat summary, v0 notes, designer instructions),
- the module library (templates with allowed widths, rows, tags),
- rule parameters (clearances, tolerances).

Studio is authoritative: it validates every proposal with the shared
declarative rules and the designer decides. v1 sketch analysis
(`/api/v1/sketch/analyze`) is unchanged.

## Issues

| Issue | Spec |
| --- | --- |
| #40 Proposal contract | [40-distribution-proposal-contract.md](40-distribution-proposal-contract.md) |
| #41 Endpoint: zoning + width packing | [41-distribution-proposals-endpoint.md](41-distribution-proposals-endpoint.md) |
| #42 Evaluation set | [42-distribution-evaluation-set.md](42-distribution-evaluation-set.md) |

## Epic acceptance criteria

- [ ] Endpoint returns 2–3 proposals in the Studio distribution schema.
- [ ] Every proposal uses only library codes and allowed widths, and fits its walls.
- [ ] Each proposal includes a Spanish rationale and assumptions.
- [ ] Evaluation baseline recorded (validity rate under Studio rules, designer rating).
