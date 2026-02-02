import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
from pathlib import Path

plt.rcParams.update({
    "axes.titlesize": 24,
    "axes.labelsize": 22,
    "xtick.labelsize": 20,
    "ytick.labelsize": 20,
    "legend.fontsize": 20,
    "legend.title_fontsize": 20
})


# ---- Colors (colorblind-friendly: Okabe–Ito) ----
COL_NOT_EXP = "#a2c2aa"  # orange
COL_EXP     = "#e0c379"  # blue
EDGE        = "white"

# -------------------------
# IO paths
# -------------------------
EXCEL_PATH = "./data/Surveys/questionnaires_aggregated.xlsx"  # <-- change if needed
SHEET_NAME = "Adaptive Transparency for Virtu"
EXPORT_DIR = Path("./outputs")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
SAVE_PATH = EXPORT_DIR / "03_plot_participant_distribution.png"


# =========================
# Helpers
# =========================
def extract_importid(colname: str) -> str:
    """Extract Qualtrics ImportId from a header like '{"ImportId":"QID1_1"}'."""
    s = str(colname)
    m = re.search(r'"?ImportId"?:"?([^"}]+)', s)
    return m.group(1) if m else s.strip()

def order_by_trailing_number(items):
    """Sort items like QID1_1, QID1_2 numerically by the last number."""
    def key_func(x):
        m = re.findall(r'(\d+)', str(x))
        return (0, int(m[-1])) if m else (1, 9999)
    return sorted(items, key=key_func)

def clean_latin_square(series: pd.Series, keep_unassigned: bool = False) -> pd.Categorical:
    """Normalize latin-square codes to an ordered categorical."""
    valid_codes = ['SA/DB','SB/DA','DA/SB','DB/SA']
    pattern = r'(SA/DB|SB/DA|DA/SB|DB/SA)'

    s = series.astype(str).str.strip()
    s = s.str.replace('Latin Square Assignment', '', regex=False).str.strip()
    s_extracted = s.str.extract(pattern, expand=False)

    if keep_unassigned:
        s_extracted = s_extracted.fillna('Unassigned')

    cat_order = valid_codes + (['Unassigned'] if keep_unassigned else [])
    return pd.Categorical(s_extracted, categories=cat_order, ordered=True)

# =========================
# Load & normalize headers
# =========================
df_raw = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, header=0)
df = df_raw.copy()
df.columns = [extract_importid(c) for c in df_raw.columns]

# Required columns (robust detection)
pid_col = next((c for c in ['_recordId','_recordid','recordid','responseid','response id',
                            'participant_id','participantid'] if c in df.columns), None)
ls_col  = next((c for c in ['LatinSquareAssignment','latinSquareAssignment','LatinSquare','latinSquare']
                if c in df.columns), None)

# Pre-study piano experience (first QID1_* is used as PreQ1)
pre_cols = [c for c in df.columns
            if c.startswith('QID1_') or 'pre-study' in c.lower() or 'pre study' in c.lower()]
pre_cols = order_by_trailing_number(pre_cols)

if not pre_cols:
    # Fallback heuristic (rare): any column containing 'piano' & 'exp'
    pre_cols = [c for c in df.columns if ('piano' in c.lower() and 'exp' in c.lower())]

if not pre_cols:
    raise ValueError("Could not find any pre-study (QID1_*) columns in this sheet.")

pre1_col = pre_cols[0]

# =========================
# Build analysis table
# =========================
analysis = pd.DataFrame({
    'participant_id': df[pid_col] if pid_col else np.arange(len(df)),
    'latin_square':   df[ls_col]  if ls_col  else pd.NA,
    'PreQ1':          pd.to_numeric(df[pre1_col], errors='coerce'),
})

# Experience rule: rating >= 3 → experienced
analysis['piano_experienced'] = analysis['PreQ1'] >= 3

# Drop rows missing critical fields
analysis = analysis.dropna(subset=['latin_square', 'piano_experienced'])

# =========================
# Crosstab & plot
# =========================
analysis['latin_square_clean'] = clean_latin_square(analysis['latin_square'], keep_unassigned=False)

tab = (pd.crosstab(analysis['latin_square_clean'], analysis['piano_experienced'])
         .reindex(analysis['latin_square_clean'].cat.categories)
         .fillna(0)
         .astype(int))

# Ensure both True/False columns exist
cats = list(tab.index)
not_exp = tab.get(False, pd.Series([0]*len(cats), index=cats)).values
exp     = tab.get(True,  pd.Series([0]*len(cats), index=cats)).values

# Plot
x = np.arange(len(cats))
width = 0.6
plt.figure(figsize=(10, 6))
plt.bar(x, exp, width, bottom=not_exp, label='Experienced',
        color=COL_EXP, edgecolor=EDGE, linewidth=1)
plt.bar(x, not_exp, width, label='Not experienced',
        color=COL_NOT_EXP, edgecolor=EDGE, linewidth=1)

plt.xticks(x, cats)
plt.ylabel("Participants")
# plt.title("Latin-square assignment by piano experience")
plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=2, frameon=False)

plt.tight_layout(rect=[0, 0, 1, 0.92])
plt.savefig(SAVE_PATH, dpi=300, bbox_inches="tight")
plt.show()

print(f"Figure saved to: {SAVE_PATH.resolve()}")
