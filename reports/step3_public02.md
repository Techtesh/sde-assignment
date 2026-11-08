# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.285 | +15.2% | 0.201 | +9.6% | 0.493 | +3.6% | 26% | 89 (330) |
| nw_kyc | 0.374 | -0.1% | 0.238 | -1.8% | 0.602 | +1.7% | 0% | 33 (31) |
| nw_renewal | 0.436 | +2.2% | 0.266 | +1.6% | 0.550 | +0.4% | 5% | 54 (55) |
| ALL | 0.354 | +6.0% | 0.231 | +3.9% | 0.538 | +1.4% | 13% | 176 (416) |

## Changes applied by the controller

2 applied — beneficial: 2

- ks_cancel v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.481 → **beneficial**
- ks_cancel v4 (controller_approved) dims=['prompt_version'] engageΔ=+0.102 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 2,
  "decisions": {
    "approved": 2,
    "expired": 0
  },
  "rejection_reasons": {},
  "applied_via_approval": 2,
  "auto_applied": 0,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "ks_cancel": 1
  }
}
```

## Incidents

```
[
  {
    "type": "did_flagged",
    "workflow": "ks_cancel",
    "at": "D2 10:00",
    "flagged_did_share_by_day": {
      "2": 0.156,
      "3": 0.0,
      "4": 0.0,
      "5": 0.0,
      "6": 0.0,
      "7": 0.0,
      "8": 0.0,
      "9": 0.0
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D3 11:30",
    "mttr_minutes": 1365,
    "fixed_by": "controller_approved"
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_renewal",
    "at": "D5 15:00"
  }
]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{}
```

Credits used: 6 · validation runs: 1 · LLM fix calls: 1