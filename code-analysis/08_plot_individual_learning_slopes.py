# -*- coding: utf-8 -*-
"""
Plot per-user learning slopes with colors for first training order
(Dynamic-first vs Static-first).

Note: Latin-square Excel is parsed with header=2 (skip first two rows).
"""
import argparse
import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import ttest_rel, t as t_dist

# ------------------ CLI ------------------
parser = argparse.ArgumentParser()
parser.add_argument("--slopes", type=str,
                    default="./outputs/slopes_errorRate.csv",
                    help="Path to slopes CSV (columns: user, condition, slope)")
parser.add_argument("--latin", type=str,
                    default="./data/Surveys/questionnaires_aggregated.xlsx",
                    help="Path to Excel with Latin-square / order assignment")
parser.add_argument("--outdir", type=str,
                    default="./outputs",
                    help="Output directory")
parser.add_argument("--exclude_user", type=int, nargs="*", default=[],
                    help="User IDs to exclude (default: none)")
parser.add_argument("--match_old", action="store_true",
                    help="Match old style jitter (randomly between -0.08 and 0.08)")
args = parser.parse_args()

IN_CSV = args.slopes
XLSX_PATH = args.latin
OUT_DIR = args.outdir
EXCLUDE = set(args.exclude_user)
os.makedirs(OUT_DIR, exist_ok=True)

FIG_W, FIG_H = 3.8, 6.0
BOX_ASPECT = FIG_H / FIG_W
ORDER = ["Static", "Dynamic"]  # x-axis order for paired plot
GROUP_COLORS = {"Dynamic": "#1F77B4", "Static": "#FF7F0E"}  # Dynamic-first (blue), Static-first (orange)

plt.rcParams.update({
    "axes.titlesize": 18,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 14,
    "legend.title_fontsize": 16
})

# ------------------ Helpers ------------------
def mean_se_ci(series, alpha=0.05):
    arr = pd.Series(series).dropna().to_numpy()
    n = len(arr)
    m = np.mean(arr) if n else np.nan
    se = np.std(arr, ddof=1) / np.sqrt(n) if n > 1 else np.nan
    tcrit = t_dist.ppf(1 - alpha/2, df=n-1) if n > 1 else np.nan
    lo = m - tcrit * se if n > 1 else np.nan
    hi = m + tcrit * se if n > 1 else np.nan
    return m, se, lo, hi, n

def find_latin_square_sheet(xlsx_path):
    xl = pd.ExcelFile(xlsx_path)
    # Prefer sheets with these keywords
    targets = ["latin", "assignment", "order", "design", "sequence"]
    for s in xl.sheet_names:
        s_low = s.lower()
        if any(k in s_low for k in targets):
            return s, xl
    # fallback to first sheet
    return xl.sheet_names[0], xl

def derive_first_condition(df):
    """
    Infer per-user first condition (Dynamic/Static) from a DataFrame parsed
    from the Latin-square sheet. Returns DataFrame columns: user, first_cond.
    """
    # Find a likely user-id column
    lower = {c.lower(): c for c in df.columns}
    user_col = None
    for key in ["user", "participant", "id", "pid", "subject", "responseid", "response id"]:
        if key in lower:
            user_col = lower[key]
            break
    if user_col is None:
        # synthesize an index if no explicit id column
        df = df.copy()
        df["__row_idx__"] = np.arange(1, len(df) + 1)
        user_col = "__row_idx__"

    # Find an order/sequence column
    order_col = None
    for key in ["order", "sequence", "design", "block", "latin", "assignment"]:
        matches = [c for c in df.columns if key in c.lower()]
        if matches:
            order_col = matches[0]
            break
    if order_col is None:
        # any column containing our tokens
        for c in df.columns:
            ser = df[c].astype(str).str.lower()
            if ser.str.contains("sa/db|da/sb|sb/da|db/sa|static|dynamic", regex=True).any():
                order_col = c
                break
    if order_col is None:
        raise ValueError("Could not find a column with order/sequence info in the Latin Square sheet.")

    out_rows = []
    for _, r in df[[user_col, order_col]].dropna(how="all").iterrows():
        uid_raw = str(r[user_col])
        m = re.search(r"(\d+)", uid_raw)
        uid = int(m.group(1)) if m else None

        order_raw = str(r[order_col]).strip()
        low = order_raw.lower()
        low_norm = re.sub(r"[\s\-]+", "", low)  # remove spaces and hyphens, support "SA / DB" etc.

        first = None
        # Patterns like "SA/DB", "DA/SB", etc., allowing spaces/hyphens
        if any(tok in low_norm for tok in ["sa/db", "da/sb", "sb/da", "db/sa"]):
            first = "Dynamic" if low_norm.startswith("d") else "Static"
        # Words like "Dynamic first" / "Static first"
        if first is None:
            if "dynamic" in low:
                first = "Dynamic"
            elif "static" in low:
                first = "Static"

        if uid is not None and first in ("Dynamic", "Static"):
            out_rows.append({"user": uid, "first_cond": first})

    if not out_rows:
        raise ValueError("Parsed the sheet but could not infer any (user, first_cond) pairs.")
    return pd.DataFrame(out_rows).drop_duplicates(subset=["user"])

