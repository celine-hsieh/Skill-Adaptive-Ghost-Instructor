# Code Analysis — Reproducing Figures & Tables

This folder contains Python scripts to regenerate the paper’s plots and tables from the anonymized **/data** samples. Each script is **single‑purpose** and writes outputs to **../outputs**.

---

## Quick start

```bash
# 1) Create env (Python 3.9–3.11 recommended)
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Run a script (example)
python 04_plot_performance_static_vs_dynamic.py
# outputs -> ../outputs/04_plot_performance_static_vs_dynamic/
```

---

## Runability matrix

### ✅ Runnable (data included in this package)
- `03_plot_participant_distribution.py`
- `04_plot_performance_static_vs_dynamic.py`
- `05_plot_retention_scores_delta.py`
- `06_plot_interaction_experience_condition.py`
- `08_plot_individual_learning_slopes.py`
- `10_plot_NASA-TLX.py`
- `analyzeQuestionnaires.py`
- `make_hand_similarity_table.py`

### ❌ Not runnable in this bundle (data minimized / omitted)
- `07_plot_group_learning_curves.py`  
  Requires full `UserPerformanceLogs` (trial/block raw logs), only provided User1 as an example.
- `09_plot_block_switch_transfer.py`  
  Requires full `UserPerformanceLogs` for block-switch / transfer analysis, only provided User1 as an example.
- `analyzeHandSimilarity.py`  
  Requires `HandMotionClips/UserSample` (hand motion clips) for trajectory similarity, only provided User1 as an example.
- `performance_to_csv.py`  
  Requires `PianoKeyEvents/UserSample` (per-key JSON/CSV raw events), only provided User1 as an example.

---

## Directory layout

```
code-analysis/                                                    # this folder
├─ 03_plot_participant_distribution.py                  
├─ 04_plot_performance_static_vs_dynamic.py                
├─ 05_plot_retention_scores_delta.py
├─ 06_plot_interaction_experience_condition.py
├─ 07_plot_group_learning_curves.py
├─ 08_plot_individual_learning_slopes.py
├─ 09_plot_block_switch_transfer.py
├─ 10_plot_NASA-TLX.py
│
├─ analyzeHandSimilarity.py
├─ analyzeQuestionnaires.py
├─ make_hand_similarity_table.py
├─ performance_to_csv.py
├─ training_curve_analysis_personal.py
│
├─ requirements.txt
│
└─ README_code-analysis.md                       # this file

```

- **Inputs** (relative to this folder): `../data/` contains aggregated CSV/JSON exported from Unity (e.g., `UserPerformanceRecord/*.csv`, `HandCSV/*.csv`, `NASATLX/*.csv`).  
- **Outputs**: each script creates a subfolder under `../outputs/` with the same stem as the script (e.g., `../outputs/04_plot_performance_static_vs_dynamic/`).

---

## Dependencies

A minimal set is listed in `requirements.txt`:
```
pandas>=2.0
numpy>=1.24
matplotlib>=3.7
scipy>=1.10
statsmodels>=0.14
```

> If you use conda:
> ```bash
> conda create -n ghost-analysis python=3.10 -y
> conda activate ghost-analysis
> pip install -r requirements.txt
> ```

---

## Script index (what each file produces)

- **03_plot_participant_distribution.py**  
  Creates the **participant distribution** chart across Latin‑square orders and experience (S=Static, D=Dynamic; A/B melodies). Output: `03_plot_participant_distribution.png`.

- **04_plot_performance_static_vs_dynamic.py**  
  Bar/CI plot comparing **Static vs Dynamic** across **pitch accuracy, finger accuracy, timing accuracy, error rate**. Output: `04_plot_performance_static_vs_dynamic.png`.

- **05_plot_retention_scores_delta.py**  
  Δ‑retention scores (post‑test minus immediate) per condition. Output: `05_plot_retention_scores_delta.png`.

- **06_plot_interaction_experience_condition.py**  
  **Interaction plot** of condition (Static/Dynamic) × **piano experience** (experienced / non‑experienced). Output: `06_plot_interaction_experience_condition.png`.

- **07_plot_group_learning_curves.py**  [NOT-RUNNABLE]
  Group **learning curves** over trials/blocks (mean ± SEM), separated by condition. Output: `07_plot_group_learning_curves.png`.

- **08_plot_individual_learning_slopes.py**  
  Per‑participant **learning slopes** (trend lines) and a summary histogram. Output: `08_plot_individual_learning_slopes.png`.

- **09_plot_block_switch_transfer.py**  [NOT-RUNNABLE]
  Block‑switch / **transfer** effect visualization (e.g., A→B vs B→A). Output: `09_plot_block_switch_transfer.png`.

- **10_plot_NASA-TLX.py**  
  **NASA‑TLX** subscales bar plot with SEM and optionally paired stats. Output: `10_plot_NASA-TLX.png`.

- **analyzeHandSimilarity.py**   [NOT-RUNNABLE]
  Computes hand‑trajectory similarity metrics and produces a **summary table**. Output: `hand_similarity_table.csv` and optional figure.

- **analyzeQuestionnaires.py**  
  Aggregates questionnaire results, exports summaries.

- **make_hand_similarity_table.py**  
  Utility to format the similarity metrics into a paper‑ready table (CSV/LaTeX).

- **performance_to_csv.py**   [NOT-RUNNABLE]
  Parses Unity logs to generate an **analysis‑ready CSV** with per‑trial metrics used by the plots above.

- **training_curve_analysis_personal.py**  
  Helper for quick ad‑hoc inspection of an individual participant’s **training curve** (diagnostics/debug, not used in the paper).

