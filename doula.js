/**
 * SensorLens · Doula Care residual state + REA v1.2
 * Domain surface for insurance-backed doula residual after policy/enrollment decision.
 * Synthetic data only. No real patient, doula, or plan data.
 * Valid residual shape in states with Medicaid doula reimbursement (26 states + DC as of 2026).
 */
(function () {
  const KEY = 'sensorlens_doula_state';
  const METRICS_KEY = 'sensorlens_doula_metrics';
  const REA_LOG_KEY = 'sensorlens_doula_rea_log';

  const defaults = {
    // Event / case
    event_id: 'DOULA-EVT-2026-0825-031',
    program_name: 'Cascadia Community Doula Collective (fictional)',
    state: 'Washington (synthetic · high reimbursement band)',
    doula_alias: 'Maya Okonkwo (synthetic)',
    client_alias: 'Amina R. (synthetic)',
    mco_or_plan: 'Apple Health Managed Care · Plan A (synthetic)',
    trigger:
      'Program newly eligible for Medicaid doula reimbursement. ' +
      'Credentialing packet incomplete for one MCO. ' +
      'Coverage confirmation still required for a synthetic postpartum client. ' +
      'Outcomes documentation residual remains before claim can be cleanly submitted.',
    residual_notes:
      'Upstream policy / enrollment decision complete.\n' +
      'Residual still on operator:\n' +
      '• Complete MCO credentialing portal fields + attach training / certification packet\n' +
      '• Stage coverage confirmation for synthetic client\n' +
      '• Prepare required outcomes / visit documentation\n' +
      '• Human approve before irreversible credential submit or claim-related action',
    baseline_minutes: '14-22',
    baseline_declared_at: '',
    baseline_cohort: '',
    baseline_metric: 'operator residual minutes per credentialing / coverage residual',
    baseline_value: '',
    baseline_unit: 'minutes',
    baseline_method: '',
    baseline_notes: '',

    // Residual form fields
    portal_cred_ref: '',
    npi_or_id: '',
    cert_codes: '',
    training_packet_note: '',
    coverage_status: '',
    visit_docs_note: '',
    outcomes_note: '',
    optical_notes: '',
    telephony_notes: '',
    evidence_notes: '',
    quality_notes: '',

    submitted: false,
    submit_ts: '',
    timing_json: '',
    run_seconds: '',
    gate_blocked: false,
    last_rea: null,

    // Qualification
    pilot_org: '',
    pilot_email: '',
    pilot_workflow: '',
    pilot_baseline: '',
    pilot_success: '',
    pilot_fail: '',
    pilot_notes: '',
    pilot_recorded: false,
    pilot_recorded_ts: ''
  };

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return { ...defaults };
      return { ...defaults, ...JSON.parse(raw) };
    } catch {
      return { ...defaults };
    }
  }

  function save(partial) {
    const state = { ...load(), ...partial };
    localStorage.setItem(KEY, JSON.stringify(state));
    return state;
  }

  function clear() {
    localStorage.removeItem(KEY);
  }

  function nowUtc() {
    return new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
  }

  function uid() {
    return 'rea_' + new Date().toISOString().slice(0, 10).replace(/-/g, '') + '_' +
      Math.random().toString(36).slice(2, 8);
  }

  async function sha256(text) {
    try {
      const data = new TextEncoder().encode(text);
      const hash = await crypto.subtle.digest('SHA-256', data);
      return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
    } catch {
      return 'hash_unavailable';
    }
  }

  async function buildREA(extra) {
    const s = load();
    const timing = extra && extra.timing ? extra.timing : (s.timing_json ? JSON.parse(s.timing_json) : {});
    const completedAt = s.submit_ts || new Date().toISOString();
    const startedAt = extra && extra.started_at ? extra.started_at : completedAt;

    const rea = {
      rea_version: '1.2',
      artifact_id: uid(),
      created_at: new Date().toISOString(),
      origin: location.origin || 'sensorlens.app',
      domain: 'doula_care_residual',

      baseline: {
        declared_at: s.baseline_declared_at || null,
        cohort: s.baseline_cohort || s.pilot_workflow || null,
        metric: s.baseline_metric || 'operator residual minutes per credentialing / coverage residual',
        value: s.baseline_value || s.baseline_minutes || null,
        unit: s.baseline_unit || 'minutes',
        method: s.baseline_method || null,
        notes: s.baseline_notes || null
      },

      event: {
        event_id: s.event_id || null,
        program: s.program_name || null,
        state: s.state || null,
        doula_alias: s.doula_alias || null,
        client_alias: s.client_alias || null,
        mco_or_plan: s.mco_or_plan || null,
        trigger_summary: s.trigger || null,
        decision_already_made: true
      },

      run: {
        started_at: startedAt,
        completed_at: completedAt,
        duration_seconds: s.run_seconds ? parseFloat(s.run_seconds) : (timing.total_seconds || null),
        steps: [],
        fields_captured: {
          portal_cred_ref: s.portal_cred_ref || null,
          npi_or_id: s.npi_or_id || null,
          cert_codes: s.cert_codes || null,
          training_packet_note: s.training_packet_note || null,
          coverage_status: s.coverage_status || null,
          visit_docs_note: s.visit_docs_note || null,
          outcomes_note: s.outcomes_note || null
        }
      },

      verification: {
        optical: {
          used: !!(s.optical_notes && s.optical_notes.trim()),
          notes: s.optical_notes || null,
          purpose: 'Verify and document on-screen inputs and outputs during residual run'
        },
        telephony: {
          used: !!(s.telephony_notes && s.telephony_notes.trim()),
          notes: s.telephony_notes || null,
          purpose: 'Status / coordination residual via voice where portal is insufficient'
        }
      },

      evidence: {
        pdf_or_dossier: s.evidence_notes || null,
        storage_note: s.evidence_notes
          ? 'Credentialing packet / outcomes documentation referenced or staged for this run'
          : null
      },

      execution_quality: {
        notes: s.quality_notes || null,
        dimensions: [
          'accuracy of residual actions',
          'consistency of flow',
          'verification completeness',
          'documentation integrity',
          'human-gate discipline'
        ]
      },

      human_gate: {
        required: true,
        approved: !!s.submitted,
        approved_at: s.submitted ? (s.submit_ts || completedAt) : null,
        statement: 'I approve irreversible residual actions (credentialing portal submit + coverage-related documentation) for this synthetic case'
      },

      outcome: {
        status: s.submitted ? 'submitted_synthetic' : 'not_submitted',
        notes: s.submitted
          ? 'Residual run completed under human gate. Verification and evidence fields captured where provided. No live payer, MCO, or clinical system was contacted from this origin. No clinical determination was made by the runtime.'
          : 'Human gate was not approved or run was not completed.'
      },

      integrity: {
        content_hash: null,
        generated_by: 'sensorlens-static/1.2-rea-doula'
      },

      trust_boundary: {
        synthetic_only: true,
        no_real_patient_data: true,
        no_partner_endorsement: true,
        no_clinical_determination: true,
        human_approval_required: true,
        states_context: 'Demonstrates residual shape relevant to Medicaid doula reimbursement states (26 + DC as of 2026)'
      }
    };

    if (timing) {
      const stepKeys = Object.keys(timing).filter(k => k.startsWith('step_'));
      rea.run.steps = stepKeys.map(k => {
        const id = k.replace(/^step_\d+_/, '');
        return { id: id, seconds: timing[k] };
      });
      if (timing.total_seconds != null) {
        rea.run.duration_seconds = timing.total_seconds;
      }
    }

    const forHash = JSON.stringify(rea);
    rea.integrity.content_hash = 'sha256:' + await sha256(forHash);
    return rea;
  }

  function saveREA(rea) {
    save({ last_rea: rea });
    try {
      const log = JSON.parse(localStorage.getItem(REA_LOG_KEY) || '[]');
      log.push({ id: rea.artifact_id, created_at: rea.created_at, event_id: rea.event.event_id });
      localStorage.setItem(REA_LOG_KEY, JSON.stringify(log.slice(-50)));
    } catch (e) {}
    return rea;
  }

  function downloadREA(rea) {
    const blob = new Blob([JSON.stringify(rea, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (rea.artifact_id || 'rea') + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function humanSummary(rea) {
    if (!rea) return 'No residual evidence artifact yet.';
    const b = rea.baseline || {};
    const e = rea.event || {};
    const r = rea.run || {};
    const v = rea.verification || {};
    const ev = rea.evidence || {};
    const q = rea.execution_quality || {};
    const g = rea.human_gate || {};
    const o = rea.outcome || {};
    return [
      'RESIDUAL EVIDENCE ARTIFACT (REA) v1.2 — Doula Care Residual',
      'ID: ' + rea.artifact_id,
      'Created: ' + rea.created_at,
      'Domain: doula_care_residual',
      '',
      '— BASELINE (declared) —',
      'Cohort: ' + (b.cohort || '—'),
      'Metric: ' + (b.metric || '—'),
      'Value: ' + (b.value || '—') + ' ' + (b.unit || ''),
      'Method: ' + (b.method || '—'),
      '',
      '— EVENT —',
      'Event ID: ' + (e.event_id || '—'),
      'Program: ' + (e.program || '—'),
      'State context: ' + (e.state || '—'),
      'Doula (synthetic): ' + (e.doula_alias || '—'),
      'Client (synthetic): ' + (e.client_alias || '—'),
      'MCO / Plan: ' + (e.mco_or_plan || '—'),
      'Trigger: ' + (e.trigger_summary || '—'),
      '',
      '— RUN —',
      'Duration: ' + (r.duration_seconds != null ? r.duration_seconds + 's' : '—'),
      'Completed: ' + (r.completed_at || '—'),
      '',
      '— VERIFICATION —',
      'Optical: ' + (v.optical && v.optical.used ? 'YES' : 'no') + (v.optical && v.optical.notes ? ' · ' + v.optical.notes : ''),
      'Telephony: ' + (v.telephony && v.telephony.used ? 'YES' : 'no') + (v.telephony && v.telephony.notes ? ' · ' + v.telephony.notes : ''),
      '',
      '— EVIDENCE / PACKET —',
      (ev.pdf_or_dossier || '—'),
      '',
      '— EXECUTION QUALITY —',
      (q.notes || '—'),
      '',
      '— HUMAN GATE —',
      'Approved: ' + (g.approved ? 'YES' : 'NO'),
      'Approved at: ' + (g.approved_at || '—'),
      '',
      '— OUTCOME —',
      'Status: ' + (o.status || '—'),
      'Notes: ' + (o.notes || '—'),
      '',
      'Integrity: ' + (rea.integrity && rea.integrity.content_hash ? rea.integrity.content_hash : '—'),
      '',
      'TRUST BOUNDARY: Synthetic data only. No real patient/doula data. No partner endorsement claimed.',
      'LensDNA does not make clinical determinations. Human approval required for irreversible actions.',
      'Demonstrates residual shape relevant to Medicaid doula reimbursement states (26 + DC as of 2026).'
    ].join('\n');
  }

  window.DoulaLens = {
    load,
    save,
    clear,
    nowUtc,
    buildREA,
    saveREA,
    downloadREA,
    humanSummary,
    METRICS_KEY,
    REA_LOG_KEY
  };

  document.addEventListener('DOMContentLoaded', function () {
    const el = document.getElementById('sl-now');
    if (el) el.textContent = nowUtc();
  });
})();
