# -*- coding: utf-8 -*-
# Analyze post-study questionnaires (NO NASA-TLX)
# - Supports headers like {"ImportId":"_recordId"} / {"ImportId":"QID3_6"}
# - Likert = 5; Reverse items handled
# - Outputs long tables + reliability + indices + paired tests

import os, re
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest

# ========= 0) Settings =========
PATH = r"./data/Surveys/questionnaires_aggregated.xlsx"
OUT_DIR = os.path.dirname(PATH)
N_USERS = 30                 # use first 30 rows of data (rows 4–33 in your export)
SAVE_CSV = True
SCALE_MAX = 5
NEUTRAL_POINT = (SCALE_MAX + 1) / 2.0

# High score = better. Reverse these negatively-worded items:
REVERSE_ITEMS = {"QID3_7", "QID28_7", "QID27_5", "QID11_5"}

# ========= 1) Read meta + data =========
meta = pd.read_excel(PATH, header=None, nrows=3)
import_ids_raw = meta.iloc[0].astype(str).tolist()   # row1: ImportId (may be JSON style)
qtexts_raw      = meta.iloc[2].astype(str).tolist()  # row3: the question text

df_all = pd.read_excel(PATH, header=0, skiprows=[1, 2])
df = df_all.iloc[:N_USERS].copy()
df.columns = df.columns.astype(str).str.strip()

# ========= 2) Canonicalize ImportIds from JSON-ish headers =========
def canonical_import_id(s: str):
    """
    Extracts canonical ImportId:
      - 'QID3_6'
      - '_recordId'
      from strings like:
      - 'QID3_6'
      - 'QID3_6 - The static ghost...'
      - '{"ImportId":"QID3_6"}'
      - '{"ImportId":"_recordId"}'
    """
    s = str(s)
    m = re.search(r'QID\d+_\d+|_recordId', s)
    return m.group(0) if m else None

# Map canonical -> actual column name in df
alias_map = {}
for col in df.columns:
    cid = canonical_import_id(col)
    if cid and cid not in alias_map:
        alias_map[cid] = col

# Map canonical ImportId -> question text (from meta)
col_to_qtext_can = {}
for raw_id, qtext in zip(import_ids_raw, qtexts_raw):
    cid = canonical_import_id(raw_id)
    if cid and cid not in col_to_qtext_can:
        col_to_qtext_can[cid] = str(qtext)

print(f"Detected questionnaire-like columns: {len(alias_map)}")

# ========= 3) Participant column (explicitly use {"ImportId":"_recordId"}) =========
pid_col = alias_map.get("_recordId", None)
if pid_col is None:
    # Fallback: make 1..N participants
    df.insert(0, "participant", np.arange(1, len(df) + 1).astype(str))
else:
    df.rename(columns={pid_col: "participant"}, inplace=True)
    df["participant"] = df["participant"].astype(str).str.strip()

# ========= 4) Convert only QID* columns to numeric (skip participant/_recordId) =========
for cid, real_col in alias_map.items():
    if cid.startswith("QID"):
        df[real_col] = pd.to_numeric(df[real_col], errors="coerce")

# ========= 5) Define item sets (canonical IDs) =========
LE_STATIC   = [f"QID3_{i}"  for i in range(1, 8)]
LE_DYNAMIC  = [f"QID28_{i}" for i in range(1, 8)]
VISUAL      = [f"QID8_{i}"  for i in range(1, 5)]
COMP_LIKERT = ["QID9_1", "QID9_2"]                       # 5-pt Likert: Static easy / Dynamic easy
COMP_CHOICE = [f"QID10_{i}" for i in range(1, 3+1)]      # 1=Static / 2=Dynamic / 3=Not sure
RET_STATIC  = [f"QID27_{i}" for i in range(1, 8)]
RET_DYNAMIC = [f"QID11_{i}" for i in range(1, 8)]

EXPECTED = LE_STATIC + LE_DYNAMIC + VISUAL + COMP_LIKERT + COMP_CHOICE + RET_STATIC + RET_DYNAMIC
present  = [c for c in EXPECTED if c in alias_map]
missing  = [c for c in EXPECTED if c not in alias_map]
print(f"Matched canonical ImportIds: {len(present)}/{len(EXPECTED)}")
if missing:
    print("Missing (canonical):", ", ".join(missing[:30]), "..." if len(missing) > 30 else "")

# ========= 6) Build long tables =========
def reverse_likert(series: pd.Series) -> pd.Series:
    return (SCALE_MAX + 1) - pd.to_numeric(series, errors="coerce")

likert_rows, choice_rows = [], []

