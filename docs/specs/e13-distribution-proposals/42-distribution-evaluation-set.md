# E13 Issue 42: Distribution Proposal Evaluation Set

Status: Draft
Issue: #42
Epic: #39
Studio: outis10/kalitron-furniture-studio#122 (rules + vectors used for scoring)

## Goal

Measure proposal quality and detect regressions when prompts, models or the
packer change.

## Scope

- 10–15 anonymized cases under `tests/eval/distribution/<case>/`: measurement,
  interview, library snapshot, and the distribution a Kalitron designer
  actually approved (reference).
- Metrics per run:
  - **validity rate** — % proposals with zero unacknowledgeable ERRORs under
    Studio rules (run through Studio's validate endpoint or its published
    vectors/engine in a CI job);
  - fit and allowed-width invariants (must be 100 %);
  - service alignment rate (sink over water/drain, cooking over gas);
  - distinctness between proposals;
  - designer rating (1–5) recorded manually per case.
- Report table to stdout / `report.json`.

## Acceptance Criteria

- [ ] Cases committed with no client PII.
- [ ] `pytest -m eval_distribution` prints the metrics table (slow/manual; calls the model).
- [ ] Baseline recorded below.

## Baseline

| Date | Prompt | Validity | Service alignment | Distinctness | Designer rating |
| --- | --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD | TBD |
