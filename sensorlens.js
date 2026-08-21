/**
 * SensorLens static state + Residual Evidence Artifact (REA) v1.2
 * System-of-record for residual runs: accuracy, verification, evidence, baseline.
 */
(function () {
  const KEY = 'sensorlens_state';
  const METRICS_KEY = 'sensorlens_practice_metrics';
  const REA_LOG_KEY = 'sensorlens_rea_log';

  const defaults = {
    case_id: 'DEMO-PA-2026-0820',
    payer: 'BCBS commercial PPO',
    decision: 'Medical necessity supported — residual portal submit/attach still required',
    export_notes:
      'Upstream decision complete.\n' +
      'Residual still on operator:\n' +
      '• Open payer portal auth request\n' +
      '• Attach clinical packet\n' +
      '• Human approve before irreversible submit\n' +
      '• Confirm status if not auto-updated',
    baseline_minutes: '12-18',
    baseline_declared_at: '',
    baseline_cohort: '',
    baseline_metric: 'operator residual minutes per case',
    baseline_value: '',
    baseline_unit: 'minutes',
    baseline_method: '',
    baseline_notes: '',
    portal_member: '',
    auth_ref: '',
    cpt: '',
    attachment_note: '',
    status_note: '',
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

      baseline: {
        declared_at: s.baseline_declared_at || null,
        cohort: s.baseline_cohort || s.pilot_workflow || null,
        metric: s.baseline_metric || 'operator residual minutes per case',
        value: s.baseline_value || s.baseline_minutes || null,
        unit: s.baseline_unit || 'minutes',
        method: s.baseline_method || null,
        notes: s.baseline_notes || null
      },

      case: {
        case_id: s.case_id || null,
        payer_or_system: s.payer || null,
        member_or_subject: s.portal_member || null,
        decision_already_made: true,
        decision_summary: s.decision || null
      },

      run: {
        started_at: startedAt,
        completed_at: completedAt,
        duration_seconds: s.run_seconds ? parseFloat(s.run_seconds) : (timing.total_seconds || null),
        steps: [],
        fields_captured: {
          auth_ref: s.auth_ref || null,
          cpt: s.cpt || null,
          attachment_note: s.attachment_note || null,
          status_note: s.status_note || null
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
          purpose: 'Status / verification residual via voice where portal is insufficient'
        }
      },

      evidence: {
        pdf_or_dossier: s.evidence_notes || null,
        storage_note: s.evidence_notes
          ? 'Residual evidence / PDF referenced or stored for this run'
          : null
      },

      execution_quality: {
        notes: s.quality_notes || null,
        dimensions: [
          'accuracy of residual actions',
          'consistency of flow',
          'verification completeness',
          'documentation integrity'
        ]
      },

      human_gate: {
        required: true,
        approved: !!s.submitted,
        approved_at: s.submitted ? (s.submit_ts || completedAt) : null,
        statement: 'I approve irreversible residual submit for this case'
      },

      outcome: {
        status: s.submitted ? 'submitted_synthetic' : 'not_submitted',
        notes: s.submitted
          ? 'Residual run completed under human gate. Verification and evidence fields captured where provided. No live payer / upstream system was contacted from this origin.'
          : 'Human gate was not approved or run was not completed.'
      },

      integrity: {
        content_hash: null,
        generated_by: 'sensorlens-static/1.2-rea'
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
      log.push({ id: rea.artifact_id, created_at: rea.created_at, case_id: rea.case.case_id });
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
    const c = rea.case || {};
    const r = rea.run || {};
    const v = rea.verification || {};
    const e = rea.evidence || {};
    const q = rea.execution_quality || {};
    const g = rea.human_gate || {};
    const o = rea.outcome || {};
    return [
      'RESIDUAL EVIDENCE ARTIFACT (REA) v1.2',
      'ID: ' + rea.artifact_id,
      'Created: ' + rea.created_at,
      '',
      '— BASELINE (declared) —',
      'Cohort: ' + (b.cohort || '—'),
      'Metric: ' + (b.metric || '—'),
      'Value: ' + (b.value || '—') + ' ' + (b.unit || ''),
      'Method: ' + (b.method || '—'),
      '',
      '— CASE —',
      'Case ID: ' + (c.case_id || '—'),
      'System / Payer: ' + (c.payer_or_system || '—'),
      'Subject: ' + (c.member_or_subject || '—'),
      'Decision already made: yes',
      '',
      '— RUN —',
      'Duration: ' + (r.duration_seconds != null ? r.duration_seconds + 's' : '—'),
      'Completed: ' + (r.completed_at || '—'),
      '',
      '— VERIFICATION —',
      'Optical: ' + (v.optical && v.optical.used ? 'YES' : 'no') + (v.optical && v.optical.notes ? ' · ' + v.optical.notes : ''),
      'Telephony: ' + (v.telephony && v.telephony.used ? 'YES' : 'no') + (v.telephony && v.telephony.notes ? ' · ' + v.telephony.notes : ''),
      '',
      '— EVIDENCE / PDF —',
      (e.pdf_or_dossier || '—'),
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
      'This artifact is a system-of-record entry for residual work.',
      'It records verified, documented residual execution under human gate.',
      'It does not claim live upstream integration or audited economic ROI.'
    ].join('\n');
  }

  window.SensorLens = {
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
