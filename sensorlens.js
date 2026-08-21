/**
 * SensorLens static state layer
 * Replaces Flask session with localStorage.
 * Same residual flow, human gate, metrics, pilot intake.
 */
(function () {
  const KEY = 'sensorlens_state';
  const METRICS_KEY = 'sensorlens_practice_metrics';

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
    portal_member: '',
    auth_ref: '',
    cpt: '',
    attachment_note: '',
    status_note: '',
    submitted: false,
    submit_ts: '',
    timing_json: '',
    run_seconds: '',
    gate_blocked: false,
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

  // Expose for page scripts
  window.SensorLens = {
    load,
    save,
    clear,
    nowUtc,
    METRICS_KEY
  };

  // Footer timestamp
  document.addEventListener('DOMContentLoaded', function () {
    const el = document.getElementById('sl-now');
    if (el) el.textContent = nowUtc();
  });
})();
