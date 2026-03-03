// ============================================================
// PAGE 2 CHARTS
// ============================================================

// P2-TREND: US anemia prevalence by sex over time
new Chart(document.getElementById('p2-trend'), {
  type: 'line',
  data: {
    labels: [1999,2001,2003,2005,2007,2009,2011,2013,2015,2017,2021],
    datasets: [
      { label: 'Females (all ages)', data: [12.1,11.8,12.0,12.5,12.8,13.0,12.9,13.1,13.0,13.2,13.0], borderColor:'#f472b6', pointBackgroundColor:'#f472b6', borderWidth:2.5, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:2, tension:0.3, fill:false },
      { label: 'Males (all ages)', data: [5.0,4.8,4.9,5.1,5.2,5.3,5.3,5.4,5.4,5.5,5.5], borderColor:'#38bdf8', pointBackgroundColor:'#38bdf8', borderWidth:2.5, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:2, tension:0.3, fill:false },
      { label: 'Overall', data: [8.5,8.2,8.4,8.7,9.0,9.1,9.0,9.2,9.1,9.3,9.3], borderColor:'#a78bfa', pointBackgroundColor:'#a78bfa', borderWidth:2, pointRadius:3, pointBorderColor:'#080c14', pointBorderWidth:1, tension:0.3, fill:false, borderDash:[4,3] }
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
      y: { min: 0, max: 20, grid: { color: '#111c2e' }, ticks: { color: '#4a6080', callback: v => v + '%', font: { size: 11 } } }
    }
  }
});

// P2-DALYS: DALYs by sex over time (area)
new Chart(document.getElementById('p2-dalys'), {
  type: 'line',
  data: {
    labels: [1990,1995,2000,2005,2010,2015,2019],
    datasets: [
      { label: 'Female DALYs', data: [119,126,134,143,153,161,167], borderColor:'#f472b6', backgroundColor:'rgba(244,114,182,0.12)', borderWidth:2.5, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:2, tension:0.35, fill:true },
      { label: 'Male DALYs', data: [44,47,50,53,56,59,61], borderColor:'#38bdf8', backgroundColor:'rgba(56,189,248,0.07)', borderWidth:2.5, pointRadius:4, pointBorderColor:'#080c14', pointBorderWidth:2, tension:0.35, fill:true }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { position: 'top', labels: { color: '#8fa3bf', boxWidth: 12, font: { size: 11 } } },
      tooltip: { ...sharedTooltip, callbacks: { label: c => ` ${c.dataset.label}: ${c.parsed.y.toFixed(0)}k` } }
    },
    scales: {
      x: { grid: { color: '#111c2e' }, ticks: { color: '#4a6080', font: { size: 11 } } },
      y: { grid: { color: '#111c2e' }, ticks: { color: '#4a6080', callback: v => v + 'k', font: { size: 11 } } }
    }
  }
});

// P2-CAUSE: DALYs by cause (doughnut)
new Chart(document.getElementById('p2-cause'), {
  type: 'doughnut',
  data: {
    labels: ['Dietary Iron Deficiency','Gynecological / Obstetric','Chronic Kidney Disease','Hemoglobinopathies','Digestive / GI','Other'],
    datasets: [{
      data: [54,16,10,8,6,6],
      backgroundColor: ['#f472b6','#fb923c','#38bdf8','#a78bfa','#34d399','#475569'],
      borderColor: '#0e1422', borderWidth: 3, hoverOffset: 6
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: 'right', labels: { color: '#8fa3bf', boxWidth: 10, font: { size: 10 }, padding: 8 } },
      tooltip: { ...sharedTooltip, callbacks: { label: c => ` ${c.label}: ${c.parsed}%` } }
    },
    cutout: '62%'
  }
});

// P2-AGE: anemia by age group and sex (grouped bar)
new Chart(document.getElementById('p2-age'), {
  type: 'bar',
  data: {
    labels: ['Ages 2–11','Ages 12–19','Ages 20–59','Ages 60+'],
    datasets: [
      { label: 'Female', data: [5.7,17.4,14.0,12.4], backgroundColor:'rgba(244,114,182,0.75)', borderRadius:5 },
      { label: 'Male',   data: [3.9, 0.9, 3.9,12.8], backgroundColor:'rgba(56,189,248,0.65)',  borderRadius:5 }
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
      x: { grid: { display: false }, ticks: { color: '#4a6080', font: { size: 11 } } },
      y: { grid: { color: '#111c2e' }, ticks: { color: '#4a6080', callback: v => v + '%', font: { size: 11 } } }
    }
  }
});

// P2-RACE: anemia by race/ethnicity and sex (grouped bar)
new Chart(document.getElementById('p2-race'), {
  type: 'bar',
  data: {
    labels: ['Black non-Hispanic','Hispanic / Latino','Other / Multiracial','White non-Hispanic','Asian'],
    datasets: [
      { label: 'Female', data: [31.4,14.2,13.5,12.9,11.8], backgroundColor:'rgba(244,114,182,0.75)', borderRadius:5 },
      { label: 'Male',   data: [10.8, 5.2, 5.0, 4.3, 4.1], backgroundColor:'rgba(56,189,248,0.65)',  borderRadius:5 }
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
      x: { grid: { display: false }, ticks: { color: '#4a6080', font: { size: 10 } } },
      y: { grid: { color: '#111c2e' }, ticks: { color: '#4a6080', callback: v => v + '%', font: { size: 11 } } }
    }
  }
});
