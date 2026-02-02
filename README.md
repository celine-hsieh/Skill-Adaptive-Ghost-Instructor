# Skill‑Adaptive Ghost Instructor

This package contains **source code, tiny anonymized data samples, and documentation** accompanying the paper.

> We share **readable Unity scripts** and **minimal example data** to understand and reproduce the reported figures.  
> This is **not a runnable Unity project** (no Scenes/Prefabs/materials/audio).

---

## Directory layout

```
Supplementary Material/
├─  code-unity/              // Unity C# scripts (read‑only logic; no scenes/assets)
├─  code-analysis/           // Scripts to reproduce tables/figures
├─  data/                    // Tiny anonymized samples (formats & examples)
├─  outputs/                 // Outputs from code-analysis
└─  README.md                // this file
```

### Highlights

- **code‑unity/** — Adaptive opacity controller, playback/sync, piano interaction, motion utilities, and performance logging. See `code‑unity/README_code‑unity.md`.  
- **data/** — Small **illustrative** samples only: ghost reference clips/events, one user sample, and aggregate logs. See `data/README_data.md`.  
- **code‑analysis/** — If included, provides scripts/notebooks to regenerate key tables/plots from `data/` (aggregated forms). See `code‑analysis/README_code‑analysis.md`.

---

## Privacy & access policy

- Data here are **pseudonymized examples** (User1) for illustration only; **re‑identification is prohibited**.  
- Full raw motion/keystroke datasets are **not public**; contact the authors for controlled access if applicable.

---

## Usage & limitations

- These samples are **for illustration and figure reproduction only**.  
- They are intentionally small and pseudonymized; do not attempt re‑identification.  
