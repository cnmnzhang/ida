// ============================================================
// POLICY BUILDER — Page 4
// Loads pre-computed cohort summary JSON + per-patient records
// and renders the Surveillance Policy Builder experience.
//
// Entry point: initPolicyBuilder()
//   Called lazily by nav.js on first visit to tab 4.
// ============================================================

const PB_DEFAULTS = Object.freeze({
  nPatients: 5000,
  seed: 1,
  gender: 'F',
  minAge: 18,
  maxAge: 65,
  source: 'auto', // auto | api | static
  flaggedPageSize: 200,
});

function _pbGetSearchParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function _pbCssVar(name, fallback) {
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return val || fallback;
}

function _pbNum(value, fallback) {
  const n = parseInt(value, 10);
  return Number.isFinite(n) ? n : fallback;
}

function _pbGetConfig() {
  const cfg = (window.IDA_CONFIG && window.IDA_CONFIG.policyBuilder) || {};
  const globalApiBase = (window.IDA_CONFIG && window.IDA_CONFIG.apiBase) || window.IDA_API_BASE || '';

  const nPatients = _pbNum(
    _pbGetSearchParam('pb_n') ?? cfg.nPatients,
    PB_DEFAULTS.nPatients
  );
  const seed = _pbNum(
    _pbGetSearchParam('pb_seed') ?? cfg.seed,
    PB_DEFAULTS.seed
  );
  const gender = (
    (_pbGetSearchParam('pb_gender') || cfg.gender || PB_DEFAULTS.gender)
  ).toUpperCase();
  const minAge = _pbNum(
    _pbGetSearchParam('pb_min_age') ?? cfg.minAge,
    PB_DEFAULTS.minAge
  );
  const maxAge = _pbNum(
    _pbGetSearchParam('pb_max_age') ?? cfg.maxAge,
    PB_DEFAULTS.maxAge
  );
  const staticBase = cfg.staticBasePath || `data/synth_runs/${nPatients}_${seed}`;
  const cohortPath = _pbGetSearchParam('pb_cohort_path')
    || cfg.cohortPath
    || `${staticBase}/cohort_summary_${gender}_${minAge}_${maxAge}.json`;
  const patientsPath = _pbGetSearchParam('pb_patients_path')
    || cfg.patientsPath
    || `${staticBase}/patients_${gender}_${minAge}_${maxAge}.json`;

  const apiFromQuery = _pbGetSearchParam('pb_api_base') || '';
  const apiBaseRaw = (apiFromQuery || cfg.apiBase || globalApiBase || '').trim();
  const apiBase = apiBaseRaw ? apiBaseRaw.replace(/\/+$/, '') : '';

  const sourceFromQuery = (_pbGetSearchParam('pb_source') || '').toLowerCase();
  const sourceRaw = (sourceFromQuery || cfg.source || PB_DEFAULTS.source).toLowerCase();
  const source = ['auto', 'api', 'static'].includes(sourceRaw) ? sourceRaw : PB_DEFAULTS.source;
  const flaggedPageSize = Math.max(1, _pbNum(cfg.flaggedPageSize, PB_DEFAULTS.flaggedPageSize));

  return {
    nPatients,
    seed,
    gender,
    minAge,
    maxAge,
    source,
    apiBase,
    cohortPath,
    patientsPath,
    flaggedPageSize,
  };
}

const PB_CFG = _pbGetConfig();

let _pbCohort      = null;   // cohort summary JSON
let _pbPatients    = null;   // array of per-patient records
let _pbMode        = 'local'; // local | api
let _pbInitialized = false;  // lazy-init guard
let _pbChart       = null;   // Chart.js instance for investigation panel
let _pbReqSeq      = 0;      // avoids stale async policy responses
let _pbPatientReqSeq = 0;    // avoids stale async patient-detail responses

// ── Entry point ───────────────────────────────────────────────────────────────

function _pbApiParams(extra = {}) {
  return new URLSearchParams({
    n_patients: String(PB_CFG.nPatients),
    seed: String(PB_CFG.seed),
    gender: PB_CFG.gender,
    min_age: String(PB_CFG.minAge),
    max_age: String(PB_CFG.maxAge),
    ...extra,
  });
}

function _pbApiUrl(path, extra = {}) {
  return `${PB_CFG.apiBase}${path}?${_pbApiParams(extra).toString()}`;
}