def add_likert_rows(canonical_list, phase, condition, block):
    for cid in canonical_list:
        real_col = alias_map.get(cid)
        if real_col is None:
            continue
        s = pd.to_numeric(df[real_col], errors="coerce")
        if cid in REVERSE_ITEMS:
            s = reverse_likert(s)
        for pid, val in zip(df["participant"], s):
            if pd.isna(val):
                continue
            likert_rows.append({
                "participant": str(pid),
                "phase": phase,
                "condition": condition,   # None allowed for ComparativeLikert if ever needed
                "block": block,
                "item_id": cid,           # store canonical ImportId
                "rating": float(val),
                "qtext": col_to_qtext_can.get(cid, "")
            })

def add_choice_rows(canonical_list):
    for cid in canonical_list:
        real_col = alias_map.get(cid)
        if real_col is None:
            continue
        s = pd.to_numeric(df[real_col], errors="coerce")
        for pid, val in zip(df["participant"], s):
            if pd.isna(val):
                continue
            v = int(val)
            choice_rows.append({
                "participant": str(pid),
                "item_id": cid,
                "question": col_to_qtext_can.get(cid, ""),
                "choice_raw": v,  # 1/2/3
                "choice_label": {1:"Static", 2:"Dynamic", 3:"Not sure"}.get(v, None)
            })

# Fill rows
add_likert_rows(LE_STATIC,   phase="Practice", condition="Static",  block="LearningExp")
add_likert_rows(LE_DYNAMIC,  phase="Practice", condition="Dynamic", block="LearningExp")
add_likert_rows(VISUAL,      phase="Practice", condition="Dynamic", block="VisualDesign")
add_likert_rows(RET_STATIC,  phase="Recall",   condition="Static",  block="Retention")
add_likert_rows(RET_DYNAMIC, phase="Recall",   condition="Dynamic", block="Retention")
# Comparative Likert is two single items (Static easy / Dynamic easy). We keep them in a separate block:
add_likert_rows(COMP_LIKERT, phase="Overall",  condition=None,      block="ComparativeLikert")
# Comparative choice
add_choice_rows(COMP_CHOICE)

df_long   = pd.DataFrame(likert_rows)
df_choice = pd.DataFrame(choice_rows)
print("Likert long shape:", df_long.shape)
print("ComparativeChoice shape:", df_choice.shape)

if df_long.empty:
    raise SystemExit("df_long is empty. Check matched canonical ImportIds above.")

if SAVE_CSV:
    df_long.to_csv(os.path.join(OUT_DIR, "questionnaires_long.csv"), index=False)
    df_choice.to_csv(os.path.join(OUT_DIR, "comparative_choice.csv"), index=False)
    print("Saved: questionnaires_long.csv, comparative_choice.csv")

# ========= 7) Reliability (Cronbach's alpha) & index scores =========
def cronbach_alpha(wide_df: pd.DataFrame) -> float:
    wide = wide_df.dropna(axis=1, how="all")
    k = wide.shape[1]
    if k <= 1:
        return np.nan
    variances = wide.var(axis=0, ddof=1)
    total_var = wide.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return np.nan
    return (k/(k-1.0)) * (1 - variances.sum()/total_var)

def alpha_by(group_df: pd.DataFrame) -> float:
    if group_df.empty:
        return np.nan
    wide = group_df.pivot_table(index="participant", columns="item_id", values="rating")
    return cronbach_alpha(wide)

def index_score(g: pd.DataFrame) -> pd.DataFrame:
    return (
        g.groupby(["participant","phase","condition","block"])["rating"]
         .mean()
         .reset_index(name="index_score")
    )

idx = index_score(df_long)
if SAVE_CSV:
    idx.to_csv(os.path.join(OUT_DIR, "questionnaires_indices.csv"), index=False)
    print("Saved: questionnaires_indices.csv")

# ========= 8) Learning Experience (Practice) — Dynamic vs Static =========
le = df_long[df_long["block"]=="LearningExp"]
print("α LearningExp Static :", round(alpha_by(le[le["condition"]=="Static"]), 3))
print("α LearningExp Dynamic:", round(alpha_by(le[le["condition"]=="Dynamic"]), 3))

le_prac = idx[(idx["block"]=="LearningExp") & (idx["phase"]=="Practice")]
pivot_le = le_prac.pivot_table(index="participant", columns="condition", values="index_score").dropna()
if not pivot_le.empty and {"Static","Dynamic"} <= set(pivot_le.columns):
    t_le = stats.ttest_rel(pivot_le["Dynamic"], pivot_le["Static"])
    n = pivot_le.shape[0]
    dz = t_le.statistic / np.sqrt(n)
    print(f"[LearningExp] Dynamic vs Static: t({n-1})={t_le.statistic:.3f}, p={t_le.pvalue:.4f}, dz={dz:.3f}, n={n}")
