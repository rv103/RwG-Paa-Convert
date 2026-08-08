#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  RwG PAA Convert
  --------------------------------------------------------------------------
  Grafisches Tool zum Stapel-Konvertieren von .paa-Texturen nach PNG oder TGA
  mit Pal2PacE.exe (Bohemia Interactive).

  Mehrsprachig ueber Stringtable.csv (Arma/DayZ-typisches Format).
  Faellt die Datei weg, greifen eingebaute Texte (Deutsch/Englisch).

  Benoetigt: Python 3.8+ (Tkinter ist unter Windows enthalten)
  Start:     RwG_Paa_Convert.bat  (Doppelklick)  oder  python RwG_Paa_Convert.py
================================================================================
"""

import os
import sys
import csv
import json
import time
import queue
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor

APP_NAME = "RwG Paa-Convert"

# --- Pfade: portabel im .exe-Betrieb ---------------------------------------
# Als PyInstaller-Onefile-EXE liegt der entpackte Code in sys._MEIPASS,
# die eigentliche .exe aber woanders. Externe, editierbare Dateien
# (Einstellungen + Stringtable) sollen NEBEN der .exe liegen, nicht im Temp.
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))   # neben der .exe
    RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)             # eingebettete Ressourcen
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR

SCRIPT_DIR = BASE_DIR  # Kompatibilitaet
SETTINGS_PATH = os.path.join(BASE_DIR, "RwG_Paa_Convert.settings.json")

# Stringtable: externe Datei neben der .exe hat Vorrang (editierbar),
# sonst die eingebettete Kopie.
STRINGTABLE_EXTERNAL = os.path.join(BASE_DIR, "Stringtable.csv")
STRINGTABLE_BUNDLED = os.path.join(RESOURCE_DIR, "Stringtable.csv")


def stringtable_path():
    return STRINGTABLE_EXTERNAL if os.path.isfile(STRINGTABLE_EXTERNAL) else STRINGTABLE_BUNDLED


# Icon: eingebettet, dann neben der .exe, dann Original-Ort im Painter-Plugin
ICON_PATHS = [
    os.path.join(RESOURCE_DIR, "RwG_Logo.ico"),
    os.path.join(BASE_DIR, "RwG_Logo.ico"),
    r"E:\Git\RwG_DayZ_Painter_Plugin\RwG_DayZ_Painter\RwG_Logo.ico",
]


def apply_icon(root):
    for p in ICON_PATHS:
        if os.path.isfile(p):
            try:
                root.iconbitmap(p)
                return True
            except Exception:  # noqa  (z. B. Nicht-Windows)
                pass
    return False

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ----------------------------------------------------------------- i18n
# Anzeigenamen der Sprachen (Spaltenkopf -> native Bezeichnung)
LANG_NATIVE = {
    "English": "English", "German": "Deutsch", "French": "Français",
    "Spanish": "Español", "Italian": "Italiano", "Portuguese": "Português",
    "Polish": "Polski", "Russian": "Русский", "Czech": "Čeština",
    "Chinese": "中文",
}

# Eingebauter Rueckfall (Deutsch/Englisch), falls Stringtable.csv fehlt
FALLBACK = {
    "STR_RWG_Title":       {"English": "PAA  →  PNG / TGA   Batch Converter",
                            "German":  "PAA  →  PNG / TGA   Stapelkonverter"},
    "STR_RWG_Language":    {"English": "Language:", "German": "Sprache:"},
    "STR_RWG_Pal":         {"English": "Pal2PacE.exe:", "German": "Pal2PacE.exe:"},
    "STR_RWG_Source":      {"English": "Source folder:", "German": "Quellordner:"},
    "STR_RWG_Browse":      {"English": "Browse…", "German": "Durchsuchen…"},
    "STR_RWG_Recurse":     {"English": "Include subfolders (recursive)",
                            "German":  "Unterordner einbeziehen (rekursiv)"},
    "STR_RWG_Found":       {"English": "Found: {n} .paa file(s)",
                            "German":  "Gefunden: {n} .paa-Datei(en)"},
    "STR_RWG_FoundNone":   {"English": "Found: -", "German": "Gefunden: -"},
    "STR_RWG_FmtGroup":    {"English": "Output format", "German": "Ausgabeformat"},
    "STR_RWG_ThreadsGroup":{"English": "Parallel processes", "German": "Parallele Prozesse"},
    "STR_RWG_ThreadsHint": {"English": "at once (faster with many files)",
                            "German":  "gleichzeitig (schneller bei vielen Dateien)"},
    "STR_RWG_OutGroup":    {"English": "Output location", "German": "Ausgabeort"},
    "STR_RWG_InPlace":     {"English": "Next to original (same folder)",
                            "German":  "Neben Originaldatei (im selben Ordner)"},
    "STR_RWG_Separate":    {"English": "Separate folder:", "German": "Separater Ordner:"},
    "STR_RWG_KeepTree":    {"English": "Keep folder structure in target",
                            "German":  "Ordnerstruktur im Zielordner beibehalten"},
    "STR_RWG_Skip":        {"English": "Skip existing target files",
                            "German":  "Bereits vorhandene Zieldateien überspringen"},
    "STR_RWG_Delete":      {"English": "Delete source PAA after success (caution!)",
                            "German":  "Original-PAA nach Erfolg löschen (Vorsicht!)"},
    "STR_RWG_Start":       {"English": "Start conversion", "German": "Konvertierung starten"},
    "STR_RWG_Cancel":      {"English": "Cancel", "German": "Abbrechen"},
    "STR_RWG_Ready":       {"English": "Ready.", "German": "Bereit."},
    "STR_RWG_SaveLog":     {"English": "Save log", "German": "Log speichern"},
    "STR_RWG_DlgPal":      {"English": "Select Pal2PacE.exe", "German": "Pal2PacE.exe auswählen"},
    "STR_RWG_DlgSrc":      {"English": "Select source folder with .paa files",
                            "German":  "Quellordner mit .paa-Dateien wählen"},
    "STR_RWG_DlgOut":      {"English": "Select target folder", "German": "Zielordner wählen"},
    "STR_RWG_WarnPal":     {"English": "Please select a valid Pal2PacE.exe.",
                            "German":  "Bitte eine gültige Pal2PacE.exe auswählen."},
    "STR_RWG_WarnSrc":     {"English": "Please select a valid source folder.",
                            "German":  "Bitte einen gültigen Quellordner auswählen."},
    "STR_RWG_WarnOut":     {"English": "Please choose a target folder or select \"Next to original\".",
                            "German":  "Bitte einen Zielordner wählen oder „Neben Originaldatei\" wählen."},
    "STR_RWG_NoPaa":       {"English": "No .paa files found in the source folder.",
                            "German":  "Keine .paa-Dateien im Quellordner gefunden."},
    "STR_RWG_LogStart":    {"English": "Start: {n} file(s)  →  .{fmt}  ({t} parallel)",
                            "German":  "Start: {n} Datei(en)  →  .{fmt}  ({t} parallel)"},
    "STR_RWG_LogOK":       {"English": "OK: {name}", "German": "OK: {name}"},
    "STR_RWG_LogSkip":     {"English": "Skipped: {name}", "German": "Übersprungen: {name}"},
    "STR_RWG_LogFail":     {"English": "ERROR: {name} — {msg}", "German": "FEHLER: {name} — {msg}"},
    "STR_RWG_Progress":    {"English": "Progress: {p} / {t}   |   OK: {ok}   |   Skipped: {sk}   |   Errors: {fa}{eta}",
                            "German":  "Fortschritt: {p} / {t}   |   OK: {ok}   |   Übersprungen: {sk}   |   Fehler: {fa}{eta}"},
    "STR_RWG_Eta":         {"English": "   |   ETA {t}", "German": "   |   ETA {t}"},
    "STR_RWG_DoneOK":      {"English": "Done in {t} — OK: {ok}, Skipped: {sk}, Errors: {fa}",
                            "German":  "Fertig in {t} — OK: {ok}, Übersprungen: {sk}, Fehler: {fa}"},
    "STR_RWG_DoneCancel":  {"English": "Cancelled after {t} — OK: {ok}, Skipped: {sk}, Errors: {fa}",
                            "German":  "Abgebrochen nach {t} — OK: {ok}, Übersprungen: {sk}, Fehler: {fa}"},
    "STR_RWG_CancelReq":   {"English": "Cancellation requested…", "German": "Abbruch angefordert…"},
    "STR_RWG_LogSaved":    {"English": "Log saved.", "German": "Log gespeichert."},
}

_I18N = {"table": {}, "langs": ["English", "German"], "cur": "German"}


def load_stringtable(path):
    """Liest Stringtable.csv (erste Spalte = Schluessel, weitere Spalten = Sprachen)."""
    table = {}
    langs = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if not header or len(header) < 2:
                return None, None
            langs = [h.strip() for h in header[1:] if h.strip()]
            for lang in langs:
                table[lang] = {}
            for row in reader:
                if not row or not row[0].strip():
                    continue
                key = row[0].strip()
                for i, lang in enumerate(langs, start=1):
                    val = row[i] if i < len(row) else ""
                    table[lang][key] = val
        if not langs:
            return None, None
        return langs, table
    except (OSError, ValueError, StopIteration):
        return None, None


def init_i18n():
    langs, table = load_stringtable(stringtable_path())
    if not langs:
        # Rueckfall aus eingebautem Woerterbuch
        langs = ["English", "German"]
        table = {"English": {}, "German": {}}
        for key, d in FALLBACK.items():
            table["English"][key] = d["English"]
            table["German"][key] = d["German"]
    else:
        # Fehlende Schluessel je Sprache mit Fallback/Englisch auffuellen
        for key, d in FALLBACK.items():
            for lang in langs:
                if not table[lang].get(key):
                    table[lang][key] = d.get(lang) or d.get("English") or key
    _I18N["langs"] = langs
    _I18N["table"] = table


def set_language(lang):
    if lang in _I18N["table"]:
        _I18N["cur"] = lang


def tr(key, **kw):
    tbl = _I18N["table"]
    cur = _I18N["cur"]
    s = (tbl.get(cur, {}).get(key)
         or tbl.get("English", {}).get(key)
         or FALLBACK.get(key, {}).get("English")
         or key)
    if kw:
        try:
            return s.format(**kw)
        except (KeyError, IndexError, ValueError):
            return s
    return s


# ============================================================ Kern-Logik (GUI-frei)
def find_pal2pace():
    candidates = [
        os.path.join(SCRIPT_DIR, "Pal2PacE.exe"),
        os.path.join(os.path.dirname(SCRIPT_DIR), "DayZ Tools", "Pal2PacE.exe"),
        os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "DayZ Tools", "Pal2PacE.exe"),
        r"E:\DayZ\DayZ Tools\Pal2PacE.exe",
        r"E:\DayZ Tools\Pal2PacE.exe",
        r"C:\Program Files (x86)\Steam\steamapps\common\Arma 3 Tools\TexView2\Pal2PacE.exe",
        r"C:\Program Files\Steam\steamapps\common\Arma 3 Tools\TexView2\Pal2PacE.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return ""


def scan_paa(source, recursive):
    result = []
    if not source or not os.path.isdir(source):
        return result
    if recursive:
        for root, _dirs, files in os.walk(source):
            for name in files:
                if name.lower().endswith(".paa"):
                    result.append(os.path.join(root, name))
    else:
        for name in os.listdir(source):
            full = os.path.join(source, name)
            if os.path.isfile(full) and name.lower().endswith(".paa"):
                result.append(full)
    return result


def compute_out_path(paa_path, cfg):
    fmt = cfg["format"]
    base = os.path.splitext(os.path.basename(paa_path))[0] + "." + fmt
    if cfg["separate"]:
        if cfg["keep_tree"]:
            rel = os.path.relpath(paa_path, cfg["source"])
            rel = os.path.splitext(rel)[0] + "." + fmt
            return os.path.join(cfg["out_folder"], rel)
        return os.path.join(cfg["out_folder"], base)
    return os.path.splitext(paa_path)[0] + "." + fmt


def convert_one(paa_path, cfg):
    name = os.path.basename(paa_path)
    out = compute_out_path(paa_path, cfg)

    if cfg["skip_existing"] and os.path.exists(out):
        return {"status": "skipped", "name": name, "out": out, "message": "exists"}

    out_dir = os.path.dirname(out)
    if out_dir and not os.path.isdir(out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as exc:
            return {"status": "failed", "name": name, "out": out, "message": f"target dir: {exc}"}

    try:
        proc = subprocess.run(
            [cfg["pal2pace"], paa_path, out],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=_NO_WINDOW, timeout=cfg.get("timeout", 120),
        )
    except subprocess.TimeoutExpired:
        return {"status": "failed", "name": name, "out": out, "message": "timeout"}
    except OSError as exc:
        return {"status": "failed", "name": name, "out": out, "message": str(exc)}

    if proc.returncode == 0 and os.path.exists(out):
        if cfg["delete_source"]:
            try:
                os.remove(paa_path)
            except OSError as exc:
                return {"status": "ok", "name": name, "out": out,
                        "message": f"source not deleted ({exc})"}
        return {"status": "ok", "name": name, "out": out, "message": ""}

    detail = (proc.stderr or proc.stdout or b"").decode("utf-8", "ignore").strip()
    return {"status": "failed", "name": name, "out": out,
            "message": f"exit code {proc.returncode}" + (f": {detail}" if detail else "")}


def convert_batch(cfg, files, on_event, cancel_event):
    total = len(files)
    counts = {"ok": 0, "skipped": 0, "failed": 0}
    start = time.time()
    processed = 0

    workers = max(1, int(cfg.get("threads", 4)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        it = iter(files)
        for _ in range(workers):
            try:
                f = next(it)
            except StopIteration:
                break
            futures[pool.submit(convert_one, f, cfg)] = f

        while futures:
            if cancel_event.is_set():
                break
            done_now = [fut for fut in list(futures) if fut.done()]
            if not done_now:
                time.sleep(0.03)
                continue
            for fut in done_now:
                futures.pop(fut, None)
                try:
                    res = fut.result()
                except Exception as exc:  # noqa
                    res = {"status": "failed", "name": "?", "out": "", "message": str(exc)}
                counts[res["status"]] += 1
                processed += 1
                elapsed = time.time() - start
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total - processed) / rate if rate > 0 and processed < total else 0
                on_event("file", {"res": res, "processed": processed, "total": total,
                                  "counts": dict(counts), "eta": eta})
                if not cancel_event.is_set():
                    try:
                        nf = next(it)
                        futures[pool.submit(convert_one, nf, cfg)] = nf
                    except StopIteration:
                        pass

    on_event("done", {"counts": dict(counts), "processed": processed, "total": total,
                      "elapsed": time.time() - start, "cancelled": cancel_event.is_set()})


# ============================================================ Einstellungen
def load_settings():
    if os.path.isfile(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}
    return {}


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass


# ============================================================ GUI
def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    init_i18n()

    BG = "#252526"; FG = "#dcdcdc"; FIELD = "#333337"; ACCENT = "#007acc"
    OKC = "#78c878"; ERRC = "#e66e6e"; SKIPC = "#b4b478"

    root = tk.Tk()
    root.title(APP_NAME)
    apply_icon(root)
    root.geometry("780x680")
    root.minsize(780, 680)
    root.configure(bg=BG)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=BG, foreground=FG, fieldbackground=FIELD)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("TCheckbutton", background=BG, foreground=FG)
    style.configure("TRadiobutton", background=BG, foreground=FG)
    style.map("TCheckbutton", background=[("active", BG)])
    style.map("TRadiobutton", background=[("active", BG)])
    style.configure("TButton", background=FIELD, foreground=FG)
    style.configure("Accent.TButton", background=ACCENT, foreground="white",
                    font=("Segoe UI", 10, "bold"))
    style.configure("TLabelframe", background=BG, foreground=FG)
    style.configure("TLabelframe.Label", background=BG, foreground=FG)
    style.configure("TProgressbar", background=ACCENT, troughcolor=FIELD)
    style.configure("TSpinbox", fieldbackground=FIELD, foreground=FG, background=FIELD)
    style.configure("TEntry", fieldbackground=FIELD, foreground=FG)
    style.configure("TCombobox", fieldbackground=FIELD, foreground=FG, background=FIELD,
                    arrowcolor=FG)
    style.map("TCombobox",
              fieldbackground=[("readonly", FIELD)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", FG)])
    # Dropdown-Liste der Combobox einfaerben
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")

    pad = {"padx": 6, "pady": 4}

    # ---- Variablen
    v_pal = tk.StringVar(); v_src = tk.StringVar()
    v_recurse = tk.BooleanVar(value=True)
    v_format = tk.StringVar(value="png")
    v_outmode = tk.StringVar(value="inplace")
    v_out = tk.StringVar()
    v_keeptree = tk.BooleanVar(value=True)
    v_skip = tk.BooleanVar(value=True)
    v_delete = tk.BooleanVar(value=False)
    v_threads = tk.IntVar(value=min(4, max(1, os.cpu_count() or 4)))
    v_found = tk.StringVar()
    v_status = tk.StringVar()

    state = {"running": False, "cancel": None, "thread": None}
    ui_queue = queue.Queue()
    i18n_widgets = []  # (widget, key)

    def T(widget, key):
        widget.configure(text=tr(key))
        i18n_widgets.append((widget, key))
        return widget

    main = ttk.Frame(root)
    main.pack(fill="both", expand=True, padx=10, pady=8)
    main.columnconfigure(1, weight=1)

    # ---- Kopfzeile: Titel + Sprachauswahl
    title = ttk.Label(main, font=("Segoe UI", 14, "bold"), foreground=ACCENT)
    T(title, "STR_RWG_Title")
    title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    lang_box = ttk.Frame(main)
    lang_box.grid(row=0, column=2, sticky="e")
    lbl_lang = ttk.Label(lang_box); T(lbl_lang, "STR_RWG_Language")
    lbl_lang.pack(side="left", padx=(0, 4))
    cmb_lang = ttk.Combobox(lang_box, state="readonly", width=12,
                            values=[LANG_NATIVE.get(l, l) for l in _I18N["langs"]])
    cmb_lang.pack(side="left")

    # ---- Pal2PacE
    lbl_pal = ttk.Label(main); T(lbl_pal, "STR_RWG_Pal")
    lbl_pal.grid(row=1, column=0, sticky="w", **pad)
    e_pal = ttk.Entry(main, textvariable=v_pal, width=60)
    e_pal.grid(row=1, column=1, sticky="we", **pad)

    def browse_pal():
        f = filedialog.askopenfilename(title=tr("STR_RWG_DlgPal"),
                                       filetypes=[("Pal2PacE.exe", "Pal2PacE.exe"),
                                                  ("EXE", "*.exe"), ("*", "*.*")])
        if f:
            v_pal.set(f)
    b_pal = ttk.Button(main, command=browse_pal); T(b_pal, "STR_RWG_Browse")
    b_pal.grid(row=1, column=2, **pad)

    # ---- Quellordner
    lbl_src = ttk.Label(main); T(lbl_src, "STR_RWG_Source")
    lbl_src.grid(row=2, column=0, sticky="w", **pad)
    e_src = ttk.Entry(main, textvariable=v_src, width=60)
    e_src.grid(row=2, column=1, sticky="we", **pad)

    def update_found(*_):
        if v_src.get():
            n = len(scan_paa(v_src.get(), v_recurse.get()))
            v_found.set(tr("STR_RWG_Found", n=n))
        else:
            v_found.set(tr("STR_RWG_FoundNone"))

    def browse_src():
        d = filedialog.askdirectory(title=tr("STR_RWG_DlgSrc"))
        if d:
            v_src.set(d); update_found()
    b_src = ttk.Button(main, command=browse_src); T(b_src, "STR_RWG_Browse")
    b_src.grid(row=2, column=2, **pad)

    # ---- Rekursiv + gefunden
    row3 = ttk.Frame(main)
    row3.grid(row=3, column=1, columnspan=2, sticky="we")
    cb_rec = ttk.Checkbutton(row3, variable=v_recurse, command=update_found)
    T(cb_rec, "STR_RWG_Recurse"); cb_rec.pack(side="left")
    ttk.Label(row3, textvariable=v_found, foreground=OKC).pack(side="right", padx=8)

    # ---- Format + Threads
    fr = ttk.Frame(main)
    fr.grid(row=4, column=0, columnspan=3, sticky="we", pady=(6, 0))
    gb_fmt = ttk.Labelframe(fr); T(gb_fmt, "STR_RWG_FmtGroup")
    gb_fmt.pack(side="left", padx=(0, 10))
    ttk.Radiobutton(gb_fmt, text="PNG", variable=v_format, value="png").pack(side="left", padx=8, pady=6)
    ttk.Radiobutton(gb_fmt, text="TGA", variable=v_format, value="tga").pack(side="left", padx=8, pady=6)
    gb_thr = ttk.Labelframe(fr); T(gb_thr, "STR_RWG_ThreadsGroup")
    gb_thr.pack(side="left")
    ttk.Spinbox(gb_thr, from_=1, to=32, width=5, textvariable=v_threads).pack(side="left", padx=8, pady=6)
    lbl_thr = ttk.Label(gb_thr); T(lbl_thr, "STR_RWG_ThreadsHint")
    lbl_thr.pack(side="left", padx=(0, 8))

    # ---- Ausgabeort
    gb_out = ttk.Labelframe(main); T(gb_out, "STR_RWG_OutGroup")
    gb_out.grid(row=5, column=0, columnspan=3, sticky="we", pady=8)
    gb_out.columnconfigure(1, weight=1)

    def toggle_out(*_):
        sep = v_outmode.get() == "separate"
        st = "normal" if sep else "disabled"
        e_out.configure(state=st); b_out.configure(state=st); cb_tree.configure(state=st)

    rb_ip = ttk.Radiobutton(gb_out, variable=v_outmode, value="inplace", command=toggle_out)
    T(rb_ip, "STR_RWG_InPlace")
    rb_ip.grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 0))
    rb_sep = ttk.Radiobutton(gb_out, variable=v_outmode, value="separate", command=toggle_out)
    T(rb_sep, "STR_RWG_Separate")
    rb_sep.grid(row=1, column=0, sticky="w", padx=8)
    e_out = ttk.Entry(gb_out, textvariable=v_out)
    e_out.grid(row=1, column=1, sticky="we", padx=6)

    def browse_out():
        d = filedialog.askdirectory(title=tr("STR_RWG_DlgOut"))
        if d:
            v_out.set(d)
    b_out = ttk.Button(gb_out, command=browse_out); T(b_out, "STR_RWG_Browse")
    b_out.grid(row=1, column=2, padx=6, pady=4)
    cb_tree = ttk.Checkbutton(gb_out, variable=v_keeptree); T(cb_tree, "STR_RWG_KeepTree")
    cb_tree.grid(row=2, column=1, sticky="w", padx=6, pady=(0, 6))

    # ---- Optionen
    opt = ttk.Frame(main)
    opt.grid(row=6, column=0, columnspan=3, sticky="we")
    cb_skip = ttk.Checkbutton(opt, variable=v_skip); T(cb_skip, "STR_RWG_Skip")
    cb_skip.pack(side="left", padx=(6, 20))
    cb_del = ttk.Checkbutton(opt, variable=v_delete); T(cb_del, "STR_RWG_Delete")
    cb_del.pack(side="left")

    # ---- Start / Abbrechen
    btns = ttk.Frame(main)
    btns.grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 4))
    b_start = ttk.Button(btns, style="Accent.TButton"); T(b_start, "STR_RWG_Start")
    b_start.pack(side="left", padx=(6, 8), ipady=3)
    b_cancel = ttk.Button(btns, state="disabled"); T(b_cancel, "STR_RWG_Cancel")
    b_cancel.pack(side="left")

    # ---- Fortschritt
    prog = ttk.Progressbar(main, mode="determinate")
    prog.grid(row=8, column=0, columnspan=3, sticky="we", padx=6, pady=(6, 2))
    ttk.Label(main, textvariable=v_status).grid(row=9, column=0, columnspan=3, sticky="w", padx=6)

    # ---- Log
    log_frame = ttk.Frame(main)
    log_frame.grid(row=10, column=0, columnspan=3, sticky="nsew", padx=6, pady=(6, 2))
    log = tk.Text(log_frame, height=8, bg="#18181a", fg=FG, insertbackground=FG,
                  font=("Consolas", 9), wrap="none", relief="flat")
    log.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(log_frame, command=log.yview)
    sb.pack(side="right", fill="y")
    log.configure(yscrollcommand=sb.set, state="disabled")
    log.tag_configure("ok", foreground=OKC)
    log.tag_configure("skip", foreground=SKIPC)
    log.tag_configure("fail", foreground=ERRC)
    log.tag_configure("info", foreground=ACCENT)

    def log_line(text, tag="info"):
        log.configure(state="normal")
        log.insert("end", time.strftime("[%H:%M:%S] ") + text + "\n", tag)
        log.see("end")
        log.configure(state="disabled")

    def save_log():
        f = filedialog.asksaveasfilename(defaultextension=".txt",
                                         initialfile="RwG_Paa_Convert_Log.txt",
                                         filetypes=[("TXT", "*.txt")])
        if f:
            try:
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(log.get("1.0", "end"))
                messagebox.showinfo(APP_NAME, tr("STR_RWG_LogSaved"))
            except OSError as exc:
                messagebox.showerror(APP_NAME, str(exc))

    bottom = ttk.Frame(main)
    bottom.grid(row=11, column=0, columnspan=3, sticky="we", padx=6)
    b_savelog = ttk.Button(bottom, command=save_log); T(b_savelog, "STR_RWG_SaveLog")
    b_savelog.pack(side="right")

    main.rowconfigure(10, weight=1)

    # ---- Sprache anwenden
    def apply_language(*_):
        for w, key in i18n_widgets:
            try:
                w.configure(text=tr(key))
            except tk.TclError:
                pass
        root.title(APP_NAME)
        update_found()
        if not state["running"]:
            v_status.set(tr("STR_RWG_Ready"))

    def on_lang_change(_evt=None):
        idx = cmb_lang.current()
        if 0 <= idx < len(_I18N["langs"]):
            set_language(_I18N["langs"][idx])
            apply_language()
    cmb_lang.bind("<<ComboboxSelected>>", on_lang_change)

    # ---- Einstellungen einsammeln
    def gather_settings():
        return {
            "Language": _I18N["cur"],
            "Pal2PacE": v_pal.get(), "Source": v_src.get(), "Recurse": v_recurse.get(),
            "Format": v_format.get(), "OutMode": v_outmode.get(), "OutFolder": v_out.get(),
            "KeepTree": v_keeptree.get(), "SkipExist": v_skip.get(),
            "DeleteSrc": v_delete.get(), "Threads": int(v_threads.get()),
        }

    def set_running(running):
        state["running"] = running
        b_start.configure(state="disabled" if running else "normal")
        b_cancel.configure(state="normal" if running else "disabled")

    # ---- Start
    def on_start():
        if state["running"]:
            return
        pal = v_pal.get().strip(); src = v_src.get().strip()
        if not pal or not os.path.isfile(pal):
            messagebox.showwarning(APP_NAME, tr("STR_RWG_WarnPal")); return
        if not src or not os.path.isdir(src):
            messagebox.showwarning(APP_NAME, tr("STR_RWG_WarnSrc")); return
        if v_outmode.get() == "separate" and not v_out.get().strip():
            messagebox.showwarning(APP_NAME, tr("STR_RWG_WarnOut")); return
        files = scan_paa(src, v_recurse.get())
        if not files:
            messagebox.showinfo(APP_NAME, tr("STR_RWG_NoPaa")); return
        try:
            threads = max(1, min(32, int(v_threads.get())))
        except (tk.TclError, ValueError):
            threads = 4
        cfg = {"pal2pace": pal, "source": os.path.abspath(src), "format": v_format.get(),
               "separate": v_outmode.get() == "separate",
               "out_folder": os.path.abspath(v_out.get()) if v_out.get() else "",
               "keep_tree": v_keeptree.get(), "skip_existing": v_skip.get(),
               "delete_source": v_delete.get(), "threads": threads}
        save_settings(gather_settings())
        log.configure(state="normal"); log.delete("1.0", "end"); log.configure(state="disabled")
        log_line(tr("STR_RWG_LogStart", n=len(files), fmt=cfg["format"], t=threads), "info")
        prog.configure(maximum=len(files), value=0)
        cancel_event = threading.Event()
        state["cancel"] = cancel_event
        set_running(True)

        def worker():
            convert_batch(cfg, files, lambda k, p: ui_queue.put((k, p)), cancel_event)
        t = threading.Thread(target=worker, daemon=True)
        state["thread"] = t; t.start()

    def on_cancel():
        if state["running"] and state["cancel"]:
            state["cancel"].set()
            v_status.set(tr("STR_RWG_CancelReq"))
    b_start.configure(command=on_start)
    b_cancel.configure(command=on_cancel)

    # ---- UI-Queue verarbeiten
    def pump():
        try:
            while True:
                kind, p = ui_queue.get_nowait()
                if kind == "file":
                    res = p["res"]; st = res["status"]; name = res["name"]
                    if st == "ok":
                        extra = f"  ({res['message']})" if res["message"] else ""
                        log_line(tr("STR_RWG_LogOK", name=name) + extra, "ok")
                    elif st == "skipped":
                        log_line(tr("STR_RWG_LogSkip", name=name), "skip")
                    else:
                        log_line(tr("STR_RWG_LogFail", name=name, msg=res["message"]), "fail")
                    prog.configure(value=p["processed"])
                    c = p["counts"]; eta = p["eta"]
                    eta_txt = tr("STR_RWG_Eta", t=time.strftime("%H:%M:%S", time.gmtime(eta))) if eta > 0 else ""
                    v_status.set(tr("STR_RWG_Progress", p=p["processed"], t=p["total"],
                                    ok=c["ok"], sk=c["skipped"], fa=c["failed"], eta=eta_txt))
                elif kind == "done":
                    c = p["counts"]; elapsed = time.strftime("%H:%M:%S", time.gmtime(p["elapsed"]))
                    key = "STR_RWG_DoneCancel" if p["cancelled"] else "STR_RWG_DoneOK"
                    summary = tr(key, t=elapsed, ok=c["ok"], sk=c["skipped"], fa=c["failed"])
                    log_line(summary, "info"); v_status.set(summary)
                    set_running(False)
                    if not p["cancelled"]:
                        (messagebox.showwarning if c["failed"] > 0 else messagebox.showinfo)(APP_NAME, summary)
        except queue.Empty:
            pass
        root.after(80, pump)

    # ---- Einstellungen laden
    s = load_settings()
    if s:
        if s.get("Language") in _I18N["table"]:
            set_language(s["Language"])
        v_pal.set(s.get("Pal2PacE", "")); v_src.set(s.get("Source", ""))
        v_recurse.set(bool(s.get("Recurse", True)))
        v_format.set(s.get("Format", "png") if s.get("Format") in ("png", "tga") else "png")
        v_outmode.set(s.get("OutMode", "inplace") if s.get("OutMode") in ("inplace", "separate") else "inplace")
        v_out.set(s.get("OutFolder", ""))
        v_keeptree.set(bool(s.get("KeepTree", True)))
        v_skip.set(bool(s.get("SkipExist", True)))
        v_delete.set(bool(s.get("DeleteSrc", False)))
        try:
            v_threads.set(max(1, min(32, int(s.get("Threads", 4)))))
        except (ValueError, TypeError):
            pass
    if not v_pal.get():
        v_pal.set(find_pal2pace())

    # aktuelle Sprache im Dropdown markieren
    try:
        cmb_lang.current(_I18N["langs"].index(_I18N["cur"]))
    except ValueError:
        cmb_lang.current(0)

    e_src.bind("<FocusOut>", update_found)
    toggle_out()
    apply_language()   # setzt alle Texte + found + status in aktueller Sprache

    def on_close():
        if state["running"] and state["cancel"]:
            state["cancel"].set()
        save_settings(gather_settings())
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)

    root.after(80, pump)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
