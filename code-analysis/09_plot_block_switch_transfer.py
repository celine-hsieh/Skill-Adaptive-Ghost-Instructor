"""
Block Switch Transfer Analysis for VR Piano Study
=========================================
This script loads per-loop JSON logs from ../data/UserPerformanceLogs/**,
aggregates to loop-level scores, plots block switch transfer,
and runs trend tests via linear mixed-effects models.

Usage (from your project root):
    pip install pandas numpy matplotlib scipy statsmodels
    python 09_plot_block_switch_transfer.py --root ./data/UserPerformanceLogs --out ./outputs

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
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
import statsmodels.formula.api as smf

# Matplotlib text sizing; comments translated to English.
plt.rcParams.update({
    "axes.titlesize": 18,   # subplot title size
    "axes.labelsize": 16,   # x/y label size
    "xtick.labelsize": 14,  # x tick size
    "ytick.labelsize": 14,  # y tick size
    "legend.fontsize": 14,  # legend font size
    "legend.title_fontsize": 16
})

# Palette for order-level plots (Static-first vs Dynamic-first)
PALETTE = {"Static-first": "#FF7F0E", "Dynamic-first": "#1F77B4"}

# Defaults
DEFAULT_ROOT = "./data/UserPerformanceLogs"
DEFAULT_OUT  = "./outputs"
COND_MAP = {"d": "Dynamic", "s": "Static"}
EPS = 1e-8
PLACEHOLDER_COLS = ["totalScore", "pitchScore", "timeScore", "fingerScore", "errorRate"]

def parse_filename(path: str) -> Optional[Tuple[str, str, str]]:
    """Parse 'UserX_[d|s]_[A|B].json' -> (user, condition, melody)."""
    fname = os.path.basename(path)
    m = re.match(r"User(\w+)_([ds])_([ABab])\.json$", fname)
    if not m:
        return None
    user = str(m.group(1))
    cond = COND_MAP.get(m.group(2).lower(), m.group(2).lower())
    melody = m.group(3).upper()
    return user, cond, melody

def load_all_records(root_dir: str) -> pd.DataFrame:
    """Load all JSONs under root_dir recursively into a single DataFrame."""
    rows = []
    paths = glob.glob(os.path.join(root_dir, "**", "*.json"), recursive=True)
    for p in paths:
        parsed = parse_filename(p)
        if not parsed:
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

def drop_placeholder_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove initialization/empty events: rows where all five metrics are approximately 0.
    This does not affect real perfect scores (total near 1 and error near 0) or non-zero records.
    """
    if df.empty:
        return df
    zero_block = (df[PLACEHOLDER_COLS].fillna(0).abs() <= EPS).all(axis=1)
    return df.loc[~zero_block].copy()

