# SensorLens (Static)

**Residual practice desk · client-mimic host for LensDNA OS domain overlay**

[sensorlens.app](https://sensorlens.app) · companion lab to [lensdna.app](https://lensdna.app)

---

## Surfaces

| Surface | Entry | Purpose |
|---------|-------|---------|
| **Education & Therapy Robotics** | `robotics.html` | Event → residual ops → human gate → REA dossier → qualification |
| **HealthAdmin residual** | `handoff.html` | Prior-auth residual practice (original path) |

Both use the identical production embed pattern and human-gate discipline.

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
| Synthetic cases for **practice and product learning** | Live payer / district / clinical submission or real PHI/PII workflows |
| Honest scope for **pilot design conversations** | A guarantee of $ economic outcomes for a named prospect |
| Domain surfaces (Education & Therapy Robotics, HealthAdmin, …) | A claim of endorsement or partnership with any robotics or education provider |

Commercial runtime, pilots, and licensing live on **[lensdna.app](https://lensdna.app)**.

---

## Education & Therapy Robotics surface

**Positioning:** “From robot event to completed human-approved workflow.”

**Primary synthetic demonstration**

A fictional therapy support robot (Companion-3) completes a scheduled social-emotional check-in. Engagement drops; residual operational work remains:

1. Receive event + preserve context  
2. Open synthetic district support portal  
3. Log observation + stage evidence  
4. Draft teacher / SPED and caregiver notifications  
5. Pause at human gate before any external send or irreversible log  
6. Produce Residual Evidence Artifact (REA)  
7. Capture qualification parameters for a narrow pilot  

**Trust boundary (stated on every page)**

- Synthetic data only — no real student, teacher, therapist, or family data  
- No endorsement, partnership, integration, or customer status with any named robotics or education provider  
- LensDNA does not make educational or clinical determinations  
- Irreversible actions require explicit human approval  

**Files**

```
robotics.html           Surface home / scope
robotics-event.html     Step 1 — robot event received, residual listed
robotics-residual.html  Step 2 — multi-step residual ops + human gate + timers
robotics-status.html    Step 3 — REA dossier + baseline binding + metrics
robotics-qualify.html   Step 4 — discovery questions + bounded pilot parameters
robotics.js             Domain state + REA builder (education_therapy_robotics)
```

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

## Practice flow (Education & Therapy Robotics)

| Step | File | What you do |
|------|------|-------------|
| Surface home | `robotics.html` | Scope, trust boundary, start |
| Event | `robotics-event.html` | Robot event assumed complete; residual still listed |
| Residual ops | `robotics-residual.html` | Portal fields, notifications, evidence, verify · **human gate required** |
| Dossier | `robotics-status.html` | REA + baseline binding + practice metrics |
| Qualify | `robotics-qualify.html` | Discovery questions + bounded pilot parameters · copy / email summary |
| Reset | any page → Reset | Clears domain `localStorage` |

**Discipline under test**

1. No educational or clinical re-determination on this desk — residual only after the robot event  
2. Irreversible submit / external notification blocked until the operator explicitly approves  
3. Economic language stays **underwriting / plan bands** until a real measured pilot  
4. Qualification captures owner, systems, minutes, volume, gate points, and success/fail criteria  

---

## HealthAdmin residual (original)

```
index.html          Home / scope (now dual-surface)
handoff.html        Step 1 — residual after decision
residual.html       Step 2 — portal-shaped fields + human gate + timers
status.html         Step 3 — outcome + practice metrics
pilot-intake.html   Step 4 — pilot parameters + copy/email
styles.css          Shared styles
sensorlens.js       localStorage state layer (health path)
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

- **Synthetic data only** — do not enter real PHI / PII / student data  
- **No live payer, district, or clinical connectivity**  
- **noindex** on pages  
- Production LensDNA HIPAA / Zero-Retention posture is documented on the commercial product when Enterprise + BAA + ZRM conditions are met; this lab does not assert those conditions by itself  

---

## Contact

Practice desk source is published for transparency for operators, SAFE participants, and portfolio stakeholders evaluating residual last-mile execution.

Commercial licensing, pilots, and white-label runtime: **[lensdna.app](https://lensdna.app)**

---

*SensorLens — practice the residual path. Measure real deployments under pilot parameters. Do not confuse synthetic practice with audited outcomes for a named prospect. Do not claim partner relationships that do not exist.*
