// ============================================================
// CITATIONS DATA
// Each key matches a data-cid attribute on a .cite element.
// Fields:
//   claim  — short version of the cited claim (shown in tooltip)
//   source — author, journal, year
//   url    — opened on click (empty string if no URL)
//   num    — auto-assigned sequential number (set by initCitations)
// ============================================================
const CITATIONS = {
  gbd2021_global: {
    claim: "Global anemia prevalence fell from 28.2% (1990) to 24.3% (2021), totaling 1.92 billion cases. Iron deficiency accounts for 66.2% of all anemia.",
    source: "Gardner et al., Lancet Haematology, 2023",
    url: "https://www.thelancet.com/journals/lanhae/article/PIIS2352-3026(23)00160-6/fulltext"
  },
  gbd2021_sex: {
    claim: "In 2021, 31.2% of women had anemia globally versus 17.5% of men.",
    source: "GBD 2021 Anaemia Collaborators, Lancet Haematology, 2023",
    url: "https://www.thelancet.com/journals/lanhae/article/PIIS2352-3026(23)00160-6/fulltext"
  },
  gbd2021_repro: {
    claim: "Among adults aged 15–49, anemia prevalence in women was 33.7% versus 11.3% in men.",
    source: "IHME Press Release, 2023 (GBD 2021 data)",
    url: "https://www.healthdata.org/news-events/newsroom/news-releases/lancet-new-study-reveals-global-anemia-cases-remain-persistently"
  },
  gbd2021_geography: {
    claim: "Western sub-Saharan Africa (47.4%), South Asia (35.7%), and Central sub-Saharan Africa (35.7%) had the highest anemia prevalence in 2021. Australasia (5.7%), Western Europe (6%), and North America (6.8%) had the lowest.",
    source: "IHME / GBD 2021 Anaemia Collaborators",
    url: "https://www.healthdata.org/news-events/newsroom/news-releases/lancet-new-study-reveals-global-anemia-cases-remain-persistently"
  },
  gbd2021_stagnation: {
    claim: "The decline in age-standardized prevalence among women of reproductive age stagnated after 2009, with a slight increase through 2021, primarily driven by rising mild anemia.",
    source: "Frontiers in Nutrition, GBD 2021 analysis, 2025",
    url: "https://www.frontiersin.org/journals/nutrition/articles/10.3389/fnut.2025.1588496/full"
  },
  us_dalyrise: {
    claim: "Anemia-related DALYs in the US increased 26% from 332,449 in 1990 to 418,855 in 2019.",
    source: "Shwarz, Frontiers in Public Health, 2025",
    url: "https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2025.1653222/full"
  },
  us_female75: {
    claim: "Female individuals account for nearly three-quarters of all US anemia DALYs. Dietary iron deficiency contributes more than half of total burden.",
    source: "Shwarz, Frontiers in Public Health, 2025",
    url: "https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2025.1653222/full"
  },
  nhanes_sex: {
    claim: "US anemia prevalence is 13.0% in females versus 5.5% in males (NHANES 2021–2023, age 2+).",
    source: "Williams et al., NCHS Data Brief No. 519, CDC, December 2024",
    url: "https://www.cdc.gov/nchs/products/databriefs/db519.htm"
  },
  nhanes_teen: {
    claim: "Female adolescents ages 12–19 have the highest US anemia prevalence at 17.4%, versus 0.9% in males of the same age group.",
    source: "Williams et al., NCHS Data Brief No. 519, CDC, December 2024",
    url: "https://www.cdc.gov/nchs/products/databriefs/db519.htm"
  },
  black_women: {
    claim: "Black non-Hispanic women face an anemia prevalence of 31.4% — the highest burden of any demographic group in the US, more than double the rate of non-Hispanic White women.",
    source: "Williams et al., NCHS Data Brief No. 519, CDC, December 2024",
    url: "https://www.cdc.gov/nchs/products/databriefs/db519.htm"
  },
  ida_increase: {
    claim: "IDA prevalence in pregnant US women rose from 6.63% (2015–16) to 9.9% (2021–23), with an increasing trend over the past decade. COVID-19 may have intensified vulnerabilities.",
    source: "ASH Blood, 2025 (NHANES analysis)",
    url: "https://ashpublications.org/blood/article/146/Supplement%201/4478/556301"
  },
  daly_3x: {
    claim: "In 2019, female individuals in the US accounted for 166,741 anemia DALYs versus 61,499 in males — nearly 3× more.",
    source: "Shwarz, Frontiers in Public Health, 2025",
    url: "https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2025.1653222/full"
  },
  state_burden: {
    claim: "At the state level, Mississippi, the District of Columbia, and Alabama have the highest anemia-related DALY burden in the US.",
    source: "Shwarz, Frontiers in Public Health, 2025",
    url: "https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2025.1653222/full"
  },
  black_women_detail: {
    claim: "Black non-Hispanic females have 31.4% anemia prevalence versus 10.8% in Black non-Hispanic males (NHANES 2021–2023).",
    source: "Williams et al., NCHS Data Brief No. 519, CDC, December 2024",
    url: "https://www.cdc.gov/nchs/products/databriefs/db519.htm"
  },
  iron_intake_drop: {
    claim: "Female adult dietary iron intake fell ~9.5% between 1999–2018. Beef consumption fell 15.3%, chicken rose 21.5%. 62.4% of US food items had lower iron in 2015 vs. 1999 databases.",
    source: "Sun & Weaver, Journal of Nutrition, 2021",
    url: "https://www.sciencedirect.com/science/article/pii/S0022316622002413"
  },
  hepcidin_obesity: {
    claim: "Hepcidin levels are elevated in obese individuals due to subclinical inflammation, reducing iron absorption and blunting iron fortification effects.",
    source: "McClung & Karl, Nutrition Reviews, 2009",
    url: "https://pubmed.ncbi.nlm.nih.gov/19178651/"
  },
  upf_trend: {
    claim: "Ultra-processed foods rose from 53.5% to 57% of US adult caloric intake 2001–2018. Minimally processed foods fell from 32.7% to 27.4%. Trend consistent across all subgroups except Hispanics.",
    source: "Juul et al., American Journal of Clinical Nutrition, 2021",
    url: "https://www.sciencedirect.com/science/article/pii/S0002916522001253"
  },
  ferroportin: {
    claim: "Hepcidin binds to ferroportin — the only known iron export channel — causing its degradation. Iron gets trapped inside cells and cannot enter circulation.",
    source: "Nemeth et al., Science, 2004 / McClung & Karl, Nutr Rev, 2009",
    url: "https://pubmed.ncbi.nlm.nih.gov/19178651/"
  },
  ascorbic_half: {
    claim: "In overweight and obese women, the enhancement of iron absorption by ascorbic acid is only half that seen in normal-weight women.",
    source: "Cepeda-Lopez et al., American Journal of Clinical Nutrition, 2015",
    url: ""
  },
  screening_gap: {
    claim: "The US Preventive Services Task Force does not recommend routine iron deficiency screening for non-pregnant women. CDC guidelines date from 1998.",
    source: "Williams et al., American Journal of Public Health, 2022",
    url: "https://ajph.aphapublications.org/doi/full/10.2105/AJPH.2022.306998"
  },
  obesity_ascorbic: {
    claim: "In overweight and obese women, dietary iron absorption is reduced and iron fortification is less effective than in normal-weight women.",
    source: "Cepeda-Lopez et al., American Journal of Clinical Nutrition, 2015",
    url: ""
  },
  why_women_harder: {
    claim: "Women of reproductive age need 18 mg/day of iron versus 8 mg/day for men. A 9.5% drop in dietary iron intake is negligible for men but tips millions of women into deficiency.",
    source: "NIH Office of Dietary Supplements; Sun & Weaver, J Nutr 2021",
    url: "https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/"
  },
  womens_threshold: {
    claim: "Dietary iron requirements: 18 mg/day for women of reproductive age, 8 mg/day for men, 27 mg/day during pregnancy.",
    source: "NIH Office of Dietary Supplements / Dietary Reference Intakes",
    url: "https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/"
  }
};