def norm_cond(x):
    s = str(x).strip().lower()
    if s in {"s", "static", "stat", "sta", "0"}:
        return "Static"
    if s in {"d", "dynamic", "dyn", "dy", "1"}:
        return "Dynamic"
    return np.nan


# ------------------ Load data ------------------
if not os.path.exists(IN_CSV):
    raise FileNotFoundError(f"Slopes CSV not found: {IN_CSV}")
slopes = pd.read_csv(IN_CSV)

# clean cols
slopes.columns = [c.strip() for c in slopes.columns]
need = {"user", "condition", "slope"}
if not need.issubset(set(slopes.columns)):
    raise ValueError(f"CSV must contain columns {need}, got {slopes.columns.tolist()}")

# --- align ID: slopes user31 is actually Excel User10 ---
ID_ALIASES = {31: 10}
slopes["user"] = slopes["user"].replace(ID_ALIASES).astype(int)

# exclude users if needed
if EXCLUDE:
    slopes = slopes[~slopes["user"].isin(EXCLUDE)]

# --- normalize condition ---
slopes["condition"] = slopes["condition"].apply(norm_cond)
print("Unique condition labels after normalization:",
      sorted(slopes["condition"].dropna().unique()))

# --- aggregate to user x condition (first don't drop, see who's missing)---
agg_raw = (
    slopes.groupby(["user", "condition"])["slope"]
    .mean()
    .reset_index()
    .pivot(index="user", columns="condition", values="slope")
)

# debug: which users are missing columns (missing Static or Dynamic)
if not {"Static", "Dynamic"}.issubset(set(agg_raw.columns)):
    for miss in {"Static", "Dynamic"} - set(agg_raw.columns):
        agg_raw[miss] = np.nan
missing_either = agg_raw[["Static", "Dynamic"]].isna().any(axis=1)
if missing_either.any():
    print("Users missing one condition (will be dropped):",
          sorted(agg_raw.index[missing_either].astype(int).tolist()))

# here we reindex + dropna
agg = agg_raw.reindex(columns=ORDER).dropna()

# ------------------ Latin-square mapping (skip first two rows) ------------------
if not os.path.exists(XLSX_PATH):
    raise FileNotFoundError(f"Latin-square Excel not found: {XLSX_PATH}")
sheet_name, xl = find_latin_square_sheet(XLSX_PATH)

# if exact name exists, use it, otherwise use find_latin_square_sheet found
if "Latin Square Assignment" in xl.sheet_names:
    sheet_name = "Latin Square Assignment"

# directly skip first two rows and read (3rd row is header)
latin_df = xl.parse(sheet_name, header=2)  # <-- key modification: header=2
print(f"Parsing Latin-square sheet '{sheet_name}' with header=2 (skip first two rows).")

map_df = derive_first_condition(latin_df)
map_df["first_cond"] = map_df["first_cond"].apply(norm_cond)

# merge mapping
agg2 = agg.copy().merge(map_df, left_index=True, right_on="user", how="left")

# debug: which users are missing first_cond in Latin square
no_first = agg2["first_cond"].isna()
if no_first.any():
    print("Users missing first_cond in Latin-square mapping (will be dropped):",
          sorted(agg2.loc[no_first, "user"].astype(int).tolist()))

agg2 = agg2.dropna(subset=["first_cond"])

# ------------------ Save per-user summary ------------------
summary = agg2[["user", "Static", "Dynamic", "first_cond"]].rename(
    columns={"Static": "slope_Static", "Dynamic": "slope_Dynamic"}
)
summary["delta"] = summary["slope_Dynamic"] - summary["slope_Static"]
summary_path = os.path.join(OUT_DIR, "per_user_slope_summary_with_firstcond.csv")
# summary.to_csv(summary_path, index=False)

# ------------------ Plot 1: paired lines colored by first order ------------------
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), constrained_layout=True)
ax.set_box_aspect(BOX_ASPECT)

for _, r in agg2.iterrows():
    color = GROUP_COLORS.get(r["first_cond"], "C2")
    ax.plot([0, 1], [r["Static"], r["Dynamic"]],
            marker="o", linewidth=1.2, alpha=0.5, color=color)

# overall group means ± SE (white squares)
for i, cond in enumerate(ORDER):
    vals = agg2[cond].dropna()
    m = np.mean(vals)
    se = np.std(vals, ddof=1) / np.sqrt(len(vals))
    ax.errorbar(i, m, yerr=se, fmt="s", mfc="white", mec="black",
                ecolor="black", capsize=4, linewidth=1.2, zorder=3)

ax.set_xticks([0, 1], ORDER)
ax.set_ylabel("Learning slope")