async function _pbFetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status} loading ${url}`);
  return r.json();
}

async function _pbLoadFromStatic() {
  const [cohort, patients] = await Promise.all([
    _pbFetchJson(PB_CFG.cohortPath),
    _pbFetchJson(PB_CFG.patientsPath),
  ]);
  if (!cohort || !Array.isArray(patients)) {
    throw new Error('Invalid static cohort payload.');
  }
  return { mode: 'local', cohort, patients };
}

async function _pbLoadFromApiPrecomputed() {
  if (!PB_CFG.apiBase) {
    throw new Error('No API base URL configured. Set window.IDA_CONFIG.apiBase or window.IDA_CONFIG.policyBuilder.apiBase.');
  }
  const [summaryPayload, heatmapPayload] = await Promise.all([
    _pbFetchJson(_pbApiUrl('/v1/policy-builder/summary')),
    _pbFetchJson(_pbApiUrl('/v1/policy-builder/heatmap')),
  ]);
  if (!summaryPayload || !summaryPayload.cohort || !heatmapPayload || !Array.isArray(heatmapPayload.cells)) {
    throw new Error('Invalid precomputed API payload.');
  }
  return { mode: 'api', cohort: summaryPayload.cohort, heatmap: heatmapPayload };
}

async function _pbLoadFromApiLegacy() {
  if (!PB_CFG.apiBase) {
    throw new Error('No API base URL configured. Set window.IDA_CONFIG.apiBase or window.IDA_CONFIG.policyBuilder.apiBase.');
  }
  const payload = await _pbFetchJson(_pbApiUrl('/v1/policy-builder/cohort'));
  if (!payload || typeof payload !== 'object' || !payload.cohort || !Array.isArray(payload.patients)) {
    throw new Error('Invalid legacy API cohort payload.');
  }
  return { mode: 'local', cohort: payload.cohort, patients: payload.patients };
}

async function _pbLoadFromApi() {
  try {
    return await _pbLoadFromApiPrecomputed();
  } catch (err) {
    console.warn('Precomputed API load failed; trying legacy cohort endpoint.', err);
    return _pbLoadFromApiLegacy();
  }
}

async function _pbLoadData() {
  if (PB_CFG.source === 'static') return _pbLoadFromStatic();
  if (PB_CFG.source === 'api') return _pbLoadFromApi();

  const errors = [];
  if (PB_CFG.apiBase) {
    try {
      return await _pbLoadFromApi();
    } catch (err) {
      errors.push(`API: ${err.message}`);
      console.warn('Policy Builder API load failed; falling back to static files.', err);
    }
  }
  try {
    return await _pbLoadFromStatic();
  } catch (err) {
    errors.push(`Static: ${err.message}`);
    throw new Error(errors.join(' | '));
  }
}

async function initPolicyBuilder() {
  if (_pbInitialized) return;
  _pbInitialized = true;

  _pbLoadData().then((payload) => {
    _pbCohort = payload.cohort;
    _pbMode = payload.mode;
    _pbPatients = payload.mode === 'local' ? payload.patients : null;

    const builderSub = document.querySelector('.pb-builder .card-sub');
    if (builderSub) {
      if (_pbMode === 'local') {
        builderSub.textContent = `Patient-level mode · ${_pbPatients.length.toLocaleString()} records loaded`;
      } else {
        builderSub.textContent = `API mode · ${(_pbCohort.cohort_size || 0).toLocaleString()} indexed records (paginated)`;
      }
    }

    document.getElementById('pb-loading').style.display = 'none';
    document.getElementById('pb-content').style.display = '';

    _pbRenderContext(_pbCohort);
    _pbRenderSignals(_pbCohort);
    _pbRenderDisclaimers(_pbCohort);
    _pbRenderFerritinHeatmap(_pbMode === 'local' ? _pbPatients : payload.heatmap);
    _pbWireListeners();
    _pbSyncExclusionState();
    _pbSyncSetpointSlider();
    _pbUpdateOutput();
  }).catch(err => {
    document.getElementById('pb-loading').style.display = 'none';
    document.getElementById('pb-error').style.display   = '';
    document.getElementById('pb-error-msg').textContent =
      `Could not load cohort data: ${err.message}. ` +
      `For GitHub Pages, point the builder to a backend API (window.IDA_CONFIG.apiBase) ` +
      `or commit static files at ${PB_CFG.cohortPath} and ${PB_CFG.patientsPath}.`;
  });
}

// ── Section renderers ─────────────────────────────────────────────────────────

function _pbRenderContext(d) {
  const f      = d.cohort_filter || {};
  const gender = f.gender === 'F' ? 'Female'
               : f.gender === 'M' ? 'Male'
               : f.gender         || 'All';
  const ages   = `${f.min_age ?? '?'}–${f.max_age ?? '?'}`;
  const genAt  = d.generated_at
    ? new Date(d.generated_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
    : '—';

  document.getElementById('pb-context-inner').innerHTML = `
    <div class="pb-context-items">
      <div class="pb-context-item">
        <div class="pb-context-key">Location</div>
        <div class="pb-context-val">${d.location || '—'}</div>
      </div>
      <div class="pb-context-sep" aria-hidden="true"></div>
      <div class="pb-context-item">
        <div class="pb-context-key">Filter</div>
        <div class="pb-context-val">${gender} &middot; Age ${ages}</div>
      </div>
      <div class="pb-context-sep" aria-hidden="true"></div>
      <div class="pb-context-item">
        <div class="pb-context-key">Cohort size</div>
        <div class="pb-context-val">${(d.cohort_size || 0).toLocaleString()}</div>
      </div>
      <div class="pb-context-sep" aria-hidden="true"></div>
      <div class="pb-context-item">
        <div class="pb-context-key">Seed</div>
        <div class="pb-context-val">${d.seed ?? '—'}</div>
      </div>
      <div class="pb-context-sep" aria-hidden="true"></div>
      <div class="pb-context-item">
        <div class="pb-context-key">Generated</div>
        <div class="pb-context-val">${genAt}</div>
      </div>
      <div class="pb-context-note">
        ${(d.patients_requested || 0).toLocaleString()} requested
        &rarr; ${(d.patients_generated || 0).toLocaleString()} generated by Synthea
        &rarr; ${(d.cohort_size || 0).toLocaleString()} after filter
      </div>
    </div>
  `;
}

function _pbRenderSignals(d) {
  const n   = d.cohort_size || 1;
  const lab = d.lab_anemia  || {};
  const dx  = d.diagnoses   || {};
  const pct = (c) => n > 0 ? `${((c / n) * 100).toFixed(1)}% of cohort` : '—';

  document.getElementById('pb-t-lab-val').textContent   = (lab.lab_anemia_count      || 0).toLocaleString();
  document.getElementById('pb-t-lab-pct').textContent   = pct(lab.lab_anemia_count   || 0);
  document.getElementById('pb-t-coded-val').textContent = (dx.anemia_dx_count        || 0).toLocaleString();
  document.getElementById('pb-t-coded-pct').textContent = pct(dx.anemia_dx_count     || 0);
}

function _pbRenderDisclaimers(d) {
  const idaDxCount = (d.diagnoses || {}).ida_dx_count ?? 0;

  const items = [
    {
      text: 'Synthea may encode IDA as generic anemia (SNOMED 271737000); ' +
            'IDA-specific codes (87522002, 234347009) may be absent from this cohort.',
      warn: true,
    },
    {
      text: 'Coded anemia may persist after Hb normalizes. ' +
            'Lab-defined anemia reflects only the most-recent Hb reading per patient.',
      warn: false,
    },
    {
      text: 'Setpoint = mean of up to 5 readings preceding the most-recent Hb. ' +
            'Patients with fewer than 2 Hb readings have no setpoint and cannot be flagged by the baseline-drop trigger.',
      warn: false,
    },
  ];

  if (idaDxCount === 0) {
    items.push({
      text: 'IDA-specific codes were not observed in this cohort. ' +
            'All coded anemia reflects the generic anemia SNOMED code.',
      warn: true,
    });
  }

  document.getElementById('pb-disclaimer-list').innerHTML = items
    .map(({ text, warn }) => `<li class="${warn ? 'pb-warn' : ''}">${text}</li>`)
    .join('');
}

// ── Event wiring ──────────────────────────────────────────────────────────────

function _pbWireListeners() {
  document.getElementById('pb-trigger').addEventListener('change', () => {
    _pbSyncExclusionState();
    _pbSyncSetpointSlider();
    _pbUpdateOutput();
  });

  document.getElementById('pb-excl-coded').addEventListener('change', () => {
    _pbSyncExclusionState();
    _pbUpdateOutput();
  });

  document.getElementById('pb-excl-hb-min').addEventListener('change', _pbUpdateOutput);

  document.getElementById('pb-setpoint-thresh').addEventListener('input', () => {
    const val = document.getElementById('pb-setpoint-thresh').value;
    document.getElementById('pb-setpoint-val-num').textContent = parseFloat(val).toFixed(1);
    _pbUpdateOutput();
  });

  document.getElementById('pb-pt-select').addEventListener('change', () => {
    const id = document.getElementById('pb-pt-select').value;
    if (!id) {
      _pbClearPatientDetail();
      return;
    }
    if (_pbMode === 'api') {
      _pbFetchPatientDetail(id);
      return;
    }
    const patient = _pbPatients.find(p => p.id === id);
    if (patient) _pbRenderPatientDetail(patient);
  });
}

// ── UI sync ───────────────────────────────────────────────────────────────────

function _pbSyncExclusionState() {
  const trigger   = document.getElementById('pb-trigger').value;
  const codedCb   = document.getElementById('pb-excl-coded');
  const codedRow  = document.getElementById('pb-excl-coded-row');
  const codedNote = document.getElementById('pb-excl-coded-note');

  if (trigger === 'gap') {
    codedCb.checked        = true;
    codedCb.disabled       = true;
    codedRow.style.opacity = '0.65';
    codedNote.style.display  = '';
    codedNote.textContent    = 'Implied by "Diagnostic gap only" trigger.';
  } else if (trigger === 'coded') {
    codedCb.disabled       = true;
    codedRow.style.opacity = '0.45';
    codedNote.style.display  = 'none';
  } else {
    // lab or setpoint
    codedCb.disabled       = false;
    codedRow.style.opacity = '1';
    const isChecked = codedCb.checked;
    codedNote.style.display = isChecked ? '' : 'none';
    if (isChecked) {
      codedNote.textContent = trigger === 'lab'
        ? 'Switches output to diagnostic gap (lab anemia without coded anemia).'
        : 'Restricts to patients without a coded anemia diagnosis.';
    }
  }
}

function _pbSyncSetpointSlider() {
  const trigger = document.getElementById('pb-trigger').value;
  document.getElementById('pb-setpoint-row').style.display =
    trigger === 'setpoint' ? '' : 'none';
}

function _pbGetPolicyState() {
  return {
    trigger: document.getElementById('pb-trigger').value,
    excludeCoded: document.getElementById('pb-excl-coded').checked,
    requireMinHb: document.getElementById('pb-excl-hb-min').checked,
    threshold: parseFloat(document.getElementById('pb-setpoint-thresh').value),
  };
}

function _pbSignalText(trigger, threshold, excludeCoded) {
  if (trigger === 'lab' && !excludeCoded) {
    return {
      subtitle: 'Lab-defined anemia · WHO criterion',
      signalDesc: 'Most-recent Hb below WHO threshold (female: <12.0 g/dL).',
    };
  }
  if (trigger === 'lab' && excludeCoded) {
    return {
      subtitle: 'Diagnostic gap · lab anemia without coded anemia',
      signalDesc: 'Lab-defined anemia (WHO) with no coded anemia diagnosis on record.',
    };
  }
  if (trigger === 'coded') {
    return {
      subtitle: 'Coded anemia',
      signalDesc: 'Anemia diagnosis code on record (SNOMED 271737000 or equivalent).',
    };
  }
  if (trigger === 'gap') {
    return {
      subtitle: 'Diagnostic gap only',
      signalDesc: 'Lab-defined anemia (WHO) with no coded anemia diagnosis on record.',
    };
  }
  return {
    subtitle: `Drop from Bayesian setpoint >= ${threshold.toFixed(1)} g/dL`,
    signalDesc: `Latest Hb is >= ${threshold.toFixed(1)} g/dL below the patient's Bayesian adaptive setpoint ` +
      '(conjugate Gaussian model, personalized per patient).',
  };
}

