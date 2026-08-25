# SensorLens (Static) — with Doula Care Residual

**Residual practice desk · client-mimic host for LensDNA OS domain overlay**

[sensorlens.app](https://sensorlens.app) · companion lab to [lensdna.app](https://lensdna.app)

---

## Surfaces

| Surface | Entry | Purpose |
|---------|-------|---------|
| **Doula Care Residual** | `doula.html` | Credentialing + coverage confirmation + outcomes documentation residual after Medicaid / commercial eligibility (26 states + DC) |
| **Education & Therapy Robotics** | `robotics.html` | Event → residual ops → human gate → REA dossier → qualification |
| **HealthAdmin residual** | `handoff.html` | Prior-auth residual practice (original path) |

All three use the identical production embed pattern and human-gate discipline.

---

## Doula Care Residual (new)

**Positioning:** “From policy decision to completed human-approved residual.”

**Primary synthetic demonstration**

A fictional community doula program is newly eligible for Medicaid reimbursement. Residual work remains:

1. Receive enrollment / coverage decision + preserve context  
2. Open synthetic MCO credentialing portal  
3. Complete fields + attach training / certification packet  
4. Stage coverage confirmation for a synthetic client  
5. Prepare visit / outcomes documentation  
6. Pause at human gate before irreversible submit  
7. Produce Residual Evidence Artifact (REA)  
8. Capture qualification parameters for a narrow pilot  

**Trust boundary (stated on every page)**

- Synthetic data only — no real patient, doula, or plan data  
- No endorsement, partnership, integration, or customer status with any named organization  
- LensDNA does not make clinical determinations  
- Irreversible actions require explicit human approval  
- Residual shape is relevant to the 26 states + DC with Medicaid doula reimbursement (as of 2026)

**Files**

```
doula.html           Surface home / scope
doula-event.html     Step 1 — coverage decision received, residual listed
doula-residual.html  Step 2 — multi-step residual ops + human gate + timers
doula-status.html    Step 3 — REA dossier + baseline binding + metrics
doula-qualify.html   Step 4 — discovery questions + bounded pilot parameters
doula.js             Domain state + REA builder (doula_care_residual)
```

---

## Why this version is static

SensorLens is a **synthetic practice surface**. It does not need a Python process, sessions on the server, or SMTP.

This static build keeps the exact same layout, residual flow, human gate, timers, metrics, and pilot intake — using only:

- Plain HTML pages
- `localStorage` for practice state
- The production embed from `lensdna.app`

**Benefits**
- Free / near-free hosting (Render Static Site, Cloudflare Pages, Netlify, GitHub Pages…)
- No cold starts
- No runtime secrets required
- Still demonstrates the identical client install pattern

---

## Architecture (one client pattern)

Every page loads the production domain overlay:

```html
<script
  src="https://lensdna.app/embed.js"
  data-overlay-url="https://lensdna.app/overlay.html"
  data-tenant-id="sensorlens-sandbox"
  data-theme="dark"
  data-position="bottom-right">
</script>
```

| Layer | Role |
|-------|------|
| **This site** | Parent pages: event, residual fields, human gate, dossier, qualify |
| **embed.js** | Floating pill + resizable overlay iframe |
| **overlay.html (lensdna.app)** | Voice (optional WebRTC), DOM tools on *this* parent, Pilot Ops |
| **Control boundary** | Overlay can drive only the origin that embeds it |

The runtime remains domain-agnostic. Domain pages supply event types, workflow steps, approval rules, synthetic portals, terminology, evidence requirements, escalation paths, dossier templates, and pilot metrics.

---

## Deploy (Render Static Site)

1. New → **Static Site** → connect the repository (or upload the folder)
2. Build command: leave empty (or `echo "static"`)
3. Publish directory: `.` (or the folder that contains `index.html`)
4. Map custom domain **sensorlens.app** (HTTPS)

Alternative hosts that work identically:
- Cloudflare Pages
- Netlify
- GitHub Pages
- Any static file host

No environment variables required.

---

## Local preview

```bash
npx serve .
# or
python -m http.server 5055
```

Open http://127.0.0.1:5055

---

## Security and compliance posture (sandbox)

- **Synthetic data only** — do not enter real PHI / PII / patient data  
- **No live payer, district, or clinical connectivity**  
- **noindex** on pages  
- Production LensDNA HIPAA / Zero-Retention posture is documented on the commercial product when Enterprise + BAA + ZRM conditions are met; this lab does not assert those conditions by itself  

---

## Contact

Practice desk source is published for transparency for operators, SAFE participants, and portfolio stakeholders evaluating residual last-mile execution.

Commercial licensing, pilots, and white-label runtime: **[lensdna.app](https://lensdna.app)**

---

*SensorLens — practice the residual path. Measure real deployments under pilot parameters. Do not confuse synthetic practice with audited outcomes for a named prospect. Do not claim partner relationships that do not exist.*