legend_elems = [
    Line2D([0], [0], color=GROUP_COLORS["Dynamic"], lw=2, marker="o", label="Dynamic-first"),
    Line2D([0], [0], color=GROUP_COLORS["Static"], lw=2, marker="o", label="Static-first"),
]
fig.legend(handles=legend_elems,
           loc="upper center", bbox_to_anchor=(0.5, 1.02),
           ncol=2, frameon=False)

paired_plot_path = os.path.join(OUT_DIR, "08_a_Individual learning slopes.png")
plt.tight_layout()
plt.subplots_adjust(top=0.88)
plt.savefig(paired_plot_path, dpi=300, bbox_inches="tight")
plt.close()

# ------------------ Plot 2: delta (Dynamic − Static), match the OLD script's scatter ------------------
# 1) use the same way as the old script to rebuild agg_base (same user, same aggregation)
agg_base = (
    slopes.groupby(["user", "condition"])["slope"]
    .mean()
    .reset_index()
    .pivot(index="user", columns="condition", values="slope")
    .reindex(columns=ORDER)
    .dropna()
    .sort_index()  # make user order stable, align with old script pivot default sort
)

# 2) make our first_cond color info align with the same order (only affects color, not y value)
agg2_aligned = (
    agg2.set_index("user")
        .reindex(agg_base.index)   # align first_cond to the same user order as the old script
        .reset_index()
)

delta = agg_base["Dynamic"] - agg_base["Static"]

fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), constrained_layout=False)
ax.set_box_aspect(BOX_ASPECT)
    
# 3) the same jitter as the old script (no seed; use global np.random.rand; amplitude ±0.04)
jitter = (np.random.rand(len(delta)) - 0.5) * 0.08

# 4) plot points: y = Δslope; x = jitter (color still use first_cond)
for xj, (_, r) in zip(jitter, agg2_aligned.iterrows()):
    color = GROUP_COLORS.get(r["first_cond"], "C2")
    ax.scatter(xj, r["Dynamic"] - r["Static"], s=30, alpha=0.8, color=color, clip_on=True)

# 5) group mean ± SE (white squares) - align with old script's position and style
m, se = delta.mean(), delta.std(ddof=1) / np.sqrt(len(delta))
ax.errorbar(0.18, m, yerr=se, fmt="s", mfc="white", mec="black",
            ecolor="black", capsize=4, linewidth=1.2, zorder=3, clip_on=True)

# 6) reference line (color/style same as old script)
for y in [0, 0.01, -0.01]:
    ax.axhline(y=y, color="gray", linestyle="--", linewidth=1, alpha=0.6, clip_on=True)

ax.set_xlim(-0.3, 0.35)
ax.set_xticks([])
ax.set_ylabel("Δ slope (Dynamic − Static)")

# legend
n_dyn = (agg2_aligned["first_cond"] == "Dynamic").sum()
n_sta = (agg2_aligned["first_cond"] == "Static").sum()
legend_elems = [
    Line2D([0], [0], color=GROUP_COLORS["Dynamic"], lw=0, marker="o", label=f"Dynamic-first (n={n_dyn})"),
    Line2D([0], [0], color=GROUP_COLORS["Static"],  lw=0, marker="o", label=f"Static-first (n={n_sta})"),
]
fig.legend(handles=legend_elems,
           loc="upper center", bbox_to_anchor=(0.5, 1.02),
           ncol=2, frameon=False)

delta_plot_path = os.path.join(OUT_DIR, "08_b_Per-participant difference.png")
plt.tight_layout()
plt.subplots_adjust(top=0.88)
plt.savefig(delta_plot_path, dpi=300, bbox_inches="tight")
plt.close()

# ------------------ Stats summary CSV ------------------
rows = []
for cond in ORDER:
    m, se, lo, hi, n = mean_se_ci(agg2[cond])
    rows.append({"target": cond, "mean": m, "SE": se, "CI_low": lo, "CI_high": hi, "n": n})
m_d, se_d, lo_d, hi_d, n_d = mean_se_ci(delta)
rows.append({"target": "Delta (Dynamic−Static)", "mean": m_d, "SE": se_d, "CI_low": lo_d, "CI_high": hi_d, "n": n_d})
group_stats = pd.DataFrame(rows)
group_stats_path = os.path.join(OUT_DIR, "group_slope_summary.csv")
# group_stats.to_csv(group_stats_path, index=False)

# ------------------ Paired t-test (overall) ------------------
t_stat, p_val = ttest_rel(agg2["Dynamic"], agg2["Static"])

print("=== Files saved ===")
# print("Per-user summary (with first_cond):", summary_path)
print("Paired plot:", paired_plot_path)
print("Delta plot:", delta_plot_path)
# print("Group mean/CI summary:", group_stats_path)
print(f"Paired t-test on slopes: t={t_stat:.2f}, p={p_val:.3f}, n={len(delta)}")
print("Latin Square sheet used:", sheet_name)
