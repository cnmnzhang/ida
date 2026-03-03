// ============================================================
// CHART DEFAULTS — shared across all pages
// ============================================================
Chart.defaults.color = '#4a6080';
Chart.defaults.borderColor = '#1e2d45';
Chart.defaults.font.family = "'DM Mono', monospace";

// Shared tooltip config factory
const sharedTooltip = {
  backgroundColor: '#050810',
  borderColor: '#f59e0b',
  borderWidth: 1,
  titleColor: '#e8edf5',
  bodyColor: '#8fa3bf',
  padding: 12,
  cornerRadius: 8
};

// Lazy-init tracking
const _chartsInitialized = { 1: false, 2: false, 3: false };

// ============================================================
// PAGE 1 CHARTS
// ============================================================
function initPage1Charts() {
  if (_chartsInitialized[1]) return;
  _chartsInitialized[1] = true;

  // P1-MAIN: Global prevalence by demographic group (line)
  new Chart(document.getElementById('p1-main'), {
    type: 'line',
    data: {
      labels: [1990,1995,2000,2005,2010,2015,2019,2021],
      datasets: [
        {
          label: 'All Ages (Global)',
          data: [28.2, 27.3, 26.5, 26.0, 25.6, 25.1, 24.6, 24.3],
          borderColor: '#38bdf8', pointBackgroundColor: '#38bdf8',
          borderWidth: 2.5, pointRadius: 5, pointBorderColor: '#080c14', pointBorderWidth: 2,
          tension: 0.35, fill: false
        },
        {
          label: 'Women 15–49',
          data: [37.0, 36.0, 35.1, 34.5, 34.0, 33.8, 33.5, 33.7],
          borderColor: '#f472b6', pointBackgroundColor: '#f472b6',
          borderWidth: 2.5, pointRadius: 5, pointBorderColor: '#080c14', pointBorderWidth: 2,
          tension: 0.35, fill: false
        },
        {
          label: 'Children <5 yrs',
          data: [47.0, 45.5, 44.0, 43.0, 42.0, 41.5, 40.8, 40.2],
          borderColor: '#fb923c', pointBackgroundColor: '#fb923c',
          borderWidth: 2.5, pointRadius: 5, pointBorderColor: '#080c14', pointBorderWidth: 2,
          tension: 0.35, fill: false
        },
        {
          label: 'Adult Males',
          data: [20.0, 18.5, 17.0, 15.8, 14.5, 13.3, 12.0, 11.3],
          borderColor: '#34d399', pointBackgroundColor: '#34d399',
          borderWidth: 2.5, pointRadius: 5, pointBorderColor: '#080c14', pointBorderWidth: 2,
          tension: 0.35, fill: false
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { color: '#8fa3bf', boxWidth: 12, font: { size: 11 } } },
        tooltip: { ...sharedTooltip, callbacks: { label: c => ` ${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` } }
      },
      scales: {
        x: { grid: { color: '#111c2e' }, ticks: { color: '#4a6080', font: { size: 11 } } },
        y: {
          min: 5, max: 55,
          grid: { color: '#111c2e' },
          ticks: { color: '#4a6080', callback: v => v + '%', font: { size: 11 } },
          title: { display: true, text: 'Prevalence (%)', color: '#4a6080', font: { size: 11 } }
        }
      }
    }
  });

  // P1-REGIONAL: bar chart of anemia by world region 2021
  new Chart(document.getElementById('p1-regional'), {
    type: 'bar',
    data: {
      labels: ['W. Sub-Saharan Africa','Central SS Africa','South Asia','E. Sub-Saharan Africa','Oceania','Southeast Asia','Middle East & N. Africa','Latin America','East Asia','Central Europe','W. Europe','North America','Australasia'],
      datasets: [{
        label: 'Anemia prevalence 2021 (%)',
        data: [47.4, 35.7, 35.7, 33.2, 29.1, 27.8, 24.5, 18.2, 15.1, 10.4, 6.0, 6.8, 5.7],
        backgroundColor: ctx => {
          const v = ctx.parsed.y;
          if (v > 35) return '#f87171';
          if (v > 25) return '#fb923c';
          if (v > 15) return '#fbbf24';
          return '#34d399';
        },
        borderRadius: 5,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { ...sharedTooltip, callbacks: { label: c => ` ${c.parsed.x.toFixed(1)}%` } }
      },
      scales: {
        x: {
          grid: { color: '#111c2e' },
          ticks: { color: '#4a6080', callback: v => v + '%', font: { size: 11 } },
          title: { display: true, text: 'Prevalence (%)', color: '#4a6080', font: { size: 11 } }
        },
        y: { grid: { display: false }, ticks: { color: '#8fa3bf', font: { size: 10 } } }
      }
    }
  });
}