// ============================================================
// CITATION SYSTEM — initCitations()
// Assigns sequential numbers to .cite elements,
// sets up hover/click event delegation on document body.
// ============================================================
function initCitations() {
  const tooltip = document.getElementById('cite-tooltip');
  const claimEl = document.getElementById('cite-tooltip-claim');
  const sourceEl = document.getElementById('cite-tooltip-source');

  // Assign sequential citation numbers across all pages
  let num = 1;
  document.querySelectorAll('.cite').forEach(el => {
    const cid = el.getAttribute('data-cid');
    if (CITATIONS[cid]) {
      CITATIONS[cid]._num = CITATIONS[cid]._num || num++;
      el.setAttribute('data-cnum', CITATIONS[cid]._num);
    }
  });

  // Hover: show tooltip
  document.body.addEventListener('mouseover', e => {
    const cite = e.target.closest('.cite');
    if (!cite) return;
    const cid = cite.getAttribute('data-cid');
    const c = CITATIONS[cid];
    if (!c) return;

    claimEl.textContent = c.claim;
    sourceEl.textContent = c.source;
    tooltip.classList.add('visible');
    positionTooltip(e);
  });

  // Move tooltip with mouse
  document.body.addEventListener('mousemove', e => {
    if (tooltip.classList.contains('visible')) positionTooltip(e);
  });

  // Hide on mouseout
  document.body.addEventListener('mouseout', e => {
    if (e.target.closest('.cite') && !e.relatedTarget?.closest('.cite')) {
      tooltip.classList.remove('visible');
    }
  });

  // Click: open source URL
  document.body.addEventListener('click', e => {
    const cite = e.target.closest('.cite');
    if (!cite) return;
    const cid = cite.getAttribute('data-cid');
    const url = CITATIONS[cid]?.url;
    if (url) window.open(url, '_blank', 'noopener');
  });
}

// Positions tooltip above/below cursor, clamped to viewport
function positionTooltip(e) {
  const tooltip = document.getElementById('cite-tooltip');
  const pad = 14;
  const tw = tooltip.offsetWidth || 320;
  const th = tooltip.offsetHeight || 100;
  let x = e.clientX + pad;
  let y = e.clientY - th - pad;
  if (x + tw > window.innerWidth - pad) x = e.clientX - tw - pad;
  if (y < pad) y = e.clientY + pad;
  tooltip.style.left = x + 'px';
  tooltip.style.top  = y + 'px';
}
