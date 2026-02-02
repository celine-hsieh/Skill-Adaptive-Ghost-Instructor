
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import ttest_rel
import statsmodels.api as sm
from statsmodels.formula.api import ols
import matplotlib.ticker as mtick
import numpy as np

plt.rcParams.update({
    "axes.titlesize": 24,
    "axes.labelsize": 22,
    "xtick.labelsize": 20,
    "ytick.labelsize": 20,
    "legend.fontsize": 20,
    "legend.title_fontsize": 20
})

COL_DYNAMIC = "#1F77B4"
COL_STATIC  = "#FF7F0E"
EDGE        = "white"

ORDER_COND = ["Static", "Dynamic"]
palette = {"Dynamic": COL_DYNAMIC, "Static": COL_STATIC}

metrics = ["PitchAcc(%)", "FingerAcc(%)", "TimingAcc(%)", "ErrorRate(%)"]

df = pd.read_csv("./data/PianoKeyEvents/UserSample/UserStudy_Results_Best.csv")

def annotate_bar_values(ax, fmt="%.1f", offset=2):
    for p in ax.patches:
        v = p.get_height()
        if v is None or np.isnan(v):
            continue
        x = p.get_x() + p.get_width() / 2
        y = v
        va = "bottom" if v >= 0 else "top"
        pad = offset if v >= 0 else -offset
        ax.annotate(fmt % v, (x, y), ha="center", va=va,
                    xytext=(0, pad), textcoords="offset points")

def label_test_type(trial):
    if "R" in str(trial):
        return "Retention Test"
    else:
        return "Immediate Test"

df["TestType"] = df["Trial"].apply(label_test_type)

df_grouped = df.groupby(["UserID","Condition","Melody","TestType"]).mean(numeric_only=True).reset_index()

df_grouped = df_grouped[df_grouped["UserID"] != 10]
df_grouped.loc[df_grouped["UserID"] == 31, "UserID"] = 10

print("\nMerged data (Immediate vs Retention):")
print(df_grouped.head())

df_immediate = df_grouped[df_grouped["TestType"]=="Immediate Test"].set_index(["UserID","Condition","Melody"])
df_retention = df_grouped[df_grouped["TestType"]=="Retention Test"].set_index(["UserID","Condition","Melody"])

df_diff = df_retention[metrics] - df_immediate[metrics]
df_diff = df_diff.reset_index()
df_diff["TestType"] = "Retention Score"

print("\nRetention Score (first 5 rows):")
print(df_diff.head())

df_diff["Condition"] = pd.Categorical(df_diff["Condition"], categories=ORDER_COND, ordered=True)

fig, axes = plt.subplots(2, 2, figsize=(12, 10))
axes = axes.flatten()

titles = {
    "PitchAcc(%)": "Pitch Accuracy",
    "FingerAcc(%)": "Finger Accuracy",
    "TimingAcc(%)": "Timing Accuracy",
    "ErrorRate(%)": "Error Rate"
}

for i, metric in enumerate(metrics):
    sns.barplot(
        data=df_diff, x="Condition", y=metric,
        order=ORDER_COND,
        palette=palette,
        errorbar="se",
        err_kws=dict(color="black", linewidth=1.2),
        ax=axes[i],
        alpha=1.0
    )
    axes[i].axhline(0, color="black", linestyle="--")
    axes[i].set_title(f"{titles[metric]}")
    axes[i].set_ylabel("Retention Score (Δ)")
    axes[i].set_xlabel("")
    axes[i].yaxis.set_major_formatter(mtick.FormatStrFormatter("%.1f"))

plt.tight_layout()
plt.show()

for metric in metrics:
    print(f"\n==== {metric} ====")
    df_wide_diff = df_diff.pivot_table(index=["UserID","Melody"], columns="Condition", values=metric).reset_index()
    if "Dynamic" in df_wide_diff and "Static" in df_wide_diff:
        t, p = ttest_rel(df_wide_diff["Dynamic"], df_wide_diff["Static"])
        print(f"Paired t-test (Retention Score, {metric}, Dynamic vs Static): t={t:.3f}, p={p:.4f}")

    model_diff = ols(f"Q('{metric}') ~ C(Condition)", data=df_diff).fit()
    anova_table_diff = sm.stats.anova_lm(model_diff, typ=2)
    print("One-way ANOVA (Retention Score, Condition effect):")
    print(anova_table_diff)

summary_list = []
for metric in metrics:
    g = (df_diff.groupby("Condition")[metric]
         .agg(mean="mean", sd="std", n="count")
         .assign(se=lambda x: x["sd"] / np.sqrt(x["n"])))
    g["metric"] = metric
    summary_list.append(g.reset_index())

summary = pd.concat(summary_list, ignore_index=True)
print("\nRetention Score summary (mean ± SE):")
print(summary.assign(mean=lambda x: x["mean"].round(2),
                     sd=lambda x: x["sd"].round(2),
                     se=lambda x: x["se"].round(2)).to_string(index=False))

# summary.to_csv("RetentionScore_summary.csv", index=False)
# print("\n[Saved] RetentionScore_summary.csv")
