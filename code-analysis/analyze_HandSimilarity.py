# -*- coding: utf-8 -*-
r"""
analyzeHandSimilarity.py — automatically select joints (avoid warning for each file) + unify time axis/mask

Notes:
- --angle-only：only calculate "direction similarity" (dir_cos_fw) and "angle error" (dir_mae_deg_fw), not pos/vel/DTW
- --no-pos：not calculate all position-related metrics (pos_*), only keep direction/velocity/DTW
- --dtw-signal {pos,dir,vel}：determine the signal source for DTW (position/direction/velocity)
- joints in thin before, use the same keys for both sides
- keep shift/linear/none time alignment, event radius/compare window, anchor relative coordinates, RMSE, optional DTW, --smoke, --debug

output:
./outputs/hand_similarity_summary.csv (based on ./data/HandMotionClips/UserSample)

Fast Test:
  python analyzeHandSimilarity.py --fast --skip-dtw --compare-seconds 4 --event-radius 0.25 --debug

Run first N:
  python analyzeHandSimilarity.py --smoke 12

Only compare "direction+velocity+DTW(direction)", not position:
  python analyzeHandSimilarity.py --fast --no-pos --with-dtw --dtw-signal dir --joints-auto tips --time-mode shift
"""

import os, re, glob, json, argparse
import numpy as np
import pandas as pd
from typing import Dict, Tuple, List

try:
    from tqdm.auto import tqdm
except Exception:
    def tqdm(iterable=None, **kwargs):
        return iterable if iterable is not None else range(kwargs.get("total", 0))

# ---------- small tool: standardize joint name (tolerant to various naming) ----------
def _canon_joint_name(base: str) -> str:
    s = base.strip()
    s = re.sub(r'^(right(hand)?[\.\-_]?)', '', s, flags=re.I)
    s = re.sub(r'^(left(hand)?[\.\-_]?)',  '', s, flags=re.I)
    s = re.sub(r'^(hand[\.\-_]?)',         '', s, flags=re.I)
    key = re.sub(r'[\.\-_ \t]', '', s).lower()
    synonyms = {
        'thumbtip': 'ThumbTip', 'thumbfingertip': 'ThumbTip', 'thumbdistal': 'ThumbTip',
        'indextip': 'IndexTip', 'indexfingertip': 'IndexTip', 'indexfinger': 'IndexTip', 'indexdistal': 'IndexTip',
        'middletip': 'MiddleTip','middlefingertip':'MiddleTip','middlefinger':'MiddleTip','middledistal':'MiddleTip',
        'ringtip': 'RingTip',    'ringfingertip': 'RingTip',  'ringfinger': 'RingTip',  'ringdistal': 'RingTip',
        'pinkytip':'PinkyTip','pinkyfingertip':'PinkyTip','littlefingertip':'PinkyTip','littletip':'PinkyTip','littlefinger':'PinkyTip','pinkydistal':'PinkyTip',
    }
    if key in synonyms: return synonyms[key]
    if key in ('wrist','handwrist','righthandwrist','lefthandwrist'): return 'Wrist'
    if key in ('palm','handpalm','righthandpalm','lefthandpalm'):     return 'Palm'
    toks = re.split(r'[._\- ]+', base)
    tl = [t.lower() for t in toks if t]
    if any('wrist'==t for t in tl): return 'Wrist'
    if any('palm'==t  for t in tl): return 'Palm'
    return re.sub(r'\s+', '', base).strip()