function _pbRenderOutput(state, flaggedN, flaggedPatients) {
  const d = _pbCohort;
  const cohortSize = d.cohort_size || 1;
  const flaggedPct = `${((flaggedN / cohortSize) * 100).toFixed(1)}%`;

  const gapCount = (d.diagnostic_gap || {}).lab_anemia_without_dx || 0;
  const gapPct = `${((gapCount / cohortSize) * 100).toFixed(1)}%`;
  const { subtitle, signalDesc } = _pbSignalText(state.trigger, state.threshold, state.excludeCoded);

  document.getElementById('pb-out-subtitle').textContent = subtitle;
  document.getElementById('pb-out-count').textContent = flaggedN.toLocaleString();
  document.getElementById('pb-out-pct').textContent =
    `${flaggedPct} of cohort (n = ${cohortSize.toLocaleString()})`;
  document.getElementById('pb-out-signal').textContent = signalDesc;

  const isGapPolicy = (state.trigger === 'gap') || (state.trigger === 'lab' && state.excludeCoded);
  const gapNote = isGapPolicy
    ? 'This policy directly targets the diagnostic gap.'
    : 'This policy does not specifically target the diagnostic gap.';
  document.getElementById('pb-gap-context-val').innerHTML =
    `<strong style="color:var(--accent-pink);">${gapCount.toLocaleString()}</strong> patients ` +
    `(${gapPct} of cohort) have lab-defined anemia without a coded anemia diagnosis. ` +
    `<span style="color:var(--text-muted);">${gapNote}</span>`;

  _pbUpdateInvestigationPanel(flaggedPatients);
}

