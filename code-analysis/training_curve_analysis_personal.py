import os
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# ====== Config ======
ROOT_FOLDER = './data/UserPerformanceLogs'
PHASE_INDEXES = [0, 1, 2]   # will save one figure for each phase
NUM_LOOPS_DEFAULT = 10      # default split how many loops

# ====== Helpers ======
def load_entries(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('entries', [])

def process_one_phrase(user_id, base_name, entries, phase_index, out_dir_user, num_loops_default=10):
    # filter by chunkIndex=phase_index
    entries = sorted(entries, key=lambda e: e.get('timestamp', 0))
    chunk_groups = {}
    for e in entries:
        idx = e.get('chunkIndex')
        chunk_groups.setdefault(idx, []).append(e)

    filtered = chunk_groups.get(phase_index, [])
    if not filtered:
        print(f"[User{user_id}] {base_name} has no data for chunkIndex={phase_index}, skip this phase")
        return

    # split loop (avoid empty segments, and not exceed data length)
    num_loops = min(num_loops_default, max(1, len(filtered)))
    raw_loops = np.array_split(filtered, num_loops)
    loops = [loop for loop in raw_loops if len(loop) > 0]
    if not loops:
        print(f"[User{user_id}] {base_name} phase {phase_index} split loop has no valid data, skip")
        return

    cmap = plt.cm.get_cmap('tab10', len(loops))

    # ---- shared legend element (one color for each loop)----
    legend_elements = [
        Line2D([0], [0], marker='o', linestyle='-', color=cmap(i-1), label=f'Loop {i}')
        for i in range(1, len(loops)+1)
    ]

    # ====== Figure 1: four scores ======
    metrics = [
        ('pitchScore',  'Pitch Score'),
        ('timeScore',   'Time Score'),
        ('fingerScore', 'Finger Score'),
        ('totalScore',  'Total Score'),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True, constrained_layout=False)
    axes = axes.flatten()

    for ax, (key, title) in zip(axes, metrics):
        for i, loop in enumerate(loops, start=1):
            ts   = [e.get('timestamp', np.nan) for e in loop]
            vals = [e.get(key, np.nan)        for e in loop]
            ax.plot(ts, vals, marker='o', color=cmap(i-1))
        ax.set_title(f'{title} over Time (Phase {phase_index})')
        ax.set_xlabel('Timestamp (s)')
        ax.set_ylabel(title)
        ax.grid(True)

    # shared legend at the top center; rect leave a little space for legend, avoid big white space
    fig.legend(handles=legend_elements, loc='upper center',
               bbox_to_anchor=(0.5, 1.0), ncol=min(len(legend_elements), 10),
               fontsize='small', frameon=True)
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.95])  # top=0.90 for subplots
    fig1_path = os.path.join(out_dir_user, f'{base_name}_phase{phase_index}.jpg')
    fig.savefig(fig1_path, format='jpg', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"[User{user_id}] Figure saved: {fig1_path}")

    # ====== Figure 2: errorRate / targetAlpha ======
    metrics2 = [
        ('errorRate',   'Error Rate'),
        ('targetAlpha', 'Target Alpha'),
    ]
    fig2, axes2 = plt.subplots(1, 2, figsize=(14, 6), sharex=True, constrained_layout=False)
    axes2 = axes2.flatten()

    for ax, (key, title) in zip(axes2, metrics2):
        for i, loop in enumerate(loops, start=1):
            ts   = [e.get('timestamp', np.nan) for e in loop]
            vraw = [e.get(key, None) for e in loop]
            vals = [np.nan if (v is None) else v for v in vraw]
            if np.all(np.isnan(vals)):
                continue
            ax.plot(ts, vals, marker='o', color=cmap(i-1))
        ax.set_title(f'{title} over Time (Phase {phase_index})')
        ax.set_xlabel('Timestamp (s)')
        ax.set_ylabel(title)
        ax.grid(True)

    fig2.legend(handles=legend_elements, loc='upper center',
                bbox_to_anchor=(0.5, 1.0), ncol=min(len(legend_elements), 10),
                fontsize='small', frameon=True)
    fig2.tight_layout(rect=[0.02, 0.02, 0.98, 0.88])  # adjust height of two figures
    fig2_path = os.path.join(out_dir_user, f'{base_name}_phase{phase_index}_error_alpha_grid.jpg')
    fig2.savefig(fig2_path, format='jpg', dpi=300, bbox_inches='tight')
    plt.close(fig2)
    print(f"[User{user_id}] Figure saved: {fig2_path}")

def process_one_json(user_id, json_path):
    base_name = os.path.splitext(os.path.basename(json_path))[0]
    try:
        entries = load_entries(json_path)
    except Exception as e:
        print(f"[User{user_id}] Failed to load: {json_path} | Error: {e}")
        return

    if not entries:
        print(f"[User{user_id}] No entries, skip: {json_path}")
        return

    out_dir_user = os.path.join('./python/plots', f'User{user_id}')
    os.makedirs(out_dir_user, exist_ok=True)

    # run for phase 0/1/2
    for phase_index in PHASE_INDEXES:
        process_one_phrase(
            user_id=user_id,
            base_name=base_name,
            entries=entries,
            phase_index=phase_index,
            out_dir_user=out_dir_user,
            num_loops_default=NUM_LOOPS_DEFAULT
        )

# ====== Batch over User1~User31 ======
def main():
    for uid in range(1, 32):
        user_folder = os.path.join(ROOT_FOLDER, f'User{uid}')
        if not os.path.isdir(user_folder):
            print(f"[User{uid}] Folder not found, skip: {user_folder}")
            continue

        json_files = [f for f in os.listdir(user_folder) if f.lower().endswith('.json')]
        if not json_files:
            print(f"[User{uid}] No .json file, skip.")
            continue

        for fname in sorted(json_files):
            fpath = os.path.join(user_folder, fname)
            process_one_json(uid, fpath)

if __name__ == "__main__":
    main()
