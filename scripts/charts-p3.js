// ============================================================
// PAGE 3 CHARTS
// ============================================================
function initPage3Charts() {
  if (_chartsInitialized[3]) return;
  _chartsInitialized[3] = true;

  // P3-MEAT: Red meat vs poultry (line)
  new Chart(document.getElementById('p3-meat'), {
    type: 'line',
    data: {
      labels: [1999,2001,2003,2005,2007,2009,2011,2013,2015,2016],
      datasets: [
        { label: 'Unprocessed red meat (g/wk)', data: [340,328,316,310,303,298,292,286,284,283], borderColor:'#f87171', backgroundColor:'rgba(248,113,113,0.1)', borderWidth:2.5, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:2, tension:0.3, fill:true },
        { label: 'Poultry (g/wk)', data: [190,200,210,218,224,228,230,232,237,237], borderColor:'#34d399', backgroundColor:'rgba(52,211,153,0.07)', borderWidth:2.5, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:2, tension:0.3, fill:true }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { color: '#8fa3bf', boxWidth: 12, font: { size: 11 } } },
        tooltip: { ...sharedTooltip, callbacks: { label: c => ` ${c.dataset.label}: ${c.parsed.y.toFixed(0)}g` } }
      },
      scales: {
        x: { grid: { color: '#111c2e' }, ticks: { color: '#4a6080', font: { size: 11 } } },
        y: { grid: { color: '#111c2e' }, ticks: { color: '#4a6080', font: { size: 11 } }, title: { display: true, text: 'g / week', color: '#4a6080', font: { size: 11 } } }
      }
    }
  });

  // P3-OBESITY: US women obesity rate (line/area)
  new Chart(document.getElementById('p3-obesity'), {
    type: 'line',
    data: {
      labels: [1999,2001,2003,2005,2007,2009,2011,2013,2015,2018,2020],
      datasets: [{
        label: 'Women obesity rate (BMI ≥30)',
        data: [33.4,33.9,34.5,35.2,36.1,36.6,38.3,38.8,40.0,42.5,43.9],
        borderColor:'#fb923c', backgroundColor:'rgba(251,146,60,0.1)',
        borderWidth:2.5, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:2,
        tension:0.3, fill:true
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { color: '#8fa3bf', boxWidth: 12, font: { size: 11 } } },
        tooltip: { ...sharedTooltip, callbacks: { label: c => ` ${c.parsed.y.toFixed(1)}%` } }
      },
      scales: {
        x: { grid: { color: '#111c2e' }, ticks: { color: '#4a6080', font: { size: 11 } } },
        y: { min: 25, max: 50, grid: { color: '#111c2e' }, ticks: { color: '#4a6080', callback: v => v + '%', font: { size: 11 } } }
      }
    }
  });

  // P3-UPF: Ultra-processed food share of calories (line)
  new Chart(document.getElementById('p3-upf'), {
    type: 'line',
    data: {
      labels: [2001,2003,2005,2007,2009,2011,2013,2015,2017],
      datasets: [
        { label: 'Ultra-processed (%kcal)', data: [53.5,54.2,54.8,55.3,55.8,56.0,56.3,56.7,57.0], borderColor:'#a78bfa', backgroundColor:'rgba(167,139,250,0.1)', borderWidth:2.5, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:2, tension:0.3, fill:true },
        { label: 'Minimally processed (%kcal)', data: [32.7,31.9,31.2,30.5,30.0,29.5,29.0,28.0,27.4], borderColor:'#34d399', backgroundColor:'transparent', borderWidth:2, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:1, tension:0.3, fill:false, borderDash:[4,3] }
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
        y: { min: 20, max: 65, grid: { color: '#111c2e' }, ticks: { color: '#4a6080', callback: v => v + '%', font: { size: 11 } } }
      }
    }
  });

  // P3-REQ: Iron requirements vs actual intake (grouped bar)
  new Chart(document.getElementById('p3-req'), {
    type: 'bar',
    data: {
      labels: ['Daily requirement\n(mg/day)','Dietary intake\n1999 (mg/day)','Dietary intake\n2018 (mg/day)','Intake as % of\nrequirement (2018)'],
      datasets: [
        { label: 'Women (reproductive age)', data: [18, 13.1, 11.9, 66], backgroundColor:'rgba(244,114,182,0.75)', borderRadius:5 },
        { label: 'Men', data: [8, 16.8, 15.7, 196], backgroundColor:'rgba(56,189,248,0.65)', borderRadius:5 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { color: '#8fa3bf', boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          ...sharedTooltip,
          callbacks: {
            label: c => {
              const units = c.dataIndex === 3 ? '%' : ' mg';
              return ` ${c.dataset.label}: ${c.parsed.y.toFixed(0)}${units}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#4a6080', font: { size: 10 } } },
        y: { grid: { color: '#111c2e' }, ticks: { color: '#4a6080', font: { size: 11 } }, title: { display: true, text: 'Value (mg or %)', color: '#4a6080', font: { size: 11 } } }
      }
    }
  });
}
