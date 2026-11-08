# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.288 | +16.4% | 0.202 | +9.8% | 0.496 | +4.1% | 29% | 79 (330) |
| nw_kyc | 0.370 | -1.3% | 0.242 | +0.1% | 0.588 | -0.8% | 0% | 31 (31) |
| nw_renewal | 0.422 | -1.0% | 0.260 | -0.8% | 0.548 | -0.0% | 6% | 65 (55) |
| ALL | 0.350 | +4.8% | 0.230 | +3.4% | 0.535 | +0.9% | 14% | 175 (416) |

## Changes applied by the controller

13 applied — neutral: 11, beneficial: 2

- ks_cancel v2 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v2 (controller_approved) dims=['voice'] engageΔ=+0.005 didΔ=+0.000 → **neutral**
- ks_cancel v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.482 → **beneficial**
- ks_cancel v4 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v5 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v7 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v8 (controller_approved) dims=['prompt_version'] engageΔ=+0.102 didΔ=+0.000 → **beneficial**
- nw_renewal v3 (controller_approved) dims=['voice'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- ks_cancel v9 (controller_auto) dims=['voice'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- nw_renewal v4 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v10 (controller_auto) dims=['voice'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- ks_cancel v11 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v12 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**

## Governance

```
{
  "approval_requests": 6,
  "decisions": {
    "approved": 5,
    "rejected": 1,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 5,
  "auto_applied": 8,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 2,
    "nw_kyc": 1,
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
      "2": 0.188,
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
    "mttr_minutes": 300,
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