# ---------- read CSV (tolerant to various naming) ----------
def load_clip_csv(path: str, default_fps: float = 60.0) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    df = pd.read_csv(path, encoding="utf-8-sig")
    # time column
    time_col = next((c for c in ["time","Time","timestamp","Timestamp"] if c in df.columns), None)
    if time_col is None:
        first_col = df.columns[0]
        if np.issubdtype(df[first_col].dtype, np.number):
            time = pd.to_numeric(df[first_col], errors="coerce").astype(float).values
        else:
            time = (np.arange(len(df)) / float(default_fps)).astype(float)
    else:
        time = pd.to_numeric(df[time_col], errors="coerce").astype(float).values

    # X/Y/Z group
    AXIS_RES = [
        re.compile(r"^(?P<base>.*?)[\.\-_]?(?P<axis>[XYZxyz])$"),
        re.compile(r"^(?P<base>.*?)(_)(?P<axis>[XYZxyz])$"),
        re.compile(r"^(?P<base>.*?)(?P<axis>[XYZxyz])$"),
        re.compile(r"^(?P<base>.*?)(?:Position)?[\.\-_]?(?P<axis>[XYZxyz])$"),
    ]
    groups = {}
    for col in df.columns:
        if col == time_col: continue
        name = str(col).strip()
        if name.lower().startswith("unnamed"): continue
        s = pd.to_numeric(df[col], errors="coerce").astype(float)
        m = None
        for rx in AXIS_RES:
            m = rx.match(name)
            if m: break
        if not m: continue
        base_raw = m.group("base").rstrip("._- ").strip() or "Joint"
        axis = m.group("axis").upper()
        base = _canon_joint_name(base_raw)
        groups.setdefault(base, {})[axis] = s.values

    joints = {}
    for base, axes in groups.items():
        if all(ax in axes for ax in ("X","Y","Z")):
            T = min(len(axes["X"]), len(axes["Y"]), len(axes["Z"]), len(time))
            if T>1:
                arr = np.stack([axes["X"][:T], axes["Y"][:T], axes["Z"][:T]], axis=1).astype(np.float64)
                joints[base] = arr
    return time.astype(np.float64), joints

# ---------- read keyEvents ----------
def read_keyevents_json(path: str) -> List[dict]:
    if not path or not os.path.exists(path): return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ev = data.get("keyEvents", [])
    return sorted([{"t": float(e["pressTime"]), "key": str(e.get("keyName","")), "finger": int(e.get("finger",0))} for e in ev],
                  key=lambda x: x["t"])

# ---------- file name/path ----------
def parse_meta(basename: str):
    m = re.match(r'^(User\d+)_(Dynamic|Static)_(Immediate|Retention)_(T\d+)_Melody_([A-Z])$', basename)
    if m:
        return {"user": m.group(1), "cond": m.group(2), "test": m.group(3),
                "trial": m.group(4), "melody": f"Melody_{m.group(5)}"}
    return None

def get_task_json_path(meta, task_json_dir: str) -> str:
    letter = meta["melody"][-1]
    if letter == "B": return os.path.join(task_json_dir, "ghost_melody_B.json")
    if letter == "A": return os.path.join(task_json_dir, "ghost_melody_A.json")
    return os.path.join(task_json_dir, f"ghost_melody_{letter}.json")

def get_user_json_path(meta, user_json_root: str) -> str:
    cond_letter = "d" if meta["cond"]=="Dynamic" else "s"
    test_R = "R" if meta["test"]=="Retention" else ""
    trial_num = re.search(r'\d+', meta["trial"]).group()
    melody_letter = "B" if meta["melody"]=="Melody_B" else "A"
    base = f'{meta["user"]}_{cond_letter}{test_R}{trial_num}_{melody_letter}.json'
    udir = os.path.join(user_json_root, meta["user"])
    cand = os.path.join(udir, base)
    if os.path.exists(cand): return cand
    pats = glob.glob(os.path.join(udir, f'{meta["user"]}_{cond_letter}{test_R}{trial_num}_*.json'))
    return pats[0] if pats else ""

# ---------- time alignment ----------
def compute_time_mapping(user_events, ref_events, preroll_sec):
    tu0 = (user_events[0]["t"] if user_events else 0.0)
    tr0 = (ref_events[0]["t"]  if ref_events  else 0.0)
    t0u = max(0.0, tu0 - preroll_sec)
    t0r = max(0.0, tr0 - preroll_sec)
    n = min(len(user_events), len(ref_events))
    if n >= 3:
        Tu = np.array([e["t"] for e in user_events[:n]]) - t0u
        Tr = np.array([e["t"] for e in ref_events[:n]])  - t0r
        b, a = np.polyfit(Tu, Tr, 1)
    else:
        a, b = 0.0, 1.0
    return a, b, t0u, t0r

