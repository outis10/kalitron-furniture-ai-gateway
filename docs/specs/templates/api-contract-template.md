# API Contract: Endpoint Name

Status: Draft

## Endpoint

`METHOD /api/path`

## Auth

- Required: yes/no
- Roles:
- Public access:

## Request

```json
{
  "field": "value"
}
```

## Validation

- `field`: required, constraints.

## Success Response

Status: `200 OK`

```json
{
  "field": "value"
}
```

## Error Responses

| Status | Cause | Body |
| --- | --- | --- |
| 400 | Validation failure | ProblemDetail |
| 401 | Missing authentication | ProblemDetail |
| 500 | Unexpected failure | ProblemDetail |

## Persistence

- Records created:
- Records updated:
- Records not stored:

## Observability

- Logs:
- Metrics:
- Correlation identifiers:
