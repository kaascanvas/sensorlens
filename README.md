# SensorLens (Static) — residual practice desk

**Client-mimic host for the LensDNA overlay · companion lab to [lensdna.app](https://lensdna.app)**

Issuer: **LensDNA, Inc.** (Delaware C-Corp)  
Commercial product: **HealthAdminDNA**  
Terms: [Schedule S + I + M](https://lensdna.app/master-terms)

This origin is an **internal synthetic lab**. It is not a second company and not the SAFE.

---

## Surfaces

| Surface | Entry | Role |
|---------|-------|------|
| **HealthAdminDNA residual** | `handoff.html` | **Commercial wedge practice path** — prior-auth residual after an upstream decision |
| **Doula Care Residual** | `doula.html` | Method-transfer sandbox (coverage decision → credentialing / docs residual) |
| **Education & Therapy Robotics** | `robotics.html` | Method-transfer sandbox (robot event → portal / notify residual) |

All three use the identical production embed pattern and human-gate discipline.

---

## Alignment (2026-09-05)

- Featured path is HealthAdmin residual, not Doula / robotics.
- Retired **Schedule D $25k / ≥60% minutes SLA**. Qualification language is **Schedule M** (14-day frozen-cohort ledger, no savings warranty).
- Commercial links point to `https://lensdna.app/master-terms` (S + I + M).
- Contact remains `hans@lensdna.app` only.
- Multi-vertical PropTech / minerals / “domain-agnostic OS company” copy removed from diligence-facing pages.

---

## HealthAdmin practice loop

1. `handoff.html` — decision already done; residual listed
2. `residual.html` — portal fields + attachments + status + human gate + timers
3. `status.html` — REA v1.2 dossier + baseline binding
4. `pilot-intake.html` — local Schedule M parameters (browser only)

---

## Doula / robotics (method transfer only)

Same 4-step shape: event → residual ops → REA dossier → qualify.  
Synthetic only. No partner endorsement. Not Year-1 revenue.

---

## Why static

SensorLens does not need a Python process, server sessions, or SMTP.

- Plain HTML + `localStorage`
- Production embed from `lensdna.app`
- Free static hosting (Render Static Site, Cloudflare Pages, Netlify, GitHub Pages)

---

## Install pattern (identical to production)

```html
<script
  src="https://lensdna.app/embed.js"
  data-overlay-url="https://lensdna.app/overlay.html"
  data-tenant-id="sensorlens-sandbox"
  data-theme="dark"
  data-position="bottom-right">
</script>
```

Overlay can drive only the origin that embeds it.

---

## Deploy

1. Static host → publish directory = this folder (contains `index.html`)
2. Optional custom domain **sensorlens.app**
3. No environment variables

Local preview:

```bash
npx serve .
# or
python -m http.server 5055
```

---

## Security posture (sandbox)

- Synthetic data only — do not enter real PHI / PII
- No live payer, district, or clinical connectivity
- `noindex` on pages
- Production HIPAA / ZRM claims live on the commercial product when Enterprise + BAA + ZRM conditions are met; this lab does not assert those conditions by itself

---

## Contact

Commercial licensing and desks: **[lensdna.app](https://lensdna.app)** · hans@lensdna.app · [@LensDNA_OS](https://x.com/LensDNA_OS)

*Practice the residual path. Measure real deployments under Schedule M parameters. Do not confuse synthetic practice with audited outcomes for a named prospect.*
