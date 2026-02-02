
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
# Import AnovaRM for Repeated-Measures analysis
from statsmodels.stats.anova import AnovaRM
# Removed ols and sm.stats.anova_lm imports as they are no longer used

sns.set_theme(style="whitegrid")
plt.rcParams.update({
    "axes.titlesize": 22,
    "axes.labelsize": 20,
    "xtick.labelsize": 18,
    "ytick.labelsize": 18,
    "legend.fontsize": 18,
    "legend.title_fontsize": 18
})

PALETTE_TEST = {"Immediate": "#8fc6d1", "Retention": "#356f96"}
HUE_ORDER = ["Immediate", "Retention"]
ORDER_COND = ["Static", "Dynamic"]

# Load data
df = pd.read_csv("./data/PianoKeyEvents/UserSample/UserStudy_Results_Best.csv")
print("Data loaded:", df.shape)
print(df.head())

def label_test_type(trial):
    t = str(trial)
    return "Retention" if "R" in t else "Immediate"

df["TestType"] = df["Trial"].apply(label_test_type)

# Aggregate data by subject, condition, melody, and test type
df_grouped = (
    df.groupby(["UserID", "Condition", "Melody", "TestType"], as_index=False)
      .mean(numeric_only=True)
)

df_grouped = df_grouped[df_grouped["UserID"] != 10]
df_grouped.loc[df_grouped["UserID"] == 31, "UserID"] = 10

df_grouped["Condition"] = pd.Categorical(df_grouped["Condition"], categories=ORDER_COND)
df_grouped["TestType"]  = pd.Categorical(df_grouped["TestType"],  categories=HUE_ORDER)

print("\nMerged data (Immediate vs Retention):")
print(df_grouped.head())

print("\nMeans by Condition × TestType:")
print(
    df_grouped.groupby(["Condition","TestType"])[
        ["PitchAcc(%)","FingerAcc(%)","TimingAcc(%)","ErrorRate(%)"]
    ].mean()
)

metrics = {
    "PitchAcc(%)":  "Pitch Accuracy",
    "FingerAcc(%)": "Finger Accuracy",
    "TimingAcc(%)": "Timing Accuracy",
    "ErrorRate(%)": "Error Rate"
}

fig, axes = plt.subplots(1, 4, figsize=(20, 5), sharey=False)
axes = axes.flatten()

for ax, (metric, title) in zip(axes, metrics.items()):
    sns.barplot(
        data=df_grouped,
        x="Condition", y=metric, hue="TestType",
        order=ORDER_COND, hue_order=HUE_ORDER, palette=PALETTE_TEST,
        errorbar="se", capsize=0.2, ax=ax
    )
    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel("%" if "Error" not in title else "Error (%)")
    ax.set_ylim(0, 100)
    leg = ax.get_legend()
    if leg is not None:
        leg.remove()

handles = [Patch(facecolor=PALETTE_TEST[h], label=h) for h in HUE_ORDER]
fig.legend(handles, HUE_ORDER, loc="upper center", ncol=2)

plt.tight_layout(rect=[0, 0, 1, 0.90])
plt.show()

# --- MODIFIED STATISTICAL ANALYSIS SECTION ---
# The analysis is corrected to a Two-way Repeated-Measures ANOVA
# using AnovaRM to respect the within-subject structure of Condition and TestType.

print("\n\n===== Two-way Repeated-Measures ANOVA =====")

# Removed the partial_eta_squared function as AnovaRM provides effect size measures

for metric, title in metrics.items():
    print(f"\n----- {title} -----")

    # Initialize the Repeated Measures ANOVA model
    aovrm = AnovaRM(
        data=df_grouped,
        depvar=metric,        # Dependent Variable (the metric being tested)
        subject='UserID',     # Subject Identifier (defines the repeated measures)
        within=['Condition', 'TestType'] # Within-Subject Factors
    )
    
    # Fit the model and print the ANOVA table
    res = aovrm.fit()
    print(res.anova_table.round(4))