else:
    print("[LearningExp] Not enough paired data.")

# ========= 9) Visual Design (Dynamic only, 4Q) =========
vd = df_long[(df_long["block"]=="VisualDesign") & (df_long["condition"]=="Dynamic")]
print("α VisualDesign (Dynamic):", round(alpha_by(vd), 3))
vd_idx = idx[(idx["block"]=="VisualDesign") & (idx["condition"]=="Dynamic")]

# ========= 10) Retention (Recall) — Dynamic vs Static =========
ret = df_long[df_long["block"]=="Retention"]
print("α Retention Static :", round(alpha_by(ret[ret["condition"]=="Static"]), 3))
print("α Retention Dynamic:", round(alpha_by(ret[ret["condition"]=="Dynamic"]), 3))

ret_idx = idx[(idx["block"]=="Retention") & (idx["phase"]=="Recall")]
pivot_ret = ret_idx.pivot_table(index="participant", columns="condition", values="index_score").dropna()
if not pivot_ret.empty and {"Static","Dynamic"} <= set(pivot_ret.columns):
    t_ret = stats.ttest_rel(pivot_ret["Dynamic"], pivot_ret["Static"])
    n2 = pivot_ret.shape[0]
    dz2 = t_ret.statistic / np.sqrt(n2)
    print(f"[Retention] Dynamic vs Static: t({n2-1})={t_ret.statistic:.3f}, p={t_ret.pvalue:.4f}, dz={dz2:.3f}, n={n2}")
else:
    print("[Retention] Not enough paired data.")

# ========= 11) Comparative =========
# QID9 — Likert (5pt), two items: Static-easy vs Dynamic-easy (paired)
comp_like = df_long[df_long["block"]=="ComparativeLikert"]
if not comp_like.empty:
    comp_item = (comp_like
        .groupby(["participant","item_id"])["rating"]
        .mean().reset_index())
    comp_item["condition"] = comp_item["item_id"].map({"QID9_1":"Static","QID9_2":"Dynamic"})
    comp_wide = (comp_item.pivot_table(index="participant", columns="condition", values="rating")
                           .dropna())
    if not comp_wide.empty and {"Static","Dynamic"} <= set(comp_wide.columns):
        t9 = stats.ttest_rel(comp_wide["Dynamic"], comp_wide["Static"])
        n9 = comp_wide.shape[0]
        dz9 = t9.statistic / np.sqrt(n9)
        print(f"[ComparativeLikert] Dynamic vs Static: t({n9-1})={t9.statistic:.3f}, p={t9.pvalue:.4f}, dz={dz9:.3f}, n={n9}")
    else:
        print("[ComparativeLikert] Not enough paired data.")
else:
    print("[ComparativeLikert] No data.")

# QID10 — 1=Static / 2=Dynamic / 3=Not sure (proportions, binomial vs 50%, excluding Not sure)
if not df_choice.empty:
    for q in sorted(df_choice["item_id"].unique()):
        sub = df_choice[df_choice["item_id"]==q]
        known = sub[sub["choice_raw"].isin([1,2])]
        dyn = (known["choice_raw"]==2).sum()
        trials = known.shape[0]
        if trials > 0:
            z, p = proportions_ztest(dyn, trials, value=0.5)
            print(f"[{q}] Pref Dynamic: {dyn}/{trials} = {dyn/trials:.2%}; z={z:.3f}, p={p:.4f}")
        else:
            print(f"[{q}] No valid (excluding Not sure).")
        pct = sub["choice_label"].value_counts(normalize=True).reindex(
            ["Static","Dynamic","Not sure"]).fillna(0.0)
        print(f"    Dist: Static={pct['Static']:.2%}, Dynamic={pct['Dynamic']:.2%}, NotSure={pct['Not sure']:.2%}")

    # Combine QID10_1~3 as one pooled preference test
    known_all = df_choice[df_choice["choice_raw"].isin([1,2])]
    dyn_all = (known_all["choice_raw"]==2).sum()
    trials_all = known_all.shape[0]
    if trials_all > 0:
        z_all, p_all = proportions_ztest(dyn_all, trials_all, value=0.5)
        print(f"[QID10 ALL] Pref Dynamic: {dyn_all}/{trials_all} = {dyn_all/trials_all:.2%}; z={z_all:.3f}, p={p_all:.4f}")
    else:
        print("[QID10 ALL] No valid (excluding Not sure).")
else:
    print("[ComparativeChoice] No data.")
