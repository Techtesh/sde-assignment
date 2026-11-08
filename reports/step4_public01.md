# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.339 | +1.8% | 0.240 | +0.7% | 0.497 | +1.2% | 0% | 61 (47) |
| nw_kyc | 0.369 | +1.6% | 0.240 | -0.7% | 0.602 | +1.9% | 3% | 20 (21) |
| nw_renewal | 0.412 | -1.8% | 0.260 | -1.4% | 0.550 | +0.7% | 0% | 39 (42) |
| ALL | 0.370 | +0.4% | 0.247 | -0.4% | 0.536 | +1.1% | 1% | 120 (110) |

## Changes applied by the controller

10 applied — neutral: 8, beneficial: 1, harmful: 1

- ks_cancel v2 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v2 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_kyc v2 (controller_approved) dims=['voice'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v4 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v3 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v4 (controller_approved) dims=['voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- nw_kyc v3 (controller_approved) dims=['voice'] engageΔ=-0.014 didΔ=+0.000 → **harmful**
- ks_cancel v5 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v5 (controller_approved) dims=['voice'] engageΔ=-0.002 didΔ=+0.000 → **neutral**

## Governance

```
{
  "approval_requests": 6,
  "decisions": {
    "approved": 6,
    "expired": 0
  },
  "rejection_reasons": {},
  "applied_via_approval": 6,
  "auto_applied": 4,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 2,
    "nw_kyc": 1
  }
}
```

## Incidents

```
[]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0