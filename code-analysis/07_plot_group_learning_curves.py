"""
Group Learning Curve Analysis for VR Piano Study
=========================================
This script loads per-loop JSON logs from ./data/UserPerformanceLogs/**,
aggregates to loop-level scores, plots learning curves (group and individual),
and runs trend tests via slope comparisons and linear mixed-effects models.
Optionally, it attempts a repeated-measures ANOVA on loop (when data are balanced).

Usage (from your project root):
    pip install pandas numpy matplotlib scipy statsmodels
    python 07_plot_group_learning_curves.py --root ./data/UserPerformanceLogs --out ./outputs

File naming convention (examples):
  User1_d_B.json  -> user=1, condition=d (dynamic), melody=B
  User1_s_A.json  -> user=1, condition=s (static),  melody=A

Inside each JSON: "entries": [ { ... } ]
Relevant fields per entry:
  pitchScore, timeScore, fingerScore, totalScore, errorRate,
  targetAlpha, timestamp, chunkIndex, countloop

Notes
- chunkIndex: 1 = Phase 1, 2 = Phase 2, 0 = Full melody
- countloop: training loop index (expected 1..10 per chunk)
- Multiple entries can share (chunkIndex, countloop). We aggregate by mean.
"""

import os
import re
import json
import glob
import argparse
from typing import List, Dict, Tuple, Optional, Iterable, Set

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
import statsmodels.formula.api as smf
from statsmodels.stats.anova import AnovaRM
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator



plt.rcParams.update({
    "axes.titlesize": 18,   # Subplot title
    "axes.labelsize": 16,   # x/y labels
    "xtick.labelsize": 14,  # x axis tick labels
    "ytick.labelsize": 14,  # y axis tick labels
    "legend.fontsize": 14,  # Legend labels
    "legend.title_fontsize": 16
})

# -------------------- Defaults --------------------
DEFAULT_ROOT = "./data/UserPerformanceLogs"
DEFAULT_OUT  = "./outputs"

ALL_METRICS = ["totalScore", "pitchScore", "fingerScore", "timeScore", "errorRate"]
PRIMARY_METRIC = "totalScore"
ORDER = ["Static", "Dynamic"] 
COND_MAP = {"d": "Dynamic", "s": "Static"}
CHUNK_NAME = {1: "Phase 1", 2: "Phase 2", 0: "Full Melody"}

# === NEW === placeholder filter settings
EPS = 1e-8
PLACEHOLDER_COLS = ["totalScore", "pitchScore", "timeScore", "fingerScore", "errorRate"]


