# -*- coding: utf-8 -*-
# Combined NASA‑TLX analysis + plotting (subscales‑only)
# (Merged and simplified from analyzeNASA-TLX.py and plot_NASA-TLX.py)
# Dependencies: pandas, numpy, scipy, openpyxl, matplotlib
#
# This script first runs the analysis to produce data outputs (CSV/JSON) identical
# to the originals, and then generates ONLY the subscales+overall bar chart:
#   ./outputs/10_plot_NASA-TLX.png
#
# Data outputs (same as originals):
#   - ./outputs/nasa_tlx_paired_tests.csv
#   - ./outputs/nasa_tlx_long.csv
#   - ./outputs/nasa_tlx_summary_by_condition.csv
#   - ./outputs/nasa_tlx_detected_columns.json

import os, re, json
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt

# ========= 1) Paths & parameters (same behavior as the original analysis script) =========
PATH = r"./data/Surveys/questionnaires_aggregated.xlsx"
OUT_DIR = os.path.dirname(PATH)
ID_COL = None   # If you have a specific participant ID column (e.g., "ResponseId"), set it here; otherwise use 1..N_USERS
N_USERS = 30    # Use the first 30 records (corresponding to rows 4–33 in the source file)

# ========= Read the top 3 rows to capture ImportId (row 1) and question text (row 3) =========
meta = pd.read_excel(PATH, header=None, nrows=3)
import_ids = meta.iloc[0].astype(str).tolist()    # Row 1: ImportId (used as column names)
qtexts      = meta.iloc[2].astype(str).tolist()   # Row 3: question text
col_to_qtext = dict(zip(import_ids, qtexts))

# ========= Load data (row 1 as header; skip rows 2–3; keep the first 30 participants) =========
df_all = pd.read_excel(PATH, header=0, skiprows=[1, 2])
df = df_all.iloc[:N_USERS].copy()

# Attempt to convert TLX columns to numeric (non-numerics -> NaN), where we can match them
for c in df.columns:
    if c in col_to_qtext:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# ========= Map question text → TLX subscale =========
def which_subscale(q: str):
    ql = q.lower().strip()
    if ql.startswith("how mentally demanding"):
        return "Mental"
    if ql.startswith("how physically demanding"):
        return "Physical"
    if ql.startswith("how hurried or rushed"):
        return "Temporal"
    if ql.startswith("how hard did you have to work"):
        return "Effort"
    if ql.startswith("how irritated, stressed, or annoyed"):
        return "Frustration"
    if ql.startswith("how successful were you in accomplishing the task"):
        return "Performance"
    return None

REV_RE = re.compile(r"\(reverse\)", re.IGNORECASE)

def get_cols_for_condition(prefix: str):
    """Return the six subscale columns and the Performance(reverse) column for a condition.
       prefix: 'D' (Dynamic) or 'S' (Static).
       The sheet uses tokens like 'NASA-TLX_D4' and 'NASA-TLX_S7'."""
    sub_map = {"Mental":None,"Physical":None,"Temporal":None,"Performance":None,"Effort":None,"Frustration":None}
    perf_rev_col = None
    for i in range(1, 8):
        token = f"NASA-TLX_{prefix}{i}"   # e.g., "NASA-TLX_D4"
        col = next((c for c in df.columns.astype(str) if token in c), None)
        if not col:
            continue
        q = col_to_qtext.get(col, "")
        sub = which_subscale(q)
        if sub == "Performance" and REV_RE.search(q):
            perf_rev_col = col
        elif sub in sub_map and sub_map[sub] is None:
            sub_map[sub] = col
    return sub_map, perf_rev_col

map_dyn, dyn_perf_rev = get_cols_for_condition("D")
map_sta, sta_perf_rev = get_cols_for_condition("S")

# ========= Build long-format table (Participant × Condition) and compute RTLX =========
def participant_series(frame: pd.DataFrame):
    if ID_COL and ID_COL in frame.columns:
        return frame[ID_COL].astype(str).reset_index(drop=True)
    return pd.Series(range(1, len(frame)+1), name="Participant")

