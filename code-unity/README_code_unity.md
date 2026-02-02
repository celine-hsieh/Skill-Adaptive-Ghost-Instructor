# Unity Scripts (Read-Only)

This folder provides **readable Unity C# scripts** that illustrate how to implement a **skill-adaptive (performance-aware) ghost hand** for VR piano learning, including keyboard interaction, hand-motion capture utilities, and performance logging.

> **Note**: This package **does not include** Prefabs, Scenes, materials/animations/audio, or third-party packages. It is intended for **reading and reference** alongside the paper and demo video.

---

## Directory layout

```
code-unity/
├─ Scripts/                                   // Unity C# (read‑only, core logic)
│  ├─ Ghost/
│  │  ├─ GhostHandTransparencyController.cs   // Adaptive opacity (asymmetric EMA)
│  │  ├─ GhostPlaybackSync.cs                 // Play/pause, timeline, rate, progress events
│  │  ├─ PianoGhostPlayer.cs                  // Load keyEvents/animations; drive ghost hands & key audio
│  │  ├─ PianoGhostRecorder.cs                // Record author demo ghost motions
│  │  ├─ GhostFollower.cs                     // Align ghost/piano to scene (calibration helpers)
│  │  └─ GhostChunkController.cs              // (Optional) Segment / chunk navigation
│  │
│  ├─ Motion/
│  │  ├─ HandAnimationRecorderRuntime.cs      // 30 fps hand joint capture to AnimationClip/cache
│  │  ├─ HandJoint.cs                         // Joint indices & driving helpers
│  │  └─ HandCSVExporter.cs                   // Editor tool: export joint sequences to CSV
│  │
│  ├─ Metrics/
│  │  └─ UserEvaluation.cs                    // Per-event / per-chunk scores + target alpha logging
│  │
│  └─ Piano/
│     ├─ PianoKey.cs                          // Key metadata & state
│     ├─ PianoKeyTouchListener.cs             // Press/release events (with finger mapping)
│     ├─ KeyColliderTrigger.cs                // Collider triggers + audio bridge
│     └─ FingerIdentifier.cs                  // Finger IDs (Right 1–5, Left 6–10)
│
└─ README_code_unity.md                       // This file
```

---

## What this repository is

- **Goal**: Share the core logic and data flow behind the adaptive transparency controller and instrumentation so others can understand or re-implement it alongside the paper and demo video.  

---

## Version & dependencies (for readers who want to integrate)

- **Unity**: 2022.3 LTS (author’s development version)  
- **XR**: Meta/Oculus XR (All-in-One or XR Hands) — only needed in a full project  
- **UI**: TextMeshPro (if you hook progress/score labels)  
- **Others**: standard `AudioSource`, `Animator`, and Colliders

> `HandCSVExporter.cs` is **Editor-only** and lives under `Motion/Editor/`. You can also wrap it with `#if UNITY_EDITOR` if needed.

---

## How scripts use the data (mapping)

1) **Ghost playback & scoring**  
   - `PianoGhostPlayer` reads `keyEvents` (e.g., `keyName`, `pressTime`, `duration`, `fingerIndex`) from `../data/PianoKeyEvents/.../*.json`, triggers key audio and ghost animation in `../data/HandMotionClips/.../*.anim`. 
   - `UserEvaluation` computes `pitchScore / timeScore / fingerScore / totalScore` and `errorRate` per event/chunk, and logs the current `targetAlpha`. Example aggregate logs live in `../data/UserPerformanceLogs/User1/`.

2) **Scores → Opacity (adaptive)**  
   - `GhostHandTransparencyController` ingests error/score updates (e.g., `AddErrorRate(float e, float dt)`), applies **asymmetric EMA** (separate rise/decay factors), maps to opacity, and clamps to `[minAlpha, maxAlpha]`.

3) **Playback & alignment**  
   - `GhostPlaybackSync` controls play/pause, timeline, playback rate, and progress events (optionally bound to UI).  
   - `GhostFollower` keeps ghost/piano aligned to the scene (desk/piano calibration).

4) **Hand-motion utilities (author demo / tools)**  
   - `HandAnimationRecorderRuntime` records joint transforms at a fixed rate (default 30 fps) to `AnimationClip` or an in-memory cache.  
   - `HandCSVExporter` exports joint sequences to CSV from the Editor (supports translation/rotation normalization).

5) **Piano interaction**  
   - `PianoKey`, `PianoKeyTouchListener`, `KeyColliderTrigger`, `FingerIdentifier` manage key state, collisions, audio triggering, and finger ID mapping.

6) **Reference ghost (author) & Participant sample (one user)**  
    - Files in `../data/HandMotionClips/Task/` and `../data PianoKeyEvents/Task/` are **author/reference** (not participant). Use them to demonstrate playback without exposing raw participant motion.
    - Files under `../data/HandMotionClips/UserSample/User1/` and `../data/PianoKeyEvents/UserSample/User1/` are a **single, anonymized sample** provided only for illustration and basic figure reproduction.

---

## Data formats (under `../data/`)

**Keystrokes JSON (used by `PianoGhostPlayer`)**
```json
{
  "keyEvents": [
    {"keyName": "1C", "pressTime": 0.12, "duration": 0.30, "fingerIndex": 1},
    {"keyName": "1D", "pressTime": 0.55, "duration": 0.28, "fingerIndex": 2}
  ]
}
```

**Performance log JSON (produced by `UserEvaluation`)**
```json
{
  "entries": [
    {
      "pitchScore": 0.78,
      "timeScore": 0.83,
      "fingerScore": 0.72,
      "totalScore": 0.79,
      "errorRate": 0.21,
      "targetAlpha": 0.46,
      "timestamp": 123.45,
      "chunkIndex": 1,
      "countloop": 3
    }
  ]
}
```

**Hand‑motion CSV (Exports/HandCSV)**
```text
time (s), joint, px, py, pz, qx, qy, qz, qw
```

---

## Key parameters

- **Opacity bounds**:  
  `GhostHandTransparencyController.minAlpha / maxAlpha`
- **Asymmetric EMA**:  
  `GhostHandTransparencyController.AddErrorRate(e, dt)` uses separate **rise / decay** factors (fill in your λ↑ / λ↓)
- **Score weights** (total score):  
  `total = w_p * pitch + w_t * time + w_f * finger`
- **Timing tolerance**:  
  Used in `PianoGhostPlayer` scoring
- **Key naming / pitch mapping**:  
  e.g., `1C`, `1D`, … 

> The actural numbers see reported in paper.