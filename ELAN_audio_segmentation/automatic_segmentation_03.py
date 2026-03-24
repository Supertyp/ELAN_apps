import os
import tkinter as tk
from tkinter import filedialog, messagebox
import auditok
import pympi
from pydub import AudioSegment



def process_file(input_file, buffer_value, max_silence, min_dur):
    # --- detect regions with adjustable gap recognition ---
    speech_regions = auditok.split(
        input_file,
        energy_threshold=55,
        max_silence=max_silence   # silence allowed inside a region
        # min_pause removed
    )
    # Use r.start and r.end (not r.meta)
    regions = sorted([(int(r.start * 1000), int(r.end * 1000)) for r in speech_regions])

    audio = AudioSegment.from_file(input_file)
    audio_len_ms = len(audio)

    eaf = pympi.Elan.Eaf(file_path=None)

    # Define linguistic types
    eaf.add_linguistic_type("ts")  # time-alignable type
    eaf.add_linguistic_type("tl", constraints="Symbolic_Association", timealignable=False)
    if "default" in eaf.get_tier_names():
        eaf.remove_tier("default")
    eaf.add_tier("default", "ts")



    # Add dependent tier with LINGUISTIC_TYPE_REF="tl"
    if "translation" not in eaf.get_tier_names():
        eaf.add_tier("translation", "tl", parent="default")

    BUFFER = buffer_value
    MIN_DUR = min_dur

    extended = []
    for i, (start_ms, end_ms) in enumerate(regions):
        left_gap  = float("inf") if i == 0 else start_ms - regions[i-1][1]
        right_gap = float("inf") if i == len(regions)-1 else regions[i+1][0] - end_ms

        new_start = start_ms - BUFFER if left_gap  > BUFFER else start_ms
        new_end   = end_ms   + BUFFER if right_gap > BUFFER else end_ms

        new_start = max(0, new_start)
        new_end   = min(audio_len_ms, new_end)
        if new_end <= new_start:
            new_end = min(audio_len_ms, new_start + MIN_DUR)

        extended.append([new_start, new_end])

    # resolve overlaps
    i = 0
    while i < len(extended) - 1:
        a_start, a_end   = extended[i]
        b_start, b_end   = extended[i+1]

        if a_end > b_start:
            mid = (a_end + b_start) // 2
            new_a_end = max(a_start, mid)
            new_b_start = min(b_end, max(new_a_end, mid))

            if new_b_start >= b_end:
                b_end = min(audio_len_ms, new_b_start + MIN_DUR)

            extended[i]   = [a_start, new_a_end]
            extended[i+1] = [new_b_start, b_end]

            if i > 0:
                i -= 1
                continue
        i += 1

    # Add annotations to parent tier and dependent tier
    for start_ms, end_ms in extended:
        # Parent annotation
        eaf.add_annotation("default", start=start_ms, end=end_ms, value="")

        # Dependent annotation referencing parent tier
        eaf.add_ref_annotation("translation", "default", value="", time=start_ms)

    eaf.add_linked_file(os.path.basename(input_file))
    output_file = os.path.splitext(input_file)[0] + ".eaf"
    eaf.to_file(output_file)

    num_annotations = len(extended)
    messagebox.showinfo("Done", f"Annotations written to {output_file}\nNumber of annotations: {num_annotations}")
    annotation_label.config(text=f"ELAN file saved. Number of annotations: {num_annotations}")

def select_file():
    filename = filedialog.askopenfilename(
        title="Select WAV file",
        filetypes=[("WAV files", "*.wav")]
    )
    if filename:
        selected_file.set(filename)
        file_label.config(text=f"Selected File: {os.path.basename(filename)}")

def run_processing():
    input_file = selected_file.get()
    if not input_file:
        messagebox.showerror("Error", "Please select a WAV file.")
        return
    try:
        buffer_value = int(buffer_var.get())
        max_silence = float(max_silence_var.get())
        min_dur = int(min_dur_var.get())
    except ValueError:
        messagebox.showerror("Error", "Buffer/MinDur must be integers, Max Silence must be a number.")
        return
    process_file(input_file, buffer_value, max_silence, min_dur)

def reset_defaults():
    buffer_var.set("500")
    max_silence_var.set("0.3")
    min_dur_var.set("200")
    annotation_label.config(text="")  # clear annotation count

# --- GUI setup ---
root = tk.Tk()
root.title("WAV to EAF Processor")
root.geometry("750x420")


selected_file = tk.StringVar()
buffer_var = tk.StringVar(value="000")
max_silence_var = tk.StringVar(value="0.3")
min_dur_var = tk.StringVar(value="200")

# Title
title_label = tk.Label(root, text="Segmentation of audio files (wav to elan)", font=("Arial", 14, "bold"))
title_label.grid(row=0, column=0, columnspan=4, pady=10)

# File selection
tk.Button(root, text="Select File", command=select_file, width=15).grid(row=1, column=0, padx=10, pady=5)
file_label = tk.Label(root, text="No file selected", anchor="w")
file_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=10)

# Buffer input + explanation
tk.Label(root, text="Buffer (ms):").grid(row=3, column=0, sticky="w", padx=10, pady=5)
tk.Entry(root, textvariable=buffer_var, width=10).grid(row=3, column=1, sticky="w", padx=10, pady=5)
tk.Label(root, text="Extra margin added before/after regions").grid(row=3, column=2, sticky="w")

# Max silence input + explanation
tk.Label(root, text="Max Silence (s):").grid(row=4, column=0, sticky="w", padx=10, pady=5)
tk.Entry(root, textvariable=max_silence_var, width=10).grid(row=4, column=1, sticky="w", padx=10, pady=5)
tk.Label(root, text="Silence allowed inside a region. More trickers a split").grid(row=4, column=2, sticky="w")

# Min duration input + explanation
tk.Label(root, text="Min Duration (ms):").grid(row=5, column=0, sticky="w", padx=10, pady=5)
tk.Entry(root, textvariable=min_dur_var, width=10).grid(row=5, column=1, sticky="w", padx=10, pady=5)
tk.Label(root, text="Safeguard: shortest allowed annotation").grid(row=5, column=2, sticky="w")

# Run + Reset buttons
tk.Button(root, text="Run", command=run_processing, width=10).grid(row=6, column=0, padx=10, pady=15)
tk.Button(root, text="Reset Defaults", command=reset_defaults, width=15).grid(row=6, column=1, padx=10, pady=15)

# Annotation count
annotation_label = tk.Label(root, text="", anchor="w", fg="blue")
annotation_label.grid(row=7, column=0, columnspan=4, sticky="w", padx=10, pady=5)

root.mainloop()