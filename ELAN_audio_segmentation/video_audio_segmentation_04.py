import os
import pympi
import auditok
import tkinter as tk
from pydub import AudioSegment
from tkinter import filedialog, messagebox


def process_file(input_file, buffer_value, max_silence, min_dur, tier_suffix, energy_threshold):
    # --- Step 1: Detect whether input is video ---
    ext = os.path.splitext(input_file)[1].lower()
    is_video = ext in [".mp4", ".mov", ".avi", ".mkv"]

    # --- Step 2: Extract audio if needed ---
    if is_video:
        temp_audio = input_file + "_temp_audio.wav"
        AudioSegment.from_file(input_file).export(temp_audio, format="wav")
        audio_file = temp_audio
    else:
        audio_file = input_file

    # --- Step 3: Force-convert to 16-bit PCM WAV (auditok requirement) ---
    converted_audio = input_file + "_pcm.wav"
    AudioSegment.from_file(audio_file).set_sample_width(2).export(converted_audio, format="wav")
    audio_file = converted_audio

    # --- Step 4: Detect speech regions ---
    speech_regions = auditok.split(
        audio_file,
        energy_threshold=energy_threshold,
        max_silence=max_silence
    )

    regions = sorted([(int(r.start * 1000), int(r.end * 1000)) for r in speech_regions])

    audio = AudioSegment.from_file(audio_file)
    audio_len_ms = len(audio)

    # --- Step 5: Create dynamic tier names ---
    default_tier = f"MJK@{tier_suffix}"
    translation_tier = f"TPI@{tier_suffix}"
    eng_tier = f"ENG@{tier_suffix}"

    # --- Step 6: Create EAF ---
    eaf = pympi.Elan.Eaf(file_path=None)
    
    # Remove auto-created default tier if present
    if "default" in eaf.get_tier_names():
        eaf.remove_tier("default")

    eaf.add_linguistic_type("ts")
    eaf.add_linguistic_type("tl", constraints="Symbolic_Association", timealignable=False)

    # Add tiers
    eaf.add_tier(default_tier, "ts")
    eaf.add_tier(translation_tier, "tl", parent=default_tier)
    eaf.add_tier(eng_tier, "tl", parent=default_tier)

    BUFFER = buffer_value
    MIN_DUR = min_dur

    # --- Step 7: Extend regions with buffer ---
    extended = []
    for i, (start_ms, end_ms) in enumerate(regions):
        left_gap = float("inf") if i == 0 else start_ms - regions[i - 1][1]
        right_gap = float("inf") if i == len(regions) - 1 else regions[i + 1][0] - end_ms

        new_start = start_ms - BUFFER if left_gap > BUFFER else start_ms
        new_end = end_ms + BUFFER if right_gap > BUFFER else end_ms

        new_start = max(0, new_start)
        new_end = min(audio_len_ms, new_end)

        if new_end <= new_start:
            new_end = min(audio_len_ms, new_start + MIN_DUR)

        extended.append([new_start, new_end])

    # --- Step 8: Resolve overlaps ---
    i = 0
    while i < len(extended) - 1:
        a_start, a_end = extended[i]
        b_start, b_end = extended[i + 1]

        if a_end > b_start:
            mid = (a_end + b_start) // 2
            new_a_end = max(a_start, mid)
            new_b_start = min(b_end, max(new_a_end, mid))

            if new_b_start >= b_end:
                b_end = min(audio_len_ms, new_b_start + MIN_DUR)

            extended[i] = [a_start, new_a_end]
            extended[i + 1] = [new_b_start, b_end]

            if i > 0:
                i -= 1
                continue
        i += 1

    # --- Step 9: Add annotations ---
    for start_ms, end_ms in extended:
        eaf.add_annotation(default_tier, start=start_ms, end=end_ms, value="")
        eaf.add_ref_annotation(translation_tier, default_tier, value="", time=start_ms)
        eaf.add_ref_annotation(eng_tier, default_tier, value="", time=start_ms)

    # --- Step 10: Link the media file ---
    mime_map = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg"
    }
    mimetype = mime_map.get(ext, "application/octet-stream")

    eaf.add_linked_file(os.path.basename(input_file), mimetype=mimetype)

    # --- Step 11: Save EAF ---
    output_file = os.path.splitext(input_file)[0] + ".eaf"
    eaf.to_file(output_file)

    # --- Step 12: Cleanup ---
    if is_video and os.path.exists(temp_audio):
        os.remove(temp_audio)

    if os.path.exists(converted_audio):
        os.remove(converted_audio)

    # --- Step 13: UI feedback ---
    num_annotations = len(extended)
    messagebox.showinfo("Done", f"Annotations written to {output_file}\nNumber of annotations: {num_annotations}")
    annotation_label.config(text=f"ELAN file saved. Number of annotations: {num_annotations}")


def select_file():
    filename = filedialog.askopenfilename(
        title="Select Video or Audio File",
        filetypes=[
            ("Media files", "*.mp4 *.mov *.avi *.mkv *.wav *.mp3"),
            ("All files", "*.*")
        ]
    )
    if filename:
        selected_file.set(filename)
        file_label.config(text=f"Selected File: {os.path.basename(filename)}")