def resample_user_to_ref_timeline(t_user, J_user, t_ref, a, b, t0_user, t0_ref):
    u_times = (t_ref - t0_ref - a) / (b + 1e-12) + t0_user
    def interp_series(ts, arr, tq):
        out = np.empty((len(tq), arr.shape[1]))
        for d in range(arr.shape[1]):
            out[:, d] = np.interp(tq, ts, arr[:, d])
        return out
    return {k: interp_series(t_user, v, u_times) for k, v in J_user.items()}

def apply_time_mode(tU, JU, tR, a, b, t0u, t0r, mode: str):
    if mode == "linear":
        return resample_user_to_ref_timeline(tU, JU, tR, a, b, t0u, t0r)
    elif mode == "shift":
        return resample_user_to_ref_timeline(tU, JU, tR, 0.0, 1.0, t0u, t0r)
    elif mode == "none":
        return resample_user_to_ref_timeline(tU, JU, tR, 0.0, 1.0, 0.0, 0.0)
    else:
        raise ValueError("unknown time-mode")

# ---------- direction (only consider angle) ----------
def _pick_anchor_for_dirs(joints: dict, keys: list, prefer: str = "Wrist"):
    if prefer and prefer in joints:
        return joints[prefer]
    mats = [joints[k] for k in keys if k in joints]
    if not mats:
        anyk = next(iter(joints))
        return joints[anyk] * 0.0
    return np.mean(np.stack(mats, axis=0), axis=0)

def unit_directions(joints: dict, keys: list, prefer_anchor: str = "Wrist"):
    A = _pick_anchor_for_dirs(joints, keys, prefer_anchor)  # T×3
    out = {}
    for k in keys:
        V = joints[k] - A
        n = np.linalg.norm(V, axis=1, keepdims=True)
        out[k] = V / np.maximum(n, 1e-12)
    return out

def angle_only_metrics(JU: dict, JR: dict, keys: list, prefer_anchor: str = "Wrist"):
    Udir = unit_directions(JU, keys, prefer_anchor)
    Rdir = unit_directions(JR, keys, prefer_anchor)
    dots = []
    for k in keys:
        d = np.sum(Udir[k] * Rdir[k], axis=1)
        d = np.clip(d, -1.0, 1.0)
        dots.append(d)
    D = np.stack(dots, axis=1)                # T × K
    cos_per_frame = np.nanmedian(D, axis=1)   # across joints median
    dir_cos_fw = float(np.nanmedian(cos_per_frame))  # [-1,1]
    ang_deg = np.degrees(np.arccos(cos_per_frame))
    dir_mae_deg_fw = float(np.nanmedian(ang_deg))    # degree, smaller is better
    return dir_cos_fw, dir_mae_deg_fw

# ---------- other tools ----------
def build_event_mask(t_ref, ref_events, radius):
    if radius is None or radius <= 0 or not ref_events:
        return np.ones_like(t_ref, dtype=bool)
    ts = np.array([e["t"] for e in ref_events], dtype=float)
    m = np.zeros_like(t_ref, dtype=bool)
    for tt in ts:
        m |= (np.abs(t_ref - tt) <= radius)
    return m

def crop_compare_window(t_ref, start_ref, seconds):
    if seconds is None or seconds <= 0:
        return np.ones_like(t_ref, dtype=bool)
    end = start_ref + seconds
    return (t_ref >= start_ref) & (t_ref <= end)

def subtract_anchor(joints, anchor_name):
    if not anchor_name or anchor_name.lower() == "none": return joints
    if anchor_name not in joints: return joints
    A = joints[anchor_name]
    return {k: (V - A) for k, V in joints.items()}

def concat_series(jdict, keys):
    return np.concatenate([jdict[k] for k in keys], axis=1)

def cosine_global(A, B):
    a = A.reshape(-1); b = B.reshape(-1)
    den = np.linalg.norm(a)*np.linalg.norm(b)
    return np.nan if den < 1e-12 else float(np.dot(a,b)/den)

def cosine_global_centered(A, B):
    A2 = A - A.mean(axis=0, keepdims=True)
    B2 = B - B.mean(axis=0, keepdims=True)
    return cosine_global(A2, B2)

