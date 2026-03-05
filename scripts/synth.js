// ============================================================
// SYNTHETIC COHORT — Page 4
// Calls the FastAPI backend to generate / fetch Synthea cohort summaries.
// ============================================================

const API_BASE = 'http://localhost:8000';

function initPage4() {
  // Nothing to auto-initialize; UI is driven by button click.
}

async function triggerGenerate() {
  const nPatients = parseInt(document.getElementById('p4-n-patients').value, 10);
  const seed = parseInt(document.getElementById('p4-seed').value, 10);
  const btn = document.getElementById('p4-generate-btn');
  const status = document.getElementById('p4-status');

  if (!nPatients || nPatients < 1) {
    _p4ShowError('Patient count must be a positive integer.');
    return;
  }

  // Reset UI
  document.getElementById('p4-results').style.display = 'none';
  document.getElementById('p4-error').style.display = 'none';
  btn.disabled = true;
  btn.textContent = 'Running…';
  status.textContent = 'Sending request to API… (first run may take 30–90s for Synthea)';

  try {
    const resp = await fetch(`${API_BASE}/v1/synth/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ n_patients: nPatients, seed }),
    });

    const data = await resp.json();

    if (!resp.ok) {
      const detail = data.detail || {};
      const msg = typeof detail === 'string' ? detail : (detail.message || JSON.stringify(detail));
      _p4ShowError(msg);
      return;
    }

    status.textContent = data.status === 'done' ? 'Done. Results loaded from cache or fresh run.' : '';
    _p4RenderSummary(data.summary);

  } catch (err) {
    _p4ShowError(
      `Could not reach the API at ${API_BASE}. ` +
      'Make sure uvicorn is running: uvicorn apps.api.main:app --reload --port 8000\n\n' +
      err.message
    );
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Cohort';
  }
}

function _p4RenderSummary(s) {
  // KPI strip
  const kpiStrip = document.getElementById('p4-kpi-strip');
  const prevalencePct = s.ida_prevalence != null ? (s.ida_prevalence * 100).toFixed(1) + '%' : '—';
  const hbMean = s.hb_mean != null ? s.hb_mean.toFixed(2) + ' g/dL' : '—';
  kpiStrip.innerHTML = `
    <div class="kpi">
      <div class="kpi-val" style="color:var(--accent-amber)">${s.cohort_size.toLocaleString()}</div>
      <div class="kpi-lbl">Patients generated</div>
    </div>
    <div class="kpi">
      <div class="kpi-val" style="color:var(--accent-pink)">${s.ida_dx_count.toLocaleString()}</div>
      <div class="kpi-lbl">IDA diagnoses</div>
    </div>
    <div class="kpi">
      <div class="kpi-val" style="color:var(--accent-blue)">${prevalencePct}</div>
      <div class="kpi-lbl">IDA prevalence</div>
    </div>
    <div class="kpi">
      <div class="kpi-val" style="color:var(--accent-green)">${hbMean}</div>
      <div class="kpi-lbl">Mean HB</div>
    </div>
    <div class="kpi">
      <div class="kpi-val" style="color:var(--accent-purple)">${s.hb_observation_count.toLocaleString()}</div>
      <div class="kpi-lbl">HB observations</div>
    </div>
  `;

  // Summary table rows
  const rows = [
    ['Location', s.location],
    ['Patients requested', s.n_patients_requested.toLocaleString()],
    ['Seed', s.seed],
    ['Cohort size (generated)', s.cohort_size.toLocaleString()],
    ['IDA diagnoses', s.ida_dx_count.toLocaleString()],
    ['IDA prevalence', prevalencePct],
    ['HB observations', s.hb_observation_count.toLocaleString()],
    ['HB mean (g/dL)', s.hb_mean != null ? s.hb_mean.toFixed(3) : '—'],
    ['HB std dev (g/dL)', s.hb_std != null ? s.hb_std.toFixed(3) : '—'],
    ['Generated at', s.generated_at],
  ];

  const tbody = document.getElementById('p4-summary-tbody');
  tbody.innerHTML = rows.map(([label, val], i) => `
    <tr style="border-bottom:1px solid var(--border); ${i % 2 === 0 ? 'background:rgba(255,255,255,0.02);' : ''}">
      <td style="padding:8px 12px; color:var(--text-muted);">${label}</td>
      <td style="padding:8px 12px; color:var(--text-primary); text-align:right;">${val}</td>
    </tr>
  `).join('');

  // Histogram
  if (s.hb_hist && s.hb_hist.length > 0) {
    const maxCount = Math.max(...s.hb_hist.map(b => b.count));
    const barWidth = 30;
    const histHtml = s.hb_hist.map(b => {
      const filled = maxCount > 0 ? Math.round((b.count / maxCount) * barWidth) : 0;
      const bar = '█'.repeat(filled) + '░'.repeat(barWidth - filled);
      return `<div style="display:flex; gap:12px; align-items:center; margin-bottom:4px;">
        <span style="color:var(--text-muted); width:130px; text-align:right;">${b.bin_start.toFixed(1)}–${b.bin_end.toFixed(1)}</span>
        <span style="color:var(--accent-blue);">${bar}</span>
        <span style="color:var(--text-primary);">${b.count}</span>
      </div>`;
    }).join('');
    document.getElementById('p4-histogram').innerHTML = histHtml;
    document.getElementById('p4-hist-card').style.display = '';
  } else {
    document.getElementById('p4-hist-card').style.display = 'none';
  }

  document.getElementById('p4-results').style.display = '';
}

function _p4ShowError(msg) {
  document.getElementById('p4-error-msg').textContent = msg;
  document.getElementById('p4-error').style.display = '';
  document.getElementById('p4-results').style.display = 'none';
  document.getElementById('p4-status').textContent = '';
}
