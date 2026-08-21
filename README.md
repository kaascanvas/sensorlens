# SensorLens (Static)

**Residual practice desk · client-mimic host for LensDNA OS domain overlay**

[sensorlens.app](https://sensorlens.app) · companion lab to [lensdna.app](https://lensdna.app)

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

## What SensorLens is

| SensorLens is | SensorLens is not |
|---------------|-------------------|
| A **client-mimic sandbox** for residual last-mile shape | The commercial LensDNA product |
| A place to **feel embed + overlay** on a separate origin | A production integration with any named upstream vendor |
| Synthetic cases for **practice and product learning** | Live payer submission or real PHI workflows |
| Honest scope for **pilot design conversations** | A guarantee of $ economic outcomes for a named prospect |

Commercial runtime, pilots, and licensing live on **[lensdna.app](https://lensdna.app)**.

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
| **This site** | Parent pages: handoff, residual fields, human gate, status |
| **embed.js** | Floating pill + resizable overlay iframe |
| **overlay.html (lensdna.app)** | Voice (optional WebRTC), DOM tools on *this* parent, Pilot Ops, dossier helpers |
| **Control boundary** | Overlay can drive only the origin that embeds it |

---

## Practice flow

| Step | File | What you do |
|------|------|-------------|
| Home | `index.html` | Scope, install pattern, start |
| Handoff | `handoff.html` | Decision assumed **complete**; residual still listed for the operator |
| Residual portal | `residual.html` | Member, auth ref, CPT, attachments, status notes · **human gate required** |
| Status / metrics | `status.html` | Synthetic outcome · practice dossier · local learning log |
| Pilot intake | `pilot-intake.html` | Bounded parameters · copy / email summary |
| Reset | any page → Reset | Clears `localStorage` |

**Discipline under test**

1. No re-decision of medical necessity on this desk — residual only after the decision  
2. Irreversible submit blocked until the operator explicitly approves  
3. Economic language stays **underwriting / plan bands** until a real measured pilot  
4. Pilot Ops (in the overlay) exists so parameters are visible before anyone talks ROI  

---

## Files

```
index.html          Home / scope
handoff.html        Step 1 — residual after decision
residual.html       Step 2 — portal-shaped fields + human gate + timers
status.html         Step 3 — outcome + practice metrics
pilot-intake.html   Step 4 — pilot parameters + copy/email
styles.css          Shared styles
sensorlens.js       localStorage state layer
README.md           This document
```

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
# any static server
npx serve .
# or
python -m http.server 5055
```

Open http://127.0.0.1:5055

---

## Security and compliance posture (sandbox)

- **Synthetic data only** — do not enter real PHI  
- **No live payer connectivity**  
- **noindex** on pages  
- Production LensDNA HIPAA / Zero-Retention posture is documented on the commercial product when Enterprise + BAA + ZRM conditions are met; this lab does not assert those conditions by itself  

---

## Contact

Practice desk source is published for transparency for operators, SAFE participants, and portfolio stakeholders evaluating residual last-mile execution.

Commercial licensing, pilots, and white-label runtime: **[lensdna.app](https://lensdna.app)**

---

*SensorLens — practice the residual path. Measure real deployments under pilot parameters. Do not confuse synthetic practice with audited outcomes for a named prospect.*