def cosine_framewise_median(A, B, centered=False):
    if centered:
        A = A - A.mean(axis=0, keepdims=True)
        B = B - B.mean(axis=0, keepdims=True)
    num = (A*B).sum(axis=1)
    den = np.linalg.norm(A,axis=1)*np.linalg.norm(B,axis=1) + 1e-12
    c = num/den
    zeroA = (np.linalg.norm(A,axis=1) < 1e-12)
    zeroB = (np.linalg.norm(B,axis=1) < 1e-12)
    c[(zeroA & zeroB)] = np.nan
    return float(np.nanmedian(c)) if np.any(~np.isnan(c)) else np.nan

def pair_rmse(A, B):
    diff = (A - B)
    return float(np.sqrt(np.mean(diff**2)))

def velocity_series(X, dt):
    if len(X) < 2 or dt <= 0: return np.zeros_like(X)
    V = np.zeros_like(X)
    V[1:-1] = (X[2:] - X[:-2]) / (2*dt)
    V[0]    = (X[1] - X[0]) / dt
    V[-1]   = (X[-1] - X[-2]) / dt
    return V

def ref_scale(JR_dict, keys):
    scales = []
    for k in keys:
        v = JR_dict[k]
        c = v - v.mean(axis=0, keepdims=True)
        d = np.linalg.norm(c, axis=1)
        scales.append(np.percentile(d, 95))
    s = float(np.median(scales)) if scales else 1.0
    return max(s, 1e-6)

def dtw_distance(A, B, band_frac=None):
    n, m = len(A), len(B)
    INF = 1e30
    dp = np.full((n+1, m+1), INF, dtype=np.float64)
    dp[0,0] = 0.0
    w = int(np.ceil(band_frac * max(n, m))) if (band_frac and band_frac>0) else None
    for i in range(1, n+1):
        ai = A[i-1]
        j0, j1 = 1, m
        if w is not None:
            j0, j1 = max(1, i-w), min(m, i+w)
        for j in range(j0, j1+1):
            cost = np.linalg.norm(ai - B[j-1])
            dp[i,j] = cost + min(dp[i-1,j], dp[i,j-1], dp[i-1,j-1])
    return dp[n,m] / (n + m)

# ---------- joints selection strategy ----------
def select_joint_keys(JU: Dict[str,np.ndarray], JR: Dict[str,np.ndarray],
                      joints_limit: List[str], mode: str) -> List[str]:
    U = set(JU.keys()); R = set(JR.keys())
    inter = sorted(U & R)
    if mode == "tips":
        inter = [k for k in inter if k.lower().endswith("tip")]
    if mode == "common":
        if inter: return inter
    elif mode == "tips":
        if inter: return inter
    elif mode == "none":
        pass
    if joints_limit:
        chosen = [k for k in joints_limit if (k in U and k in R)]
        if chosen: return chosen
    if inter: return inter
    return []

# ---------- parameters ----------
def build_argparser():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--csv-dir", default=r"./data/HandMotionClips/Exports/HandCSV")
    ap.add_argument("--task-json-dir", default=r"./data/HandMotionClips/Task/final")
    ap.add_argument("--user-json-root", default=r"./data/HandMotionClips/UserSample")
    ap.add_argument("--out-dir", default=r"./outputs")

    ap.add_argument("--preroll", type=float, default=0.25)
    ap.add_argument("--time-mode", default="shift", choices=["shift","linear","none"])
    ap.add_argument("--compare-seconds", type=float, default=6.0)
    ap.add_argument("--event-radius", type=float, default=0.0)
    ap.add_argument("--anchor", type=str, default="none")

    ap.add_argument("--joints", type=str, default="IndexTip,MiddleTip,RingTip,PinkyTip,ThumbTip")
    ap.add_argument("--joints-auto", type=str, default="common", choices=["common","tips","none"],
                    help="joints auto selection strategy")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--target-fps", type=int, default=30)
    ap.add_argument("--max-seconds", type=float, default=20.0)
    ap.add_argument("--smoke", type=int, default=0)

    ap.add_argument("--skip-dtw", action="store_true")
    ap.add_argument("--with-dtw", action="store_true")
    ap.add_argument("--dtw-band-frac", type=float, default=0.15)

    ap.add_argument("--angle-only", action="store_true",
                    help="only calculate direction similarity (dir_cos_fw) and angle error (dir_mae_deg_fw)")
    ap.add_argument("--no-pos", action="store_true",
                    help="not calculate all position-related metrics (pos_*), only keep direction/velocity/DTW")
    ap.add_argument("--dtw-signal", default="pos", choices=["pos","dir","vel"],
                    help="DTW signal source: position(pos), direction(dir), velocity(vel)")

    ap.add_argument("--debug", action="store_true")
    return ap