// ── Patient-level flagging ────────────────────────────────────────────────────

function _pbGetFlaggedPatients() {
  const trigger      = document.getElementById('pb-trigger').value;
  const excludeCoded = document.getElementById('pb-excl-coded').checked;
  const requireMinHb = document.getElementById('pb-excl-hb-min').checked;
  const threshold    = parseFloat(document.getElementById('pb-setpoint-thresh').value);

  let flagged = _pbPatients;

  if (requireMinHb) {
    flagged = flagged.filter(p => ((p.hb_history && p.hb_history.length) || p.hb_count || 0) >= 3);
  }

  if (trigger === 'lab') {
    flagged = flagged.filter(p => p.lab_anemia);
    if (excludeCoded) flagged = flagged.filter(p => !p.coded_anemia);
  } else if (trigger === 'coded') {
    flagged = flagged.filter(p => p.coded_anemia);
  } else if (trigger === 'gap') {
    flagged = flagged.filter(p => p.lab_anemia && !p.coded_anemia);
  } else if (trigger === 'setpoint') {
    flagged = flagged.filter(p => p.hb_drop !== null && p.hb_drop >= threshold);
    if (excludeCoded) flagged = flagged.filter(p => !p.coded_anemia);
  }

  return flagged;
}

// ── Output computation ────────────────────────────────────────────────────────

