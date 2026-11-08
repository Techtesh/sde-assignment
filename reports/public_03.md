# Grade report — public_03_load

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.342 | +0.1% | 0.245 | +0.3% | 0.498 | -0.5% | 0% | 413 (408) |
| arav_kyc_1 | 0.358 | +1.1% | 0.213 | -0.7% | 0.602 | +1.1% | 5% | 355 (370) |
| arav_renewal_0 | 0.405 | +0.7% | 0.264 | -0.1% | 0.547 | +0.7% | 0% | 423 (440) |
| kest_cancel_2 | 0.338 | -0.1% | 0.244 | +0.5% | 0.495 | -0.8% | 0% | 398 (411) |
| kest_kyc_1 | 0.361 | +2.2% | 0.215 | +0.4% | 0.602 | +1.3% | 3% | 348 (339) |
| kest_renewal_0 | 0.403 | +0.8% | 0.263 | -0.1% | 0.545 | +0.5% | 0% | 452 (433) |
| nort_cancel_2 | 0.344 | +1.5% | 0.245 | +1.1% | 0.499 | +0.1% | 0% | 418 (393) |
| nort_kyc_1 | 0.355 | +0.3% | 0.213 | -0.2% | 0.601 | +0.9% | 3% | 353 (323) |
| nort_renewal_0 | 0.405 | +0.1% | 0.264 | +0.1% | 0.548 | +0.1% | 0% | 447 (411) |
| tide_cancel_2 | 0.339 | +0.1% | 0.245 | +0.3% | 0.496 | -0.6% | 0% | 396 (407) |
| tide_kyc_1 | 0.357 | +1.1% | 0.214 | -0.1% | 0.599 | +1.1% | 5% | 308 (356) |
| tide_renewal_0 | 0.402 | +0.2% | 0.264 | -0.0% | 0.544 | +0.2% | 0% | 408 (438) |
| ALL | 0.367 | +0.7% | 0.241 | +0.1% | 0.546 | +0.3% | 1% | 4719 (4729) |

## Changes applied by the controller

22 applied — neutral: 16, beneficial: 4, harmful: 2

- arav_cancel_2 v2 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_cancel_2 v2 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_cancel_2 v2 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_cancel_2 v2 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_renewal_0 v2 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_renewal_0 v2 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_renewal_0 v2 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_renewal_0 v2 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_kyc_1 v2 (controller_approved) dims=['voice'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**
- tide_kyc_1 v2 (controller_approved) dims=['voice'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**
- kest_kyc_1 v2 (controller_approved) dims=['voice'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v2 (controller_approved) dims=['voice'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v3 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_cancel_2 v3 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_cancel_2 v3 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_cancel_2 v3 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_renewal_0 v3 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_renewal_0 v3 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_renewal_0 v3 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_renewal_0 v3 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_kyc_1 v3 (controller_approved) dims=['voice'] engageΔ=-0.014 didΔ=+0.000 → **harmful**
- arav_kyc_1 v3 (controller_approved) dims=['voice'] engageΔ=-0.014 didΔ=+0.000 → **harmful**

## Governance

```
{
  "approval_requests": 14,
  "decisions": {
    "approved": 14,
    "expired": 0
  },
  "rejection_reasons": {},
  "applied_via_approval": 14,
  "auto_applied": 8,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "arav_renewal_0": 1,
    "kest_renewal_0": 1,
    "nort_renewal_0": 1,
    "tide_renewal_0": 1,
    "arav_kyc_1": 1,
    "kest_kyc_1": 1,
    "nort_kyc_1": 1,
    "tide_kyc_1": 1
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