# ---------- main ----------
def main():
    args = build_argparser().parse_args()
    CSV_DIR, TASK_JSON_DIR, USER_JSON_ROOT, OUT_DIR = args.csv_dir, args.task_json_dir, args.user_json_root, args.out_dir
    os.makedirs(OUT_DIR, exist_ok=True)

    PREROLL_SEC     = float(args.preroll)
    TIME_MODE       = args.time_mode
    COMPARE_SECONDS = float(args.compare_seconds)
    EVENT_RADIUS    = float(args.event_radius)
    ANCHOR          = (args.anchor or "none").strip()

    FAST_MODE  = bool(args.fast) and not args.full
    SKIP_DTW   = args.skip_dtw or (FAST_MODE and not args.with_dtw)
    TARGET_FPS = int(args.target_fps)
    MAX_SECONDS = float(args.max_seconds) if args.max_seconds and args.max_seconds>0 else None
    SMOKE_FILES = int(args.smoke)
    DTW_BAND_FRAC = None if args.dtw_band_frac<=0 else float(args.dtw_band_frac)
    DEBUG = bool(args.debug)

    JOINTS_LIMIT = [s.strip() for s in (args.joints or "").split(",") if s.strip()]
    JOINTS_AUTO  = args.joints_auto

    # reference CSV
    ref_csv = {}
    for mel in ["Melody_B","Melody_C"]:
        p = os.path.join(CSV_DIR, f"Ref_{mel}.csv")
        if os.path.exists(p):
            t, J = load_clip_csv(p)
            if J: ref_csv[mel] = (t, J)
            else: print(f"[WARN] reference CSV has no valid joints: {p}")
        else:
            print(f"[WARN] reference CSV not found: {p}")

    # user CSV
    csv_files = sorted(glob.glob(os.path.join(CSV_DIR, "User*.csv")))
    if SMOKE_FILES>0: csv_files = csv_files[:SMOKE_FILES]

    rows = []
    pbar = tqdm(csv_files, desc="Analyzing clips", unit="clip")
    for path in pbar:
        base = os.path.splitext(os.path.basename(path))[0]
        meta = parse_meta(base)
        if not meta:
            if DEBUG: print(f"[SKIP:meta] file name cannot be parsed: {base}")
            continue
        mel = meta["melody"]
        if mel not in ref_csv:
            if DEBUG: print(f"[SKIP:ref] no reference CSV: {mel}")
            continue

        tU, JU = load_clip_csv(path)
        if not JU:
            if DEBUG: print(f"[SKIP:user] user CSV has no valid joints: {base}")
            continue
        tR, JR = ref_csv[mel]

        user_json = get_user_json_path(meta, USER_JSON_ROOT)
        task_json = get_task_json_path(meta, TASK_JSON_DIR)
        EU = read_keyevents_json(user_json)
        ER = read_keyevents_json(task_json)

        # align to ref time
        a,b,t0u,t0r = compute_time_mapping(EU, ER, PREROLL_SEC)
        JU_aln = apply_time_mode(tU, JU, tR, a, b, t0u, t0r, TIME_MODE)

        # relative coordinates (position-related metrics will use; direction-related metrics will not affect)
        JU_aln  = subtract_anchor(JU_aln, ANCHOR)
        JR_anch = subtract_anchor(JR,    ANCHOR)

        # joints selection
        sel_keys = select_joint_keys(JU_aln, JR_anch, JOINTS_LIMIT, JOINTS_AUTO)
        if not sel_keys:
            if DEBUG:
                print(f"[SKIP:joints] {base}: user has {len(JU_aln)} joints, ref has {len(JR_anch)} joints, but intersection is 0.")
            continue
        if DEBUG:
            print(f"[INFO] {base}: joints = {', '.join(sel_keys[:20])}" + (" ..." if len(sel_keys)>20 else ""))

        # downsample (use the same keys for both sides)
        def thin(jdict, times_ref):
            if not FAST_MODE:
                out = {k: jdict[k] for k in sel_keys}
                idx = np.arange(len(times_ref), dtype=int)
                return out, times_ref, idx
            dt = np.median(np.diff(times_ref)) if len(times_ref)>1 else 1/60.0
            src_fps = max(1.0 / max(dt,1e-6), 1.0)
            step = max(1, int(round(src_fps / max(1, TARGET_FPS))))
            max_frames = int(MAX_SECONDS*src_fps) if MAX_SECONDS else None
            N = len(times_ref)
            end = N if max_frames is None else min(N, max_frames)
            idx = np.arange(0, end, step, dtype=int)
            t_new = times_ref[idx]
            out = {k: jdict[k][idx] for k in sel_keys}
            return out, t_new, idx

        JU_rs, tR_thin,  idxU = thin(JU_aln, tR)
        JR_thin, tR_thin2,idxR = thin(JR_anch, tR)

        # sync index
        if not np.array_equal(idxU, idxR):
            common = np.intersect1d(idxU, idxR)
            if len(common)==0:
                if DEBUG:
                    print(f"[SKIP:index] {base}: downsampled index has no intersection (|idxU|={len(idxU)}, |idxR|={len(idxR)})")
                continue
            mapU = {v:i for i,v in enumerate(idxU)}
            mapR = {v:i for i,v in enumerate(idxR)}
            selU = np.array([mapU[v] for v in common], dtype=int)
            selR = np.array([mapR[v] for v in common], dtype=int)
            for k in sel_keys:
                JU_rs[k] = JU_rs[k][selU]
                JR_thin[k] = JR_thin[k][selR]
            tR_used = tR[common]
        else:
            tR_used = tR_thin

        L = len(tR_used)
        if L == 0:
            if DEBUG: print(f"[SKIP:L0] {base}: tR_used length is 0")
            continue

        # mask (build on original tR, then project to downsampled)
        mask_win_full = crop_compare_window(tR, start_ref=t0r, seconds=COMPARE_SECONDS)
        mask_evt_full = build_event_mask(tR, ER, radius=EVENT_RADIUS)
        mask_full = mask_win_full & mask_evt_full

        idx_used = idxU
        if len(idx_used)==0:
            if DEBUG: print(f"[SKIP:idx] {base}: idx is empty")
            continue

        if idx_used.max() >= len(mask_full):
            mask = np.ones(L, dtype=bool)
        else:
            mask = mask_full[idx_used]

        if not mask.any():
            if DEBUG:
                print(f"[SKIP:mask] {base}: window_true={int(mask_win_full.sum())}, event_true={int(mask_evt_full.sum())}, after_thin_true={int(mask.sum())}")
            continue

        for k in sel_keys:
            JU_rs[k]   = JU_rs[k][mask]
            JR_thin[k] = JR_thin[k][mask]
        tR_masked = tR_used[mask]
        if len(tR_masked) < 2:
            if DEBUG: print(f"[SKIP:len] {base}: after mask, sample is too few ({len(tR_masked)})")
            continue

        # ===== metrics =====
        prefer_anchor_for_dir = ANCHOR if ANCHOR.lower() != "none" else "Wrist"

        if args.angle_only:
            # only calculate direction (fastest)
            dir_cos_fw, dir_mae_deg_fw = angle_only_metrics(JU_rs, JR_thin, sel_keys, prefer_anchor_for_dir)
            row = {
                **meta,
                "clip": base,
                "time_mode": TIME_MODE,
                "compare_start_ref": float(t0r),
                "compare_seconds": float(COMPARE_SECONDS),
                "event_radius": float(EVENT_RADIUS),
                "anchor": ANCHOR,
                "n_timepoints": int(len(tR_masked)),
                "n_joints": int(len(sel_keys)),
                "joints_used": "|".join(sel_keys),

                "dir_cos_fw": dir_cos_fw,            # [-1,1]
                "dir_mae_deg_fw": dir_mae_deg_fw     # deg, smaller is better
            }
            rows.append(row)
        else:
            dt_ref = float(np.median(np.diff(tR_masked))) if len(tR_masked)>1 else 1/60.0

            # merge series (velocity, DTW will use)
            U_all  = concat_series(JU_rs, sel_keys)   # T × (3K)
            R_all  = concat_series(JR_thin, sel_keys)

            # velocity-related
            Uv = velocity_series(U_all, dt_ref)
            Rv = velocity_series(R_all, dt_ref)
            vel_rmse          = pair_rmse(Uv, Rv)
            vel_rmse_norm     = vel_rmse / (ref_scale(JR_thin, sel_keys) / max(dt_ref,1e-6))
            vel_cos_fw        = cosine_framewise_median(Uv, Rv, centered=False)
            vel_cos_fw_center = cosine_framewise_median(Uv, Rv, centered=True)

            # direction-related
            dir_cos_fw, dir_mae_deg_fw = angle_only_metrics(JU_rs, JR_thin, sel_keys, prefer_anchor_for_dir)

            # position-related (determined by --no-pos)
            pos_vals = {}
            if not args.no_pos:
                scale  = ref_scale(JR_thin, sel_keys)
                pos_vals = {
                    "pos_cos_raw":       cosine_global(U_all, R_all),
                    "pos_cos_center":    cosine_global_centered(U_all, R_all),
                    "pos_cos_fw_raw":    cosine_framewise_median(U_all, R_all, centered=False),
                    "pos_cos_fw_center": cosine_framewise_median(U_all, R_all, centered=True),
                    "pos_rmse":          pair_rmse(U_all, R_all),
                    "pos_rmse_norm":     pair_rmse(U_all, R_all) / scale,
                }

            # DTW (determined by --dtw-signal)
            if SKIP_DTW:
                dtw_mean = np.nan
            else:
                sig = args.dtw_signal
                if sig == "pos":
                    A, B = U_all, R_all
                elif sig == "vel":
                    A, B = Uv, Rv
                else:  # "dir"
                    Udir = unit_directions(JU_rs, sel_keys, prefer_anchor_for_dir)
                    Rdir = unit_directions(JR_thin, sel_keys, prefer_anchor_for_dir)
                    A = concat_series(Udir, sel_keys)
                    B = concat_series(Rdir, sel_keys)
                dtw_mean = dtw_distance(A, B, band_frac=DTW_BAND_FRAC)

            row = {
                **meta,
                "clip": base,
                "time_mode": TIME_MODE,
                "compare_start_ref": float(t0r),
                "compare_seconds": float(COMPARE_SECONDS),
                "event_radius": float(EVENT_RADIUS),
                "anchor": ANCHOR,
                "n_timepoints": int(len(tR_masked)),
                "n_joints": int(len(sel_keys)),
                "joints_used": "|".join(sel_keys),

                # velocity
                "vel_cos_fw":        vel_cos_fw,
                "vel_cos_fw_center": vel_cos_fw_center,
                "vel_rmse":          vel_rmse,
                "vel_rmse_norm":     vel_rmse_norm,

                # direction
                "dir_cos_fw":        dir_cos_fw,
                "dir_mae_deg_fw":    dir_mae_deg_fw,

                # DTW
                "dtw_mean":          dtw_mean,
            }
            if not args.no_pos:
                row.update(pos_vals)

            rows.append(row)

        pbar.set_postfix_str(f'{meta["user"]} {meta["cond"]}/{meta["test"]} {meta["trial"]} {meta["melody"]} | T={len(tR_masked)} joints={len(sel_keys)}')

    # save
    res = pd.DataFrame(rows)
    out_path = os.path.join(OUT_DIR, "hand_similarity_summary.csv")
    res.to_csv(out_path, index=False)
    print("Saved:", out_path)

    if len(res):
        # according to the actual field existence, list the statistics
        cols_to_report = [
            "pos_cos_raw","pos_cos_center","pos_cos_fw_raw","pos_cos_fw_center",
            "vel_cos_fw","vel_cos_fw_center","pos_rmse_norm","vel_rmse_norm",
            "dir_cos_fw","dir_mae_deg_fw","dtw_mean"
        ]
        for col in cols_to_report:
            if col in res.columns and res[col].notna().any():
                s = res[col].dropna()
                print(f"[STAT] {col}: n={len(s)} mean={s.mean():.3f} median={s.median():.3f} min={s.min():.3f} max={s.max():.3f}")

    print("Done.")

if __name__ == "__main__":
    main()