function _pbUpdateOutput() {
  if (!_pbCohort) return;
  if (_pbMode === 'api') {
    _pbUpdateOutputApi();
    return;
  }
  if (!_pbPatients) return;

  const state = _pbGetPolicyState();
  const flagged = _pbGetFlaggedPatients();
  _pbRenderOutput(state, flagged.length, flagged);
}

async function _pbUpdateOutputApi() {
  const reqSeq = ++_pbReqSeq;
  const state = _pbGetPolicyState();

  try {
    const payload = await _pbFetchJson(_pbApiUrl('/v1/policy-builder/flagged', {
      trigger: state.trigger,
      exclude_coded: String(state.excludeCoded),
      require_min_hb: String(state.requireMinHb),
      threshold: state.threshold.toFixed(1),
      limit: String(PB_CFG.flaggedPageSize),
      offset: '0',
    }));
    if (reqSeq !== _pbReqSeq) return;

    const summary = payload.summary || {};
    const flaggedPatients = Array.isArray(payload.patients) ? payload.patients : [];
    _pbRenderOutput(
      state,
      summary.flagged_count || 0,
      flaggedPatients,
    );
  } catch (err) {
    if (reqSeq !== _pbReqSeq) return;
    document.getElementById('pb-out-subtitle').textContent = 'Unable to load policy output';
    document.getElementById('pb-out-count').textContent = '—';
    document.getElementById('pb-out-pct').textContent = '';
    document.getElementById('pb-out-signal').textContent = err.message;
    _pbUpdateInvestigationPanel([]);
  }
}

