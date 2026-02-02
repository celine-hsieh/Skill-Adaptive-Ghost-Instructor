# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path

# <<< Change the path to your CSV >>>
CSV_PATH = Path("./outputs/user_hand_similarity_table.csv")  # 例：Index, Static Imm, Dynamic, Static Ret, Dynamic Retention

# Read file & normalize column names
df = pd.read_csv(CSV_PATH)
cols = {c.lower().strip(): c for c in df.columns}

def pick(*cands):
    for k in cands:
        if k in cols: return cols[k]
    raise KeyError(f"Column not found: {cands}")

col_idx  = pick("index")
col_si   = pick("static imm", "static (imm.)", "static immediate")
col_di   = pick("dynamic", "dynamic imm", "dynamic (imm.)", "dynamic immediate")
col_sr   = pick("static ret", "static retention")
col_dr   = pick("dynamic ret", "dynamic retention")

X = df[[col_idx, col_si, col_di, col_sr, col_dr]].copy()

# Convert to float
for c in [col_si, col_di, col_sr, col_dr]:
    X[c] = pd.to_numeric(X[c], errors="coerce")

# If looks like percentage (max value > 1.2), automatically convert to 0–1
maxval = np.nanmax(pd.concat([X[col_si], X[col_di], X[col_sr], X[col_dr]]).values)
scale_note = ""
if maxval is not None and np.isfinite(maxval) and maxval > 1.2:
    for c in [col_si, col_di, col_sr, col_dr]:
        X[c] = X[c] / 100.0
    scale_note = "(automatically converted from percentage by dividing by 100)"

# Tool: Paired t and Cohen's d_z
def paired_stats(a, b):
    m = a.notna() & b.notna()
    a, b = a[m].astype(float), b[m].astype(float)
    n = len(a)
    if n < 2:
        return dict(n_pairs=n, mean_diff=np.nan, ci95_lo=np.nan, ci95_hi=np.nan,
                    dz=np.nan, t=np.nan, p=np.nan)
    dif = (b - a)  # Here defined as Dynamic − Static (b is Dynamic)
    mean_diff = float(dif.mean())
    dz = float(mean_diff / (dif.std(ddof=1) + 1e-12))
    # 95% CI use bootstrap (more robust)
    rng = np.random.default_rng(0)
    boots = rng.choice(dif, size=(20000, n), replace=True).mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    t, p = stats.ttest_rel(b, a)  # Note: Dynamic vs Static
    return dict(n_pairs=n, mean_diff=mean_diff, ci95_lo=float(lo), ci95_hi=float(hi),
                dz=dz, t=float(t), p=float(p))

# Calculate Immediate and Retention
res_im = paired_stats(X[col_si], X[col_di])
res_re = paired_stats(X[col_sr], X[col_dr])

# Overall average (average of four conditions)
overall = {
    "Static Immediate": float(X[col_si].mean()),
    "Dynamic Immediate": float(X[col_di].mean()),
    "Static Retention": float(X[col_sr].mean()),
    "Dynamic Retention": float(X[col_dr].mean()),
}

# Make the table you are familiar with (note: mean_diff>0 means Dynamic is better)
summary_rows = [
    ["Overall (μ)" + (" " + scale_note if scale_note else ""),
     f"{overall['Static Immediate']:.3f}",
     f"{overall['Dynamic Immediate']:.3f}",
     f"{overall['Static Retention']:.3f}",
     f"{overall['Dynamic Retention']:.3f}"],
    ["t-Test (p) — Immediate", "-", f"p={res_im['p']:.6f}", "-", ""],
    ["Cohen's d_z — Immediate", "-", f"d={res_im['dz']:.3f}", "-", ""],
    ["t-Test (p) — Retention", "-", "", "-", f"p={res_re['p']:.6f}"],
    ["Cohen's d_z — Retention", "-", "", "-", f"d={res_re['dz']:.3f}"],
]

summary = pd.DataFrame(summary_rows,
    columns=["Index / Stat", "Static Imm", "Dynamic Imm", "Static Ret", "Dynamic Ret"])

# Give a simple statistical summary table
compact = pd.DataFrame([
    ["Immediate (Dyn−Stat)", res_im['n_pairs'], res_im['mean_diff'], res_im['ci95_lo'], res_im['ci95_hi'], res_im['dz'], res_im['p']],
    ["Retention (Dyn−Stat)", res_re['n_pairs'], res_re['mean_diff'], res_re['ci95_lo'], res_re['ci95_hi'], res_re['dz'], res_re['p']],
], columns=["contrast","n_pairs","mean_diff","ci95_lo","ci95_hi","dz","p"])

# Output
out_dir = CSV_PATH.parent
summary.to_csv(out_dir / "overall_ttest_cohen_table.csv", index=False, encoding="utf-8-sig")
compact.to_csv(out_dir / "overall_ttest_cohen_compact.csv", index=False, encoding="utf-8-sig")

print("== Overall means ==")
print(summary.to_string(index=False))
print("\n== Paired stats (Dynamic − Static) ==")
print(compact.to_string(index=False))
