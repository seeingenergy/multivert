#!/usr/bin/env python3
"""
multivert — audio conversion as an instrument.

Chain multiple conversion passes (codec / sample rate / bit depth / bitrate /
resampler quality / dither) and render them in one action. A one-step chain
is just "pick format, hit convert." A multi-step chain lets you fake a file
that's been re-encoded five times, stack a sample-rate crush into a phone
codec into mp3, or A/B several presets against the same source at once.

Requires: Python 3.8+, Tkinter (python3-tkinter), ffmpeg on PATH.
Optional: tkinterdnd2 (pip install --user tkinterdnd2) for drag-and-drop.

Fedora setup:
    sudo dnf install python3-tkinter
    sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
    sudo dnf install ffmpeg
    (ffmpeg isn't in Fedora's default repos due to codec licensing — it
    lives in RPM Fusion free. If you already have RPM Fusion, just
    `sudo dnf install ffmpeg`.)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from pathlib import Path

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

CONFIG_DIR = Path.home() / ".config" / "multivert"
PRESETS_FILE = CONFIG_DIR / "presets.json"

# ---------------------------------------------------------------------------
# Format definitions — only parameters that touch the sound of the audio.
# ---------------------------------------------------------------------------

# Each format: extension, whether bitrate applies, whether bit depth applies,
# and how to translate bit depth -> ffmpeg codec/sample_fmt.
FORMATS = {
    "WAV (PCM)":     {"ext": "wav",  "lossy": False, "bitdepth": True,
                       "codec_by_depth": {"8": "pcm_u8", "16": "pcm_s16le",
                                          "24": "pcm_s24le", "32": "pcm_f32le"}},
    "FLAC":          {"ext": "flac", "lossy": False, "bitdepth": True,
                       "codec_by_depth": {"16": "flac", "24": "flac"},
                       "sample_fmt_by_depth": {"16": "s16", "24": "s32"}},
    "WavPack":       {"ext": "wv",   "lossy": False, "bitdepth": True,
                       "codec_by_depth": {"8": "wavpack", "16": "wavpack", "24": "wavpack"}},
    "MP3":           {"ext": "mp3",  "lossy": True,  "codec": "libmp3lame"},
    "OGG Vorbis":    {"ext": "ogg",  "lossy": True,  "codec": "libvorbis"},
    "Opus":          {"ext": "opus", "lossy": True,  "codec": "libopus",
                       "allowed_ar": [8000, 12000, 16000, 24000, 48000]},
    "AAC (m4a)":     {"ext": "m4a",  "lossy": True,  "codec": "aac"},
    "WMA":           {"ext": "wma",  "lossy": True,  "codec": "wmav2"},
    "AC3":           {"ext": "ac3",  "lossy": True,  "codec": "ac3"},
    "GSM (phone)":   {"ext": "gsm",  "lossy": False, "codec": "gsm", "force_ar": "8000"},
    "\u03bc-law":    {"ext": "wav",  "lossy": False, "codec": "pcm_mulaw"},
    "A-law":         {"ext": "wav",  "lossy": False, "codec": "pcm_alaw"},
    "ADPCM":         {"ext": "wav",  "lossy": True,  "codec": "adpcm_ima_wav"},
}

BITRATES = ["32k", "64k", "96k", "128k", "160k", "192k", "256k", "320k"]
BITDEPTHS = ["8", "16", "24", "32"]
RESAMPLERS = {
    "High quality (soxr)": "soxr",
    "Standard (swr)": "swr",
    "Crude / aliasing (swr, small filter)": "swr_crude",
}
DITHERS = {
    "None": "none",
    "Triangular": "triangular",
    "Noise-shaped (shibata)": "shibata",
}


def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def build_step_args(step, out_ext_hint=None):
    """Return (extra_input_free_args, filter_args, codec_args) lists for one step."""
    fmt = FORMATS[step["format"]]
    args = []

    # Sample rate
    ar = step.get("force_ar") or fmt.get("force_ar") or step["sample_rate"]
    allowed = fmt.get("allowed_ar")
    if allowed:
        ar = min(allowed, key=lambda a: abs(a - int(ar)))
    if ar:
        args += ["-ar", str(ar)]

    # Resampler / dither via -af aresample=...
    resampler = RESAMPLERS[step["resampler"]]
    dither = DITHERS[step["dither"]]
    if resampler == "swr_crude":
        af = f"aresample=resampler=swr:filter_size=8:dither_method={dither}"
    else:
        af = f"aresample=resampler={resampler}:dither_method={dither}"
    args += ["-af", af]

    # Codec
    if "codec_by_depth" in fmt:
        depth = step.get("bit_depth", "16")
        codec = fmt["codec_by_depth"].get(depth, list(fmt["codec_by_depth"].values())[0])
        args += ["-c:a", codec]
        if "sample_fmt_by_depth" in fmt and depth in fmt["sample_fmt_by_depth"]:
            args += ["-sample_fmt", fmt["sample_fmt_by_depth"][depth]]
    else:
        args += ["-c:a", fmt["codec"]]

    # Bitrate
    if fmt.get("lossy") and step.get("bitrate"):
        args += ["-b:a", step["bitrate"]]

    return args


def step_label(step):
    fmt = step["format"]
    parts = [fmt]
    if step.get("sample_rate"):
        parts.append(f'{step["sample_rate"]}Hz')
    if FORMATS[fmt].get("bitdepth") and step.get("bit_depth"):
        parts.append(f'{step["bit_depth"]}bit')
    if FORMATS[fmt].get("lossy") and step.get("bitrate"):
        parts.append(step["bitrate"])
    return " / ".join(parts)


# ---------------------------------------------------------------------------
# Step editor dialog
# ---------------------------------------------------------------------------

class StepDialog(tk.Toplevel):
    def __init__(self, parent, initial=None):
        super().__init__(parent)
        self.title("Chain step")
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()

        pad = {"padx": 8, "pady": 4}

        tk.Label(self, text="Format").grid(row=0, column=0, sticky="w", **pad)
        self.format_var = tk.StringVar(value=(initial or {}).get("format", "WAV (PCM)"))
        fmt_menu = ttk.Combobox(self, textvariable=self.format_var,
                                 values=list(FORMATS.keys()), state="readonly", width=28)
        fmt_menu.grid(row=0, column=1, **pad)
        fmt_menu.bind("<<ComboboxSelected>>", lambda e: self._refresh())

        tk.Label(self, text="Sample rate (Hz)").grid(row=1, column=0, sticky="w", **pad)
        self.rate_var = tk.StringVar(value=str((initial or {}).get("sample_rate", "44100")))
        tk.Entry(self, textvariable=self.rate_var, width=30).grid(row=1, column=1, **pad)

        tk.Label(self, text="Bit depth").grid(row=2, column=0, sticky="w", **pad)
        self.depth_var = tk.StringVar(value=(initial or {}).get("bit_depth", "16"))
        self.depth_menu = ttk.Combobox(self, textvariable=self.depth_var,
                                        values=BITDEPTHS, state="readonly", width=28)
        self.depth_menu.grid(row=2, column=1, **pad)

        tk.Label(self, text="Bitrate").grid(row=3, column=0, sticky="w", **pad)
        self.bitrate_var = tk.StringVar(value=(initial or {}).get("bitrate", "192k"))
        self.bitrate_menu = ttk.Combobox(self, textvariable=self.bitrate_var,
                                          values=BITRATES, state="readonly", width=28)
        self.bitrate_menu.grid(row=3, column=1, **pad)

        tk.Label(self, text="Resampler").grid(row=4, column=0, sticky="w", **pad)
        self.resampler_var = tk.StringVar(value=(initial or {}).get("resampler", "High quality (soxr)"))
        ttk.Combobox(self, textvariable=self.resampler_var, values=list(RESAMPLERS.keys()),
                     state="readonly", width=28).grid(row=4, column=1, **pad)

        tk.Label(self, text="Dither").grid(row=5, column=0, sticky="w", **pad)
        self.dither_var = tk.StringVar(value=(initial or {}).get("dither", "Triangular"))
        ttk.Combobox(self, textvariable=self.dither_var, values=list(DITHERS.keys()),
                     state="readonly", width=28).grid(row=5, column=1, **pad)

        btns = tk.Frame(self)
        btns.grid(row=6, column=0, columnspan=2, pady=(10, 8))
        tk.Button(btns, text="OK", width=10, command=self._ok).pack(side="left", padx=4)
        tk.Button(btns, text="Cancel", width=10, command=self.destroy).pack(side="left", padx=4)

        self._refresh()
        self.wait_window(self)

    def _refresh(self):
        fmt = FORMATS[self.format_var.get()]
        self.depth_menu.configure(state="readonly" if fmt.get("bitdepth") else "disabled")
        self.bitrate_menu.configure(state="readonly" if fmt.get("lossy") else "disabled")

    def _ok(self):
        try:
            rate = int(self.rate_var.get())
            if rate < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("multivert", "Sample rate must be a positive integer.")
            return
        self.result = {
            "format": self.format_var.get(),
            "sample_rate": rate,
            "bit_depth": self.depth_var.get(),
            "bitrate": self.bitrate_var.get(),
            "resampler": self.resampler_var.get(),
            "dither": self.dither_var.get(),
        }
        self.destroy()


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

BaseTk = TkinterDnD.Tk if HAS_DND else tk.Tk


class App(BaseTk):
    def __init__(self):
        super().__init__()
        self.title("multivert")
        self.resizable(False, False)
        self.configure(padx=10, pady=10)

        self.source_path = tk.StringVar()
        self.chain = []
        self.presets = self._load_presets()

        self._build_ui()

        if not ffmpeg_available():
            self._log("missing: ffmpeg is required to convert audio.")

    # -- persistence ---------------------------------------------------

    def _load_presets(self):
        if PRESETS_FILE.exists():
            try:
                return json.loads(PRESETS_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_presets(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        PRESETS_FILE.write_text(json.dumps(self.presets, indent=2))

    # -- UI --------------------------------------------------------------

    def _build_ui(self):
        # File row
        file_frame = tk.Frame(self)
        file_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        entry = tk.Entry(file_frame, textvariable=self.source_path, width=48)
        entry.pack(side="left", fill="x", expand=True)
        tk.Button(file_frame, text="Browse...", command=self._browse).pack(side="left", padx=(6, 0))

        if HAS_DND:
            entry.drop_target_register(DND_FILES)
            entry.dnd_bind("<<Drop>>", self._on_drop)
        else:
            hint = tk.Label(self, text="(tip: pip install --user tkinterdnd2 for drag-and-drop)",
                             fg="gray50", font=("PanicTF", 8))
            hint.grid(row=1, column=0, columnspan=3, sticky="w")

        # Chain list
        tk.Label(self, text="Chain (applied top to bottom):").grid(row=2, column=0, columnspan=3,
                                                                     sticky="w", pady=(10, 2))
        list_frame = tk.Frame(self)
        list_frame.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.chain_list = tk.Listbox(list_frame, height=6, width=52)
        self.chain_list.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(list_frame, command=self.chain_list.yview)
        scroll.pack(side="left", fill="y")
        self.chain_list.configure(yscrollcommand=scroll.set)

        chain_btns = tk.Frame(self)
        chain_btns.grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 8))
        tk.Button(chain_btns, text="Add Step", command=self._add_step).pack(side="left", padx=2)
        tk.Button(chain_btns, text="Edit Step", command=self._edit_step).pack(side="left", padx=2)
        tk.Button(chain_btns, text="Remove Step", command=self._remove_step).pack(side="left", padx=2)
        tk.Button(chain_btns, text="Move Up", command=lambda: self._move_step(-1)).pack(side="left", padx=2)
        tk.Button(chain_btns, text="Move Down", command=lambda: self._move_step(1)).pack(side="left", padx=2)

        # Presets
        preset_frame = tk.Frame(self)
        preset_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        tk.Label(preset_frame, text="Preset:").pack(side="left")
        self.preset_var = tk.StringVar()
        self.preset_menu = ttk.Combobox(preset_frame, textvariable=self.preset_var,
                                         values=list(self.presets.keys()), state="readonly", width=20)
        self.preset_menu.pack(side="left", padx=4)
        tk.Button(preset_frame, text="Load", command=self._load_preset).pack(side="left", padx=2)
        tk.Button(preset_frame, text="Save Chain As...", command=self._save_preset).pack(side="left", padx=2)
        tk.Button(preset_frame, text="Delete", command=self._delete_preset).pack(side="left", padx=2)

        # Convert buttons
        convert_frame = tk.Frame(self)
        convert_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(4, 4))
        tk.Button(convert_frame, text="Convert", width=14, command=self._convert,
                  bg="#fff", activebackground="#fff").pack(side="left")
        tk.Button(convert_frame, text="Render All Presets", command=self._convert_all_presets).pack(
            side="left", padx=(8, 0))

        # Status
        self.status = tk.Label(self, text="", fg="gray30", anchor="w", justify="left", wraplength=440)
        self.status.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    # -- helpers -----------------------------------------------------------

    def _log(self, text):
        self.status.configure(text=text)
        self.update_idletasks()

    def _browse(self):
        path = filedialog.askopenfilename(title="Select audio file")
        if path:
            self.source_path.set(path)

    def _on_drop(self, event):
        path = event.data.strip("{}")
        self.source_path.set(path)

    def _refresh_chain_list(self):
        self.chain_list.delete(0, tk.END)
        for i, step in enumerate(self.chain, 1):
            self.chain_list.insert(tk.END, f"{i}. {step_label(step)}")

    def _add_step(self):
        dlg = StepDialog(self)
        if dlg.result:
            self.chain.append(dlg.result)
            self._refresh_chain_list()

    def _edit_step(self):
        sel = self.chain_list.curselection()
        if not sel:
            return
        idx = sel[0]
        dlg = StepDialog(self, initial=self.chain[idx])
        if dlg.result:
            self.chain[idx] = dlg.result
            self._refresh_chain_list()

    def _remove_step(self):
        sel = self.chain_list.curselection()
        if not sel:
            return
        del self.chain[sel[0]]
        self._refresh_chain_list()

    def _move_step(self, direction):
        sel = self.chain_list.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + direction
        if 0 <= new_idx < len(self.chain):
            self.chain[idx], self.chain[new_idx] = self.chain[new_idx], self.chain[idx]
            self._refresh_chain_list()
            self.chain_list.selection_set(new_idx)

    def _load_preset(self):
        name = self.preset_var.get()
        if name in self.presets:
            self.chain = [dict(s) for s in self.presets[name]]
            self._refresh_chain_list()

    def _save_preset(self):
        if not self.chain:
            messagebox.showinfo("multivert", "Chain is empty — add at least one step first.")
            return
        name = simpledialog.askstring("Save Preset", "Preset name:")
        if not name:
            return
        self.presets[name] = [dict(s) for s in self.chain]
        self._save_presets()
        self.preset_menu.configure(values=list(self.presets.keys()))
        self.preset_var.set(name)

    def _delete_preset(self):
        name = self.preset_var.get()
        if name in self.presets:
            del self.presets[name]
            self._save_presets()
            self.preset_menu.configure(values=list(self.presets.keys()))
            self.preset_var.set("")

    # -- conversion -----------------------------------------------------

    def _run_chain(self, source, chain, out_path):
        """Run a chain of ffmpeg passes, source -> out_path. Raises RuntimeError on failure."""
        current = source
        tmp_files = []
        try:
            for i, step in enumerate(chain):
                is_last = i == len(chain) - 1
                ext = FORMATS[step["format"]]["ext"]
                if is_last:
                    dest = out_path
                else:
                    fd, tmp = tempfile.mkstemp(suffix=f".{ext}")
                    os.close(fd)
                    tmp_files.append(tmp)
                    dest = tmp
                args = ["ffmpeg", "-y", "-i", current] + build_step_args(step) + [dest]
                proc = subprocess.run(args, capture_output=True, text=True)
                if proc.returncode != 0:
                    raise RuntimeError(proc.stderr[-800:] if proc.stderr else "ffmpeg failed")
                current = dest
        finally:
            for t in tmp_files:
                try:
                    os.remove(t)
                except OSError:
                    pass

    def _convert(self):
        if not ffmpeg_available():
            messagebox.showerror("multivert", "ffmpeg not found on PATH.")
            return
        source = self.source_path.get().strip()
        if not source or not os.path.isfile(source):
            messagebox.showerror("multivert", "Select a valid audio file first.")
            return
        if not self.chain:
            messagebox.showinfo("multivert", "Add at least one step to the chain.")
            return

        src = Path(source)
        out_ext = FORMATS[self.chain[-1]["format"]]["ext"]
        out_path = str(src.with_name(f"{src.stem}_1v.{out_ext}"))

        self._log("Converting...")
        try:
            self._run_chain(source, self.chain, out_path)
            self._log(f"Done: {out_path}")
        except RuntimeError as e:
            self._log("ffmpeg error — see details.")
            messagebox.showerror("ffmpeg error", str(e))

    def _convert_all_presets(self):
        if not ffmpeg_available():
            messagebox.showerror("multivert", "ffmpeg not found on PATH.")
            return
        source = self.source_path.get().strip()
        if not source or not os.path.isfile(source):
            messagebox.showerror("multivert", "Select a valid audio file first.")
            return
        if not self.presets:
            messagebox.showinfo("multivert", "No saved presets yet.")
            return

        src = Path(source)
        errors = []
        for name, chain in self.presets.items():
            out_ext = FORMATS[chain[-1]["format"]]["ext"]
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
            out_path = str(src.with_name(f"{src.stem}_{safe_name}.{out_ext}"))
            self._log(f"Rendering preset: {name}...")
            try:
                self._run_chain(source, chain, out_path)
            except RuntimeError as e:
                errors.append(f"{name}: {e}")

        if errors:
            self._log(f"Finished with {len(errors)} error(s).")
            messagebox.showerror("ffmpeg errors", "\n\n".join(errors))
        else:
            self._log(f"Rendered {len(self.presets)} preset(s) next to source file.")


if __name__ == "__main__":
    app = App()
    app.mainloop()