async function _pbFetchPatientDetail(patientId) {
  const reqSeq = ++_pbPatientReqSeq;
  try {
    const payload = await _pbFetchJson(_pbApiUrl(`/v1/policy-builder/patient/${encodeURIComponent(patientId)}`));
    if (reqSeq !== _pbPatientReqSeq) return;
    const patient = payload && payload.patient ? payload.patient : payload;
    _pbRenderPatientDetail(patient);
  } catch (err) {
    if (reqSeq !== _pbPatientReqSeq) return;
    _pbClearPatientDetail();
    document.getElementById('pb-pt-empty').textContent = `Could not load patient detail: ${err.message}`;
  }
}

// ── Investigation panel ───────────────────────────────────────────────────────

function _pbUpdateInvestigationPanel(flaggedPatients) {
  const sel    = document.getElementById('pb-pt-select');
  const prevId = sel.value;

  sel.innerHTML = '<option value="">— select a patient —</option>';
  flaggedPatients.forEach(p => {
    const opt      = document.createElement('option');
    opt.value      = p.id;
    opt.textContent = p.id;
    sel.appendChild(opt);
  });

  // Restore prior selection if still in the flagged list
  if (prevId && flaggedPatients.some(p => p.id === prevId)) {
    sel.value = prevId;
    if (_pbMode === 'api') {
      _pbFetchPatientDetail(prevId);
    } else {
      const patient = flaggedPatients.find(p => p.id === prevId);
      if (patient) _pbRenderPatientDetail(patient);
    }
  } else {
    sel.value = '';
    _pbClearPatientDetail();
  }
}

function _pbClearPatientDetail() {
  document.getElementById('pb-pt-empty').textContent = 'No patient selected.';
  document.getElementById('pb-pt-empty').style.display  = '';
  document.getElementById('pb-pt-detail').style.display = 'none';
  if (_pbChart) { _pbChart.destroy(); _pbChart = null; }
}

function _pbRenderPatientDetail(patient) {
  document.getElementById('pb-pt-empty').style.display  = 'none';
  document.getElementById('pb-pt-detail').style.display = '';

  // ── Meta row ─────────────────────────────────────────────────────────────
  const spText = patient.setpoint !== null
    ? `Bayesian setpoint ${patient.setpoint.toFixed(2)} ± ${patient.setpoint_sigma.toFixed(2)} g/dL`
    : 'No setpoint (< 2 readings)';
  const dropText = patient.hb_drop !== null
    ? `Drop ${patient.hb_drop.toFixed(2)} g/dL`
    : '—';
  const zText = patient.hb_drop_z !== null
    ? `${patient.hb_drop_z.toFixed(2)} σ below setpoint`
    : '—';
  document.getElementById('pb-pt-meta').innerHTML =
    `<span>Age ${patient.age}</span>` +
    `<span>Latest Hb <strong>${patient.latest_hb !== null ? patient.latest_hb.toFixed(2) : '—'}</strong> g/dL</span>` +
    `<span>WHO threshold ${patient.who_threshold} g/dL</span>` +
    `<span>${spText}</span>` +
    `<span>Drop <strong>${dropText}</strong> · ${zText}</span>` +
    `<span>${patient.coded_anemia ? 'Coded anemia on record' : 'No coded anemia on record'}</span>` +
    `<span>${patient.ferritin_tests} ferritin test${patient.ferritin_tests !== 1 ? 's' : ''}</span>`;

  // ── Chart ─────────────────────────────────────────────────────────────────
  _pbRenderPatientChart(patient);

  // ── Conditions table ──────────────────────────────────────────────────────
  _pbRenderConditionsTable(patient);
}

