# Updated Research Summary: Synthetic IDA Surveillance and Policy Tuning

Date: March 6, 2026

## 1) Purpose and scope

This summary updates the current anemia policy-builder analysis using the latest synthetic cohort artifacts in this repo, with emphasis on two goals:

1. Quantify what changes when thresholds are tunable (especially setpoint-drop thresholds and minimum hemoglobin measurement requirements).
2. Translate those quantitative shifts into practical implications for surveillance policy and public health operations.

This is a method and policy summary, not a causal or clinical effectiveness study. All results below are from synthetic data and should be interpreted as system-behavior evidence (how policy logic behaves), not population truth.

## 2) Data snapshot used for this update

Primary artifact set (female, ages 18-65):

- `data/synth_runs/1000000_1/cohort_summary_F_18_65.json`
- `data/synth_runs/1000000_1/patients_F_18_65.json` (local full file, 50,944 records)

Key cohort context:

- Patients requested from Synthea: 1,000,000
- Patients generated in this run: 171,000
- Filtered analytic cohort (F, 18-65): 50,944
- Hemoglobin observations: 122,093
- Patients with at least one Hb result: 50,944 (100% of filtered cohort)

Baseline burden estimates (cohort level):

- Lab-defined anemia (WHO threshold): 3,208 (6.30%)
- Coded anemia: 18,941 (37.18%)
- Diagnostic gap (lab anemia without coded anemia): 73 (0.143%)

Internal stability check versus the 5,000-request run (`5000_1`) suggests core distributional metrics are directionally consistent:

- Hb mean: 14.229 vs 14.205 g/dL
- Hb SD: 1.898 vs 1.932 g/dL
- Lab anemia prevalence: 6.21% vs 6.30%
- Coded anemia prevalence: 36.44% vs 37.18%

Interpretation: policy-behavior findings below are likely robust to moderate sample-size shifts in this synthetic framework.

## 3) Statistical takeaways for surveillance design

### 3.1 Coded vs lab-defined anemia are not interchangeable

Joint distribution in the 50,944-person cohort:

- Lab anemia and coded anemia: 3,135 (6.15%)
- Lab anemia only (diagnostic gap): 73 (0.143%)
- Coded anemia only: 15,806 (31.03%)
- Neither: 31,930 (62.68%)

Two notable asymmetries:

- Among lab-anemic patients, 97.72% already have coded anemia.
- Among coded-anemia patients, only 16.55% are currently lab-anemic by latest Hb.

Public health implication: coded prevalence captures a larger chronic/legacy diagnosis burden, while lab-defined prevalence reflects current physiologic status. They answer different surveillance questions and should not be conflated into one headline metric.

### 3.2 Measurement sufficiency strongly gates eligibility

Hb history sufficiency in cohort:

- At least 2 Hb readings: 43,604 (85.59%)
- At least 3 Hb readings: 10,066 (19.76%)

The policy setting `Require >=3 Hb measurements` is not a minor tweak; it is a major denominator control. This improves reliability for trajectory-based alerts but sharply reduces coverage.

### 3.3 Ferritin testing remains sparse at population level

Patient-level ferritin testing (>=1 ferritin test):

- Overall cohort: 850 / 50,944 (1.67%)
- Among lab-anemic: 79 / 3,208 (2.46%)
- Among diagnostic-gap subgroup: 17 / 73 (23.29%)

Implication: ferritin is currently low-frequency and should be treated as a secondary enrichment signal for targeted pathways, not a primary surveillance requirement.

## 4) Tunable-threshold findings (setpoint trigger)

The setpoint policy flags patients when latest Hb falls below each patient-specific Bayesian adaptive setpoint by a chosen threshold.

Below are flagged counts across threshold and gating choices:

| Setpoint drop threshold (g/dL) | Trigger only (all) | Trigger + `>=3 Hb` | Trigger + exclude coded | Trigger + exclude coded + `>=3 Hb` |
| --- | ---: | ---: | ---: | ---: |
| 0.5 | 16,663 (32.71%) | 3,362 (6.60%) | 9,955 (19.54%) | 503 (0.99%) |
| 1.0 | 13,503 (26.51%) | 2,811 (5.52%) | 7,863 (15.43%) | 378 (0.74%) |
| 1.5 | 10,659 (20.92%) | 2,340 (4.59%) | 6,023 (11.82%) | 290 (0.57%) |
| 2.0 | 8,151 (16.00%) | 1,897 (3.72%) | 4,385 (8.61%) | 199 (0.39%) |
| 2.5 | 6,068 (11.91%) | 1,567 (3.08%) | 3,041 (5.97%) | 120 (0.24%) |
| 3.0 | 4,192 (8.23%) | 1,199 (2.35%) | 1,937 (3.80%) | 66 (0.13%) |