pid = participant_series(df)
rows = []

for r_idx, r in df.iterrows():
    for cond, cmap, perf_rev_col in [
        ("Dynamic", map_dyn, dyn_perf_rev),
        ("Static",  map_sta, sta_perf_rev),
    ]:
        rec = {"Participant": pid.iloc[r_idx], "Condition": cond}
        # Copy subscales (except performance for now)
        for s in ["Mental","Physical","Temporal","Effort","Frustration"]:
            col = cmap.get(s)
            rec[s] = r[col] if (col in df.columns) else np.nan

        # Handle Performance (reverse if reverse-worded column exists)
        base_perf_col = cmap.get("Performance")
        if perf_rev_col and perf_rev_col in df.columns:
            perf_val = r[perf_rev_col]
        elif base_perf_col and base_perf_col in df.columns:
            perf_val = 100 - r[base_perf_col] if pd.notnull(r[base_perf_col]) else np.nan
        else:
            perf_val = np.nan
        rec["Performance"] = perf_val

        subs = [rec.get(s, np.nan) for s in ["Mental","Physical","Temporal","Performance","Effort","Frustration"]]
        rec["RTLX"] = float(np.nanmean(subs)) if np.sum(~pd.isna(subs)) > 0 else np.nan
        rows.append(rec)

tlx_long = pd.DataFrame(rows)

# ========= Paired t-tests + 95% CI + Holm correction =========
def paired_test(df_long: pd.DataFrame, measure: str):
    wide = df_long.pivot(index="Participant", columns="Condition", values=measure).dropna()
    n = wide.shape[0]
    if n < 2:
        return dict(measure=measure, n=n, mean_dyn=np.nan, sd_dyn=np.nan,
                    mean_sta=np.nan, sd_sta=np.nan, mean_diff=np.nan,
                    t=np.nan, p=np.nan, dz=np.nan, ci95_low=np.nan, ci95_high=np.nan)
    a = wide["Dynamic"].to_numpy(); b = wide["Static"].to_numpy()
    diff = a - b
    t, p = stats.ttest_rel(a, b, nan_policy="omit")
    md = float(np.nanmean(diff))
    sd = float(np.nanstd(diff, ddof=1))
    dz = md / sd if sd > 0 else np.nan
    se = sd / np.sqrt(n)
    tcrit = stats.t.ppf(0.975, df=n-1)
    ci_low, ci_high = md - tcrit*se, md + tcrit*se
    return dict(measure=measure, n=int(n),
                mean_dyn=float(np.nanmean(a)), sd_dyn=float(np.nanstd(a, ddof=1)),
                mean_sta=float(np.nanmean(b)), sd_sta=float(np.nanstd(b, ddof=1)),
                mean_diff=md, t=float(t), p=float(p), dz=float(dz),
                ci95_low=float(ci_low), ci95_high=float(ci_high))

MEASURES = ["RTLX","Mental","Physical","Temporal","Performance","Effort","Frustration"]
tests_df = pd.DataFrame([paired_test(tlx_long, m) for m in MEASURES])

def holm_adjust(pvals):
    m = len(pvals)
    order = np.argsort(pvals)
    p_sorted = np.array(pvals, dtype=float)[order]
    adj = np.minimum(1, (m - np.arange(m)) * p_sorted)
    # Enforce monotonicity
    for i in range(1, m):
        adj[i] = max(adj[i], adj[i-1])
    out = np.empty(m)
    out[order] = adj
    return out

tests_df["p_holm"] = holm_adjust(tests_df["p"].fillna(1.0).values)
tests_df["sig"] = tests_df["p_holm"].apply(lambda x: "***" if x < 0.001 else ("**" if x < 0.01 else ("*" if x < 0.05 else "")))

