import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.formula.api import ols
from matplotlib.lines import Line2D

plt.rcParams.update({
    "axes.titlesize": 26,
    "axes.labelsize": 24,
    "xtick.labelsize": 22,
    "ytick.labelsize": 22,
    "legend.fontsize": 22,
    "legend.title_fontsize": 22
})

# ---- Colors (colorblind-friendly: Okabe–Ito) ----
COL_NOT_EXP = "#a2c2aa"  # green
COL_EXP     = "#e0c379"  # yellow

# Fixed colors and order
PALETTE = {
    "Non-experienced": COL_NOT_EXP,  # "#a2c2aa"
    "Experienced":     COL_EXP       # "#e0c379"
}
HUE_ORDER = ["Non-experienced", "Experienced"]
HUE2_ORDER = ["Experienced", "Non-experienced"]
COND_ORDER = ["Static", "Dynamic"]
MARKERS   = {"Non-experienced": "o", "Experienced": "s"}
# ======================================================
# 1. Performance Data
# ======================================================
df = pd.read_csv("./data/PianoKeyEvents/UserSample/UserStudy_Results_Best.csv")

# ======================================================
# 2. Survey Data
# ======================================================
survey = pd.read_excel(
    r"./data/Surveys/questionnaires_aggregated.xlsx",
    header=1,
    nrows=32,
    skiprows=[2]
)

survey = survey[['ResponseId', 'Pre-study Question_1']].dropna()
survey["UserID"] = (
    survey["ResponseId"]
    .astype(str)
    .str.extract(r'(\d+)')
    .dropna()
    .astype(int)
)
survey["Experience"] = survey['Pre-study Question_1'].astype(int).apply(
    lambda x: "Experienced" if x >= 3 else "Non-experienced"
)

# ======================================================
# 3. Merge
# ======================================================
df = df.merge(survey[["UserID", "Experience"]], on="UserID", how="inner")
df["Experience"] = pd.Categorical(df["Experience"], categories=HUE_ORDER, ordered=True)
df["Condition"]  = pd.Categorical(df["Condition"],  categories=COND_ORDER, ordered=True)
# ======================================================
# 4. Plot multiple subplots
# ======================================================
metrics = ["PitchAcc(%)", "FingerAcc(%)", "TimingAcc(%)", "ErrorRate(%)"]
titles = {
    "PitchAcc(%)": "Pitch Accuracy",
    "FingerAcc(%)": "Finger Accuracy",
    "TimingAcc(%)": "Timing Accuracy",
    "ErrorRate(%)": "Error Rate"
}

fig, axes = plt.subplots(2, 2, figsize=(12, 10))

for ax, metric in zip(axes.flatten(), metrics):
    sns.pointplot(
        data=df,
        x="Condition", y=metric,
        order=COND_ORDER,
        hue="Experience",
        hue_order=HUE_ORDER,
        palette=PALETTE,
        dodge=0,
        markers=[MARKERS[h] for h in HUE_ORDER],
        join=True,
        errorbar="se",
        errwidth=1.2,
        ax=ax
    )

    ax.set_title(f"{titles[metric]}")
    ax.set_ylim(0, 100 if "%" in metric else None)
    ax.legend_.remove()
    ax.set_xlabel("")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)

# Shared legend (top, average layout)
legend_handles = [
    Line2D([0],[0], color=PALETTE[name], marker=MARKERS[name], linestyle='-',
           label=name, markersize=8)
    for name in HUE2_ORDER
]

handles, labels = ax.get_legend_handles_labels()
fig.legend(
    handles=legend_handles,
    loc="upper center",
    ncol=len(HUE_ORDER),
    frameon=False,
    fontsize=20
)
# plt.title("Dynamic vs Static × Experience")
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.show()
