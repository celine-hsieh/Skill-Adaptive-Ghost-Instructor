import os
import json
import pandas as pd
import numpy as np
import re

# ====== Helper functions ======
def load_json(path):
    if os.path.getsize(path) == 0:  # file is empty
        print(f"Skip empty file: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None

def analyze_performance(ref_data, user_data,
                        w_p=0.7, w_t=0.2, w_f=0.1):
    ref_notes = ref_data["keyEvents"]
    user_notes = user_data["keyEvents"]

    if not ref_notes or not user_notes:
        return 0, 0, None, None, 100

    # === time alignment ===
    ref_start = ref_notes[0]["pressTime"]
    ref_end = ref_notes[-1]["pressTime"]
    user_start = user_notes[0]["pressTime"]
    user_end = user_notes[-1]["pressTime"]

    scale = (ref_end - ref_start) / (user_end - user_start)

    for note in user_notes:
        note["pressTime"] = ref_start + (note["pressTime"] - user_start) * scale

    total_notes = len(ref_notes)
    correct_pitch = 0
    correct_finger = 0
    timing_errors = []
    matched_user_idx = set()

    for i, ref in enumerate(ref_notes):
        ref_key = ref["keyName"]
        ref_time = ref["pressTime"]
        ref_finger = ref["finger"]

        candidates = [
            (j, note)
            for j, note in enumerate(user_notes)
            if j not in matched_user_idx
        ]
        if not candidates:
            continue

        # first find pitch same
        pitch_candidates = [
            (j, note) for j, note in candidates
            if note["keyName"] == ref_key
        ]
        if pitch_candidates:
            j, best_note = min(pitch_candidates, key=lambda x: abs(x[1]["pressTime"] - ref_time))
        else:
            # if no same pitch, then compare time
            j, best_note = min(candidates, key=lambda x: abs(x[1]["pressTime"] - ref_time))

        matched_user_idx.add(j)

        if best_note["keyName"] == ref_key:
            correct_pitch += 1
        if best_note["keyName"] == ref_key and best_note["finger"] == ref_finger:
            correct_finger += 1

        timing_errors.append(abs(best_note["pressTime"] - ref_time))

    # ==== three sub scores ====
    s_p = correct_pitch / total_notes
    s_f = correct_finger / total_notes
    # timing use "1 - average error / tolerance range" to normalize
    # assume 200ms is completely correct
    if timing_errors:
        mean_err = np.mean(timing_errors) * 1000  # ms
        scale = 500.0   # adjust decay speed
        s_t = np.exp(-mean_err / scale)
    else:
        mean_err = None
        s_t = 0

    # ==== Overall performance score ====
    S = w_p * s_p + w_t * s_t + w_f * s_f
    E = 1 - S  # error rate in [0,1]

    # ErrorRate (only consider Pitch+Finger, not Timing)
    S_pf = w_p * s_p + w_f * s_f + 0.2
    E_pf = 1 - S_pf

    finger_acc = s_f * 100
    pitch_acc = s_p * 100
    timing_acc = s_t * 100
    std_timing_error = np.std(timing_errors) * 1000 if timing_errors else None

    return pitch_acc, finger_acc, timing_acc, mean_err, std_timing_error, E * 100, E_pf * 100




def natural_sort_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

# ====== Batch processing ======
def process_all_users(user_root="./data/PianoKeyEvents/UserSample", ref_root="./data/PianoKeyEvents/Task"):
    results = []

    # Reference melodies
    ref_map = {
        "A": load_json(os.path.join(ref_root, "ghost_melody_C.json")),
        "B": load_json(os.path.join(ref_root, "ghost_melody_B.json")),
    }

    # Regex pattern for filename parsing
    pattern = re.compile(r"User(\d+)_(d|s)(R?\d+)_(A|B)\.json")

    for user_dir in sorted(os.listdir(user_root), key=natural_sort_key):
        dir_path = os.path.join(user_root, user_dir)
        if not os.path.isdir(dir_path):
            continue

        for file in sorted(os.listdir(dir_path), key=natural_sort_key):
            match = pattern.match(file)
            if not match:
                continue

            user_id, cond, trial, melody = match.groups()
            ref_data = ref_map[melody]
            user_data = load_json(os.path.join(dir_path, file))
            if user_data is None:  # skip empty or bad file
                continue

            pitch_acc, finger_acc, timing_acc, mean_timing_error, std_timing_error, error_rate, error_rate_pf = analyze_performance(ref_data, user_data)

            results.append({
                "UserID": int(user_id),
                "Condition": "Dynamic" if cond == "d" else "Static",
                "Trial": trial,  # "1", "2", or "R1", "R2"
                "Melody": melody,
                "PitchAcc(%)": round(pitch_acc, 2),
                "FingerAcc(%)": round(finger_acc, 2),
                "TimingAcc(%)": round(timing_acc, 2),
                "MeanTimingErr(ms)": round(mean_timing_error, 2) if mean_timing_error else None,
                "StdTimingErr(ms)": round(std_timing_error, 2) if std_timing_error else None,
                "ErrorRate(%)": round(error_rate, 2),
                "ErrorRate(P+F)%": round(error_rate_pf, 2),
            })

        print(f"{user_dir} is done")

    df = pd.DataFrame(results)
    print(f"All users processed, total {len(df)} records")
    return df

def pick_best_trials(df):
    best_rows = []
    
    # Trial type normalization, make "1"/"2" and "R1"/"R2" can be grouped
    def trial_group(trial):
        if trial.startswith("R"):
            return "R"
        else:
            return "N"  # normal
    
    # group by UserID, Condition, Melody, TrialGroup
    grouped = df.groupby(["UserID", "Condition", "Melody", df["Trial"].map(trial_group)])
    
    for _, group in grouped:
        if len(group) == 1:
            best_rows.append(group.iloc[0])
        else:
            # sort rule: first PitchAcc high, then FingerAcc high, then ErrorRate low
            group_sorted = group.sort_values(
                by=["PitchAcc(%)", "FingerAcc(%)", "ErrorRate(%)"],
                ascending=[False, False, True]
            )
            best_rows.append(group_sorted.iloc[0])
    
    return pd.DataFrame(best_rows)



# ====== Run ======
if __name__ == "__main__":
    df = process_all_users()
    print("Original data:", len(df))
    
    df_best = pick_best_trials(df)
    print("Best selected:", len(df_best))
    
    df_best.to_csv("./data/PianoKeyEvents/UserSample/UserStudy_Results_Best.csv", index=False)
    print(df_best)