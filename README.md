# SensorLens

Customer-origin fixture for the LensDNA `embed.js` + overlay.

This host is **not** the product site. Pages live here on purpose so you can see the script load from [lensdna.app](https://lensdna.app) onto a different origin — the same pattern a buyer uses on their own workbench.

Vendor: **LensDNA, Inc.**  
Product: **HealthAdminDNA**  
Terms: [Schedule S + I + M](https://lensdna.app/master-terms)

## What this origin proves

- Script tag on a foreign host mounts the overlay
- Overlay can read / type fields marked `data-lensdna-target` **on this origin**
- Human gate blocks irreversible submit
- REA v1.2 can be assembled in the browser

## What this origin does not prove

- Driving Availity, UnitedHealthcare, or any third-party payer tab
- Bypassing Same-Origin Policy
- A live clearinghouse integration

Payer-tab execution is a separate operator runtime (extension or managed browser).

## Workbench loop

1. `handoff.html` — synthetic case export
2. `residual.html` — portal-shaped fields, attachments, gate, timers
3. `status.html` — REA dossier
4. `pilot-intake.html` — local parameters only

`doula.html` and `robotics.html` are extra fixtures of the same embed. They are not additional products.

## Tag

```html
<script
  src="https://lensdna.app/embed.js"
  data-overlay-url="https://lensdna.app/overlay.html"
  data-tenant-id="sensorlens-sandbox"
  data-theme="dark"
  data-position="bottom-right">
</script>
```

## Run

```bash
npx serve .
# or
python -m http.server 5055
```

Publish the folder that contains `index.html`. No env vars. Do not enter real PHI or PII. Pages are `noindex`.

Contact: [lensdna.app](https://lensdna.app) · hans@lensdna.app · [@LensDNA_OS](https://x.com/LensDNA_OS)