Key signal-management insight:

- Threshold tuning from 0.5 to 3.0 g/dL cuts raw volume by 74.8% (16,663 to 4,192).
- Adding `>=3 Hb` and excluding coded anemia can reduce volume to a very narrow triage stream (down to 66 at threshold 3.0).

This demonstrates that threshold and eligibility controls are effective levers for matching alert volume to workforce capacity.

## 5) Broader surveillance and policy implications

### 5.1 Policy should be tiered, not binary

A single fixed case definition is operationally brittle. A better model is a tiered policy stack:

- Tier A (broad surveillance): lab-defined anemia and/or low-threshold setpoint drop.
- Tier B (targeted outreach): exclude already coded anemia and require `>=3 Hb`.
- Tier C (high-priority review): high setpoint threshold (for example >=2.0 g/dL) plus gap focus.

This structure allows one analytics framework to serve different public-health functions: monitoring burden, targeting high-risk under-recognition, and triaging scarce follow-up resources.

### 5.2 Tunable thresholds can become governance artifacts

The threshold itself is a policy object. Governance should define:

- Who can change thresholds.
- Review cadence (for example monthly volume/performance review).
- Required evidence to tighten or loosen sensitivity.

Without governance, threshold drift can create artificial trend changes that look epidemiologic but are actually configuration effects.

### 5.3 Denominator discipline matters for surveillance comparability

Rates are highly sensitive to inclusion logic (for example `>=3 Hb`). Therefore every dashboard export or surveillance memo should carry explicit denominator metadata:

- Cohort definition (age, sex, geography).
- Trigger logic and threshold.
- Measurement sufficiency requirement.
- Exclusion rules (for example coded anemia exclusion on/off).

This is necessary for fair year-to-year, site-to-site, and policy-to-policy comparisons.

### 5.4 Use coded and lab streams together

Given high coded prevalence and lower current lab anemia prevalence, a combined interpretation model is recommended:

- Coded stream for prevalence and historical burden.
- Lab stream for active physiology and near-term clinical relevance.
- Gap stream for potential under-recognition.

This avoids overreacting to any one stream and supports balanced policy decisions.

## 6) Recommended policy defaults for next phase

If the immediate objective is a manageable, clinically plausible surveillance queue in this synthetic system:

1. Keep `Require >=3 Hb measurements` enabled.
2. Use setpoint trigger with threshold 1.5-2.0 g/dL for operational review queues.
3. Keep a secondary lab-defined dashboard panel for population monitoring.
4. Keep diagnostic gap explicitly visible as a contextual metric even if not used as primary trigger.
5. Track two required process indicators each cycle:
   - flagged count and flagged percent,
   - percent already coded vs not coded.

If the objective shifts to high sensitivity screening, lower threshold and loosen Hb-count gating, but pre-commit to downstream capacity before deployment.

## 7) Limitations and caution

- Data are synthetic and generated under Synthea assumptions.
- `patients_generated` was 171,000 for this 1,000,000-request run, so this is not a fully completed million-patient simulation.
- Policy performance metrics here are volume and composition metrics, not outcomes validation metrics.
- False-positive and false-negative tradeoffs against real clinical endpoints remain unmeasured.

## 8) Bottom line

This update shows that policy-builder logic is highly tunable and operationally expressive:

- The same underlying data can produce broad surveillance streams or narrow high-priority queues depending on threshold and eligibility settings.
- `>=3 Hb` is a major reliability lever with major coverage cost.
- Setpoint thresholds provide a practical sensitivity-specificity dial for public-health implementation.
- Coded, lab-defined, and diagnostic-gap streams should be reported together to avoid biased interpretation.

Overall, the system is ready for policy prototyping workflows where explicit threshold governance and denominator transparency are first-class requirements.
