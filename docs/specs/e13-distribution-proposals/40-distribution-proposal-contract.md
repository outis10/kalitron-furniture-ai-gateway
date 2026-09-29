# E13 Issue 40: Distribution Proposal Contract

Status: Draft
Issue: #40
Epic: #39
Studio: outis10/kalitron-furniture-studio#125 (caller), #118 (distribution schema), #120 (library)

## Goal

Define the request/response Studio and the gateway build against for
distribution proposals.

## Endpoint

`POST /api/v1/distribution/proposals` — service-to-service (Studio only), JSON.

## Request

```json
{
  "sessionCode": "KD-2026-120",
  "language": "es-MX",
  "count": 3,
  "measurement": {
    "ceilingHeightMm": 2440,
    "walls": [ { "wallCode": "A", "designLengthMm": 3448, "outOfPlumbMm": 4, "startXMm": 0, "startYMm": 0, "angleDeg": 0 } ],
    "roomClosed": true,
    "corners": [ { "cornerCode": "E-AB", "angleDeg": 90 } ],
    "elements": [
      { "wallCode": "A", "code": "TA", "category": "SERVICE", "xMm": 1500, "yMm": 450 },
      { "wallCode": "A", "code": "V", "category": "OPENING", "xMm": 1200, "yMm": 1050, "widthMm": 900, "heightMm": 1000 }
    ]
  },
  "interview": {
    "projectType": "KITCHEN",
    "style": "moderno",
    "preferences": ["más cajones", "refrigerador de 90 cm"],
    "chatSummary": "…",
    "v0ClientNotes": "…",
    "designerInstructions": "sin isla"
  },
  "library": { "libraryVersion": "2026-10-01.1", "modules": [], "applianceSlots": [] },
  "ruleParams": { "minFillerMm": 50, "serviceToleranceMm": 100, "clearances": { "FRIDGE": 30, "COOKING": 300, "CORNER": 50 } },
  "allowFreestanding": true,
  "startingPoint": null,
  "previousIssues": []
}
```

- `library` and `ruleParams` shapes = Studio #120 export and catalog params.
- `startingPoint`: optional existing distribution (e.g. v0) to refine.
- `previousIssues`: Studio validation issues from a previous attempt (repair retry).
- No client email, phone or address.

## Response `200`

```json
{
  "proposals": [
    {
      "label": "Propuesta A — tarja bajo ventana",
      "rationaleEsMx": "Tarja alineada con agua y drenaje del muro A; zona de cocción en B sobre gas; refrigerador al final del muro B.",
      "assumptions": ["Refrigerador de 900 mm"],
      "distribution": { "schemaVersion": 1, "walls": [ { "wallCode": "A", "runs": [ { "row": "BASE", "startOffsetMm": 0, "items": [ { "kind": "FILLER", "widthMm": 50 } ] } ] } ] }
    }
  ],
  "rawExtraction": { "promptVersion": "distribution-v1.0.0", "model": "…", "packer": "v1" }
}
```

- `distribution` follows the Studio E13 schema (`walls/runs/items` and, when
  `allowFreestanding`, `freestandingRuns` for islands/peninsulas — Studio #128;
  no `xMm`; `itemUuid` optional — Studio assigns).
- `ruleParams` are the **effective** values (defaults + admin overrides, Studio #127).
- Proposals must use only codes in `library` and widths in `allowedWidthsMm`.

## Errors

| Status | Cause |
| --- | --- |
| 400 | Invalid request (no walls, empty library, count ∉ 1–3) |
| 401 | Missing service auth |
| 502 | LLM provider failure |
| 504 | Timeout |

## Acceptance Criteria

- [ ] Pydantic models for request/response with fixtures shared with Studio.
- [ ] Contract mirrored/linked from Studio #125.