# -------------------- I/O & parsing --------------------
def parse_filename(path: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse 'UserX_[d|s]_[A|B].json' -> (user, condition, melody)
    """
    fname = os.path.basename(path)
    m = re.match(r"User(\w+)_([ds])_([ABab])\.json$", fname)
    if not m:
        return None
    user = str(m.group(1))
    cond = COND_MAP.get(m.group(2).lower(), m.group(2).lower())
    melody = m.group(3).upper()
    return user, cond, melody


def load_all_records(root_dir: str) -> pd.DataFrame:
    rows = []
    paths = glob.glob(os.path.join(root_dir, "**", "*.json"), recursive=True)
    for p in paths:
        parsed = parse_filename(p)
        if not parsed:
            # print(f"Skip non-matching filename: {p}")
            continue
        user, condition, melody = parsed
        try:
            with open(p, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            print(f"Skip {p}: {e}")
            continue

        for e in payload.get("entries", []):
            rows.append({
                "user": user,
                "condition": condition,
                "melody": melody,
                "chunkIndex": e.get("chunkIndex", np.nan),
                "countloop": e.get("countloop", np.nan),
                "timestamp": e.get("timestamp", np.nan),
                "targetAlpha": e.get("targetAlpha", np.nan),
                "pitchScore": e.get("pitchScore", np.nan),
                "timeScore": e.get("timeScore", np.nan),
                "fingerScore": e.get("fingerScore", np.nan),
                "totalScore": e.get("totalScore", np.nan),
                "errorRate": e.get("errorRate", np.nan),
                "_src": p
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.dropna(subset=["chunkIndex", "countloop"])
    df["chunkIndex"] = df["chunkIndex"].astype(int)
    df["countloop"] = df["countloop"].astype(int)

    return df


# === NEW === filter out init/empty placeholder rows
def drop_placeholder_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove initial/empty events: rows where all five scores are 0 (with small floating point errors).
    This does not affect actual "perfect" (totalScore≈1 and errorRate≈0) or "error" records.
    """
    if df.empty:
        return df
    zero_block = (df[PLACEHOLDER_COLS].fillna(0).abs() <= EPS).all(axis=1)
    return df.loc[~zero_block].copy()

# -------------------- Aggregation --------------------
def aggregate_to_loop(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    """
    Aggregate repeated entries within (user, condition, melody, chunkIndex, countloop) by mean.
    """
    agg = (
        df.groupby(["user", "condition", "melody", "chunkIndex", "countloop"], as_index=False)
          .agg({**{m: "mean" for m in metrics},
                "targetAlpha": "mean", "timestamp": "mean", "_src": "count"})
          .rename(columns={"_src": "n_entries"})
    )
    return agg


def to_long(df_loop: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    long = df_loop.melt(
        id_vars=["user", "condition", "melody", "chunkIndex", "countloop", "targetAlpha"],
        value_vars=metrics,
        var_name="metric",
        value_name="score"
    )
    return long


# -------------------- Plotting --------------------
def _maybe_flip_for_plot(df: pd.DataFrame, flip_error: bool) -> pd.DataFrame:
    df = df.copy()
    if flip_error and "metric" in df:
        mask = df["metric"].eq("errorRate")
        if mask.any():
            vals = df.loc[mask, "score"].astype(float).values
            if np.isfinite(vals).any():
                vmax = np.nanmax(vals)
                vmin = np.nanmin(vals)
                if vmax <= 1.0 and vmin >= 0.0:
                    df.loc[mask, "score"] = 100.0 - (df.loc[mask, "score"] * 100.0)
                else:
                    df.loc[mask, "score"] = -df.loc[mask, "score"]
    return df


def _ci95_sem(x: Iterable[float]) -> float:
    x = pd.Series(x).dropna().values
    n = len(x)
    if n <= 1:
        return np.nan
    sem = np.std(x, ddof=1) / np.sqrt(n)
    # Use t critical with df=n-1
    tcrit = stats.t.ppf(0.975, df=n-1)
    return tcrit * sem


def plot_chunk_panels(long_df: pd.DataFrame, out_dir: str, flip_error: bool):
    """
    For each chunk, generate a group learning curve panel with four metrics side by side:
    PitchScore、FingerScore、timeScore、errorRate（this order）。
    Each panel has only one shared legend, top-aligned; all subplots have consistent colors.
    """
    # Fixed condition colors: Dynamic=blue, Static=orange (consistent with matplotlib's default first two colors)
    cond_colors = {"Dynamic": "#1f77b4", "Static": "#ff7f0e"}
    panels = [
        ("pitchScore",  "Pitch"),
        ("fingerScore", "Finger"),
        ("timeScore",   "Time"),
        ("errorRate",   "Error"),
    ]

    chunks = sorted(long_df["chunkIndex"].dropna().unique().tolist())
    for chunk in chunks:
        fig, axes = plt.subplots(1, 4, figsize=(16, 4.6), sharex=True, constrained_layout=False)
        axes = axes.flatten()

        # Put all actual loops in this chunk into a single set of ticks (used by all four subplots)
        all_loops = sorted(long_df.loc[long_df["chunkIndex"] == chunk, "countloop"]
                           .dropna().astype(int).unique().tolist())

        # Prepare legend elements (based on actual conditions)
        cond_present = set(long_df.loc[long_df["chunkIndex"] == chunk, "condition"].dropna().unique())
        legend_elements = [
            Line2D([0], [0], marker='o', linestyle='-', color=cond_colors[c], label=c)
            for c in ORDER if c in cond_present
        ]

        for ax, (metric, short_title) in zip(axes, panels):
            sub = long_df[(long_df["metric"] == metric) & (long_df["chunkIndex"] == chunk)].copy()
            if sub.empty:
                ax.set_visible(False)
                continue

            # Only flip errorRate when needed
            if metric == "errorRate":
                sub = _maybe_flip_for_plot(sub, flip_error)

            # Group average
            g = (sub.groupby(["condition", "countloop"], as_index=False)
                      .agg(mean=("score", "mean")))

            # Compute 95% CI based on "mean per subject per loop" to avoid pseudo-replication
            subj = (sub.groupby(["user", "condition", "countloop"], as_index=False)
                        .agg(score=("score", "mean")))
            ci = (subj.groupby(["condition", "countloop"], as_index=False)
                       .agg(ci95=("score", _ci95_sem)))
            g = g.merge(ci, on=["condition", "countloop"], how="left").sort_values(["condition","countloop"])

            for cond in ORDER:
                if cond not in cond_present:
                    continue
                s = g[g["condition"] == cond]
                if s.empty:
                    continue
                ax.plot(s["countloop"], s["mean"], marker="o", linewidth=1.4, markersize=4,
                        color=cond_colors[cond])
                if "ci95" in s.columns and s["ci95"].notna().any():
                    y1 = s["mean"] - s["ci95"]
                    y2 = s["mean"] + s["ci95"]
                    ax.fill_between(s["countloop"], y1, y2, alpha=0.18, color=cond_colors[cond])

            ax.set_title(f"{short_title} Score")
            ax.set_xlabel("Loop")
            ylab = ("Error Rate (higher=better)" if (metric == "errorRate" and flip_error)
                    else f"{short_title} Score")
            ax.set_ylabel(ylab)
            # Unify Y axis to 0–1
            ax.set_ylim(0.0, 1.0)
            ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
            ax.grid(True)

             # Explicitly set X axis to show loop counts
            if all_loops:
                ax.set_xticks(all_loops)
                ax.set_xlim(min(all_loops) - 0.5, max(all_loops) + 0.5)
                ax.xaxis.set_major_locator(MaxNLocator(integer=True))  # Ensure integer display

        # Shared legend (top-aligned, minimal padding)
        # Use mode='expand' to evenly distribute label widths, two conditions will naturally align; more will automatically wrap
        fig.legend(handles=legend_elements, loc='upper center',
                   bbox_to_anchor=(0.5, 1.0),    # Tightly aligned to top, horizontally filled
                   ncol=len(legend_elements),
                   frameon=True, fontsize=14, borderaxespad=0.0,
                   handlelength=1.6, columnspacing=1.6, labelspacing=0.6)

        # Compress the spacing between the subplots
        fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.95])

        fname = os.path.join(out_dir, f"group_panel_chunk{chunk}.png")
        fig.savefig(fname, dpi=200, bbox_inches='tight')
        plt.show()
        plt.close(fig)
        print(f"[Saved] {fname}")


# -------------------- Trend stats (slopes) --------------------
def compute_slopes(long_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    dat = long_df[long_df["metric"] == metric].copy()
    out = []
    for keys, grp in dat.groupby(["user", "melody", "chunkIndex", "condition"]):
        g = grp.dropna(subset=["countloop", "score"]).sort_values("countloop")
        if g["countloop"].nunique() < 2:
            continue
        x = g["countloop"].astype(float).values
        y = g["score"].astype(float).values
        slope, intercept = np.polyfit(x, y, 1)
        out.append({
            "user": keys[0], "melody": keys[1], "chunkIndex": keys[2], "condition": keys[3],
            "slope": slope, "intercept": intercept, "n_points": len(g)
        })
    return pd.DataFrame(out)


def paired_slope_tests(slopes: pd.DataFrame) -> pd.DataFrame:
    """
    Paired t-test (Dynamic vs Static) on slopes within each (melody, chunkIndex).
    Also condition-wise one-sample t-test vs 0.
    Adds Cohen's dz for paired differences when applicable.
    """
    results = []

    for (mel, ch), sub in slopes.groupby(["melody", "chunkIndex"]):
        pivot = sub.pivot_table(index="user", columns="condition", values="slope")
        # Paired difference D-S
        if {"Dynamic", "Static"}.issubset(pivot.columns):
            d = pivot["Dynamic"].dropna()
            s = pivot["Static"].dropna()
            common = d.index.intersection(s.index)
            if len(common) >= 3:
                diff = d.loc[common] - s.loc[common]
                t, p = stats.ttest_1samp(diff, 0.0)
                dz = diff.mean() / (diff.std(ddof=1) if diff.std(ddof=1) > 0 else np.nan)
                results.append({
                    "melody": mel, "chunkIndex": ch, "test": "paired D-S slope",
                    "n_pairs": len(common), "t": float(t), "p": float(p),
                    "mean_diff": float(diff.mean()), "cohen_dz": float(dz) if np.isfinite(dz) else np.nan
                })

        # One-sample vs 0 for each condition
        for cond in ["Dynamic", "Static"]:
            vals = sub[sub["condition"] == cond]["slope"].dropna()
            if len(vals) >= 3:
                t, p = stats.ttest_1samp(vals, 0.0)
                results.append({
                    "melody": mel, "chunkIndex": ch, "test": f"{cond} slope>0",
                    "n": len(vals), "t": float(t), "p": float(p), "mean_slope": float(vals.mean())
                })

    return pd.DataFrame(results)


# -------------------- Mixed-effects model --------------------
def mixed_effects_trend(long_df: pd.DataFrame, metric: str) -> str:
    """
    Mixed effects (REML): score ~ condition * loop_c + melody + chunkIndex + (1 + loop_c | user)
    Returns the full summary PLUS a one-line Δslope (Dynamic − Static) summary.
    """
    dat = long_df[(long_df["metric"] == metric)].dropna(subset=["score", "countloop"]).copy()
    if dat.empty:
        return "No data for mixed effects."

    # center loop & set categories (Static as baseline)
    dat["loop_c"]     = dat["countloop"] - dat["countloop"].mean()
    dat["condition"]  = pd.Categorical(dat["condition"], categories=["Static", "Dynamic"])
    dat["melody"]     = dat["melody"].astype("category")
    dat["chunkIndex"] = dat["chunkIndex"].astype("category")
    dat["user"]       = dat["user"].astype("category")

    # --- helper: fit with REML, try multiple optimizers, return (res, optimizer_name) ---
    def _fit(re_formula: str):
        model = smf.mixedlm("score ~ condition * loop_c + melody + chunkIndex",
                            data=dat, groups=dat["user"], re_formula=re_formula)
        for meth in ["lbfgs", "bfgs", "cg", "powell", "nm"]:
            try:
                res_local = model.fit(reml=True, method=meth, maxiter=500, disp=False)
                if res_local.converged:
                    return res_local, meth
            except Exception:
                continue
        # If none converge, return the last attempt (possibly not converged) and the last method name
        try:
            res_local = model.fit(reml=True, method="lbfgs", maxiter=500, disp=False)
            return res_local, "lbfgs"
        except Exception:
            return None, None

    # First try random slope; if not, downgrade to only intercept
    res, used_method = _fit(re_formula="~loop_c")
    re_formula_used = "~loop_c"
    if (res is None) or (not res.converged):
        res, used_method = _fit(re_formula="1")
        re_formula_used = "1"
        if res is None:
            return "MixedLM failed: could not obtain a solution."

    # ---- baseline-agnostic Δslope (Dynamic - Static) ----
    import numpy as np
    pname = None
    if "condition[T.Dynamic]:loop_c" in res.params.index:
        pname, sign = "condition[T.Dynamic]:loop_c", +1
    elif "condition[T.Static]:loop_c" in res.params.index:
        pname, sign = "condition[T.Static]:loop_c", -1

    oneliner = ""
    if pname is not None:
        beta_raw = float(res.params[pname])
        se       = float(res.bse[pname])
        p        = float(res.pvalues[pname])
        ci_low, ci_high = res.conf_int().loc[pname]
        beta = sign * beta_raw
        ci   = np.sort(sign * np.array([ci_low, ci_high]))

        # per-condition fixed-effect slopes
        loop_coef = float(res.params.get("loop_c", np.nan))
        if pname.endswith("Static]:loop_c"):
            slope_dynamic = loop_coef
            slope_static  = loop_coef + beta_raw
        else:
            slope_static  = loop_coef
            slope_dynamic = loop_coef + beta_raw

        oneliner = (
            f"\n\nΔslope (Dynamic - Static) = {beta:.4f}, SE={se:.4f}, "
            f"p={p:.4g}, 95% CI [{ci[0]:.4f}, {ci[1]:.4f}] | "
            f"slope_dynamic={slope_dynamic:.4f}, slope_static={slope_static:.4f} | "
            f"REML=True, optimizer={used_method}, re_formula='{re_formula_used}', "
            f"converged={res.converged}"
        )
    else:
        oneliner = "\n\n(Warning) interaction term condition×loop_c not found; check data balance."

    return res.summary().as_text() + oneliner




# -------------------- Repeated-measures ANOVA (optional) --------------------
def _users_with_complete_loops(df: pd.DataFrame, loop_levels: List[int]) -> Set[str]:
    have = set()
    for u, g in df.groupby("user"):
        got = set(g["countloop"].unique().tolist())
        if set(loop_levels).issubset(got):
            have.add(u)
    return have


def run_anovarm_on_loop(long_df: pd.DataFrame, metric: str,
                        min_common_loops: int = 3) -> pd.DataFrame:
    """
    Attempts AnovaRM(score ~ loop) within each (melody, chunk, condition).
    Keeps only loops that are common across all included users.
    Requires at least min_common_loops levels.
    Returns a table of F-tests.
    """
    out_rows = []
    dat = long_df[long_df["metric"] == metric].dropna(subset=["score", "countloop"]).copy()
    dat["loop"] = dat["countloop"].astype(int).astype(str)  # categorical as string

    for (mel, ch, cond), sub in dat.groupby(["melody", "chunkIndex", "condition"]):
        # Find loop levels common to all users
        levels = sorted(sub["countloop"].unique().tolist())
        common = set(levels)
        for u, g in sub.groupby("user"):
            common = common.intersection(set(g["countloop"].unique().tolist()))
        common = sorted(list(common))

        if len(common) < min_common_loops:
            continue

        keep_users = _users_with_complete_loops(sub, common)
        df_sub = sub[sub["user"].isin(keep_users) & sub["countloop"].isin(common)].copy()
        if df_sub.empty:
            continue

        try:
            # AnovaRM expects long format with a within factor
            df_sub["loop"] = df_sub["countloop"].astype(str)
            aov = AnovaRM(df_sub, depvar="score", subject="user", within=["loop"]).fit()
            # Extract table rows (loop main effect)
            tbl = aov.anova_table.reset_index().rename(columns={"index": "effect"})
            for _, r in tbl.iterrows():
                out_rows.append({
                    "melody": mel, "chunkIndex": ch, "condition": cond,
                    "effect": r.get("effect", ""),
                    "F": float(r.get("F Value", np.nan)),
                    "Num DF": float(r.get("Num DF", np.nan)),
                    "Den DF": float(r.get("Den DF", np.nan)),
                    "Pr>F": float(r.get("Pr > F", np.nan)),
                    "n_users": len(keep_users),
                    "n_loops": len(common),
                })
        except Exception as e:
            out_rows.append({
                "melody": mel, "chunkIndex": ch, "condition": cond,
                "effect": "loop", "F": np.nan, "Num DF": np.nan, "Den DF": np.nan,
                "Pr>F": np.nan, "n_users": np.nan, "n_loops": np.nan,
                "error": str(e)
            })

    return pd.DataFrame(out_rows)

# --- Add-on: format a paper-ready table for slope results (paired D-S) ---
def summarize_paired_slopes(slopes_df: pd.DataFrame, out_path: str):
    """
    Creates a CSV with paired D-S slope summary including 95% CI and one-tailed p.
    """
    from scipy.stats import t
    rows = []
    for (mel, ch), sub in slopes_df.groupby(["melody","chunkIndex"]):
        piv = sub.pivot_table(index="user", columns="condition", values="slope")
        if {"Dynamic","Static"}.issubset(piv.columns):
            d = piv["Dynamic"].dropna()
            s = piv["Static"].dropna()
            common = d.index.intersection(s.index)
            if len(common) >= 3:
                diff = (d.loc[common] - s.loc[common]).values
                n = len(diff)
                m = np.mean(diff)
                sd = np.std(diff, ddof=1)
                se = sd / np.sqrt(n)
                tval = m / se if se > 0 else np.nan
                df = n - 1
                # two-tailed p
                from scipy.stats import ttest_1samp
                t2, p2 = ttest_1samp(diff, 0.0)
                # one-tailed (H1: Dynamic - Static < 0)
                p1 = p2/2 if m < 0 else 1 - p2/2
                # 95% CI (two-tailed)
                tcrit = t.ppf(0.975, df=df)
                lo = m - tcrit * se
                hi = m + tcrit * se
                rows.append({
                    "melody": mel, "chunkIndex": ch,
                    "n_pairs": n,
                    "mean_diff(D- S)": m,
                    "95%CI_low": lo, "95%CI_high": hi,
                    "t": tval, "df": df, "p_two_tailed": p2, "p_one_tailed(H1:D<S)": p1
                })
    out = pd.DataFrame(rows)
    out.to_csv(out_path, index=False)
    print(f"[Saved] {out_path}")


def complement_diagnostics(raw_df: pd.DataFrame, out_dir: str):
    """
    Check the relationship between totalScore and (1 - errorRate), output three files:
      1) complement_entry_scatter.png  (each entry scatter plot)
      2) complement_loop_table.csv     (loop average by the same sample, check mean(total) + mean(error) - 1)
      3) complement_summary.txt        (overall correlation and average difference)
    Note: always use "complete-case" (both total & error) data, to avoid bias caused by different sample sets.
    """
    os.makedirs(out_dir, exist_ok=True)
    keys = ["user", "condition", "melody", "chunkIndex", "countloop"]

    # ---- Entry-level (each entry) check ----
    dfc = raw_df.dropna(subset=["totalScore", "errorRate"]).copy()
    if dfc.empty:
        with open(os.path.join(out_dir, "complement_summary.txt"), "w", encoding="utf-8") as f:
            f.write("No complete-case rows for totalScore & errorRate.\n")
        return

    dfc["one_minus_error"] = 1.0 - dfc["errorRate"].astype(float)
    # correlation and difference
    r = dfc["totalScore"].astype(float).corr(dfc["one_minus_error"].astype(float))
    diff_entry = (dfc["totalScore"] - dfc["one_minus_error"]).astype(float)
    mae = diff_entry.abs().mean()
    mean_diff = diff_entry.mean()

    # scatter plot
    plt.figure(figsize=(6, 5))
    plt.scatter(dfc["one_minus_error"], dfc["totalScore"], alpha=0.3)
    lims = [min(dfc["one_minus_error"].min(), dfc["totalScore"].min()),
            max(dfc["one_minus_error"].max(), dfc["totalScore"].max())]
    plt.plot(lims, lims, linestyle="--")  # y=x reference line
    plt.xlabel("1 - errorRate")
    plt.ylabel("totalScore")
    plt.title("Entry-level: totalScore vs (1 - errorRate)")
    plt.tight_layout()
    fig1 = os.path.join(out_dir, "complement_entry_scatter.png")
    plt.savefig(fig1, dpi=200); plt.close()

    # ---- Loop-level (same sample, filter complete-case then average)----
    loop_cc = (dfc.groupby(keys, as_index=False)
                 .agg(totalScore=("totalScore","mean"),
                      errorRate=("errorRate","mean")))
    loop_cc["check_sum_minus1"] = loop_cc["totalScore"] + loop_cc["errorRate"] - 1.0
    # if really complementary, this column should be close to 0
    loop_cc.to_csv(os.path.join(out_dir, "complement_loop_table.csv"), index=False)

    # mean difference by loop
    by_grp = (loop_cc.groupby(["condition","chunkIndex","countloop"], as_index=False)
                      .agg(mean_total=("totalScore","mean"),
                           mean_error=("errorRate","mean"),
                           mean_sum_minus1=("check_sum_minus1","mean")))

    # ---- Summary ----
    with open(os.path.join(out_dir, "complement_summary.txt"), "w", encoding="utf-8") as f:
        f.write("Entry-level diagnostics (complete-case only):\n")
        f.write(f"- corr(totalScore, 1-errorRate) = {r:.4f}\n")
        f.write(f"- mean(total - (1-error))      = {mean_diff:.4f}\n")
        f.write(f"- MAE(total - (1-error))       = {mae:.4f}\n\n")
        f.write("Loop-level mean(total)+mean(error)-1 by (cond, chunk, loop):\n")
        f.write(by_grp.to_string(index=False))
        f.write("\n")
    print(f"[Saved] {fig1}")
    print(f"[Saved] {os.path.join(out_dir, 'complement_loop_table.csv')}")
    print(f"[Saved] {os.path.join(out_dir, 'complement_summary.txt')}")


# -------------------- Main --------------------
def main():
    parser = argparse.ArgumentParser(description="Training Curve Analysis")
    parser.add_argument("--root", type=str, default=DEFAULT_ROOT, help="Root folder of JSON logs")
    parser.add_argument("--out", type=str, default=DEFAULT_OUT, help="Output folder")
    parser.add_argument("--metrics", type=str, nargs="*", default=ALL_METRICS,
                        help=f"Metrics to analyze (default: {ALL_METRICS})")
    parser.add_argument("--primary", type=str, default=PRIMARY_METRIC, help="Primary metric for stats")
    parser.add_argument("--individual", action="store_true", help="Also export individual curves")
    parser.add_argument("--flip-error", action="store_true",
                        help="Flip errorRate so that higher=better in plots")
    parser.add_argument("--do-anova", action="store_true",
                        help="Attempt repeated-measures ANOVA on loop (balanced data only)")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    df = load_all_records(args.root)
    if df.empty:
        print(f"No JSON found under: {args.root}")
        return

    # filter out initial/empty events
    n_before = len(df)
    df = drop_placeholder_rows(df)
    n_after = len(df)
    print(f"Filtered placeholder rows: {n_before - n_after} removed, {n_after} kept.")


    # print(f"Loaded {len(df)} entries from {args.root}")
    loop_df = aggregate_to_loop(df, args.metrics)
    long = to_long(loop_df, args.metrics)

    # Save loop-level data
    # long_csv = os.path.join(args.out, "loop_level_long.csv")
    # long.to_csv(long_csv, index=False)
    # print(f"[Saved] {long_csv}")

    # ---- Plots ----
    plot_chunk_panels(long, args.out, flip_error=args.flip_error)

    # # ---- Slope-based stats ----
    slopes = compute_slopes(long, args.primary)
    slopes_csv = os.path.join(args.out, f"slopes_{args.primary}.csv")
    slopes.to_csv(slopes_csv, index=False)
    print(f"[Saved] {slopes_csv}")

if __name__ == "__main__":
    main()
