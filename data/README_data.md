# Data — Samples & Formats

This folder contains **tiny, anonymized samples** to illustrate data formats used by our Unity scripts and analysis.  
Full raw datasets are **not** included here.

> **Privacy.** The files in `UserSample/User1` and `UserPerformanceLogs/User1` are *illustrative only* and pseudonymized. Re‑identification is prohibited.

---

## Directory layout

```text
data/
├─ HandMotionClips/                        // Participate in the Motion Recording in Immediate & Retention Test
│  ├─ Exports/HandCSV/                     // CSV exports of joint trajectories
│  │  ├─ Ref_Melody_A.csv                  
│  │  ├─ Ref_Melody_B.csv                  
│  │  ├─ User1_Dynamic_Immediate_T1_Melody_B.csv
│  │  ├─ User1_Dynamic_Immediate_T2_Melody_B.csv
│  │  ├─ User1_Dynamic_Retention_T1_Melody_B.csv
│  │  ├─ User1_Dynamic_Retention_T2_Melody_B.csv
│  │  ├─ User1_Static_Immediate_T1_Melody_A.csv
│  │  ├─ User1_Static_Immediate_T2_Melody_A.csv
│  │  ├─ User1_Static_Retention_T1_Melody_A.csv
│  │  └─ User1_Static_Retention_T2_Melody_A.csv
│  │ 
│  ├─ Task/                                // Author/reference demo clips (no participants)
│  │  ├─ Right_HandAnimation_Melody_A.anim
│  │  ├─ Right_HandAnimation_Melody_B.anim
│  │ 
│  └─ UserSample/User1/                    // ONE anonymized participant sample (illustrative)
│     ├─ User1_s1_A.anim   // Static,  Immediate, T1, Melody A
│     ├─ User1_s2_A.anim   // Static,  Immediate, T2, Melody A
│     ├─ User1_sR1_A.anim  // Static,  Retention,  T1, Melody A
│     ├─ User1_sR2_A.anim  // Static,  Retention,  T2, Melody A
│     ├─ User1_d1_B.anim   // Dynamic, Immediate, T1, Melody B
│     ├─ User1_d2_B.anim   // Dynamic, Immediate, T2, Melody B
│     ├─ User1_dR1_B.anim  // Dynamic, Retention,  T1, Melody B
│     └─ User1_dR2_B.anim  // Dynamic, Retention,  T2, Melody B
│   
├─ PianoKeyEvents/                          // KeyEvent logs for participants in Immediate & Retention Test
│  ├─ Task/
│  │  ├─ ghost_melody_A.json                // Author ghost events (A)
│  │  └─ ghost_melody_B.json                // Author ghost events (B)
│  └─ UserSample/User1/
│     ├─ User1_s1_A.json  User1_s2_A.json   // Static, Immediate (A), T1/T2
│     ├─ User1_sR1_A.json User1_sR2_A.json  // Static, Retention  (A), T1/T2
│     ├─ User1_d1_B.json  User1_d2_B.json   // Dynamic, Immediate (B), T1/T2
│     └─ User1_dR1_B.json User1_dR2_B.json  // Dynamic, Retention  (B), T1/T2
│
├─ UserPerformanceLogs/                     // Participants Learning Process Record (User1 Example)
│  └─ User1/
│     ├─ User1_s_A.json                     // Aggregate log for Static / Melody A
│     └─ User1_d_B.json                     // Aggregate log for Dynamic / Melody B
│
└─ Surveys/
   └─ questionnaires_aggregated.xlsx        // Participants' Questionnaire Questions and Responses
```

---

## Data schemas (minimal)

### Keystrokes JSON (`PianoKeyEvents/*.json`)
```json
{
  "keyEvents": [
    { "keyName": "1C", "pressTime": 0.12, "duration": 0.30, "fingerIndex": 1 }
  ]
}
```
- `keyName`: string (e.g., `1C`, `1D`, …)  
- `pressTime`: seconds from clip start (float)  
- `duration`: seconds (float)  
- `fingerIndex`: optional; 1–5 right hand, 6–10 left hand

### Performance log JSON (`UserPerformanceLogs/*/*.json`)
```json
{
  "entries": [
    {
      "timestamp": 12.34,
      "chunkIndex": 1,
      "loopIndex": 3,
      "pitchScore": 0.78,
      "timeScore": 0.83,
      "fingerScore": 0.72,
      "totalScore": 0.79,
      "errorRate": 0.21,
      "targetAlpha": 0.46
    }
  ]
}
```

### Hand‑motion CSV (`HandMotionClips/Exports/HandCSV/*.csv`)
```text
time (s), joint, px, py, pz, qx, qy, qz, qw
```

---

## Naming conventions

- **User samples** use `User1_*` for clarity (a single participant example).  
- **Conditions**: `s` = Static, `d` = Dynamic; `R` = Retention (omit = Immediate); `1|2` = trial index (T1/T2).  
  - Example: `User1_dR2_B.anim` → Dynamic, Retention, T2, Melody B.

---

## Usage & limitations

- These samples are **for illustration and figure reproduction only**.  
- They are intentionally small and pseudonymized; do not attempt re‑identification.  
