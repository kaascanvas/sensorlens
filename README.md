# SensorLens

Static practice desk for the [LensDNA](https://lensdna.app) overlay.

Issuer: **LensDNA, Inc.**  
Product: **HealthAdminDNA**  
Terms: [Schedule S + I + M](https://lensdna.app/master-terms)

Synthetic pages only. No live payer, plan, or clinical systems. Overlay can drive this origin’s DOM; irreversible actions stay behind a human gate.

---

## Pages

| Path | What it is |
|------|------------|
| `handoff.html` → `residual.html` → `status.html` → `pilot-intake.html` | HealthAdmin residual loop (prior-auth last-mile practice) |
| `doula.html` | Same kernel on a coverage-decision residual |
| `robotics.html` | Same kernel on an education/therapy robot event |

Entry: `index.html`.

---

## HealthAdmin loop

1. `handoff.html` — upstream decision already made; residual still listed  
2. `residual.html` — portal fields, attachments, status, human gate, timers  
3. `status.html` — REA v1.2 dossier  
4. `pilot-intake.html` — local Schedule M parameters in the browser only  

---

## Embed (same pattern as production)

```html
<script
  src="https://lensdna.app/embed.js"
  data-overlay-url="https://lensdna.app/overlay.html"
  data-tenant-id="sensorlens-sandbox"
  data-theme="dark"
  data-position="bottom-right">
</script>
```

---

## Run locally

```bash
npx serve .
# or
python -m http.server 5055
```

Publish the folder that contains `index.html` as a static site. No env vars, no backend.

Do not enter real PHI or PII. Pages are `noindex`.

---

Contact: [lensdna.app](https://lensdna.app) · hans@lensdna.app · [@LensDNA_OS](https://x.com/LensDNA_OS)
