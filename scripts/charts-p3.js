// ============================================================
// PAGE 3 CHARTS
// ============================================================

// P3-MAIN: Women's US anemia trend with stagnation band
const p3Main = new Chart(document.getElementById('p3-main'), {
  type: 'line',
  data: {
    labels: [1999,2001,2003,2005,2007,2009,2011,2013,2015,2017,2019,2021],
    datasets: [
      { label: 'Women 15–49 (anemia %)', data: [15.2,14.8,14.5,14.2,13.9,13.8,13.9,14.0,14.1,14.3,14.4,14.6], borderColor:'#f472b6', backgroundColor: ctx => { const g = ctx.chart.ctx.createLinearGradient(0,0,0,260); g.addColorStop(0,'rgba(244,114,182,0.18)'); g.addColorStop(1,'rgba(244,114,182,0.01)'); return g; }, borderWidth:2.5, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:2, tension:0.35, fill:true },
      { label: 'Males 15–49 (anemia %)', data: [4.2,4.0,3.9,3.8,3.7,3.6,3.5,3.5,3.5,3.6,3.6,3.6], borderColor:'#38bdf8', backgroundColor:'transparent', borderWidth:2, pointRadius:3, pointBorderColor:'#080c14', pointBorderWidth:1, tension:0.35, fill:false, borderDash:[5,3] }
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
      y: { min: 0, max: 20, grid: { color: '#111c2e' }, ticks: { color: '#4a6080', callback: v => v + '%', font: { size: 11 } }, title: { display: true, text: 'Anemia prevalence (%)', color: '#4a6080', font: { size: 11 } } }
    }
  }
});

// Draw stagnation zone shading after render
// NOTE: this could use Chart.js annotation plugin instead
setTimeout(() => {
  const ch = p3Main;
  const ctx2 = ch.ctx;
  const xScale = ch.scales.x;
  const yScale = ch.scales.y;
  const x2009 = xScale.getPixelForValue(2009);
  const x2021 = xScale.getPixelForValue(2021);
  const y0 = yScale.getPixelForValue(20);
  const y1 = yScale.getPixelForValue(0);
  ctx2.save();
  ctx2.fillStyle = 'rgba(245,158,11,0.04)';
  ctx2.fillRect(x2009, y0, x2021 - x2009, y1 - y0);
  ctx2.strokeStyle = 'rgba(245,158,11,0.3)';
  ctx2.lineWidth = 1.5;
  ctx2.setLineDash([4,3]);
  ctx2.beginPath(); ctx2.moveTo(x2009, y0); ctx2.lineTo(x2009, y1); ctx2.stroke();
  ctx2.setLineDash([]);
  ctx2.fillStyle = 'rgba(245,158,11,0.55)';
  ctx2.font = '10px DM Mono, monospace';
  ctx2.fillText('← Stagnation zone', x2009 + 8, y0 + 16);
  ctx2.restore();
}, 200);

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