# ========= Write outputs (same as original analysis script) =========
os.makedirs(OUT_DIR, exist_ok=True)
tests_path = os.path.join(OUT_DIR, "nasa_tlx_paired_tests.csv")
long_path  = os.path.join(OUT_DIR, "nasa_tlx_long.csv")
summary_path = os.path.join(OUT_DIR, "nasa_tlx_summary_by_condition.csv")
info_path = os.path.join(OUT_DIR, "nasa_tlx_detected_columns.json")

tests_df.to_csv(tests_path, index=False)
tlx_long.to_csv(long_path, index=False)
(
    tlx_long.groupby("Condition")[MEASURES]
            .agg(["mean","std","count"])
            .to_csv(summary_path)
)

found_info = {
    "Dynamic_map": map_dyn, "Static_map": map_sta,
    "Dynamic_PerfReverseCol": dyn_perf_rev, "Static_PerfReverseCol": sta_perf_rev,
    "n_rows_used": int(df.shape[0]), "note": "Only rows 4–33 (30 users) were analyzed."
}
with open(info_path, "w", encoding="utf-8") as f:
    json.dump(found_info, f, ensure_ascii=False, indent=2)

print("== Analysis complete ==")
print("Paired tests :", tests_path)
print("Long data    :", long_path)
print("Summary      :", summary_path)
print("Detected cols:", info_path)

# ========= Plotting (ONLY the subscales + overall grouped bar chart) =========

# Input path points to the freshly saved long CSV above (fallback to default if needed)
IN_PATH  = long_path if os.path.exists(long_path) else r"./outputs/nasa_tlx_long.csv"
PLOTS_DIR  = r"./outputs"
os.makedirs(PLOTS_DIR, exist_ok=True)

# Load
df_plot = pd.read_csv(IN_PATH)

# Ensure required columns exist
NEEDED = {"Participant","Condition","RTLX","Mental","Physical","Temporal","Performance","Effort","Frustration"}
missing = NEEDED - set(df_plot.columns)
if missing:
    raise ValueError(f"Missing columns in CSV: {missing}")

# Utility: 95% CI of the mean
def mean_ci95(series):
    arr = series.dropna().to_numpy()
    n = len(arr)
    if n == 0:
        return np.nan, np.nan
    mean = arr.mean()
    se = arr.std(ddof=1) / np.sqrt(n) if n > 1 else 0.0
    # Use z≈1.96; switch to t critical if you prefer
    ci = 1.96 * se
    return mean, ci

# Measures
measures = ["Mental","Physical","Temporal","Performance","Effort","Frustration","RTLX"]
labels   = ["Mental","Physical","Temporal","Performance","Effort","Frustration","Overall"]

means_sta, cis_sta = [], []
means_dyn, cis_dyn = [], []

for m in measures:
    pv = df_plot.pivot(index="Participant", columns="Condition", values=m).dropna()
    m_sta, ci_sta = mean_ci95(pv["Static"])
    m_dyn, ci_dy  = mean_ci95(pv["Dynamic"])
    means_sta.append(m_sta); cis_sta.append(ci_sta)
    means_dyn.append(m_dyn); cis_dyn.append(ci_dy)

x = np.arange(len(measures))
width = 0.35  # bar width

plt.figure(figsize=(9, 5), dpi=200)
# Do not set explicit colors or styles (keeps defaults)
plt.bar(x - width/2, means_sta, width, yerr=cis_sta, capsize=4, label="Static")
plt.bar(x + width/2, means_dyn, width, yerr=cis_dyn, capsize=4, label="Dynamic")
plt.xticks(x, labels, rotation=20, ha="right")
plt.ylabel("NASA‑TLX (0–100, lower is better)")
plt.ylim(0, 100)
plt.yticks(np.arange(0, 101, 20))
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(PLOTS_DIR, "10_plot_NASA-TLX.png"), bbox_inches="tight")
plt.close()

print("Done. Figure saved to:", os.path.abspath(PLOTS_DIR))