def aggregate_to_loop(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    """Aggregate repeated entries within (user, condition, melody, chunkIndex, countloop) by mean."""
    agg = (
        df.groupby(["user", "condition", "melody", "chunkIndex", "countloop"], as_index=False)
          .agg({**{m: "mean" for m in metrics},
                "targetAlpha": "mean", "timestamp": "mean", "_src": "count"})
          .rename(columns={"_src": "n_entries"})
    )
    return agg

def to_long(df_loop: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    """Convert loop-level wide metrics to long format with 'metric' and 'score' columns."""
    long = df_loop.melt(
        id_vars=["user", "condition", "melody", "chunkIndex", "countloop", "targetAlpha"],
        value_vars=metrics,
        var_name="metric",
        value_name="score"
    )
    return long

# ---------- Block/order inference (kept minimal for H1 tests) ----------
def infer_blocks_from_time(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each user, infer block1 vs block2 by earliest timestamp per melody.
    The melody with the earliest timestamp is Block 1; the other is Block 2.
    Also fetch the first condition of each block.
    """
    df = raw_df.dropna(subset=["timestamp"]).copy()
    first_t = (df.groupby(["user","melody"], as_index=False)
                 .agg(first_ts=("timestamp","min")))
    first_t["rank"] = first_t.groupby("user")["first_ts"].rank(method="first")
    first_t["block"] = first_t["rank"].map({1.0:1, 2.0:2}).astype(int)
    tmp = df.sort_values(["user","melody","timestamp"]).drop_duplicates(["user","melody"], keep="first")
    tmp = tmp[["user","melody","condition"]].rename(columns={"condition":"first_condition_of_block"})
    out = first_t.merge(tmp, on=["user","melody"], how="left")
    return out[["user","melody","block","first_condition_of_block"]]

def add_block_order(long_loop: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
    """Merge block (1/2) and order (Dynamic-first/Static-first) into the loop-level long data."""
    blk = infer_blocks_from_time(raw_df)
    ord_df = (blk[blk["block"]==1].rename(columns={"first_condition_of_block":"order"})[["user","order"]].copy())
    ord_df["order"] = ord_df["order"].map({"Dynamic":"Dynamic-first","Static":"Static-first"})
    long2 = long_loop.merge(blk[["user","melody","block"]], on=["user","melody"], how="left")
    long2 = long2.merge(ord_df, on="user", how="left")
    long2["block2_flag"] = (long2["block"] == 2).astype(int)
    return long2

# ---------- H1 metrics ----------
def compute_block2_initial(long2: pd.DataFrame, metric: str, k_loops:int=1) -> pd.DataFrame:
    """Compute Block-2 initial performance (mean of the first k loops)."""
    sub = long2[(long2["metric"]==metric) & (long2["block"]==2)].copy()
    if sub.empty:
        return pd.DataFrame()
    first_loop = (sub.groupby(["user","melody","condition"], as_index=False)
                    .agg(min_loop=("countloop","min")))
    sub = sub.merge(first_loop, on=["user","melody","condition"], how="left")
    sub = sub[sub["countloop"].between(sub["min_loop"], sub["min_loop"] + (k_loops-1), inclusive="both")]
    out = (sub.groupby(["user","melody","condition","order"], as_index=False)
              .agg(initial_score=("score","mean")))
    out = out.rename(columns={"melody":"melody_block2", "condition":"cond_block2"})
    return out

def test_block2_initial_LMM(initial_df: pd.DataFrame) -> str:
    """MixedLM: initial_score ~ order + melody_block2 + (1|user)."""
    if initial_df.empty:
        return "No block2 initial data."
    dat = initial_df.copy()
    dat["order"] = pd.Categorical(dat["order"], categories=["Static-first","Dynamic-first"])
    dat["melody_block2"] = dat["melody_block2"].astype("category")
    dat["user"] = dat["user"].astype("category")
    try:
        m = smf.mixedlm("initial_score ~ order + melody_block2", data=dat, groups=dat["user"])
        res = m.fit(reml=True, method="lbfgs", maxiter=500, disp=False)
        return res.summary().as_text()
    except Exception as e:
        return f"MixedLM failed: {e}"

def compute_block2_loops_to_criterion(long2: pd.DataFrame, metric: str,
                                      criterion: float=0.6) -> pd.DataFrame:
    """
    Return, for Block 2, the first loop index where score >= criterion.
    If never reached, mark censored=1 and set first_loop_to_hit = last_loop + 1.
    """
    sub = long2[(long2["metric"]==metric) & (long2["block"]==2)].copy()
    if sub.empty:
        return pd.DataFrame()
    g = (sub.groupby(["user","melody","condition","order","countloop"], as_index=False)
             .agg(score=("score","mean")))
    def _first_hit(gr):
        hit = gr.loc[gr["score"] >= criterion, "countloop"]
        if len(hit) > 0:
            return pd.Series({"first_loop_to_hit": int(hit.iloc[0]),
                              "censored": 0,
                              "last_loop": int(gr["countloop"].max())})
        else:
            return pd.Series({"first_loop_to_hit": int(gr["countloop"].max()+1),
                              "censored": 1,
                              "last_loop": int(gr["countloop"].max())})
    out = (g.groupby(["user","melody","condition","order"], as_index=False)
             .apply(_first_hit, include_groups=False))
    out = out.rename(columns={"melody":"melody_block2","condition":"cond_block2"})
    return out

def compare_loops_to_criterion(ttc: pd.DataFrame) -> str:
    """
    Quick comparisons:
    (1) Mann-Whitney on uncensored samples (H1: Dynamic-first < Static-first).
    (2) Poisson GLM loops ~ order + melody_block2 (treating censored as last_loop+1).
    """
    if ttc.empty:
        return "No loops-to-criterion data."
    from scipy.stats import mannwhitneyu
    import statsmodels.api as sm

    txt = []
    df_uncens = ttc[ttc["censored"]==0].copy()
    if len(df_uncens) >= 4 and df_uncens["order"].nunique()==2:
        x = df_uncens[df_uncens["order"]=="Dynamic-first"]["first_loop_to_hit"]
        y = df_uncens[df_uncens["order"]=="Static-first"]["first_loop_to_hit"]
        if len(x)>0 and len(y)>0:
            U, p = mannwhitneyu(x, y, alternative="less")
            txt.append(f"Mann-Whitney (uncensored only), H1 Dynamic-first < Static-first: U={U}, p={p:.4g}")
    glm_df = ttc.copy()
    glm_df["y"] = glm_df["first_loop_to_hit"].astype(float)
    X = pd.get_dummies(glm_df[["order","melody_block2"]], drop_first=True)
    X = sm.add_constant(X)
    try:
        model = sm.GLM(glm_df["y"], X, family=sm.families.Poisson())
        res = model.fit()
        txt.append("\nPoisson GLM on loops-to-criterion (incl. censored as last_loop+1):\n" + str(res.summary()))
    except Exception as e:
        txt.append(f"GLM Poisson failed: {e}")
    return "\n".join(txt)

# ---------- Plot helpers (show plots, prevent clipping) ----------
def _ci95(series):
    """Return (low, high) 95% CI and mean for a 1D array-like."""
    from scipy.stats import t
    x = pd.Series(series).dropna().astype(float).values
    n = len(x)
    if n <= 1:
        return (np.nan, np.nan), np.nan
    m = float(np.mean(x))
    sd = float(np.std(x, ddof=1))
    se = sd / np.sqrt(n)
    tcrit = t.ppf(0.975, df=n-1)
    return (m - tcrit*se, m + tcrit*se), m

def _jitter_mean_ci_plot(vals_by_order: dict,
                         orders=("Static-first","Dynamic-first"),
                         ylabel="", title="", outpath="figure.png",
                         criterion_line: float | None = None, criterion_label: str | None = None,
                         palette: dict | None = None,
                         show: bool = True):
    """Draw a compact jitter+mean+CI plot for two orders; save and show."""
    if palette is None:
        palette = PALETTE
    fig = plt.figure(figsize=(6,5))
    xs = [0,1]
    rng = np.random.default_rng(2025)
    for x, o in zip(xs, orders):
        v = np.array(vals_by_order.get(o, []), dtype=float)
        if v.size == 0:
            continue
        color = palette.get(o, None)
        jit = (rng.random(len(v)) - 0.5) * 0.15
        plt.scatter(np.full_like(v, x) + jit, v, alpha=0.7, color=color)
        (lo, hi), m = _ci95(v)
        plt.plot([x-0.15, x+0.15], [m, m], linewidth=3, color=color)
        if not np.isnan(lo) and not np.isnan(hi):
            plt.vlines(x, lo, hi, linewidth=2, color=color)

    if isinstance(criterion_line, (int, float)):
        plt.axhline(criterion_line, linestyle="--", linewidth=1)
        if criterion_label:
            y_text = min(0.98, criterion_line + 0.015)
            plt.text(0.02, y_text, criterion_label, transform=plt.gca().transAxes)

    plt.xticks(xs, orders)
    plt.ylim(0, 1.0)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.show()
    plt.close(fig)

def plot_block2_initial_fig(long2: pd.DataFrame, metric: str, k_loops: int,
                            out_dir: str, criterion_line: float | None = None):
    """Block-2 initial performance (mean of the first k loops), with dashed criterion line."""
    init_df = compute_block2_initial(long2, metric, k_loops=k_loops)
    vals_by_order = {
        "Static-first":  init_df.loc[init_df["order"]=="Static-first",  "initial_score"].values,
        "Dynamic-first": init_df.loc[init_df["order"]=="Dynamic-first", "initial_score"].values,
    }
    title = f"Second-block start: initial performance (mean of the first {k_loops} loop(s))"
    out = os.path.join(out_dir, f"fig_H1a_block2_initial_k{k_loops}_{metric}.png")
    label = f"Criterion = {criterion_line:.2f}" if isinstance(criterion_line, (int,float)) else None
    _jitter_mean_ci_plot(vals_by_order,
                         ylabel=f"Block-2 Initial Performance ({metric})",
                         title=title, outpath=out,
                         criterion_line=criterion_line, criterion_label=label, palette=PALETTE, show=True)

def plot_block2_endmean_fig(long2: pd.DataFrame, metric: str, k_last: int,
                            out_dir: str, criterion_line: float | None = None):
    """Block-2 end performance (mean of the last k loops), with dashed criterion line."""
    g = (long2[(long2["metric"]==metric) & (long2["block"]==2)]
            .groupby(["user","melody","condition","order","countloop"], as_index=False)
            .agg(score=("score","mean")))
    rows = []
    for keys, grp in g.groupby(["user","melody","condition","order"]):
        grp = grp.dropna(subset=["countloop","score"]).sort_values("countloop")
        if grp.empty:
            continue
        tail = grp.tail(k_last)
        rows.append({"order": keys[3], "end_avg": float(tail["score"].mean())})
    end_df = pd.DataFrame(rows)
    vals_by_order = {
        "Static-first":  end_df.loc[end_df["order"]=="Static-first",  "end_avg"].values,
        "Dynamic-first": end_df.loc[end_df["order"]=="Dynamic-first", "end_avg"].values,
    }
    title = f"End of the second block: performance (mean of the last {k_last} loop(s))"
    out = os.path.join(out_dir, f"fig_H1b_end{k_last}_{metric}.png")
    label = f"Criterion = {criterion_line:.2f}" if isinstance(criterion_line, (int,float)) else None
    _jitter_mean_ci_plot(vals_by_order,
                         ylabel=f"Block-2 End Performance ({metric})",
                         title=title, outpath=out,
                         criterion_line=criterion_line, criterion_label=label, palette=PALETTE, show=True)

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="H1 Analysis: Block-2 Initial & Loops-to-Criterion (Clean Version)")
    parser.add_argument("--root", type=str, default=DEFAULT_ROOT, help="Root folder of JSON logs")
    parser.add_argument("--out", type=str, default=DEFAULT_OUT, help="Output folder")
    parser.add_argument("--primary", type=str, default="totalScore", help="Primary metric (e.g., totalScore)")
    parser.add_argument("--h1-initial-k", type=int, default=1, help="Use first k loops in Block-2 as initial performance (1 or 2)")
    parser.add_argument("--h1-criterion", type=float, default=0.60, help="Criterion threshold for loops-to-criterion in Block-2 (e.g., 0.60)")
    parser.add_argument("--chunk", type=int, choices=[0,1,2], default=None,
                        help="Filter to a specific chunk: 0=Full melody, 1=Phase 1, 2=Phase 2 (default: all)")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    METRICS = [args.primary]

    # Load
    df = load_all_records(args.root)
    if df.empty:
        print(f"[H1] No JSON found under: {args.root}")
        return

    # Filter out placeholder/empty rows
    n_before = len(df)
    df = drop_placeholder_rows(df)
    n_after = len(df)
    print(f"[H1] Placeholder rows removed: {n_before - n_after}; kept: {n_after}")

    # Aggregate to loop level and convert to long
    loop_df = aggregate_to_loop(df, METRICS)
    long_loop = to_long(loop_df, METRICS)

    # Optional chunk filter to avoid mixing phases
    if args.chunk is not None:
        long_loop = long_loop[long_loop["chunkIndex"] == args.chunk].copy()

    # Save loop-level long for traceability
    # loop_csv = os.path.join(args.out, f"loop_level_long_{args.primary}.csv")
    # long_loop.to_csv(loop_csv, index=False)
    # print(f"[Saved] {loop_csv}")

    # Add block/order info
    long_with_block = add_block_order(long_loop, df)

    # H1a: initial Block-2 performance
    initial_df = compute_block2_initial(long_with_block, args.primary, k_loops=args.h1_initial_k)
    # initial_csv = os.path.join(args.out, f"h1_block2_initial_k{args.h1_initial_k}_{args.primary}.csv")
    # initial_df.to_csv(initial_csv, index=False)
    # print(f"[Saved] {initial_csv}  (rows={len(initial_df)})")

    lmm_txt = test_block2_initial_LMM(initial_df)
    # lmm_path = os.path.join(args.out, f"h1_block2_initial_LMM_{args.primary}.txt")
    # with open(lmm_path, "w", encoding="utf-8") as f:
        # f.write(lmm_txt)
    # print(f"[Saved] {lmm_path}")

    # H1b: loops-to-criterion
    ttc_df = compute_block2_loops_to_criterion(long_with_block, args.primary, criterion=args.h1_criterion)
    # ttc_csv = os.path.join(args.out, f"h1_block2_loops_to_criterion_{args.primary}.csv")
    # ttc_df.to_csv(ttc_csv, index=False)
    # print(f"[Saved] {ttc_csv}  (rows={len(ttc_df)})")

    cmp_txt = compare_loops_to_criterion(ttc_df)
    # cmp_path = os.path.join(args.out, f"h1_block2_loops_compare_{args.primary}.txt")
    # with open(cmp_path, "w", encoding="utf-8") as f:
        # f.write(cmp_txt)
    # print(f"[Saved] {cmp_path}")

    # Make and SHOW figures (tight layout + bbox_inches to avoid clipping)
    try:
        plot_block2_initial_fig(long_with_block, args.primary, k_loops=args.h1_initial_k,
                                out_dir=args.out, criterion_line=args.h1_criterion)
        plot_block2_endmean_fig(long_with_block, args.primary, k_last=2,
                                out_dir=args.out, criterion_line=args.h1_criterion)
    except Exception as e:
        print(f"[Warn] plotting failed: {e}")

    print("\n[H1] Done.")
    print(f"Primary metric = {args.primary}")
    print(f"Initial k loops (Block-2) = {args.h1_initial_k}")
    print(f"Criterion (Block-2) = {args.h1_criterion}")
    print(f"Outputs in: {args.out}")

if __name__ == "__main__":
    main()
