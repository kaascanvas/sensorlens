/**
 * SensorLens · Education & Therapy Robotics residual state + REA v1.2
 * Domain surface for robot/avatar event → human-gated operational residual.
 * Synthetic data only. No real student, clinical, or partner data.
 */
(function () {
  const KEY = 'sensorlens_robotics_state';
  const METRICS_KEY = 'sensorlens_robotics_metrics';
  const REA_LOG_KEY = 'sensorlens_robotics_rea_log';

  const defaults = {
    // Event / case
    event_id: 'EDU-EVT-2026-0824-014',
    robot_id: 'Companion-3',
    student_alias: 'Jordan Lee (synthetic)',
    classroom: 'Room 14B · Cascadia Learning Academy (fictional)',
    teacher: 'Ms. Elena Voss (synthetic)',
    program: 'Social-emotional check-in · IEP-aligned (synthetic)',
    trigger:
      'Engagement drop below threshold at ~7 min during scheduled 15-min session. ' +
      'Optical indicators consistent with sensory-overload protocol. ' +
      'Residual required: teacher notification + review, caregiver update, support-portal case note + evidence packet.',
    residual_notes:
      'Upstream robot event complete.\n' +
      'Residual still on operator:\n' +
      '• Open district support / case portal\n' +
      '• Log session observation + attach evidence snippet\n' +
      '• Draft teacher + SPED coordinator notification\n' +
      '• Stage caregiver update (SMS/email preferred by protocol)\n' +
      '• Human approve before any external send or irreversible log',
    baseline_minutes: '9-14',
    baseline_declared_at: '',
    baseline_cohort: '',
    baseline_metric: 'operator residual minutes per robot event',
    baseline_value: '',
    baseline_unit: 'minutes',
    baseline_method: '',
    baseline_notes: '',

    // Residual form fields
    portal_case_ref: '',
    student_id_portal: '',
    session_code: '',
    observation_note: '',
    notification_teacher: '',
    notification_caregiver: '',
    escalation_flag: '',
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
      domain: 'education_therapy_robotics',

      baseline: {
        declared_at: s.baseline_declared_at || null,
        cohort: s.baseline_cohort || s.pilot_workflow || null,
        metric: s.baseline_metric || 'operator residual minutes per robot event',
        value: s.baseline_value || s.baseline_minutes || null,
        unit: s.baseline_unit || 'minutes',
        method: s.baseline_method || null,
        notes: s.baseline_notes || null
      },

      event: {
        event_id: s.event_id || null,
        robot_or_avatar: s.robot_id || null,
        student_alias: s.student_alias || null,
        classroom: s.classroom || null,
        teacher: s.teacher || null,
        program: s.program || null,
        trigger_summary: s.trigger || null,
        decision_already_made: true
      },

      run: {
        started_at: startedAt,
        completed_at: completedAt,
        duration_seconds: s.run_seconds ? parseFloat(s.run_seconds) : (timing.total_seconds || null),
        steps: [],
        fields_captured: {
          portal_case_ref: s.portal_case_ref || null,
          student_id_portal: s.student_id_portal || null,
          session_code: s.session_code || null,
          observation_note: s.observation_note || null,
          notification_teacher: s.notification_teacher || null,
          notification_caregiver: s.notification_caregiver || null,
          escalation_flag: s.escalation_flag || null
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
          ? 'Residual evidence / session packet referenced or staged for this run'
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
        statement: 'I approve irreversible residual actions (portal log + external notifications) for this synthetic case'
      },

      outcome: {
        status: s.submitted ? 'submitted_synthetic' : 'not_submitted',
        notes: s.submitted
          ? 'Residual run completed under human gate. Verification and evidence fields captured where provided. No live district, student, or clinical system was contacted from this origin. No educational or clinical determination was made by the runtime.'
          : 'Human gate was not approved or run was not completed.'
      },

      integrity: {
        content_hash: null,
        generated_by: 'sensorlens-static/1.2-rea-robotics'
      },

      trust_boundary: {
        synthetic_only: true,
        no_real_student_data: true,
        no_partner_endorsement: true,
        no_clinical_or_educational_determination: true,
        human_approval_required: true
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
      'RESIDUAL EVIDENCE ARTIFACT (REA) v1.2 — Education & Therapy Robotics',
      'ID: ' + rea.artifact_id,
      'Created: ' + rea.created_at,
      'Domain: education_therapy_robotics',
      '',
      '— BASELINE (declared) —',
      'Cohort: ' + (b.cohort || '—'),
      'Metric: ' + (b.metric || '—'),
      'Value: ' + (b.value || '—') + ' ' + (b.unit || ''),
      'Method: ' + (b.method || '—'),
      '',
      '— EVENT —',
      'Event ID: ' + (e.event_id || '—'),
      'Robot / Avatar: ' + (e.robot_or_avatar || '—'),
      'Student (synthetic): ' + (e.student_alias || '—'),
      'Classroom: ' + (e.classroom || '—'),
      'Teacher: ' + (e.teacher || '—'),
      'Program: ' + (e.program || '—'),
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
      'TRUST BOUNDARY: Synthetic data only. No real student/patient data. No partner endorsement claimed.',
      'LensDNA does not make educational or clinical determinations. Human approval required for irreversible actions.',
      'This artifact is a system-of-record entry for residual operational work after a robot/avatar event.'
    ].join('\n');
  }

  window.RoboticsLens = {
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