def run_processing():
    input_file = selected_file.get()
    if not input_file:
        messagebox.showerror("Error", "Please select a media file.")
        return
    try:
        buffer_value = int(buffer_var.get())
        max_silence = float(max_silence_var.get())
        min_dur = int(min_dur_var.get())
        tier_suffix = tier_suffix_var.get().strip()
        energy_threshold = float(energy_threshold_var.get())  # NEW
    except ValueError:
        messagebox.showerror("Error", "Buffer/MinDur must be integers, Max Silence and Energy Threshold must be numbers.")
        return

    if not tier_suffix:
        messagebox.showerror("Error", "Please enter a tier suffix.")
        return

    process_file(input_file, buffer_value, max_silence, min_dur, tier_suffix, energy_threshold)


def reset_defaults():
    buffer_var.set("000")
    max_silence_var.set("0.3")
    min_dur_var.set("200")
    energy_threshold_var.set("55")  # NEW
    annotation_label.config(text="")


# --- GUI setup ---
root = tk.Tk()
root.title("Media to EAF Processor")
root.geometry("750x700")  # 

selected_file = tk.StringVar()
buffer_var = tk.StringVar(value="000")
max_silence_var = tk.StringVar(value="0.3")
min_dur_var = tk.StringVar(value="200")
tier_suffix_var = tk.StringVar(value="speaker")
energy_threshold_var = tk.StringVar(value="55")  # NEW

title_label = tk.Label(root, text="Segmentation of media files (audio/video → ELAN)", 
                       font=("Arial", 14, "bold"))
title_label.grid(row=0, column=0, columnspan=4, pady=10)

# File selection
tk.Button(root, text="Select File", command=select_file, width=15).grid(
    row=1, column=0, padx=10, pady=5)
file_label = tk.Label(root, text="No file selected", anchor="w")
file_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=10)

# Buffer
tk.Label(root, text="Buffer (ms):").grid(row=3, column=0, sticky="w", padx=10, pady=5)
tk.Entry(root, textvariable=buffer_var, width=10).grid(
    row=3, column=1, sticky="w", padx=10, pady=5)
tk.Label(root, text="Extra margin added before/after regions").grid(
    row=3, column=2, sticky="w")

# Max Silence
tk.Label(root, text="Max Silence (s):").grid(row=4, column=0, sticky="w", padx=10, pady=5)
tk.Entry(root, textvariable=max_silence_var, width=10).grid(
    row=4, column=1, sticky="w", padx=10, pady=5)
tk.Label(root, text="Silence allowed inside a region").grid(
    row=4, column=2, sticky="w")

# Min Duration
tk.Label(root, text="Min Duration (ms):").grid(row=5, column=0, sticky="w", padx=10, pady=5)
tk.Entry(root, textvariable=min_dur_var, width=10).grid(
    row=5, column=1, sticky="w", padx=10, pady=5)
tk.Label(root, text="Safeguard: shortest allowed annotation").grid(
    row=5, column=2, sticky="w")

# Tier Suffix
tk.Label(root, text="Tier Suffix:").grid(row=6, column=0, sticky="w", padx=10, pady=5)
tk.Entry(root, textvariable=tier_suffix_var, width=15).grid(
    row=6, column=1, sticky="w", padx=10, pady=5)
tk.Label(root, text="Used to generate tier names (MJK@X, TPI@X, ENG@X)").grid(
    row=6, column=2, sticky="w")

# NEW: Energy Threshold
tk.Label(root, text="Energy Threshold:").grid(row=7, column=0, sticky="w", padx=10, pady=5)
tk.Entry(root, textvariable=energy_threshold_var, width=10).grid(
    row=7, column=1, sticky="w", padx=10, pady=5)
tk.Label(root, text="Detection sensitivity (lower = more speech detected)").grid(
    row=7, column=2, sticky="w")

# Run + Reset
tk.Button(root, text="Run", command=run_processing, width=10).grid(
    row=8, column=0, padx=10, pady=15)
tk.Button(root, text="Reset Defaults", command=reset_defaults, width=15).grid(
    row=8, column=1, padx=10, pady=15)

# Annotation count
annotation_label = tk.Label(root, text="", anchor="w", fg="blue")
annotation_label.grid(row=9, column=0, columnspan=4, sticky="w", padx=10, pady=5)

# --- Tips and Troubleshooting section ---
tips_frame = tk.LabelFrame(root, text="Tips & Troubleshooting", padx=10, pady=5)
tips_frame.grid(row=10, column=0, columnspan=4, sticky="ew", padx=10, pady=10)

tips = [
    ("Too many short/noisy annotations",  "Increase Energy Threshold (e.g. 60–70)"),
    ("Genuine speech not detected",        "Decrease Energy Threshold (e.g. 40–50)"),
    ("Words cut off at start/end",         "Increase Buffer (e.g. 50–150 ms)"),
    ("Pauses within utterances cause splits", "Increase Max Silence (e.g. 0.5–1.0 s)"),
    ("Many very short annotations",        "Increase Min Duration (e.g. 300–500 ms)"),
]

tk.Label(tips_frame, text="Problem", font=("Arial", 9, "bold"), anchor="w", width=40).grid(
    row=0, column=0, sticky="w")
tk.Label(tips_frame, text="Suggested Fix", font=("Arial", 9, "bold"), anchor="w").grid(
    row=0, column=1, sticky="w", padx=(20, 0))

for i, (problem, fix) in enumerate(tips, start=1):
    tk.Label(tips_frame, text=problem, anchor="w", width=40).grid(
        row=i, column=0, sticky="w", pady=1)
    tk.Label(tips_frame, text=fix, anchor="w").grid(
        row=i, column=1, sticky="w", padx=(20, 0), pady=1)



root.mainloop()