function _pbRenderPatientChart(patient) {
  if (_pbChart) { _pbChart.destroy(); _pbChart = null; }

  const hb      = patient.hb_history;
  const spHist  = patient.setpoint_history || [];
  const labels  = hb.map(h => h.date);
  const values  = hb.map(h => h.value);
  const thresh  = patient.who_threshold;
  const textBody = _pbCssVar('--text-body', '#d0d8e3');
  const textMuted = _pbCssVar('--text-muted', '#8fa3bf');

  const pointColors = values.map(v => v < thresh ? '#e86464' : '#6ea8d8');

  const datasets = [
    {
      label: 'Hemoglobin (g/dL)',
      data: values,
      borderColor: '#6ea8d8',
      backgroundColor: pointColors,
      pointBackgroundColor: pointColors,
      pointRadius: 5,
      pointHoverRadius: 7,
      tension: 0.2,
      fill: false,
      order: 1,
    },
    {
      label: `WHO threshold (${thresh} g/dL)`,
      data: new Array(labels.length).fill(thresh),
      borderColor: 'rgba(232,100,100,0.55)',
      borderDash: [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
      order: 3,
    },
  ];

  // Bayesian adaptive setpoint: µ trajectory + ±σ band
  if (spHist.length === hb.length) {
    const muVals    = spHist.map(s => s.mu);
    const upperBand = spHist.map(s => parseFloat((s.mu + s.sigma).toFixed(3)));
    const lowerBand = spHist.map(s => parseFloat((s.mu - s.sigma).toFixed(3)));

    // Upper σ boundary — fill to the next dataset (lower boundary)
    datasets.push({
      label: '_upper',
      data: upperBand,
      borderColor: 'transparent',
      backgroundColor: 'rgba(255,185,50,0.10)',
      pointRadius: 0,
      fill: '+1',
      order: 4,
    });
    // Lower σ boundary
    datasets.push({
      label: '_lower',
      data: lowerBand,
      borderColor: 'transparent',
      backgroundColor: 'rgba(255,185,50,0.10)',
      pointRadius: 0,
      fill: false,
      order: 4,
    });
    // µ trajectory line
    datasets.push({
      label: 'Bayesian setpoint (µ)',
      data: muVals,
      borderColor: 'rgba(255,185,50,0.85)',
      borderDash: [4, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
      order: 2,
    });
  }

  const ctx = document.getElementById('pb-pt-chart').getContext('2d');
  _pbChart  = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: {
            color: textBody,
            font: { family: 'Karla', size: 12 },
            boxWidth: 20,
            filter: (item) => !item.text.startsWith('_'),
          },
        },
        tooltip: {
          filter: (item) => !item.dataset.label.startsWith('_'),
          backgroundColor: 'rgba(8,12,20,0.95)',
          borderColor: 'rgba(255,255,255,0.14)',
          borderWidth: 1,
          titleColor: textBody,
          bodyColor: textBody,
          callbacks: {
            label: (ctx) =>
              `${ctx.dataset.label}: ${typeof ctx.parsed.y === 'number' ? ctx.parsed.y.toFixed(2) : ctx.parsed.y}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: textMuted, maxRotation: 40, font: { size: 11 } },
          grid:  { color: 'rgba(255,255,255,0.05)' },
        },
        y: {
          ticks: { color: textMuted, font: { size: 11 } },
          grid:  { color: 'rgba(255,255,255,0.06)' },
          title: { display: true, text: 'g/dL', color: textMuted, font: { size: 11 } },
        },
      },
    },
  });
}

function _pbRenderConditionsTable(patient) {
  const wrap = document.getElementById('pb-pt-conditions-wrap');
  const conds = patient.conditions;

  if (!conds || conds.length === 0) {
    wrap.innerHTML = '<p class="pb-pt-no-conds">No conditions recorded for this patient.</p>';
    return;
  }

  const rows = conds.map(c => `
    <tr>
      <td class="pb-pt-cond-date">${c.date || '—'}</td>
      <td class="pb-pt-cond-code">${c.code}</td>
      <td>${c.description}</td>
    </tr>
  `).join('');

  wrap.innerHTML = `
    <div class="pb-pt-cond-title">Conditions (${conds.length})</div>
    <table class="pb-pt-cond-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Code</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// ── Ferritin heatmap ──────────────────────────────────────────────────────────

function _pbRenderFerritinHeatmap(data) {
  const wrap = document.getElementById('pb-heatmap-wrap');
  if (!wrap) return;

  const hbBins = [
    { label: '<10', min: -Infinity, max: 10 },
    { label: '10-11', min: 10, max: 11 },
    { label: '11-12', min: 11, max: 12 },
    { label: '12-13', min: 12, max: 13 },
    { label: '>=13', min: 13, max: Infinity },
  ];
  const dropBins = [
    { label: '>=2.0', min: 2.0, max: Infinity },
    { label: '1.5-2.0', min: 1.5, max: 2.0 },
    { label: '1.0-1.5', min: 1.0, max: 1.5 },
    { label: '0.5-1.0', min: 0.5, max: 1.0 },
    { label: '<0.5', min: -Infinity, max: 0.5 },
  ];
  let minCell = 5;
  let counts = dropBins.map(() => hbBins.map(() => ({ n: 0, fer: 0 })));

  if (Array.isArray(data)) {
    for (const p of data) {
      if (p.latest_hb == null) continue;
      const drop = p.hb_drop ?? 0;
      const hb = p.latest_hb;
      const hasFer = (p.ferritin_tests || 0) > 0;

      const xi = hbBins.findIndex(b => hb >= b.min && hb < b.max);
      const yi = dropBins.findIndex(b => drop >= b.min && drop < b.max);
      if (xi < 0 || yi < 0) continue;

      counts[yi][xi].n++;
      if (hasFer) counts[yi][xi].fer++;
    }
  } else if (data && Array.isArray(data.cells)) {
    minCell = Number.isFinite(data.min_cell) ? data.min_cell : minCell;

    const hbLabels = Array.isArray(data.hb_bins) ? data.hb_bins.map(b => b.label) : hbBins.map(b => b.label);
    const dropLabels = Array.isArray(data.drop_bins) ? data.drop_bins.map(b => b.label) : dropBins.map(b => b.label);
    hbBins.splice(0, hbBins.length, ...hbLabels.map(label => ({ label })));
    dropBins.splice(0, dropBins.length, ...dropLabels.map(label => ({ label })));

    counts = data.cells.map(row => row.map(cell => ({
      n: (cell && Number.isFinite(cell.n)) ? cell.n : 0,
      fer: (cell && Number.isFinite(cell.fer)) ? cell.fer : 0,
    })));
  }

  // Colour scale: 0 = transparent, 1 = accent-blue full
  // Parse CSS variable via computed style isn't trivial; use hardcoded palette
  const palette = [
    'rgba(56,189,248,0.08)',   // 0–5%
    'rgba(56,189,248,0.20)',   // 5–15%
    'rgba(56,189,248,0.38)',   // 15–30%
    'rgba(56,189,248,0.58)',   // 30–50%
    'rgba(56,189,248,0.82)',   // 50–75%
    'rgba(56,189,248,1.00)',   // >75%
  ];
  function rateToColor(rate) {
    if (rate < 0.05) return palette[0];
    if (rate < 0.15) return palette[1];
    if (rate < 0.30) return palette[2];
    if (rate < 0.50) return palette[3];
    if (rate < 0.75) return palette[4];
    return palette[5];
  }

  let rows = '';
  dropBins.forEach((db, yi) => {
    let cells = `<td class="pb-hm-rlabel">${db.label}</td>`;
    hbBins.forEach((hb, xi) => {
      const cell = (counts[yi] && counts[yi][xi]) ? counts[yi][xi] : { n: 0, fer: 0 };
      const suppressed = cell.n < minCell;
      const rate = suppressed || cell.n === 0 ? null : cell.fer / cell.n;
      const bg   = suppressed ? 'rgba(255,255,255,0.03)' : rateToColor(rate);
      const txt  = suppressed
        ? `<span class="pb-hm-suppressed">n&lt;${minCell}</span>`
        : `<span class="pb-hm-rate">${(rate * 100).toFixed(0)}%</span>
           <span class="pb-hm-n">${cell.fer}/${cell.n}</span>`;
      cells += `<td class="pb-hm-cell" style="background:${bg};">${txt}</td>`;
    });
    rows += `<tr>${cells}</tr>`;
  });

  const headerCells = hbBins.map(b => `<th class="pb-hm-clabel">Hb ${b.label}</th>`).join('');

  wrap.innerHTML = `
    <div class="pb-heatmap-inner">
      <div class="pb-hm-ylabel">← Hb drop from setpoint (g/dL)</div>
      <div class="pb-hm-table-wrap">
        <table class="pb-hm-table">
          <thead><tr><td></td>${headerCells}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <div class="pb-hm-xlabel">Latest Hb (g/dL) →</div>
      </div>
      <div class="pb-hm-legend">
        <span class="pb-hm-legend-label">0%</span>
        <div class="pb-hm-legend-bar"></div>
        <span class="pb-hm-legend-label">100%</span>
        <span class="pb-hm-legend-desc">P(ferritin ordered)</span>
      </div>
    </div>
  `;
}
