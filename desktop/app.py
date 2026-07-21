from __future__ import annotations

import json
import base64
import mimetypes
import os
import re
import shutil
import math
import textwrap
import uuid
import zipfile
import tkinter as tk
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from analysis_rules import (
    HAIL_SPATTER_WORDING,
    VALID_DAMAGE_TYPES,
    normalize_annotations,
    normalize_damage_result,
    normalize_rotation_degrees,
    choose_display_rotation,
)

from storage_config import (
    AI_SETTINGS_FILE,
    AUDIT_LOG_FILE,
    CLAIMS_REPORTS_DIR,
    CLAIMS_ROOT,
    DATABASES_ROOT,
    LEARNING_LIBRARY_ROOT,
    ORIGINAL_PHOTOS_DIR,
    RECENT_PROJECT_FILE,
    REFERENCE_LIBRARY_FILE,
    SESSION_FILE,
    SYNC_INBOX_DIR,
    SYNC_OUTBOX_DIR,
    USER_SETTINGS_FILE,
)

from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    DND_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageStat, ImageTk
    from forensic_learning_engine import ForensicLearningEngine
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        pass
except ImportError as exc:
    raise SystemExit("Pillow is required. Run: py -m pip install pillow") from exc

APP_DIR = Path(__file__).resolve().parent
ASSET_DIR = APP_DIR / "assets"
IMPORTED_DIR = ORIGINAL_PHOTOS_DIR
BACKUPS_ROOT = DATABASES_ROOT / "Backups"
BG = "#071524"
PANEL = "#0b1d2e"
PANEL_2 = "#10283d"
BORDER = "#29465f"
TEXT = "#f2f6fa"
MUTED = "#b7c8d6"
ACCENT = "#168ddd"
GREEN = "#5de11d"
ORANGE = "#ff9d26"
AI_USAGE_LEDGER = APP_DIR / "ai_usage_ledger.jsonl"
APPROX_MODEL_RATES = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


@dataclass
class PhotoRecord:
    title: str
    filename: str
    category: str = "Unreviewed"
    component: str = "Not Classified"
    damage_type: str = "Not Analyzed"
    severity: str = "None"
    confidence: int = 0
    include: bool = True
    observation: str = "Not analyzed."
    source_path: str = ""
    imported: bool = False
    annotations: list[dict] = field(default_factory=list)
    annotations_locked: bool = False
    sequence_position: int | None = None
    sequence_label: str = ""
    review_status: str = ""
    forensic_grade: str = ""
    grade_reason: str = ""
    ai_prediction: dict = field(default_factory=dict)
    learning_record_id: str = ""
    correction_count: int = 0
    ai_annotations: list[dict] = field(default_factory=list)
    annotation_learning_status: str = ""
    annotation_learning_record_id: str = ""
    rotation_degrees: int = 0
    training_banner: bool = False

    @property
    def image_path(self) -> Path:
        if self.source_path:
            candidate = Path(self.source_path)
            if candidate.exists():
                return candidate
        imported_candidate = IMPORTED_DIR / self.filename
        if imported_candidate.exists():
            return imported_candidate
        return ASSET_DIR / self.filename


class DamageScopeApp(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DamageScope AI â€” Personal Inspector Edition v0.4.20 â€” AI Annotation Conversion & Editing Build")
        self.geometry("1536x980")
        try:
            saved_geometry = self._load_user_settings().get("window_geometry", "")
            if saved_geometry:
                self.geometry(saved_geometry)
        except Exception:
            pass
        self.minsize(1180, 760)
        # Contest/demo mode: start maximized so the full workflow is visible.
        # The right assessment panel is also scrollable for smaller displays.
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self.configure(bg=BG)

        IMPORTED_DIR.mkdir(parents=True, exist_ok=True)
        SYNC_INBOX_DIR.mkdir(parents=True, exist_ok=True)
        SYNC_OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        CLAIMS_ROOT.mkdir(parents=True, exist_ok=True)
        BACKUPS_ROOT.mkdir(parents=True, exist_ok=True)
        self.learning_engine = ForensicLearningEngine(APP_DIR)

        self.current_project_file: Path = SESSION_FILE
        self.project_metadata = {
            "project_name": "Untitled Inspection",
            "claim_number": "",
            "insured_name": "",
            "property_address": "",
            "date_of_loss": "",
            "notes": "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.project_dirty = False
        self.customer_info = {
            "customer_name": "",
            "property_address": "",
            "city": "",
            "state": "",
            "zip_code": "",
            "phone": "",
            "email": "",
            "insurance_carrier": "",
            "claim_number": "",
            "policy_number": "",
            "adjuster_name": "",
            "adjuster_phone": "",
            "inspection_date": "",
            "inspector_name": "",
            "contractor": "",
            "public_adjuster": "",
            "notes": "",
        }
        self.ai_settings = self._load_ai_settings()
        self.photos = self._load_session_or_seed()
        self.current_index = 0
        self.image_cache: dict[str, ImageTk.PhotoImage] = {}
        self.photo_cards: list[tk.Frame] = []
        self.user_settings = self._load_user_settings()
        self.annotation_mode: str | None = None
        self.annotation_pending_point: tuple[float, float] | None = None
        self.annotation_redo_stack: dict[int, list[dict]] = {}
        self.annotations_visible = tk.BooleanVar(
            value=bool(self.user_settings.get("show_annotations", True))
        )
        self.show_ai_ghost_annotations = tk.BooleanVar(value=False)
        self.training_mode = tk.BooleanVar(value=True)
        self.annotation_drag_start: tuple[float, float] | None = None
        self.selected_annotation_index: int | None = None
        self.annotation_edit_action: str | None = None
        self.annotation_edit_original: dict | None = None
        self.annotation_edit_start: tuple[float, float] | None = None
        self.bind("<Delete>", self._delete_selected_annotation)
        self._preview_geometry: dict[str, float] = {}
        self.library_selected_index: int | None = None
        self.ai_usage_session = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost": 0.0}

        self._configure_style()
        self._build_project_menu()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_header()
        self._build_toolbar()
        self._build_footer()
        self._build_photo_library_panel()
        self._build_main_layout()
        self.authenticated_user_email = "judge@damagescope.ai"
        self._enable_global_drag_drop()
        self._refresh_all_views(select_index=int(self.user_settings.get("last_photo_index", 0)))
        self._update_project_identity()
        self._refresh_customer_header()
        self.after(30000, self._autosave_tick)


    def _default_user_settings(self) -> dict:
        return {
            "window_geometry": "",
            "last_photo_index": 0,
            "autosave_enabled": True,
            "autosave_interval_seconds": 30,
            "show_annotations": True,
        }

    def _load_user_settings(self) -> dict:
        settings = self._default_user_settings()
        if USER_SETTINGS_FILE.exists():
            try:
                saved = json.loads(USER_SETTINGS_FILE.read_text(encoding="utf-8"))
                settings.update(saved)
            except Exception:
                pass
        return settings

    def _save_user_settings(self) -> None:
        try:
            if hasattr(self, "annotations_visible"):
                self.user_settings["show_annotations"] = bool(self.annotations_visible.get())
            self.user_settings["window_geometry"] = self.geometry()
            USER_SETTINGS_FILE.write_text(
                json.dumps(self.user_settings, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _write_audit(self, action: str, details: dict | None = None) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "project_file": str(getattr(self, "current_project_file", "")),
            "project_name": self.project_metadata.get("project_name", "") if hasattr(self, "project_metadata") else "",
            "details": details or {},
        }
        try:
            with AUDIT_LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _autosave_tick(self) -> None:
        try:
            enabled = bool(self.user_settings.get("autosave_enabled", True))
            if enabled and self.project_dirty and self.current_project_file != SESSION_FILE:
                self._save_session(show_status=False)
                if hasattr(self, "analysis_status"):
                    self.analysis_status.configure(text="Autosaved.")
                self._write_audit("autosave")
            self._save_user_settings()
        finally:
            interval = int(self.user_settings.get("autosave_interval_seconds", 30))
            self.after(max(10, interval) * 1000, self._autosave_tick)

    def export_audit_log(self) -> None:
        if not AUDIT_LOG_FILE.exists():
            messagebox.showinfo("DamageScope AI", "No audit entries have been recorded yet.")
            return
        selected = filedialog.asksaveasfilename(
            title="Export Audit Log",
            defaultextension=".jsonl",
            initialfile="DamageScope_Audit_Log.jsonl",
            filetypes=[("JSON Lines", "*.jsonl"), ("Text Files", "*.txt")],
        )
        if not selected:
            return
        try:
            shutil.copy2(AUDIT_LOG_FILE, selected)
            messagebox.showinfo("DamageScope AI", f"Audit log exported:\n{selected}")
        except Exception as exc:
            messagebox.showerror("DamageScope AI", f"Could not export audit log:\n{exc}")

    def open_persistence_settings(self) -> None:
        window = tk.Toplevel(self)
        window.title("DamageScope AI â€” Persistence Settings")
        window.geometry("520x360")
        window.configure(bg=BG)
        window.transient(self)
        window.grab_set()

        tk.Label(
            window,
            text="Persistence Settings",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 17),
        ).pack(anchor="w", padx=24, pady=(20, 12))

        autosave_var = tk.BooleanVar(value=bool(self.user_settings.get("autosave_enabled", True)))
        interval_var = tk.IntVar(value=int(self.user_settings.get("autosave_interval_seconds", 30)))
        annotations_var = tk.BooleanVar(value=bool(self.user_settings.get("show_annotations", True)))

        panel = tk.Frame(window, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        panel.pack(fill="both", expand=True, padx=24, pady=(0, 18))

        tk.Checkbutton(
            panel,
            text="Enable autosave",
            variable=autosave_var,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", padx=18, pady=(18, 10))

        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill="x", padx=18, pady=8)
        tk.Label(row, text="Autosave interval", bg=PANEL, fg=TEXT).pack(side="left")
        interval_combo = ttk.Combobox(
            row,
            textvariable=interval_var,
            values=[15, 30, 60, 120, 300],
            state="readonly",
            style="Dark.TCombobox",
            width=10,
        )
        interval_combo.pack(side="right")
        tk.Label(row, text="seconds", bg=PANEL, fg=MUTED).pack(side="right", padx=(0, 8))

        tk.Checkbutton(
            panel,
            text="Show annotations when projects reopen",
            variable=annotations_var,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", padx=18, pady=10)

        tk.Label(
            panel,
            text="The application also remembers the last opened project, selected photo, "
                 "window size, AI Manager settings, annotations, and report selections.",
            bg=PANEL,
            fg=MUTED,
            justify="left",
            wraplength=430,
        ).pack(anchor="w", padx=18, pady=(10, 18))

        buttons = tk.Frame(window, bg=BG)
        buttons.pack(fill="x", padx=24, pady=(0, 18))

        def save_settings() -> None:
            self.user_settings["autosave_enabled"] = autosave_var.get()
            self.user_settings["autosave_interval_seconds"] = interval_var.get()
            self.user_settings["show_annotations"] = annotations_var.get()
            self.annotations_visible.set(annotations_var.get())
            self._save_user_settings()
            self._write_audit("persistence_settings_updated")
            self._refresh_preview()
            window.destroy()

        self._button(buttons, "Save", save_settings).pack(side="right")
        self._button(buttons, "Cancel", window.destroy).pack(side="right", padx=(0, 8))

    def _build_project_menu(self) -> None:
        menu_bar = tk.Menu(self)
        project_menu = tk.Menu(menu_bar, tearoff=False)
        project_menu.add_command(label="New Project", accelerator="Ctrl+N", command=self.new_project)
        project_menu.add_command(label="Open Project...", accelerator="Ctrl+O", command=self.open_project)
        project_menu.add_separator()
        project_menu.add_command(label="Save Project", accelerator="Ctrl+S", command=self.save_project)
        project_menu.add_command(label="Save Project As...", accelerator="Ctrl+Shift+S", command=self.save_project_as)
        project_menu.add_separator()
        project_menu.add_command(label="Project Details...", command=self.open_project_manager)
        project_menu.add_command(label="Persistence Settings...", command=self.open_persistence_settings)
        advanced_menu = tk.Menu(project_menu, tearoff=False)
        advanced_menu.add_command(label="AI Manager...", command=self.open_ai_manager)
        project_menu.add_cascade(label="Advanced Settings", menu=advanced_menu)
        project_menu.add_command(label="Export Audit Log...", command=self.export_audit_log)
        project_menu.add_separator()
        project_menu.add_command(label="Exit", command=self._on_close)
        menu_bar.add_cascade(label="Project", menu=project_menu)

        sync_menu = tk.Menu(menu_bar, tearoff=False)
        sync_menu.add_command(label="Export Sync Package...", command=self.export_sync_package)
        sync_menu.add_command(label="Import Sync Package...", command=self.import_sync_package)
        sync_menu.add_separator()
        sync_menu.add_command(label="Open Sync Folders", command=self.open_sync_folders)
        menu_bar.add_cascade(label="Sync", menu=sync_menu)
        self.config(menu=menu_bar)

        self.bind_all("<Control-n>", lambda event: self.new_project())
        self.bind_all("<Control-o>", lambda event: self.open_project())
        self.bind_all("<Control-s>", lambda event: self.save_project())
        self.bind_all("<Control-Shift-S>", lambda event: self.save_project_as())

        # Global inspection-sequence navigation. Do not steal arrow keys while
        # the user is typing in an entry, text box, or drop-down control.
        self.bind_all("<Up>", lambda event: self._handle_photo_arrow_key(event, -1), add="+")
        self.bind_all("<Down>", lambda event: self._handle_photo_arrow_key(event, 1), add="+")

    def _handle_photo_arrow_key(self, event, delta: int) -> str | None:
        """Select previous/next photo in the authoritative inspection sequence."""
        widget = getattr(event, "widget", None)
        if isinstance(widget, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox, tk.Spinbox)):
            return None
        if not self.photos:
            return "break"

        ordered_indices = [index for index, _photo in self._sequence_photos()]
        if not ordered_indices:
            ordered_indices = [
                index for index, photo in enumerate(self.photos)
                if not self._is_demo_photo(photo)
            ]
        if not ordered_indices:
            return "break"
        try:
            current_position = ordered_indices.index(self.current_index)
        except ValueError:
            current_position = 0
        target_position = max(0, min(current_position + delta, len(ordered_indices) - 1))
        target_index = ordered_indices[target_position]
        if target_index != self.current_index:
            self.library_selected_index = target_index
            self.show_photo(target_index)
        return "break"

    def _update_project_identity(self) -> None:
        name = self.project_metadata.get("project_name", "Untitled Inspection") or "Untitled Inspection"
        dirty = " *" if self.project_dirty else ""
        self.title(f"DamageScope AI â€” {name}{dirty} â€” Personal Inspector Edition v0.4.20 â€” AI Annotation Conversion & Editing Build")
        if hasattr(self, "project_name_label"):
            self.project_name_label.configure(text=f"Project: {name}{dirty}")

    def _confirm_discard_or_save(self) -> bool:
        if not self.project_dirty:
            return True
        answer = messagebox.askyesnocancel(
            "DamageScope AI",
            "Save changes to the current project before continuing?",
        )
        if answer is None:
            return False
        if answer:
            return self.save_project()
        return True

    def new_project(self) -> None:
        if not self._confirm_discard_or_save():
            return
        self.photos = []
        self.current_index = 0
        self.current_project_file = SESSION_FILE
        self.project_metadata = {
            "project_name": "Untitled Inspection",
            "claim_number": "",
            "insured_name": "",
            "property_address": "",
            "date_of_loss": "",
            "notes": "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        for key in self.customer_info:
            self.customer_info[key] = ""
        self.project_dirty = True
        self._refresh_all_views(select_index=0)
        self._refresh_customer_header()
        self._update_project_identity()
        self.open_project_manager(first_save=True)

    def open_project(self) -> None:
        if not self._confirm_discard_or_save():
            return
        selected = filedialog.askopenfilename(
            title="Open DamageScope Project",
            filetypes=[
                ("DamageScope Project", "*.dscope"),
                ("JSON Project", "*.json"),
                ("All Files", "*.*"),
            ],
        )
        if not selected:
            return
        project_file = Path(selected)
        try:
            raw = json.loads(project_file.read_text(encoding="utf-8"))
            records = [PhotoRecord(**item) for item in raw.get("photos", [])]
            self.current_project_file = project_file
            self.project_metadata = {
                "project_name": "Untitled Inspection",
                "claim_number": "",
                "insured_name": "",
                "property_address": "",
                "date_of_loss": "",
                "notes": "",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            self.project_metadata.update(raw.get("project", {}))
            loaded_customer = raw.get("customer_info", {})
            if isinstance(loaded_customer, dict):
                for key in self.customer_info:
                    if key in loaded_customer:
                        self.customer_info[key] = str(loaded_customer.get(key, ""))
            self.photos = records
            self.current_index = 0
            self.project_dirty = False
            RECENT_PROJECT_FILE.write_text(
                json.dumps({"project_file": str(project_file)}, indent=2),
                encoding="utf-8",
            )
            self._refresh_all_views(select_index=0)
            self._update_project_identity()
            self._refresh_customer_header()
            self.analysis_status.configure(text="Project opened.")
            self._write_audit("project_opened", {"project_file": str(project_file)})
        except Exception as exc:
            messagebox.showerror("DamageScope AI", f"Could not open project:\n{exc}")

    def save_project(self) -> bool:
        if self.current_project_file == SESSION_FILE:
            return self.save_project_as()
        return self._save_session(show_status=True)

    def _safe_file_identity(self) -> str:
        identity = (
            self.customer_info.get("customer_name", "").strip()
            or self.customer_info.get("claim_number", "").strip()
            or "Untitled Inspection"
        )
        cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", identity).strip().replace(" ", "_")
        return cleaned or "DamageScope_Inspection"

    def save_project_as(self) -> bool:
        """Save seamlessly to the subscriber workspace without a Save As dialog."""
        project_folder = CLAIMS_ROOT / self._safe_file_identity()
        project_folder.mkdir(parents=True, exist_ok=True)
        project_file = project_folder / f"{self._safe_file_identity()}.dscope"
        asset_dir = project_folder / "photos"
        asset_dir.mkdir(parents=True, exist_ok=True)

        try:
            for photo in self.photos:
                source = photo.image_path
                if not source.exists():
                    continue
                destination = asset_dir / photo.filename
                counter = 2
                while destination.exists() and destination.resolve() != source.resolve():
                    destination = asset_dir / f"{Path(photo.filename).stem}_{counter}{Path(photo.filename).suffix}"
                    counter += 1
                if destination.resolve() != source.resolve():
                    shutil.copy2(source, destination)
                photo.filename = destination.name
                photo.source_path = str(destination)
                photo.imported = True

            self.current_project_file = project_file
            self.project_metadata["project_name"] = (
                self.customer_info.get("customer_name", "").strip()
                or self.customer_info.get("claim_number", "").strip()
                or "Untitled Inspection"
            )
            self.project_dirty = True
            saved = self._save_session(show_status=True)
            if saved:
                self.analysis_status.configure(text="Inspection saved successfully.")
                self._write_audit("seamless_project_saved", {"project_file": str(project_file)})
            return saved
        except Exception as exc:
            messagebox.showerror("DamageScope AI", f"Could not save project:\n{exc}")
            return False

    def open_project_manager(self, first_save: bool = False) -> None:
        window = tk.Toplevel(self)
        window.title("DamageScope AI â€” Inspection Session Management")
        window.geometry("700x760")
        window.minsize(660, 680)
        window.configure(bg=BG)
        window.transient(self)
        window.grab_set()

        tk.Label(window, text="Inspection Session Management", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 17)).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(window,
                 text="The inspection file is identified by the insured/customer name or claim number.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(0, 14))

        form = tk.Frame(window, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        form.pack(fill="both", expand=True, padx=24, pady=(0, 18))

        fields = [
            ("Insured / Customer Name", "customer_name"),
            ("Insurance Company", "insurance_carrier"),
            ("Claim Number", "claim_number"),
            ("Telephone Number", "phone"),
            ("Customer Email", "email"),
            ("Property Address", "property_address"),
            ("Property City", "city"),
            ("Property State", "state"),
            ("Property ZIP Code", "zip_code"),
            ("Date of Loss", "date_of_loss"),
        ]
        variables: dict[str, tk.StringVar] = {}
        for row, (label, key) in enumerate(fields):
            tk.Label(form, text=label, bg=PANEL, fg=TEXT,
                     font=("Segoe UI Semibold", 9)).grid(
                row=row, column=0, sticky="w", padx=18, pady=(12 if row == 0 else 6, 3)
            )
            initial = self.project_metadata.get(key, "") if key == "date_of_loss" else self.customer_info.get(key, "")
            if key == "phone":
                initial = self._format_phone_number(initial)
            variable = tk.StringVar(value=initial)
            variables[key] = variable
            entry = tk.Entry(form, textvariable=variable, bg=PANEL_2, fg=TEXT,
                             insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
            entry.grid(row=row, column=1, sticky="ew", padx=18,
                       pady=(12 if row == 0 else 6, 3), ipady=7)

        tk.Label(form, text="Project Notes", bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).grid(
            row=len(fields), column=0, sticky="nw", padx=18, pady=10
        )
        notes = tk.Text(form, height=6, bg=PANEL_2, fg=TEXT, insertbackground=TEXT,
                        relief="flat", wrap="word", font=("Segoe UI", 10))
        notes.grid(row=len(fields), column=1, sticky="nsew", padx=18, pady=10)
        notes.insert("1.0", self.customer_info.get("notes", self.project_metadata.get("notes", "")))

        form.grid_columnconfigure(1, weight=1)
        form.grid_rowconfigure(len(fields), weight=1)

        tk.Label(window,
                 text="File identity: insured/customer name first; claim number used when no name is entered.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=640,
                 justify="left").pack(anchor="w", padx=24)

        buttons = tk.Frame(window, bg=BG)
        buttons.pack(fill="x", padx=24, pady=18)

        def apply_and_save() -> None:
            for key, variable in variables.items():
                value = variable.get().strip()
                if key == "date_of_loss":
                    self.project_metadata[key] = value
                else:
                    self.customer_info[key] = value

            notes_value = notes.get("1.0", "end").strip()
            self.customer_info["notes"] = notes_value
            self.project_metadata["notes"] = notes_value

            insured = self.customer_info.get("customer_name", "").strip()
            claim = self.customer_info.get("claim_number", "").strip()
            self.project_metadata["project_name"] = insured or claim or "Untitled Inspection"
            self.project_metadata["insured_name"] = insured
            self.project_metadata["claim_number"] = claim
            self.project_metadata["property_address"] = self.customer_info.get("property_address", "").strip()

            self.project_dirty = True
            self._refresh_customer_header()
            self._update_project_identity()
            saved = self.save_project()
            if saved:
                window.destroy()

        self._button(buttons, "Save Inspection", apply_and_save).pack(side="right")
        self._button(buttons, "Cancel", window.destroy).pack(side="right", padx=(0, 8))

        if first_save:
            window.protocol("WM_DELETE_WINDOW", window.destroy)

    def _on_close(self) -> None:
        if not self._confirm_discard_or_save():
            return
        self._save_user_settings()
        self._write_audit("application_closed")
        self.destroy()


    def _default_ai_settings(self) -> dict:
        return {
            "mode": "Production Vision API",
            "provider": "OpenAI Responses API",
            "model_name": "gpt-4.1",
            "model_path": "",
            "api_key": "",
            "endpoint": "https://api.openai.com/v1/responses",
            "device": "CPU",
            "confidence_threshold": 0.70,
            "auto_annotate": True,
            "offline_required": False,
            "status": "Enter API key, then test configuration.",
        }

    def _load_ai_settings(self) -> dict:
        settings = self._default_ai_settings()
        if AI_SETTINGS_FILE.exists():
            try:
                saved = json.loads(AI_SETTINGS_FILE.read_text(encoding="utf-8"))
                settings.update(saved)
            except Exception:
                pass

        legacy_model_names = {
            "DamageScope Demo Classifier",
            "DamageScope Production Vision",
            "DamageScope AI Classifier",
        }
        if (
            settings.get("mode") == "Production Vision API"
            and settings.get("model_name", "").strip() in legacy_model_names
        ):
            settings["model_name"] = "gpt-4.1"
            settings["provider"] = "OpenAI Responses API"
            settings["endpoint"] = "https://api.openai.com/v1/responses"
            settings["status"] = "Legacy model name corrected to gpt-4.1."
            try:
                AI_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            except Exception:
                pass

        return settings

    def _save_ai_settings(self) -> bool:
        try:
            AI_SETTINGS_FILE.write_text(
                json.dumps(self.ai_settings, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception as exc:
            messagebox.showerror("DamageScope AI", f"Could not save AI settings:\n{exc}")
            return False

    def _active_model_label(self) -> str:
        mode = self.ai_settings.get("mode", "Not Connected")
        model = self.ai_settings.get("model_name", "").strip()
        if model:
            return f"{mode} â€” {model}"
        return mode

    def _validate_ai_settings(self, settings: dict) -> tuple[bool, str]:
        mode = settings.get("mode", "")
        if mode == "Offline ONNX":
            model_path = Path(settings.get("model_path", ""))
            if not model_path.exists() or model_path.suffix.lower() != ".onnx":
                return False, "Select a valid .onnx model file."
        elif mode == "Production Vision API":
            if not settings.get("endpoint", "").strip():
                return False, "Enter an API endpoint."
            if not settings.get("api_key", "").strip():
                return False, (
                    "Everything else is already configured. "
                    "Enter only the API key, then click Test Configuration."
                )
            model_name = settings.get("model_name", "").strip()
            if not model_name:
                return False, "Enter a model name."
            if model_name.lower().startswith("damagescope"):
                return False, (
                    "The Model Name must be an actual API model ID. "
                    "Use gpt-4.1 for the OpenAI Responses API."
                )
        return True, "AI Manager configuration is valid."

    def _test_ai_connection(self, settings: dict) -> tuple[bool, str]:
        valid, message = self._validate_ai_settings(settings)
        if not valid:
            return False, message

        mode = settings.get("mode")
        if mode == "Demo / Rules":
            return True, "Demo / Rules engine is ready."
        if mode == "Offline ONNX":
            try:
                import onnxruntime  # type: ignore
                available = onnxruntime.get_available_providers()
                return True, f"ONNX Runtime ready. Providers: {', '.join(available)}"
            except ImportError:
                return False, "ONNX Runtime is not installed. Add onnxruntime to requirements.txt."
            except Exception as exc:
                return False, f"ONNX Runtime test failed: {exc}"
        if mode == "Production Vision API":
            return True, "Production Vision API configuration is valid."
        return False, "Unknown AI mode."


    def _filename_hints(self, photo: PhotoRecord) -> tuple[str, str]:
        name = f"{photo.title} {photo.filename}".lower()
        if "mailbox" in name or "address" in name:
            return "Mailbox", "Mailbox with Address"
        if "gutter" in name or "downspout" in name:
            return "Exterior Building", "Gutters / Downspout"
        if "window" in name or "screen" in name:
            return "Exterior Building", "Windows / Screens"
        if "roof" in name or "shingle" in name:
            return "Roof", "Roof Covering"
        if "ac" in name or "hvac" in name or "condenser" in name:
            return "Other", "AC Condenser"
        if "front" in name:
            return "Exterior Building", "Front Elevation"
        if "right" in name:
            return "Exterior Building", "Right Elevation"
        if "rear" in name or "back" in name:
            return "Exterior Building", "Rear Elevation"
        if "left" in name:
            return "Exterior Building", "Left Elevation"
        return "Unreviewed", "Not Classified"

    def _open_oriented_image(self, path: Path) -> Image.Image:
        """Open an image with EXIF orientation applied before display or AI analysis."""
        with Image.open(path) as source:
            return ImageOps.exif_transpose(source).convert("RGB")

    def _basic_image_metrics(self, path: Path) -> dict:
        with Image.open(path) as image:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            gray = rgb.convert("L")
            stat = ImageStat.Stat(gray)
            brightness = float(stat.mean[0])
            contrast = float(stat.stddev[0])

            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            sharpness = float(edge_stat.mean[0])

            width, height = rgb.size

        return {
            "brightness": brightness,
            "contrast": contrast,
            "sharpness": sharpness,
            "width": width,
            "height": height,
        }

    def _demo_rules_analysis(self, photo: PhotoRecord) -> dict:
        category, component = self._filename_hints(photo)
        metrics = self._basic_image_metrics(photo.image_path)

        warnings: list[str] = []
        if metrics["brightness"] < 45:
            warnings.append("Image appears dark.")
        elif metrics["brightness"] > 220:
            warnings.append("Image appears overexposed.")

        if metrics["sharpness"] < 8:
            warnings.append("Image may be blurry or lack detail.")

        if metrics["width"] < 800 or metrics["height"] < 600:
            warnings.append("Image resolution is low for forensic review.")

        name = f"{photo.title} {photo.filename}".lower()
        damage_type = "None"
        severity = "None"
        confidence = 78
        evidence = "No obvious damage classification was produced by the demo rules engine."

        # Conservative demo logic. This is intentionally a workflow test,
        # not a production forensic conclusion.
        if any(term in name for term in ["hail", "dent", "ding", "impact"]):
            damage_type = "Possible Impact"
            severity = "Minor"
            confidence = 72
            evidence = "Filename or user labeling suggests possible impact-related damage. Human review required."
        elif any(term in name for term in ["wind", "crease", "lifted", "missing"]):
            damage_type = "Possible Wind"
            severity = "Minor"
            confidence = 72
            evidence = "Filename or user labeling suggests possible wind-related damage. Human review required."
        elif category == "Mailbox":
            damage_type = "None"
            severity = "None"
            confidence = 94
            evidence = "Address-verification photo. No damage conclusion required for the mailbox workflow."
        else:
            confidence = 76
            evidence = "Component classified by filename and image metadata. No visible-damage conclusion from the demo engine."

        observation_lines = [
            f"Component candidate: {component}.",
            evidence,
            f"Image quality: brightness {metrics['brightness']:.0f}, "
            f"contrast {metrics['contrast']:.0f}, sharpness {metrics['sharpness']:.0f}.",
        ]
        if warnings:
            observation_lines.append("Quality warning: " + " ".join(warnings))
        else:
            observation_lines.append("Image quality appears suitable for preliminary review.")

        result = {
            "category": category,
            "component": component,
            "damage_type": damage_type,
            "severity": severity,
            "confidence": confidence,
            "observation": "\n".join(observation_lines),
            "metrics": metrics,
            "warnings": warnings,
            "engine": "Demo / Rules",
            "rotation_degrees": 0,
        }
        return normalize_damage_result(result, filename=photo.filename, image_path=photo.image_path)


    def _image_data_url(self, path: Path) -> str:
        # Re-encode after EXIF transpose so the AI receives the same upright image shown to the user.
        import io
        image = self._open_oriented_image(path)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=95)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def _load_forensic_reference_rules(self) -> list[dict]:
        try:
            raw = json.loads(REFERENCE_LIBRARY_FILE.read_text(encoding="utf-8"))
            rules = raw.get("rules", [])
            return rules if isinstance(rules, list) else []
        except Exception:
            return []

    def _forensic_reference_prompt(self) -> str:
        rules = self._load_forensic_reference_rules()
        if not rules:
            return "No local inspector-approved forensic rules are available."

        lines = [
            "INSPECTOR-APPROVED FORENSIC REFERENCE RULES:",
            "Use these as authoritative application guidance.",
        ]
        for rule in rules:
            lines.append("")
            lines.append(
                f"Rule {rule.get('rule_id', 'UNKNOWN')}: "
                f"{rule.get('finding', 'Unknown Finding')}"
            )
            if rule.get("positive_visual_cues"):
                lines.append("Positive visual cues:")
                lines.extend(f"- {x}" for x in rule["positive_visual_cues"])
            if rule.get("negative_visual_cues"):
                lines.append("Do not:")
                lines.extend(f"- {x}" for x in rule["negative_visual_cues"])
            if rule.get("approved_observation_lines"):
                lines.append("Approved observation wording:")
                lines.extend(f"- {x}" for x in rule["approved_observation_lines"])
        return "\n".join(lines)

    def _production_prompt(self, photo: PhotoRecord) -> str:
        reference_rules = self._forensic_reference_prompt()
        learning_context = self.learning_engine.build_prompt_context(
            photo.image_path, category_hint=photo.category, component_hint=photo.component
        )
        return reference_rules + "\n\n" + learning_context + "\n\n" + """
You are the production visual-analysis engine for DamageScope AI, a property
inspection and forensic documentation application.

FIRST classify the photograph into exactly one Category and one Classification.

Allowed Category values:
- Property Identification
- Elevation
- Roofing
- Exterior Component
- HVAC
- Interior
- Site / Other
- Unreviewed

Allowed Classification values by Category:

Property Identification:
- Mailbox / Address
- House Number
- Street View
- Front Property Overview

Elevation:
- Front Elevation
- Right Front Elevation
- Right Elevation
- Right Rear Elevation
- Rear Elevation
- Left Rear Elevation
- Left Elevation
- Left Front Elevation
- Garage Elevation
- Detached Structure Elevation
- Unknown Elevation

Roofing:
- Roof Overview
- Roof Covering / Shingles
- Ridge
- Valley
- Eave
- Rake
- Flashing
- Roof Vent
- Pipe Jack
- Chimney
- Other Roofing

Exterior Component:
- Windows / Screens
- Exterior Door
- Gutters
- Downspout
- Siding
- Fascia
- Soffit
- Fence
- Deck / Porch
- Other Exterior Component

HVAC:
- AC Condenser
- Heat Pump
- Package Unit
- Other HVAC

Interior:
- Interior Overview
- Ceiling
- Wall
- Flooring
- Cabinetry
- Interior Door
- Other Interior

Site / Other:
- Tree / Vegetation
- Detached Building
- Contents
- Debris
- Other

Classify a clearly visible mailbox, house number, or address marker as
Property Identification. Classify asphalt shingle close-ups as
Roofing / Roof Covering / Shingles. For elevations, use the entire inspection context, including visible entry,
driveway, garage, front door, house-number location, wall depth, roof orientation,
visible building corners, and adjacent photographs. Follow a clockwise exterior
inspection path: Front, Right Front, Right, Right Rear, Rear, Left Rear, Left,
Left Front. Do not classify a porch or deck as the primary elevation; keep the
elevation as the primary classification and mention the porch only as a visible
feature when material. Use Unknown Elevation rather than guessing.

For roof-covering/shingle photographs, inspect any pink or purple field chalk circle or bracket as an inspector-highlighted evaluation area. Independently evaluate the marked area. When a localized dark bruise, granule displacement, exposed asphalt, or impact morphology is visible inside that marked area, classify Damage Type as "Hail Impact" and use the observation "Consistent with debris and hail impact damage." Do not return "None" merely because the impact is subtle. For exterior contents such as plastic patio chairs, distributed light-colored impact marks across multiple exposed surfaces are classified as Hail Spatter when visually supported. Use Category "Site / Other", Classification "Contents", Damage Type "Hail Spatter", and the observation "Consistent with debris and hail impact damage." Do not misclassify this pattern as ordinary weathering, staining, discoloration, or Other. Determine the rotation needed to display the subject naturally upright before analysis. For chairs, legs must point downward; for roof photos, shingle courses should run left-to-right when practical.

SECOND inspect the visible component for supported conditions or damage.
Do not invent hidden damage, measurements, cause, code requirements, or
engineering conclusions. Use evidence-based language. Do not use Possible Hail, Possible Wind, or Possible Impact as final damage types. Use review_status "Needs Clarification" when evidence is insufficient.

Return ONLY one JSON object:
{
  "category": "allowed Category value",
  "component": "allowed Classification value",
  "damage_type": "None|Hail Impact|Hail Spatter|Wind Crease|Wind Lifted Shingle|Missing Shingle|Loose Shingle|Previous Repair|Water|Other",
  "rotation_degrees": "0|90|180|270",
  "severity": "None|Minor|Moderate|Severe",
  "review_status": "Confirmed|Needs Clarification|No Finding",
  "confidence": 0,
  "observation": "concise evidence-based forensic narrative",
  "damage_checks": {
    "soft_metal_damage": "Yes|No|Unknown",
    "dents": "Yes|No|Unknown",
    "dings": "Yes|No|Unknown",
    "paint_damage": "Yes|No|Unknown",
    "rust_corrosion": "Yes|No|Unknown",
    "loose_missing_parts": "Yes|No|Unknown"
  },
  "annotations": [
    {
      "type": "circle|arrow|line|label",
      "x": 0.0,
      "y": 0.0,
      "x1": 0.0,
      "y1": 0.0,
      "x2": 0.0,
      "y2": 0.0,
      "radius": 0.04,
      "text": "short evidence label"
    }
  ]
}

Coordinates must be normalized from 0.0 to 1.0. Add annotations only where a
specific visible finding can be localized. Keep callout labels away from and
outside the damaged area. For a wind crease, place a thick white LINE just below the visible crease, parallel to the nearest shingle course, so the line does not cover the evidence. For a missing shingle, use a yellow circle around the exposed area plus a yellow leader arrow and a short label outside the evidence. Do not annotate general elevation views or photographs with no supported damage.

DOMINANT-COMPONENT SAFEGUARD:
- Identify the primary visible component before assigning damage.
- The reported component must match the area being annotated.
- Never report Roof Vent when the marked evidence is on the roof covering.
- Never report Gutter or Downspout when the annotation lands on adjacent shingles, brick, siding, fascia, or sky.
- If the visible subject and proposed component do not clearly agree, set review_status to "Needs Clarification" and do not force a confirmed finding.

CONDITION-BEFORE-CAUSE RULE:
- Identify the observable condition first.
- Do not say a missing shingle was caused by wind unless visible uplift, crease, torn seal strip, displaced material, or inspection-level corroboration supports that cause.
- Use: "Missing shingle observed. Cause of loss requires additional inspection." when cause is not visually established.

SOFT-METAL LOCALIZATION RULE:
- If a gutter, downspout, roof vent, flashing, or other soft-metal component is classified as Hail Impact, return at least one tight circle centered on an actual visible dent.
- The circle must remain on the named metal component.
- If the impact can be seen but cannot be localized precisely, set review_status to "Needs Clarification" instead of returning a misleading annotation.
- Do not circle the entire component or an adjacent roof area.

MISSING-SHINGLE / PREVIOUS-REPAIR RULE:
- Missing Shingle means material is absent and an exposed void, mat, underlayment, or lower surface is visible.
- Previous Repair means replacement material, patching, sealant, or repaired material is visibly present.
- If the image does not clearly distinguish between those conditions, use review_status "Needs Clarification".

If a suspected condition cannot be classified confidently, set review_status to "Needs Clarification". Keep category and component when supported, set damage_type to "Other", and provide one short sentence requesting inspector clarification. You MAY still return circles, arrows, lines, and labels around the exact visible areas that caused uncertainty. Labels must use cautious wording such as "Wind Crease (Possible)" or "Missing Shingle (Possible)". Never cover the suspected evidence.

For property-identification photographs, carefully inspect visible house
numbers, mailbox numbers, and address plaques. State the readable number in
the observation. Do not guess an unreadable number. For elevation photographs,
support corner classifications: Front Right Corner, Right Rear Corner,
Left Rear Corner, and Left Front Corner.

CONCISE REPORTING RULE:
- Front Property Overview and elevation overview photographs are orientation/context
  photographs. When no supported damage or noteworthy condition is visible, return
  an empty observation string and no annotations.
- Do not write generic descriptions of the house, porch, windows, siding, roof form,
  landscaping, or other ordinary features in Detailed Findings.
- Only add an observation to an overview/elevation photograph when it documents a
  specific visible damage condition or another material inspection finding.
- Keep damage findings short and direct. Example: "Missing shingle consistent with
  wind displacement." Do not write a paragraph when one sentence is sufficient.
""".strip()

    def _extract_json_object(self, text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("The AI response did not contain a JSON object.")
        parsed = json.loads(cleaned[start:end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("The AI response JSON was not an object.")
        return parsed

    def _parse_responses_api_text(self, payload: dict) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        text_parts: list[str] = []
        for output_item in payload.get("output", []):
            for content_item in output_item.get("content", []):
                if content_item.get("type") in {"output_text", "text"}:
                    text = content_item.get("text", "")
                    if isinstance(text, str):
                        text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts)

        choices = payload.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, str):
                return content

        raise ValueError("The provider response did not contain readable output text.")

    def _normalize_production_result(self, photo: PhotoRecord, raw: dict) -> dict:
        raw = normalize_damage_result(raw, filename=photo.filename, image_path=photo.image_path)
        try:
            with Image.open(photo.image_path) as _orientation_image:
                _orientation_image = ImageOps.exif_transpose(_orientation_image)
                _image_width, _image_height = _orientation_image.size
        except Exception:
            _image_width, _image_height = 0, 0
        raw["rotation_degrees"] = choose_display_rotation(
            suggested_rotation=raw.get("rotation_degrees", 0),
            image_width=_image_width,
            image_height=_image_height,
            component=str(raw.get("component", "")),
            observation=str(raw.get("observation", "")),
            filename=photo.filename,
        )
        valid_categories = {
            "Property Identification", "Elevation", "Roofing",
            "Exterior Component", "HVAC", "Interior",
            "Site / Other", "Unreviewed",
        }
        valid_damage = {
            "None", "Hail Impact", "Hail Spatter", "Wind Crease", "Wind Lifted Shingle",
            "Missing Shingle", "Loose Shingle", "Previous Repair",
            "Possible Hail", "Possible Wind", "Possible Impact", "Water", "Other"
        }
        valid_severity = {"None", "Minor", "Moderate", "Severe"}

        category = str(raw.get("category", "Unreviewed"))
        if category not in valid_categories:
            category = "Unreviewed"

        damage_type = str(raw.get("damage_type", "Other"))
        if damage_type not in valid_damage:
            damage_type = "Other"

        severity = str(raw.get("severity", "None"))
        if severity not in valid_severity:
            severity = "None"

        try:
            confidence_value = float(raw.get("confidence", 0))
            confidence = int(round(confidence_value * 100)) if 0.0 <= confidence_value <= 1.0 else int(round(confidence_value))
        except (TypeError, ValueError):
            confidence = 0
        confidence = max(0, min(100, confidence))

        annotations: list[dict] = []
        for item in raw.get("annotations", []) or []:
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            if kind not in {"circle", "arrow", "line", "label"}:
                continue

            normalized = {"type": kind}
            for key in ("x", "y", "x1", "y1", "x2", "y2", "radius"):
                if key in item:
                    try:
                        normalized[key] = max(0.0, min(1.0, float(item[key])))
                    except (TypeError, ValueError):
                        pass
            if kind == "label":
                normalized["text"] = str(item.get("text", "Finding"))[:80]
            annotations.append(normalized)

        component = str(raw.get("component", "Not Classified"))[:120]
        observation = str(raw.get("observation", "")).strip()
        review_status = str(raw.get("review_status", "")).strip()
        if review_status not in {"Confirmed", "Needs Clarification", "No Finding"}:
            review_status = ""

        context_components = {
            "Front Property Overview",
            "Front Elevation",
            "Front Right Corner",
            "Right Elevation",
            "Right Rear Corner",
            "Rear Elevation",
            "Left Rear Corner",
            "Left Elevation",
            "Left Front Corner",
            "Garage Elevation",
            "Detached Structure Elevation",
            "Unknown Elevation",
        }
        if (
            component in context_components
            and damage_type == "None"
            and severity == "None"
        ):
            observation = ""
            annotations = []
            review_status = "No Finding"

        # Verify readable mailbox/house number against the claim address.
        if category == "Property Identification" or "mailbox" in component.lower() or "house number" in component.lower():
            street = self.customer_info.get("property_address", "").strip()
            city = self.customer_info.get("city", "").strip()
            state = self.customer_info.get("state", "").strip()
            zip_code = self.customer_info.get("zip_code", "").strip()
            expected_match = re.match(r"\s*(\d+[A-Za-z]?)", street)
            observed_match = re.search(r"\b(\d{2,6}[A-Za-z]?)\b", observation)
            if expected_match and observed_match and expected_match.group(1).lower() == observed_match.group(1).lower():
                full_address = ", ".join(part for part in [street, city, f"{state} {zip_code}".strip()] if part)
                observation = f"Mailbox address verified: {full_address}."
            elif expected_match and observed_match:
                observation = f"Mailbox number {observed_match.group(1)} does not match the inspection address {street}."

        if not review_status:
            if damage_type == "None":
                review_status = "No Finding"
            elif damage_type.startswith("Possible") or (confidence and confidence < 80):
                review_status = "Needs Clarification"
            else:
                review_status = "Confirmed"

        component_lower = component.lower()
        soft_metal_terms = ("gutter", "downspout", "roof vent", "flashing", "metal vent")
        circle_count = sum(1 for item in annotations if item.get("type") == "circle")

        # Do not allow a confirmed soft-metal hail finding without a localized circle.
        if (
            damage_type == "Hail Impact"
            and any(term in component_lower for term in soft_metal_terms)
            and circle_count == 0
        ):
            review_status = "Needs Clarification"
            observation = (
                "Possible hail-related soft-metal damage detected, but the impact "
                "location could not be reliably localized. Inspector clarification requested."
            )
            annotations = []

        # Preserve the physical condition without overreaching on cause.
        if damage_type == "Missing Shingle":
            lower_observation = observation.lower()
            if any(phrase in lower_observation for phrase in ("caused by high wind", "caused by wind", "due to wind")):
                observation = "Missing shingle observed. Cause of loss requires additional inspection."

        if review_status == "Needs Clarification":
            damage_type = "â€” Select Damage Type â€”"
            if not observation:
                observation = "Potential damage detected. Inspector clarification requested."

        result = {
            "category": category,
            "component": component,
            "damage_type": damage_type,
            "severity": severity,
            "confidence": confidence,
            "observation": observation,
            "damage_checks": raw.get("damage_checks", {}),
            "annotations": annotations,
            "review_status": review_status,
            "engine": "Production Vision API",
        }
        # Final centralized pass after category/component validation. This ensures
        # component-specific forensic rules cannot be lost during UI normalization.
        result = normalize_damage_result(
            result, filename=photo.filename, image_path=photo.image_path
        )
        result["annotations"] = normalize_annotations(
            str(result.get("damage_type", "")),
            list(result.get("annotations", []) or []),
        )
        grade, grade_reason = self._assign_forensic_grade(photo, result)
        result["forensic_grade"] = grade
        result["grade_reason"] = grade_reason
        return result

    def _record_ai_usage(self, photo: PhotoRecord, model: str, payload: dict, elapsed_seconds: float) -> None:
        usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or (input_tokens + output_tokens))
        input_rate, output_rate = APPROX_MODEL_RATES.get(model, (2.00, 8.00))
        estimated_cost = (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "inspection": self.project_metadata.get("project_name", ""),
            "claim_number": self.customer_info.get("claim_number", ""),
            "photo_number": self.current_index + 1,
            "filename": photo.filename,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "elapsed_seconds": round(elapsed_seconds, 3),
        }
        try:
            with AI_USAGE_LEDGER.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
        except Exception:
            pass
        self.ai_usage_session["requests"] += 1
        self.ai_usage_session["input_tokens"] += input_tokens
        self.ai_usage_session["output_tokens"] += output_tokens
        self.ai_usage_session["estimated_cost"] += estimated_cost

    def _image_quality_score(self, image_path: Path) -> tuple[int, str]:
        """Return a lightweight 0-100 image quality score without altering the original."""
        try:
            with Image.open(image_path) as image:
                sample = image.convert("L")
                sample.thumbnail((640, 640), Image.Resampling.LANCZOS)
                edges = sample.filter(ImageFilter.FIND_EDGES)
                edge_mean = float(ImageStat.Stat(edges).mean[0])
                brightness = float(ImageStat.Stat(sample).mean[0])
                sharpness_score = max(0.0, min(100.0, edge_mean * 5.0))
                exposure_score = max(0.0, 100.0 - abs(brightness - 128.0) * 0.9)
                score = int(round(sharpness_score * 0.7 + exposure_score * 0.3))
                if score >= 80:
                    reason = "Image quality is strong."
                elif score >= 60:
                    reason = "Image quality is usable with minor limitations."
                else:
                    reason = "Image quality limits forensic certainty."
                return score, reason
        except Exception:
            return 60, "Image quality could not be fully measured."

    def _assign_forensic_grade(self, photo: PhotoRecord, result: dict) -> tuple[str, str]:
        confidence = int(result.get("confidence", 0) or 0)
        review_status = str(result.get("review_status", ""))
        damage_type = str(result.get("damage_type", ""))
        quality_score, quality_reason = self._image_quality_score(photo.image_path)

        if review_status == "No Finding" and damage_type in {"None", "Not Analyzed", ""}:
            grade = "A" if quality_score >= 70 else "B"
            reason = f"Context/no-finding photo. {quality_reason}"
        elif review_status == "Needs Clarification":
            grade = "C" if confidence >= 55 and quality_score >= 55 else "D"
            reason = f"Potential condition detected, but inspector confirmation is required. {quality_reason}"
        elif confidence >= 90 and quality_score >= 70:
            grade = "A"
            reason = f"High-confidence localized finding. {quality_reason}"
        elif confidence >= 80 and quality_score >= 60:
            grade = "B"
            reason = f"Likely supported finding with minor uncertainty. {quality_reason}"
        elif confidence >= 60:
            grade = "C"
            reason = f"Possible finding; inspector review recommended. {quality_reason}"
        elif confidence > 0:
            grade = "D"
            reason = f"Weak evidence; additional information is recommended. {quality_reason}"
        else:
            grade = "F"
            reason = f"Unable to establish a reliable forensic conclusion. {quality_reason}"
        return grade, reason

    @staticmethod
    def _retry_delay_seconds(response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after", "") if response is not None else ""
        try:
            return max(0.5, min(60.0, float(retry_after)))
        except (TypeError, ValueError):
            pass
        text = getattr(response, "text", "") or ""
        match = re.search(r"try again in\s*([0-9.]+)\s*(ms|s)", text, flags=re.I)
        if match:
            value = float(match.group(1))
            if match.group(2).lower() == "ms":
                value /= 1000.0
            return max(0.5, min(60.0, value + 0.25))
        return min(30.0, 1.5 * (2 ** max(0, attempt - 1)))

    def _production_vision_analysis(self, photo: PhotoRecord) -> dict:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "The requests package is required. Run: py -m pip install requests"
            ) from exc

        endpoint = self.ai_settings.get("endpoint", "").strip()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = self.ai_settings.get("model_name", "").strip()
        provider = self.ai_settings.get("provider", "OpenAI Responses API")

        if model in {
            "DamageScope Demo Classifier",
            "DamageScope Production Vision",
            "DamageScope AI Classifier",
        }:
            model = "gpt-4.1"
            provider = "OpenAI Responses API"
            endpoint = "https://api.openai.com/v1/responses"
            self.ai_settings["model_name"] = model
            self.ai_settings["provider"] = provider
            self.ai_settings["endpoint"] = endpoint
            self._save_ai_settings()

        if not endpoint or not api_key or not model:
            raise RuntimeError("AI Manager is missing endpoint, API key, or model name.")

        image_url = self._image_data_url(photo.image_path)
        prompt = self._production_prompt(photo)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        if provider == "OpenAI Responses API":
            body = {
                "model": model,
                "input": [{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_url},
                    ],
                }],
            }
        else:
            body = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }],
                "temperature": 0,
            }

        import time
        request_started = time.perf_counter()
        response = None
        max_attempts = 6
        for attempt in range(1, max_attempts + 1):
            response = requests.post(
                endpoint,
                headers=headers,
                json=body,
                timeout=(15, 180),
            )
            if response.status_code != 429:
                break
            delay = self._retry_delay_seconds(response, attempt)
            if hasattr(self, "analysis_status"):
                self.analysis_status.configure(
                    text=f"AI service is pacing requests. Resuming in {delay:.1f} seconds..."
                )
                self.update_idletasks()
            time.sleep(delay)

        if response is None:
            raise RuntimeError("AI service did not return a response.")
        if response.status_code >= 400:
            detail = response.text[:1200]
            if response.status_code == 400 and "model_not_found" in detail:
                raise RuntimeError(
                    "The configured API model does not exist. "
                    "Open Project > Advanced Settings > AI Manager and use gpt-4.1."
                )
            if response.status_code == 429:
                raise RuntimeError(
                    "The AI service remained busy after automatic retries. "
                    "The photo can be retried without losing completed work."
                )
            raise RuntimeError(
                f"AI service request failed ({response.status_code}). Please retry this photo."
            )

        payload = response.json()
        self._record_ai_usage(photo, model, payload, time.perf_counter() - request_started)
        output_text = self._parse_responses_api_text(payload)
        raw_result = self._extract_json_object(output_text)
        normalized_result = self._normalize_production_result(photo, raw_result)

        # Temporary beta instrumentation: preserve every transformation stage so
        # annotation/localization loss can be diagnosed from one analysis run.
        try:
            debug_dir = APP_DIR / "AI_PIPELINE_DEBUG"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_record = {
                "captured_at": datetime.now().isoformat(timespec="seconds"),
                "photo": {
                    "filename": photo.filename,
                    "image_path": str(photo.image_path),
                    "category_before": photo.category,
                    "component_before": photo.component,
                    "damage_type_before": photo.damage_type,
                },
                "model": model,
                "raw_api_payload": payload,
                "parsed_output_text": output_text,
                "extracted_json": raw_result,
                "normalized_result": normalized_result,
                "annotation_counts": {
                    "extracted": len(raw_result.get("annotations", []) or [])
                    if isinstance(raw_result, dict) else 0,
                    "normalized": len(normalized_result.get("annotations", []) or [])
                    if isinstance(normalized_result, dict) else 0,
                },
            }
            timestamp = datetime.now().strftime("%m-%d-%Y_%I-%M-%S_%p")
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", photo.filename)
            timestamped_file = debug_dir / f"{timestamp}_{safe_name}.json"
            latest_file = APP_DIR / "LATEST_AI_PIPELINE_DEBUG.json"
            debug_text = json.dumps(debug_record, indent=2, default=str)
            timestamped_file.write_text(debug_text, encoding="utf-8")
            latest_file.write_text(debug_text, encoding="utf-8")
        except Exception as debug_exc:
            self._write_audit(
                "ai_pipeline_debug_capture_failed",
                {"photo": photo.filename, "error": str(debug_exc)},
            )

        return normalized_result

    def _run_selected_engine(self, photo: PhotoRecord) -> dict:
        mode = self.ai_settings.get("mode", "Demo / Rules")
        if mode == "Demo / Rules":
            return self._demo_rules_analysis(photo)

        if mode == "Offline ONNX":
            raise RuntimeError(
                "The ONNX runtime is configured, but this sprint does not yet include "
                "a model-specific preprocessing/output adapter. Select Demo / Rules "
                "or provide the target model contract for the next integration."
            )

        if mode == "Production Vision API":
            return self._production_vision_analysis(photo)

        raise RuntimeError(f"Unsupported AI mode: {mode}")


    def analyze_all(self) -> None:
        analysis_indices = [
            index for index, photo in enumerate(self.photos)
            if not self._is_demo_photo(photo)
        ]
        if not analysis_indices:
            messagebox.showwarning(
                "DamageScope AI",
                "Import or open photos before running Analyze All.",
            )
            return

        confirmed = messagebox.askyesno(
            "DamageScope AI",
            f"Analyze all {len(analysis_indices)} photo(s)?",
        )
        if not confirmed:
            return

        completed = 0
        failed: list[str] = []
        original_index = self.current_index

        for progress_number, index in enumerate(analysis_indices, start=1):
            photo = self.photos[index]
            self.current_index = index
            percent = int((progress_number / max(1, len(analysis_indices))) * 100)
            self.analysis_status.configure(
                text=f"Analyzing {progress_number} of {len(analysis_indices)} ({percent}%)..."
            )
            self.photo_counter.configure(
                text=f"Photo {progress_number} of {len(analysis_indices)}"
            )
            self.update_idletasks()

            path = photo.image_path
            if not path.exists():
                failed.append(f"{photo.filename}: image missing")
                continue

            try:
                result = self._run_selected_engine(photo)
                photo.category = result["category"]
                photo.component = result["component"]
                photo.damage_type = result["damage_type"]
                photo.severity = result["severity"]
                photo.confidence = int(result["confidence"])
                photo.observation = result["observation"]
                photo.rotation_degrees = normalize_rotation_degrees(result.get("rotation_degrees", photo.rotation_degrees))
                photo.review_status = result.get("review_status", "")
                photo.forensic_grade = result.get("forensic_grade", "")
                photo.grade_reason = result.get("grade_reason", "")
                photo.ai_prediction = {
                    "category": photo.category,
                    "component": photo.component,
                    "damage_type": photo.damage_type,
                    "observation": photo.observation,
                    "confidence": photo.confidence,
                    "review_status": photo.review_status,
                    "forensic_grade": photo.forensic_grade,
                }
                # Contest integration: preserve the AI localization immediately.
                # The separate Annotate All workflow remains available for reruns.
                ai_annotations = [
                    dict(item) for item in (result.get("annotations") or [])
                    if isinstance(item, dict)
                ]
                photo.ai_annotations = ai_annotations
                if self.ai_settings.get("auto_annotate", True):
                    photo.annotations = self._normalize_reference_style_annotations(
                        photo,
                        ai_annotations,
                    )
                completed += 1
            except Exception as exc:
                failed.append(f"{photo.filename}: {exc}")

            # Refresh visible progress without interrupting the batch.
            self._rebuild_cards()
            self._rebuild_filmstrip()
            self._update_counters()
            self.after(1, self.update_idletasks)

        # Build the first inspection sequence only after AI analysis.
        sequence_candidates = [
            photo for photo in self.photos
            if not self._is_demo_photo(photo)
        ]

        # One authoritative inspection order drives the upper sequence, lower
        # original-photo library, navigation, and report ordering.  Elevation
        # ranks follow the standard clockwise field-inspection path.
        preferred_order = {
            "mailbox / address": 10,
            "house number": 10,
            "mailbox": 10,
            "address": 10,
            "front property overview": 15,
            "front elevation": 20,
            "right front elevation": 25,
            "front right corner": 25,
            "right elevation": 30,
            "right rear elevation": 35,
            "right rear corner": 35,
            "rear elevation": 40,
            "left rear elevation": 45,
            "left rear corner": 45,
            "left elevation": 50,
            "left front elevation": 55,
            "left front corner": 55,
            "windows": 60,
            "doors": 70,
            "gutters": 80,
            "downspout": 90,
            "ac condenser": 100,
            "hvac": 100,
            "roof": 110,
            "interior": 200,
            "other": 900,
        }

        def sequence_key(photo: PhotoRecord) -> tuple[int, str]:
            combined = f"{photo.category} {photo.component}".lower()
            rank = 850
            for phrase, value in preferred_order.items():
                if phrase in combined:
                    rank = min(rank, value)
            return rank, photo.filename.lower()

        sequence_candidates.sort(key=sequence_key)
        for position, photo in enumerate(sequence_candidates, start=1):
            photo.sequence_position = position
            photo.sequence_label = photo.component or photo.category or Path(photo.filename).stem

        self.current_index = min(original_index, max(0, len(self.photos) - 1))
        self.project_dirty = True
        self._save_session()
        self._update_counters()
        self.show_photo(self.current_index)

        grade_counts = {grade: 0 for grade in "ABCDF"}
        for photo in sequence_candidates:
            if photo.forensic_grade in grade_counts:
                grade_counts[photo.forensic_grade] += 1
        grade_summary = "  ".join(f"{grade}: {grade_counts[grade]}" for grade in "ABCDF")

        if failed:
            self.analysis_status.configure(
                text=f"Analyze All complete: {completed} succeeded, {len(failed)} failed."
            )
            messagebox.showwarning(
                "DamageScope AI",
                f"Analyze All completed.\n\n"
                f"Successful: {completed}\n"
                f"Failed: {len(failed)}\n"
                f"Forensic grades: {grade_summary}\n\n"
                + "\n".join(failed[:10]),
            )
        else:
            self.analysis_status.configure(
                text=f"Analyze All complete â€” {completed} photo(s)."
            )
            messagebox.showinfo(
                "DamageScope AI",
                f"Analyze All completed successfully for {completed} photo(s).\n\n"
                f"Forensic grades: {grade_summary}",
            )
        self._write_audit("analyze_all", {"completed": completed, "failed": len(failed)})

    def _normalize_reference_style_annotations(
        self,
        photo: PhotoRecord,
        annotations: list[dict],
    ) -> list[dict]:
        """Convert AI findings into the approved circle + arrow + label style."""
        normalized = normalize_annotations(photo.damage_type, annotations)
        damage_text = f"{photo.damage_type} {photo.observation}".lower()

        # Training-only hail localization aid. Production hail reports remain
        # circle-only, while distributed Hail Spatter remains unannotated.
        if photo.damage_type == "Hail Impact" and self.training_mode.get():
            normalized = add_hail_training_target(normalized)

        if "wind" in damage_text and any(term in damage_text for term in ("crease", "fold", "lifted", "wind lift")):
            converted: list[dict] = []
            for item in normalized:
                if item.get("type") == "circle":
                    cx = float(item.get("x", 0.5))
                    cy = float(item.get("y", 0.5))
                    radius = max(float(item.get("radius", 0.04)), 0.035)
                    converted.append({
                        "type": "line",
                        "x1": max(0.02, cx - radius * 1.35),
                        "y1": min(0.97, cy + radius * 1.15),
                        "x2": min(0.98, cx + radius * 1.35),
                        "y2": min(0.97, cy + radius * 1.15),
                    })
                else:
                    converted.append(item)
            normalized = converted
            for item in normalized:
                if item.get("type") == "line":
                    # Offset the marker slightly below the crease so evidence remains visible.
                    item["y1"] = min(0.96, float(item.get("y1", 0.52)) + 0.035)
                    item["y2"] = min(0.96, float(item.get("y2", 0.52)) + 0.035)
            if not any(item.get("type") == "line" for item in normalized):
                normalized.append(
                    {"type": "line", "x1": 0.32, "y1": 0.56, "x2": 0.68, "y2": 0.56}
                )
            if not any(item.get("type") == "label" for item in normalized):
                normalized.append(
                    {
                        "type": "label",
                        "x": 0.06,
                        "y": 0.08,
                        "text": ("WIND LIFTED SHINGLE\nConsistent with wind uplift."
                                 if "lift" in damage_text else
                                 "WIND CREASE\nVisible crease consistent\nwith wind uplift."),
                    }
                )

        if photo.review_status == "Needs Clarification":
            for item in normalized:
                if item.get("type") == "circle":
                    item["radius"] = max(float(item.get("radius", 0.04)), 0.065)
                elif item.get("type") == "label":
                    text = str(item.get("text", "Possible Finding")).strip()
                    if "possible" not in text.lower():
                        item["text"] = f"{text}\n(Possible)"

        if "missing shingle" in damage_text:
            circles = [item for item in normalized if item.get("type") == "circle"]
            if not circles:
                circles = [{"type": "circle", "x": 0.52, "y": 0.52, "radius": 0.07}]
                normalized.extend(circles)
            cx = float(circles[0].get("x", 0.52))
            cy = float(circles[0].get("y", 0.52))
            if not any(item.get("type") == "arrow" for item in normalized):
                normalized.append({"type": "arrow", "x1": 0.18, "y1": 0.18, "x2": cx, "y2": cy})
            if not any(item.get("type") == "label" for item in normalized):
                normalized.append(
                    {
                        "type": "label",
                        "x": 0.06,
                        "y": 0.08,
                        "text": "MISSING SHINGLE\nInspector confirmation",
                    }
                )

        return normalized

    def annotate_all(self) -> None:
        photos_to_annotate = [
            (index, photo)
            for index, photo in enumerate(self.photos)
            if not self._is_demo_photo(photo)
        ]
        if not photos_to_annotate:
            messagebox.showwarning(
                "DamageScope AI",
                "Import and analyze photos before running Annotate All.",
            )
            return

        if self.ai_settings.get("mode") != "Production Vision API":
            messagebox.showwarning(
                "DamageScope AI",
                "Annotate All requires Production Vision API mode in AI Manager.",
            )
            return

        confirmed = messagebox.askyesno(
            "DamageScope AI",
            f"Prepare forensic annotations for {len(photos_to_annotate)} photo(s)?",
        )
        if not confirmed:
            return

        original_index = self.current_index
        annotated = 0
        no_findings = 0
        failed: list[str] = []

        for progress_number, (index, photo) in enumerate(photos_to_annotate, start=1):
            self.current_index = index
            percent = int((progress_number / max(1, len(photos_to_annotate))) * 100)
            self.analysis_status.configure(
                text=f"Annotating {progress_number} of {len(photos_to_annotate)} ({percent}%)..."
            )
            self.update_idletasks()

            try:
                result = self._production_vision_analysis(photo)

                if photo.category in {"Unreviewed", ""}:
                    photo.category = result["category"]
                if photo.component in {"Not Classified", ""}:
                    photo.component = result["component"]

                photo.damage_type = result["damage_type"]
                photo.severity = result["severity"]
                photo.confidence = int(result["confidence"])
                photo.observation = result["observation"]
                photo.rotation_degrees = normalize_rotation_degrees(result.get("rotation_degrees", photo.rotation_degrees))
                photo.review_status = result.get("review_status", "")
                photo.forensic_grade = result.get("forensic_grade", "")
                photo.grade_reason = result.get("grade_reason", "")

                annotations = result.get("annotations") or []
                photo.ai_annotations = [dict(item) for item in annotations if isinstance(item, dict)]
                photo.annotations = self._normalize_reference_style_annotations(
                    photo,
                    annotations,
                )
                annotations = photo.annotations
                if annotations:
                    annotated += 1
                else:
                    no_findings += 1
            except Exception as exc:
                failed.append(f"{photo.filename}: {exc}")

            self._rebuild_cards()
            self._rebuild_filmstrip()
            self.after(1, self.update_idletasks)

        self.current_index = min(original_index, max(0, len(self.photos) - 1))
        self.project_dirty = True
        self._save_session()
        self.show_photo(self.current_index)

        status = (
            f"Annotate All complete â€” {annotated} localized findings annotated, "
            f"{no_findings} context/no-localized-finding photos"
        )
        if failed:
            status += f", {len(failed)} failed"
        self.analysis_status.configure(text=status + ".")
        self._write_audit(
            "annotate_all",
            {"annotated": annotated, "no_findings": no_findings, "failed": len(failed)},
        )

        if failed:
            messagebox.showwarning(
                "DamageScope AI",
                status + ".\n\n" + "\n".join(failed[:10]),
            )
        else:
            messagebox.showinfo("DamageScope AI", status + ".")

    def analyze_selected(self) -> None:
        if not self.photos:
            messagebox.showwarning("DamageScope AI", "Import or open a photo before running analysis.")
            return

        photo = self.photos[self.current_index]
        path = photo.image_path
        if not path.exists():
            messagebox.showerror("DamageScope AI", f"Selected image is missing:\n{path}")
            return

        self.analysis_status.configure(text=f"Analyzing photo {self.current_index + 1}...")
        self.update_idletasks()

        try:
            result = self._run_selected_engine(photo)
        except Exception as exc:
            self.analysis_status.configure(text="Analysis failed.")
            messagebox.showerror("DamageScope AI", f"Analyze Selected failed:\n{exc}")
            return

        photo.category = result["category"]
        photo.component = result["component"]
        photo.damage_type = result["damage_type"]
        photo.severity = result["severity"]
        photo.confidence = int(result["confidence"])
        photo.observation = result["observation"]
        photo.rotation_degrees = normalize_rotation_degrees(result.get("rotation_degrees", photo.rotation_degrees))
        # Contest integration: route the AI localization into the proven
        # top-layer renderer immediately after Analyze Selected.
        ai_annotations = [
            dict(item) for item in (result.get("annotations") or [])
            if isinstance(item, dict)
        ]
        photo.ai_annotations = ai_annotations
        if self.ai_settings.get("auto_annotate", True):
            photo.annotations = self._normalize_reference_style_annotations(
                photo,
                ai_annotations,
            )

        self.project_dirty = True
        self._save_session()
        self._update_counters()
        self.show_photo(self.current_index)
        self.analysis_status.configure(
            text=f"Analysis complete â€” {result['engine']}."
        )
        self._write_audit("analyze_selected", {"photo": photo.filename, "engine": result["engine"]})

    def _prepare_testing_ai_defaults(self) -> None:
        """Prefill all required testing values except the API key."""
        self.ai_settings["mode"] = "Production Vision API"
        self.ai_settings["provider"] = "OpenAI Responses API"
        self.ai_settings["model_name"] = "gpt-4.1"
        self.ai_settings["endpoint"] = "https://api.openai.com/v1/responses"
        self.ai_settings["device"] = "CPU"
        self.ai_settings["confidence_threshold"] = float(
            self.ai_settings.get("confidence_threshold", 0.70) or 0.70
        )
        self.ai_settings["auto_annotate"] = True
        self.ai_settings["offline_required"] = False
        if not self.ai_settings.get("api_key", "").strip():
            self.ai_settings["status"] = "Enter API key, then test configuration."
        self._save_ai_settings()

    def open_ai_manager(self) -> None:
        self._prepare_testing_ai_defaults()
        window = tk.Toplevel(self)
        window.title("DamageScope AI â€” AI Manager")
        window.geometry("720x700")
        window.minsize(680, 640)
        window.configure(bg=BG)
        window.transient(self)
        window.grab_set()

        tk.Label(
            window,
            text="AI Manager",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 19),
        ).pack(anchor="w", padx=24, pady=(20, 3))

        tk.Label(
            window,
            text="Configure the analysis engine without changing the desktop interface.",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=(0, 14))

        body = tk.Frame(window, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        body.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        body.grid_columnconfigure(1, weight=1)

        mode_var = tk.StringVar(value=self.ai_settings.get("mode", "Demo / Rules"))
        provider_var = tk.StringVar(value=self.ai_settings.get("provider", "Local"))
        model_name_var = tk.StringVar(value=self.ai_settings.get("model_name", ""))
        model_path_var = tk.StringVar(value=self.ai_settings.get("model_path", ""))
        api_key_var = tk.StringVar(value=self.ai_settings.get("api_key", ""))
        endpoint_var = tk.StringVar(value=self.ai_settings.get("endpoint", ""))
        device_var = tk.StringVar(value=self.ai_settings.get("device", "CPU"))
        threshold_var = tk.DoubleVar(value=float(self.ai_settings.get("confidence_threshold", 0.70)))
        auto_annotate_var = tk.BooleanVar(value=bool(self.ai_settings.get("auto_annotate", True)))
        offline_required_var = tk.BooleanVar(value=bool(self.ai_settings.get("offline_required", True)))

        def label(row: int, text: str) -> None:
            tk.Label(
                body,
                text=text,
                bg=PANEL,
                fg=TEXT,
                font=("Segoe UI Semibold", 9),
            ).grid(row=row, column=0, sticky="w", padx=18, pady=9)

        label(0, "Engine Mode")
        mode_combo = ttk.Combobox(
            body,
            textvariable=mode_var,
            values=["Demo / Rules", "Offline ONNX", "Production Vision API"],
            state="readonly",
            style="Dark.TCombobox",
        )
        mode_combo.grid(row=0, column=1, sticky="ew", padx=18, pady=9)

        label(1, "Provider")
        provider_combo = ttk.Combobox(
            body,
            textvariable=provider_var,
            values=["Local", "OpenAI Responses API", "OpenAI-Compatible", "Custom"],
            state="readonly",
            style="Dark.TCombobox",
        )
        provider_combo.grid(row=1, column=1, sticky="ew", padx=18, pady=9)

        label(2, "Model Name")
        model_entry = tk.Entry(
            body,
            textvariable=model_name_var,
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 10),
        )
        model_entry.grid(row=2, column=1, sticky="ew", padx=18, pady=9, ipady=7)

        label(3, "ONNX Model")
        model_row = tk.Frame(body, bg=PANEL)
        model_row.grid(row=3, column=1, sticky="ew", padx=18, pady=9)
        model_row.grid_columnconfigure(0, weight=1)
        model_path_entry = tk.Entry(
            model_row,
            textvariable=model_path_var,
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 9),
        )
        model_path_entry.grid(row=0, column=0, sticky="ew", ipady=7)

        def browse_model() -> None:
            selected = filedialog.askopenfilename(
                title="Select ONNX Model",
                filetypes=[("ONNX Model", "*.onnx"), ("All Files", "*.*")],
            )
            if selected:
                model_path_var.set(selected)

        self._button(model_row, "Browse", browse_model).grid(row=0, column=1, padx=(8, 0))

        label(4, "Device")
        device_combo = ttk.Combobox(
            body,
            textvariable=device_var,
            values=["CPU", "GPU", "Auto"],
            state="readonly",
            style="Dark.TCombobox",
        )
        device_combo.grid(row=4, column=1, sticky="ew", padx=18, pady=9)

        label(5, "API Endpoint")
        endpoint_entry = tk.Entry(
            body,
            textvariable=endpoint_var,
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 10),
        )
        endpoint_entry.grid(row=5, column=1, sticky="ew", padx=18, pady=9, ipady=7)

        label(6, "API Key")
        api_entry = tk.Entry(
            body,
            textvariable=api_key_var,
            show="â€¢",
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 10),
        )
        api_entry.grid(row=6, column=1, sticky="ew", padx=18, pady=9, ipady=7)
        window.after(250, api_entry.focus_set)

        label(7, "Confidence Threshold")
        threshold_frame = tk.Frame(body, bg=PANEL)
        threshold_frame.grid(row=7, column=1, sticky="ew", padx=18, pady=9)
        threshold_frame.grid_columnconfigure(0, weight=1)
        threshold_scale = tk.Scale(
            threshold_frame,
            variable=threshold_var,
            from_=0.10,
            to=0.99,
            resolution=0.01,
            orient="horizontal",
            bg=PANEL,
            fg=TEXT,
            troughcolor=PANEL_2,
            activebackground=ACCENT,
            highlightthickness=0,
            length=360,
        )
        threshold_scale.grid(row=0, column=0, sticky="ew")
        threshold_value = tk.Label(
            threshold_frame,
            text=f"{threshold_var.get():.0%}",
            bg=PANEL,
            fg=GREEN,
            font=("Segoe UI Semibold", 10),
            width=6,
        )
        threshold_value.grid(row=0, column=1)
        threshold_scale.configure(
            command=lambda value: threshold_value.configure(text=f"{float(value):.0%}")
        )

        options = tk.Frame(body, bg=PANEL)
        options.grid(row=8, column=0, columnspan=2, sticky="ew", padx=18, pady=10)
        tk.Checkbutton(
            options,
            text="Automatically prepare annotations",
            variable=auto_annotate_var,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w")
        tk.Checkbutton(
            options,
            text="Require an offline-capable engine for field use",
            variable=offline_required_var,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=(5, 0))

        status_box = tk.Frame(body, bg="#081724", highlightthickness=1, highlightbackground=BORDER)
        status_box.grid(row=9, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 16))
        status_label = tk.Label(
            status_box,
            text=f"Status: {self.ai_settings.get('status', 'Not tested')}",
            bg="#081724",
            fg="#23bcff",
            font=("Segoe UI Semibold", 9),
            anchor="w",
            justify="left",
        )
        status_label.pack(fill="x", padx=12, pady=10)

        def collect_settings() -> dict:
            return {
                "mode": mode_var.get(),
                "provider": provider_var.get(),
                "model_name": model_name_var.get().strip(),
                "model_path": model_path_var.get().strip(),
                "api_key": api_key_var.get().strip(),
                "endpoint": endpoint_var.get().strip(),
                "device": device_var.get(),
                "confidence_threshold": round(float(threshold_var.get()), 2),
                "auto_annotate": auto_annotate_var.get(),
                "offline_required": offline_required_var.get(),
                "status": status_label.cget("text").replace("Status: ", "", 1),
            }

        def test_configuration() -> None:
            settings = collect_settings()
            success, message = self._test_ai_connection(settings)
            status_label.configure(
                text=f"Status: {message}",
                fg=GREEN if success else ORANGE,
            )

        def save_configuration() -> None:
            settings = collect_settings()
            valid, message = self._validate_ai_settings(settings)
            if not valid:
                messagebox.showwarning("DamageScope AI", message)
                return
            settings["status"] = status_label.cget("text").replace("Status: ", "", 1)
            self.ai_settings = settings
            if self._save_ai_settings():
                self.analysis_status.configure(text="AI Manager settings saved.")
                self._update_counters()
                window.destroy()

        buttons = tk.Frame(window, bg=BG)
        buttons.pack(fill="x", padx=24, pady=(0, 20))
        self._button(buttons, "Save", save_configuration).pack(side="right")
        self._button(buttons, "Test Configuration", test_configuration).pack(
            side="right", padx=(0, 8)
        )
        self._button(buttons, "Cancel", window.destroy).pack(side="right", padx=(0, 8))

        def update_mode_fields(*_args) -> None:
            mode = mode_var.get()
            if mode == "Offline ONNX":
                provider_var.set("Local")
                model_path_entry.configure(state="normal")
                endpoint_entry.configure(state="disabled")
                api_entry.configure(state="disabled")
            elif mode == "Production Vision API":
                model_path_entry.configure(state="disabled")
                endpoint_entry.configure(state="normal")
                api_entry.configure(state="normal")
                if provider_var.get() == "Local":
                    provider_var.set("OpenAI Responses API")
                if (
                    not model_name_var.get().strip()
                    or model_name_var.get().strip().lower().startswith("damagescope")
                ):
                    model_name_var.set("gpt-4.1")
                if not endpoint_var.get().strip():
                    endpoint_var.set("https://api.openai.com/v1/responses")
            else:
                provider_var.set("Local")
                model_path_entry.configure(state="disabled")
                endpoint_entry.configure(state="disabled")
                api_entry.configure(state="disabled")

        def update_provider_defaults(*_args) -> None:
            if provider_var.get() == "OpenAI Responses API":
                if not endpoint_var.get().strip():
                    endpoint_var.set("https://api.openai.com/v1/responses")
                if (
                    not model_name_var.get().strip()
                    or model_name_var.get().strip().lower().startswith("damagescope")
                ):
                    model_name_var.set("gpt-4.1")

        provider_var.trace_add("write", update_provider_defaults)
        mode_var.trace_add("write", update_mode_fields)
        update_mode_fields()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox",
            fieldbackground=PANEL_2,
            background=PANEL_2,
            foreground=TEXT,
            arrowcolor=TEXT,
            bordercolor=BORDER,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", PANEL_2)],
            foreground=[("readonly", TEXT)],
        )

    def _is_demo_photo(self, photo: PhotoRecord) -> bool:
        """Return True only for bundled startup/display photos."""
        return not photo.imported and photo.filename.lower() in {
            "mailbox.jpg",
            "front.jpg",
            "right.jpg",
            "rear.jpg",
            "left.jpg",
            "windows.jpg",
            "gutters.jpg",
            "ac.jpg",
        }

    def _real_photos(self) -> list[PhotoRecord]:
        return [photo for photo in self.photos if not self._is_demo_photo(photo)]

    def _normalize_demo_state(self, records: list[PhotoRecord]) -> list[PhotoRecord]:
        """Remove obsolete bundled demo-photo dependencies."""
        real = [photo for photo in records if not self._is_demo_photo(photo)]
        for photo in real:
            if photo.damage_type in {"Not Analyzed", ""}:
                photo.sequence_position = None
                photo.sequence_label = ""
        return real

    def _seed_photos(self) -> list[PhotoRecord]:
        """Judging build starts with a clean workspace and no bundled photos."""
        return []

    def _load_session_or_seed(self) -> list[PhotoRecord]:
        project_file = SESSION_FILE
        try:
            if RECENT_PROJECT_FILE.exists():
                recent = json.loads(RECENT_PROJECT_FILE.read_text(encoding="utf-8"))
                recent_path = Path(recent.get("project_file", ""))
                if recent_path.exists():
                    project_file = recent_path
        except Exception:
            pass

        if not project_file.exists():
            self.current_project_file = SESSION_FILE
            return []

        try:
            raw = json.loads(project_file.read_text(encoding="utf-8"))
            self.current_project_file = project_file
            metadata = raw.get("project", {})
            self.project_metadata.update(metadata)
            loaded_customer = raw.get("customer_info", {})
            if isinstance(loaded_customer, dict):
                for key in self.customer_info:
                    if key in loaded_customer:
                        self.customer_info[key] = str(loaded_customer.get(key, ""))
            records = [PhotoRecord(**item) for item in raw.get("photos", [])]
            return self._normalize_demo_state(records) if records else []
        except Exception:
            self.current_project_file = SESSION_FILE
            return []

    def _project_payload(self) -> dict:
        return {
            "format": "DamageScope Project",
            "version": "0.4.7",
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "project": self.project_metadata,
            "customer_info": self.customer_info,
            "photos": [asdict(photo) for photo in self.photos],
        }

    def _save_session(self, show_status: bool = False) -> bool:
        try:
            self.current_project_file.parent.mkdir(parents=True, exist_ok=True)
            self.current_project_file.write_text(
                json.dumps(self._project_payload(), indent=2),
                encoding="utf-8",
            )
            RECENT_PROJECT_FILE.write_text(
                json.dumps({"project_file": str(self.current_project_file)}, indent=2),
                encoding="utf-8",
            )
            self.project_dirty = False
            self._update_project_identity()
            self._write_audit("project_saved", {"project_file": str(self.current_project_file)})
            if show_status and hasattr(self, "analysis_status"):
                self.analysis_status.configure(text="Project saved.")
            return True
        except Exception as exc:
            messagebox.showerror("DamageScope AI", f"Could not save project:\n{exc}")
            return False

    def _button(self, parent: tk.Widget, text: str, command=None, width=None) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=PANEL_2,
            fg=TEXT,
            activebackground=ACCENT,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=7,
            font=("Segoe UI", 9),
            cursor="hand2",
            width=width,
        )

    def _build_header(self) -> None:
        header = tk.Frame(self, bg="#020d1d", height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="DamageScope AI",
            bg="#020d1d",
            fg=TEXT,
            font=("Segoe UI Semibold", 23),
        ).pack(side="left", padx=(25, 16))
        tk.Label(
            header,
            text="Personal Inspector Edition v0.4.20 â€” AI Annotation Conversion & Editing Build",
            bg="#020d1d",
            fg="#20b9ff",
            font=("Segoe UI", 11),
        ).pack(side="left", pady=(8, 0))
        self.project_name_label = tk.Label(
            header,
            text="",
            bg="#020d1d",
            fg=MUTED,
            font=("Segoe UI", 10),
        )
        self.project_name_label.pack(side="right", padx=22)

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self, bg=PANEL, height=42, highlightthickness=1, highlightbackground=BORDER)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        actions = [
            ("New Claim", self.new_project),
            ("Open Claim", self.open_project),
            ("Save", self.save_project),
            ("Save As", self.save_project_as),
            ("Customer Info", self.open_customer_information),
            ("Import Photos", self.import_photos),
            ("AI Manager", self.open_ai_manager),
            ("Analyze Selected", self.analyze_selected),
            ("Analyze All", self.analyze_all),
            ("Annotate All", self.annotate_all),
            ("Move Up", lambda: self.move_sequence_item(-1)),
            ("Move Down", lambda: self.move_sequence_item(1)),
            ("Generate PDF", self.generate_pdf),
            ("Sync", self.open_sync_manager),
            ("Clear", self.clear_photos),
        ]
        for text, cmd in actions:
            self._button(bar, text, cmd).pack(
                side="left",
                padx=(12 if text == "New Claim" else 4, 0),
                pady=6,
            )
        status = tk.Frame(bar, bg=PANEL)
        status.pack(side="right", padx=12)
        self.analysis_status = tk.Label(
            status, text="50-photo Analyze â†’ Annotate â†’ Report workflow active.", bg=PANEL, fg="#23bcff", font=("Segoe UI", 8)
        )
        self.analysis_status.pack(anchor="e")
        self.header_count = tk.Label(
            status, text="", bg=PANEL, fg=TEXT, font=("Segoe UI", 8)
        )
        self.header_count.pack(anchor="e")

    def _build_main_layout(self) -> None:
        main = tk.Frame(self, bg=BG)
        self.main_workspace = main
        main.pack(side="top", fill="both", expand=True)
        main.grid_columnconfigure(0, minsize=320)
        main.grid_columnconfigure(1, weight=1)
        main.grid_columnconfigure(2, minsize=420)
        main.grid_rowconfigure(0, weight=1)

        self.left = tk.Frame(
            main,
            bg=PANEL,
            width=320,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.left.grid(row=0, column=0, sticky="nsew")

        self.center = tk.Frame(main, bg=BG)
        self.center.grid(row=0, column=1, sticky="nsew")

        self.right_shell = tk.Frame(
            main,
            bg=PANEL,
            width=420,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.right_shell.grid(row=0, column=2, sticky="nsew")
        self.right_shell.grid_rowconfigure(0, weight=1)
        self.right_shell.grid_columnconfigure(0, weight=1)

        self.right_canvas = tk.Canvas(
            self.right_shell,
            bg=PANEL,
            highlightthickness=0,
            bd=0,
        )
        self.right_scrollbar = ttk.Scrollbar(
            self.right_shell,
            orient="vertical",
            command=self.right_canvas.yview,
        )
        self.right_canvas.configure(yscrollcommand=self.right_scrollbar.set)
        self.right_canvas.grid(row=0, column=0, sticky="nsew")
        self.right_scrollbar.grid(row=0, column=1, sticky="ns")

        self.right = tk.Frame(self.right_canvas, bg=PANEL)
        self._right_window = self.right_canvas.create_window(
            (0, 0),
            window=self.right,
            anchor="nw",
        )

        def _sync_right_scrollregion(_event=None):
            self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))

        def _sync_right_width(event):
            self.right_canvas.itemconfigure(self._right_window, width=event.width)

        self.right.bind("<Configure>", _sync_right_scrollregion)
        self.right_canvas.bind("<Configure>", _sync_right_width)
        self._bind_mousewheel_to_canvas(self.right_canvas)

        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

    def _show_login_home_screen(self) -> None:
        """Display the branded subscription login/home screen.

        This contest build provides the complete login experience and transition
        into the working application. Production identity verification will be
        connected to the standalone DamageScope AI authentication service.
        """
        if getattr(self, "login_home_overlay", None) is not None:
            try:
                self.login_home_overlay.destroy()
            except tk.TclError:
                pass

        overlay = tk.Frame(
            self.main_workspace,
            bg=BG,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.login_home_overlay = overlay
        overlay.grid(row=0, column=0, columnspan=2, sticky="nsew")
        overlay.grid_columnconfigure(0, minsize=330)
        overlay.grid_columnconfigure(1, weight=1)
        overlay.grid_rowconfigure(0, weight=1)

        # LEFT: subscription sign-in panel.
        login = tk.Frame(
            overlay,
            bg=PANEL,
            width=330,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        login.grid(row=0, column=0, sticky="nsew")
        login.grid_propagate(False)

        tk.Label(
            login,
            text="ðŸ”’  SIGN IN TO YOUR ACCOUNT",
            bg=PANEL,
            fg="#23bcff",
            font=("Segoe UI Semibold", 13),
        ).pack(anchor="w", padx=28, pady=(38, 12))

        tk.Label(
            login,
            text="Welcome back! Sign in to access your inspections,\nreports, settings, and subscription.",
            bg=PANEL,
            fg=TEXT,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=28, pady=(0, 24))

        tk.Label(
            login,
            text="Email",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=28, pady=(0, 5))

        self.login_email_var = tk.StringVar()
        email_entry = tk.Entry(
            login,
            textvariable=self.login_email_var,
            bg="#081725",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 10),
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        email_entry.pack(fill="x", padx=28, ipady=10)

        tk.Label(
            login,
            text="Password",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=28, pady=(18, 5))

        self.login_password_var = tk.StringVar()
        password_entry = tk.Entry(
            login,
            textvariable=self.login_password_var,
            show="â€¢",
            bg="#081725",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 10),
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        password_entry.pack(fill="x", padx=28, ipady=10)

        options = tk.Frame(login, bg=PANEL)
        options.pack(fill="x", padx=28, pady=(14, 16))
        self.login_remember_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            options,
            text="Remember me",
            variable=self.login_remember_var,
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            selectcolor="#081725",
            font=("Segoe UI", 9),
        ).pack(side="left")
        tk.Button(
            options,
            text="Forgot Password?",
            command=self._login_account_service_notice,
            bg=PANEL,
            fg="#23bcff",
            activebackground=PANEL,
            activeforeground="#66d1ff",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        ).pack(side="right")

        sign_in = tk.Button(
            login,
            text="Sign In",
            command=self._complete_login_home_screen,
            bg=ACCENT,
            fg="white",
            activebackground="#0e74bd",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI Semibold", 11),
        )
        sign_in.pack(fill="x", padx=28, ipady=11)

        separator = tk.Frame(login, bg=PANEL)
        separator.pack(fill="x", padx=28, pady=20)
        tk.Frame(separator, bg=BORDER, height=1).pack(side="left", fill="x", expand=True)
        tk.Label(separator, text="  OR  ", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        tk.Frame(separator, bg=BORDER, height=1).pack(side="left", fill="x", expand=True)

        tk.Button(
            login,
            text="Create New Account",
            command=self._login_account_service_notice,
            bg=PANEL,
            fg="#23bcff",
            activebackground=PANEL_2,
            activeforeground="#66d1ff",
            relief="solid",
            bd=1,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
        ).pack(fill="x", padx=28, ipady=10)

        tk.Label(
            login,
            text="ðŸ›¡  Your data is secure and encrypted.\n     End-to-end protection for your inspections.",
            bg=PANEL,
            fg=MUTED,
            justify="left",
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=28, pady=(38, 12))

        # CENTER: branded home screen.
        hero = tk.Frame(overlay, bg=BG)
        hero.grid(row=0, column=1, sticky="nsew")
        hero.grid_columnconfigure(0, weight=1)
        hero.grid_rowconfigure(0, weight=1)

        content = tk.Frame(hero, bg=BG)
        content.grid(row=0, column=0)

        # Vector-style roof mark built with text/canvas primitives so the screen
        # remains self-contained and does not depend on an external image file.
        logo_canvas = tk.Canvas(content, width=560, height=170, bg=BG, highlightthickness=0)
        logo_canvas.pack(pady=(8, 0))
        logo_canvas.create_polygon(
            125, 100, 225, 25, 310, 100, 285, 100, 225, 48, 155, 105,
            fill="#168ddd", outline="#23bcff", width=2
        )
        logo_canvas.create_polygon(
            290, 100, 365, 45, 445, 105, 415, 105, 365, 70, 320, 105,
            fill="#168ddd", outline="#23bcff", width=2
        )
        logo_canvas.create_rectangle(213, 75, 235, 100, fill=TEXT, outline="")
        logo_canvas.create_rectangle(353, 82, 369, 100, fill=TEXT, outline="")
        logo_canvas.create_oval(104, 72, 148, 116, outline="#23bcff", width=2)
        logo_canvas.create_line(126, 60, 126, 128, fill="#23bcff", width=2)
        logo_canvas.create_line(92, 94, 160, 94, fill="#23bcff", width=2)

        brand = tk.Frame(content, bg=BG)
        brand.pack()
        tk.Label(
            brand,
            text="DAMAGE",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Black", 38),
        ).pack(side="left")
        tk.Label(
            brand,
            text="SCOPE",
            bg=BG,
            fg=ACCENT,
            font=("Segoe UI Black", 38),
        ).pack(side="left")
        tk.Label(
            brand,
            text=" AI ",
            bg="#06111d",
            fg=TEXT,
            font=("Segoe UI Black", 32),
            highlightthickness=2,
            highlightbackground=ACCENT,
        ).pack(side="left", padx=(6, 0))

        tk.Label(
            content,
            text="F O R E N S I C   P R O P E R T Y   D A M A G E   A N A L Y S I S",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 10),
        ).pack(pady=(7, 18))

        tk.Frame(content, bg=ACCENT, height=2, width=520).pack(pady=(0, 22))

        tk.Label(
            content,
            text="Welcome to DamageScope AI",
            bg=BG,
            fg="#23bcff",
            font=("Segoe UI Semibold", 20),
        ).pack()
        tk.Label(
            content,
            text="The AI-powered inspection and annotation platform\nbuilt for property professionals.",
            bg=BG,
            fg=TEXT,
            justify="center",
            font=("Segoe UI", 11),
        ).pack(pady=(7, 25))

        steps = tk.Frame(content, bg=BG)
        steps.pack(fill="x")
        step_data = [
            ("â–£", "1. IMPORT PHOTOS", "Import one or more inspection\nphotographs from your device."),
            ("â—‰", "2. ANALYZE", "Identify, classify, and annotate\nvisible property damage."),
            ("â–¤", "3. REVIEW & REPORT", "Review findings, make corrections,\nand generate your report."),
        ]
        for index, (icon, heading, body) in enumerate(step_data):
            cell = tk.Frame(steps, bg=BG, width=210)
            cell.pack(side="left", expand=True, padx=14)
            tk.Label(
                cell,
                text=icon,
                bg="#0d3f67",
                fg=TEXT,
                font=("Segoe UI", 20),
                width=9,
                pady=8,
            ).pack()
            tk.Label(
                cell,
                text=heading,
                bg=BG,
                fg=TEXT,
                font=("Segoe UI Semibold", 10),
            ).pack(pady=(10, 5))
            tk.Label(
                cell,
                text=body,
                bg=BG,
                fg=TEXT,
                justify="center",
                font=("Segoe UI", 9),
            ).pack()
            if index < 2:
                tk.Frame(steps, bg=BORDER, width=1, height=105).pack(side="left", padx=2)

        tk.Label(
            content,
            text="Human Expertise + Artificial Intelligence",
            bg=BG,
            fg="#23bcff",
            font=("Segoe UI Semibold", 14),
        ).pack(pady=(28, 2))
        tk.Label(
            content,
            text="Accurate. Consistent. Defensible.",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 12),
        ).pack()

        email_entry.focus_set()
        email_entry.bind("<Return>", lambda _event: password_entry.focus_set())
        password_entry.bind("<Return>", lambda _event: self._complete_login_home_screen())

    def _complete_login_home_screen(self) -> None:
        email = self.login_email_var.get().strip()
        password = self.login_password_var.get()
        if not email or not password:
            messagebox.showwarning(
                "Sign In Required",
                "Enter an email address and password to continue.",
                parent=self,
            )
            return

        self.authenticated_user_email = email
        try:
            self.login_home_overlay.destroy()
        except tk.TclError:
            pass
        self.login_home_overlay = None
        self.status_var.set(f"Signed in as {email}. DamageScope AI is ready.")
        self._refresh_all_views(select_index=int(self.user_settings.get("last_photo_index", 0)))

    def _login_account_service_notice(self) -> None:
        messagebox.showinfo(
            "DamageScope AI Account Services",
            "The subscription account service is represented in this contest build. "
            "Production account creation, password recovery, billing, and identity "
            "verification will connect to the standalone DamageScope AI authentication service.",
            parent=self,
        )

    def _bind_mousewheel_to_canvas(self, canvas: tk.Canvas, horizontal: bool = False) -> None:
        """Register a canvas for reliable wheel scrolling, including child widgets."""
        if not hasattr(self, "_wheel_targets"):
            self._wheel_targets = []
            self.bind_all("<MouseWheel>", self._route_mousewheel, add="+")
            self.bind_all("<Shift-MouseWheel>", self._route_shift_mousewheel, add="+")
            self.bind_all("<Button-4>", lambda event: self._route_linux_wheel(event, -1), add="+")
            self.bind_all("<Button-5>", lambda event: self._route_linux_wheel(event, 1), add="+")
        self._wheel_targets.append((canvas, horizontal, canvas.master))

    def _widget_is_descendant(self, widget, ancestor) -> bool:
        current = widget
        while current is not None:
            if current == ancestor:
                return True
            try:
                parent_name = current.winfo_parent()
                current = current._nametowidget(parent_name) if parent_name else None
            except Exception:
                return False
        return False

    def _wheel_target_under_pointer(self):
        try:
            widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        except Exception:
            return None
        if widget is None:
            return None
        for canvas, horizontal, region in reversed(getattr(self, "_wheel_targets", [])):
            try:
                if canvas.winfo_exists() and self._widget_is_descendant(widget, region):
                    # Filmstrip/sequence descendants are siblings inside the same container,
                    # so also accept descendants of the canvas master.
                    return canvas, horizontal
            except Exception:
                continue
        return None

    def _route_mousewheel(self, event):
        target = self._wheel_target_under_pointer()
        if not target:
            return None
        canvas, horizontal = target
        steps = -max(1, abs(int(event.delta / 120))) if event.delta > 0 else max(1, abs(int(event.delta / 120)))
        if horizontal:
            canvas.xview_scroll(steps * 4, "units")
        else:
            canvas.yview_scroll(steps * 4, "units")
        return "break"

    def _route_shift_mousewheel(self, event):
        target = self._wheel_target_under_pointer()
        if not target:
            return None
        canvas, _horizontal = target
        steps = -max(1, abs(int(event.delta / 120))) if event.delta > 0 else max(1, abs(int(event.delta / 120)))
        canvas.xview_scroll(steps * 4, "units")
        return "break"

    def _route_linux_wheel(self, event, direction: int):
        target = self._wheel_target_under_pointer()
        if not target:
            return None
        canvas, horizontal = target
        if horizontal:
            canvas.xview_scroll(direction * 4, "units")
        else:
            canvas.yview_scroll(direction * 4, "units")
        return "break"

    def _build_left_panel(self) -> None:
        header = tk.Frame(self.left, bg=PANEL)
        header.pack(fill="x", padx=12, pady=(10, 5))

        self.sequence_title = tk.Label(
            header,
            text="Inspection Sequence (0)",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 11),
        )
        self.sequence_title.pack(anchor="w")

        tk.Label(
            header,
            text='Drag from Photo Library or click "Add to Sequence"',
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(2, 0))

        container = tk.Frame(self.left, bg=PANEL)
        container.pack(fill="both", expand=True)

        self.left_canvas = tk.Canvas(
            container,
            bg=PANEL,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=self.left_canvas.yview,
        )
        self.cards_frame = tk.Frame(self.left_canvas, bg=PANEL)
        self.cards_frame.bind(
            "<Configure>",
            lambda event: self.left_canvas.configure(
                scrollregion=self.left_canvas.bbox("all")
            ),
        )
        self.left_canvas.create_window(
            (0, 0),
            window=self.cards_frame,
            anchor="nw",
            width=304,
        )
        self.left_canvas.configure(yscrollcommand=scrollbar.set)
        self.left_canvas.pack(side="left", fill="both", expand=True)
        self._bind_mousewheel_to_canvas(self.left_canvas, horizontal=False)
        scrollbar.pack(side="right", fill="y")

        self.sequence_summary = tk.Frame(
            self.left,
            bg="#081724",
            height=48,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.sequence_summary.pack(fill="x", padx=12, pady=(6, 8))
        self.sequence_summary.pack_propagate(False)

        self.summary_label = tk.Label(
            self.sequence_summary,
            text="Sequence ready",
            bg="#081724",
            fg=GREEN,
            font=("Segoe UI Semibold", 9),
            anchor="w",
            justify="left",
        )
        self.summary_label.pack(fill="both", padx=12, pady=7)

    def _sequence_photos(self) -> list[tuple[int, PhotoRecord]]:
        sequenced = [
            (index, photo)
            for index, photo in enumerate(self.photos)
            if photo.sequence_position is not None and not self._is_demo_photo(photo)
        ]
        sequenced.sort(key=lambda item: int(item[1].sequence_position or 0))
        return sequenced

    def _rebuild_cards(self) -> None:
        for child in self.cards_frame.winfo_children():
            child.destroy()
        self.photo_cards.clear()

        sequenced = self._sequence_photos()

        if not sequenced:
            empty = tk.Frame(
                self.cards_frame,
                bg="#0d2234",
                height=88,
                highlightthickness=1,
                highlightbackground=BORDER,
            )
            empty.pack(fill="x", padx=10, pady=6)
            empty.pack_propagate(False)
            tk.Label(
                empty,
                text="Inspection sequence is empty",
                bg="#0d2234",
                fg=TEXT,
                font=("Segoe UI Semibold", 9),
            ).pack(anchor="w", padx=10, pady=(14, 3))
            tk.Label(
                empty,
                text="Choose photos from the library below.",
                bg="#0d2234",
                fg=MUTED,
                font=("Segoe UI", 8),
            ).pack(anchor="w", padx=10)
            return

        for display_position, (photo_index, photo) in enumerate(sequenced, start=1):
            selected = photo_index == self.current_index
            row_bg = "#0d2234"
            border_color = ACCENT if selected else BORDER

            card = tk.Frame(
                self.cards_frame,
                bg=row_bg,
                height=66,
                highlightthickness=1,
                highlightbackground=border_color,
            )
            card.pack(fill="x", padx=10, pady=2)
            card.pack_propagate(False)

            number_bg = "#168ddd" if selected else "#071724"
            number = tk.Label(
                card,
                text=str(display_position),
                bg=number_bg,
                fg="white",
                font=("Segoe UI Semibold", 9),
                width=2,
                cursor="hand2",
            )
            number.pack(side="left", fill="y")

            image = self._load_thumb(photo.image_path, (86, 58))
            thumb = tk.Label(
                card,
                image=image,
                bg="#07111b",
                cursor="hand2",
            )
            thumb.image = image
            thumb.pack(side="left", padx=(4, 7), pady=3)

            info_bg = "#168ddd" if selected else row_bg
            info = tk.Frame(card, bg=info_bg)
            info.pack(side="left", fill="both", expand=True)

            title = photo.sequence_label.strip() or photo.title.split(". ", 1)[-1]
            tk.Label(
                info,
                text=title,
                bg=info_bg,
                fg="white",
                font=("Segoe UI Semibold", 8),
                anchor="w",
            ).pack(fill="x", padx=7, pady=(5, 0))

            tk.Label(
                info,
                text=photo.filename,
                bg=info_bg,
                fg="#d9e7f1" if selected else MUTED,
                font=("Segoe UI", 7),
                anchor="w",
            ).pack(fill="x", padx=7)

            bottom = tk.Frame(info, bg=info_bg)
            bottom.pack(fill="x", padx=7, pady=(1, 4))

            tk.Label(
                bottom,
                text="REPORT" if photo.include else "NOT USED",
                bg=info_bg,
                fg="white" if selected else (GREEN if photo.include else ORANGE),
                font=("Segoe UI Semibold", 7),
            ).pack(side="left")

            tk.Label(
                bottom,
                text=f"{photo.confidence}%" if photo.confidence else "NEW",
                bg=info_bg,
                fg="white" if selected else (GREEN if photo.confidence else "#23bcff"),
                font=("Segoe UI Semibold", 7),
            ).pack(side="right")

            handle = tk.Label(
                card,
                text="â˜°",
                bg=row_bg,
                fg=MUTED,
                font=("Segoe UI", 12),
                width=2,
                cursor="hand2",
            )
            handle.pack(side="right", fill="y")

            for widget in (card, number, thumb, info, bottom, handle):
                widget.bind("<Button-1>", lambda event, i=photo_index: self.show_photo(i))

            self.photo_cards.append(card)

    def _customer_display_text(self) -> str:
        name = self.customer_info.get("customer_name", "").strip()
        street = self.customer_info.get("property_address", "").strip()
        city = self.customer_info.get("city", "").strip()
        state = self.customer_info.get("state", "").strip()
        zip_code = self.customer_info.get("zip_code", "").strip()
        claim = self.customer_info.get("claim_number", "").strip()

        location = ", ".join(part for part in (city, state) if part)
        if zip_code:
            location = f"{location} {zip_code}".strip()

        address_line = " â€” ".join(part for part in (street, location) if part)
        if claim:
            address_line = f"{address_line}    Claim #{claim}".strip()

        if name and address_line:
            return f"{name}\n{address_line}"
        if name:
            return name
        if address_line:
            return address_line
        return "Customer information not entered"

    def _refresh_customer_header(self) -> None:
        if hasattr(self, "customer_header"):
            self.customer_header.configure(text=self._customer_display_text())

        name = self.customer_info.get("customer_name", "").strip()
        claim = self.customer_info.get("claim_number", "").strip()
        self.project_metadata["insured_name"] = name
        self.project_metadata["claim_number"] = claim
        self.project_metadata["project_name"] = name or claim or "Untitled Inspection"
        if self.customer_info.get("property_address", "").strip():
            self.project_metadata["property_address"] = self.customer_info["property_address"].strip()
        self._update_project_identity()

    @staticmethod
    def _format_phone_number(value: str) -> str:
        digits = re.sub(r"\D", "", value)[:10]
        if len(digits) <= 3:
            return digits
        if len(digits) <= 6:
            return f"{digits[:3]}-{digits[3:]}"
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:10]}"

    def start_windows_voice_typing(self, target_widget=None) -> None:
        """Focus a field and launch Windows Voice Typing with Win+H."""
        if target_widget is not None:
            try:
                target_widget.focus_set()
                target_widget.icursor("end")
            except Exception:
                pass

        self.update_idletasks()

        if os.name != "nt":
            messagebox.showinfo(
                "DamageScope AI",
                "Voice typing currently uses the Windows Win+H dictation service.",
            )
            return

        try:
            import ctypes
            user32 = ctypes.windll.user32
            VK_LWIN = 0x5B
            VK_H = 0x48
            KEYEVENTF_KEYUP = 0x0002

            user32.keybd_event(VK_LWIN, 0, 0, 0)
            user32.keybd_event(VK_H, 0, 0, 0)
            user32.keybd_event(VK_H, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
            self.analysis_status.configure(
                text="Windows voice typing opened. Speak into the focused field."
            )
        except Exception as exc:
            messagebox.showerror(
                "DamageScope AI",
                f"Windows voice typing could not be opened:\n{exc}",
            )

    def open_customer_information(self) -> None:
        window = tk.Toplevel(self)
        window.title("Customer Information")
        window.configure(bg=BG)
        window.transient(self)
        window.grab_set()
        window.geometry("760x700")
        window.minsize(720, 620)

        tk.Label(
            window,
            text="Customer / Claim Information",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 15),
        ).pack(anchor="w", padx=20, pady=(16, 3))

        tk.Label(
            window,
            text="Saved with this inspection and shown above every photo.",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 12))

        canvas = tk.Canvas(window, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg=BG)
        form.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(form_window, width=event.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=(0, 58))
        scrollbar.pack(side="right", fill="y", padx=(0, 12), pady=(0, 58))

        field_definitions = [
            ("customer_name", "Customer Name"),
            ("property_address", "Property Address"),
            ("city", "City"),
            ("state", "State"),
            ("zip_code", "ZIP Code"),
            ("phone", "Telephone Number"),
            ("email", "Email Address"),
            ("insurance_carrier", "Insurance Carrier"),
            ("claim_number", "Claim Number"),
            ("policy_number", "Policy Number"),
            ("adjuster_name", "Insurance Adjuster"),
            ("adjuster_phone", "Adjuster Telephone"),
            ("inspection_date", "Inspection Date"),
            ("inspector_name", "Inspector"),
            ("contractor", "Contractor"),
            ("public_adjuster", "Public Adjuster"),
        ]

        variables: dict[str, tk.StringVar] = {}
        for row, (key, label_text) in enumerate(field_definitions):
            tk.Label(
                form,
                text=label_text,
                bg=BG,
                fg=TEXT,
                font=("Segoe UI", 9),
                anchor="w",
            ).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=5)

            initial_value = self.customer_info.get(key, "")
            if key in {"phone", "adjuster_phone"}:
                initial_value = self._format_phone_number(initial_value)
            variable = tk.StringVar(value=initial_value)
            variables[key] = variable

            if key in {"phone", "adjuster_phone"}:
                formatting_guard = {"active": False}

                def format_phone(*_args, phone_var=variable, guard=formatting_guard):
                    if guard["active"]:
                        return
                    guard["active"] = True
                    formatted = self._format_phone_number(phone_var.get())
                    if phone_var.get() != formatted:
                        phone_var.set(formatted)
                    guard["active"] = False

                variable.trace_add("write", format_phone)

            entry = tk.Entry(
                form,
                textvariable=variable,
                bg="#0b1d2b",
                fg=TEXT,
                insertbackground=TEXT,
                relief="flat",
                highlightthickness=1,
                highlightbackground=BORDER,
                highlightcolor=ACCENT,
                font=("Segoe UI", 9),
            )
            entry.grid(row=row, column=1, sticky="ew", pady=5)
            self._button(
                form,
                "ðŸŽ¤",
                lambda target=entry: self.start_windows_voice_typing(target),
            ).grid(row=row, column=2, padx=(6, 0), pady=5)

        notes_row = len(field_definitions)
        tk.Label(
            form,
            text="Pertinent Notes",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 9),
            anchor="nw",
        ).grid(row=notes_row, column=0, sticky="nw", padx=(0, 14), pady=5)

        notes = tk.Text(
            form,
            height=6,
            bg="#0b1d2b",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            wrap="word",
            font=("Segoe UI", 9),
        )
        notes.grid(row=notes_row, column=1, sticky="ew", pady=5)
        notes.insert("1.0", self.customer_info.get("notes", ""))
        self._button(
            form,
            "ðŸŽ¤",
            lambda: self.start_windows_voice_typing(notes),
        ).grid(row=notes_row, column=2, padx=(6, 0), pady=5, sticky="n")
        form.grid_columnconfigure(1, weight=1)

        buttons = tk.Frame(window, bg=PANEL)
        buttons.pack(side="bottom", fill="x")

        def save_customer() -> None:
            for key, variable in variables.items():
                self.customer_info[key] = variable.get().strip()
            self.customer_info["notes"] = notes.get("1.0", "end").strip()
            self.project_dirty = True
            self._refresh_customer_header()
            self._save_session(show_status=False)
            self.analysis_status.configure(text="Customer information saved.")
            self._write_audit("customer_information_saved")
            window.destroy()

        self._button(buttons, "Cancel", window.destroy).pack(
            side="right", padx=(6, 14), pady=10
        )
        self._button(buttons, "Save Customer Information", save_customer).pack(
            side="right", pady=10
        )

    def _build_center_panel(self) -> None:
        top = tk.Frame(self.center, bg=BG)
        top.pack(fill="x", padx=14, pady=(8, 7))
        top.grid_columnconfigure(1, weight=1)

        self.photo_counter = tk.Label(
            top,
            text="Photo 0 of 0",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        )
        self.photo_counter.grid(row=0, column=0, sticky="w")

        position_frame = tk.Frame(
            top,
            bg=PANEL_2,
            highlightthickness=1,
            highlightbackground=ACCENT,
            padx=8,
            pady=4,
        )
        position_frame.grid(row=0, column=1, sticky="w", padx=(16, 10))
        tk.Label(
            position_frame,
            text="Sequence #",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left", padx=(0, 6))
        self.sequence_position_var = tk.StringVar(value="")
        self.sequence_position_entry = tk.Entry(
            position_frame,
            textvariable=self.sequence_position_var,
            width=5,
            justify="center",
            bg="#0b1d2b",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=("Segoe UI Semibold", 10),
        )
        self.sequence_position_entry.pack(side="left")
        self.sequence_position_entry.bind(
            "<Return>", self._apply_sequence_position_from_entry
        )
        self.sequence_position_entry.bind(
            "<Escape>", lambda _event: self._refresh_sequence_position_entry()
        )

        self.customer_header = tk.Label(
            top,
            text="Customer information not entered",
            bg=BG,
            fg="#d9e7f1",
            font=("Segoe UI Semibold", 9),
            justify="left",
            anchor="w",
            wraplength=500,
        )
        self.customer_header.grid(row=0, column=2, sticky="w", padx=(8, 12))

        self.fit_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            top,
            text="Fit to window",
            bg=BG,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=BG,
            activeforeground=TEXT,
            variable=self.fit_var,
            command=self._refresh_preview,
            font=("Segoe UI", 8),
        ).grid(row=0, column=3, sticky="e", padx=(8, 10))

        self._button(
            top,
            "<  Previous",
            lambda: self.show_photo(self.current_index - 1),
        ).grid(row=0, column=4, sticky="e", padx=(0, 7))

        self._button(
            top,
            "Next  >",
            lambda: self.show_photo(self.current_index + 1),
        ).grid(row=0, column=5, sticky="e")

        # Forensic Teaching Toolbar â€” always visible directly above the image.
        self.teaching_toolbar = tk.Frame(
            self.center,
            bg=PANEL_2,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=6,
            pady=5,
        )
        self.teaching_toolbar.pack(fill="x", padx=14, pady=(0, 6))

        tools = [
            ("Select", "Select / stop drawing", lambda: self.set_annotation_mode("select")),
            ("Line", "Line - click and drag", lambda: self.set_annotation_mode("line")),
            ("Circle", "Circle - click and drag", lambda: self.set_annotation_mode("circle")),
            ("Box", "Rectangle - click and drag", lambda: self.set_annotation_mode("rectangle")),
            ("Arrow", "Arrow - click and drag", lambda: self.set_annotation_mode("arrow")),
            ("Text", "Add text label", lambda: self.set_annotation_mode("label")),
            ("Caution", "Toggle training caution banner", self.toggle_training_banner),
            ("Rotate L", "Rotate photo left", lambda: self.rotate_current_photo(-90)),
            ("Rotate R", "Rotate photo right", lambda: self.rotate_current_photo(90)),
            ("Erase", "Erase nearest annotation", lambda: self.set_annotation_mode("erase")),
            ("Undo", "Undo", self.undo_annotation),
            ("Redo", "Redo", self.redo_annotation),
            ("AI Ghost", "Show or hide AI ghost", self.toggle_ai_ghost),
            ("Save Lesson", "Save expert lesson", self.save_expert_annotation_lesson),
        ]
        for icon, help_text, command in tools:
            button = tk.Button(
                self.teaching_toolbar,
                text=icon,
                command=command,
                bg="#0b2234",
                fg=TEXT,
                activebackground=ACCENT,
                activeforeground="#00111c",
                relief="flat",
                width=3,
                font=("Segoe UI", 8, "bold"),
                cursor="hand2",
            )
            button.pack(side="left", padx=2)
            button.bind("<Enter>", lambda _e, text=help_text: self.annotation_status.configure(text=text, fg="#23bcff"))
            button.bind("<Leave>", lambda _e: self.annotation_status.configure(text="Forensic Teaching Toolbar ready.", fg=MUTED))

        tk.Label(
            self.teaching_toolbar,
            text="  Draw the correct markup, then save it as an expert lesson.",
            bg=PANEL_2,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(side="left", padx=(8, 0))

        self.preview_frame = tk.Frame(
            self.center,
            bg="#06111b",
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.preview_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self.preview_label = tk.Label(
            self.preview_frame,
            bg="#06111b",
            fg=MUTED,
            text="Import photos to begin.",
        )
        self.preview_label.pack(fill="both", expand=True, padx=6, pady=6)
        self.preview_label.bind("<Button-1>", self._on_preview_click)
        self.preview_label.bind("<ButtonPress-1>", self._on_preview_drag_start, add="+")
        self.preview_label.bind("<B1-Motion>", self._on_preview_drag_motion, add="+")
        self.preview_label.bind("<ButtonRelease-1>", self._on_preview_drag_end, add="+")
        self.preview_label.bind("<Double-Button-1>", self._on_preview_double_click, add="+")
        self.preview_frame.bind("<Configure>", lambda event: self._refresh_preview())

        # Retain the information-label data model without using vertical screen space.
        self.info_labels = [
            tk.Label(self.center, text=""),
            tk.Label(self.center, text=""),
            tk.Label(self.center, text=""),
        ]

    def _build_photo_library_panel(self) -> None:
        self.filmstrip = tk.Frame(
            self,
            bg=PANEL,
            height=164,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.filmstrip.pack(side="bottom", fill="x")
        self.filmstrip.pack_propagate(False)

    def _rebuild_filmstrip(self) -> None:
        for child in self.filmstrip.winfo_children():
            child.destroy()

        toolbar = tk.Frame(self.filmstrip, bg=PANEL, height=34)
        toolbar.pack(fill="x", padx=14, pady=(5, 0))
        toolbar.pack_propagate(False)

        tk.Label(
            toolbar,
            text=f"Photo Library ({len(self._real_photos())})",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 10),
        ).pack(side="left")

        tk.Label(
            toolbar,
            text='Click to view â€¢ Double-click or "Add to Sequence" to include',
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(side="left", padx=12)

        self._button(
            toolbar,
            "Sort âŒ„",
            self.stub,
        ).pack(side="right", padx=(6, 0))
        self._button(
            toolbar,
            "Filter",
            self.stub,
        ).pack(side="right", padx=(6, 0))
        self._button(
            toolbar,
            "Add to Sequence",
            self.add_selected_to_sequence,
        ).pack(side="right", padx=(6, 0))

        library_canvas = tk.Canvas(
            self.filmstrip,
            bg=PANEL,
            height=112,
            highlightthickness=0,
        )
        x_scroll = ttk.Scrollbar(
            self.filmstrip,
            orient="horizontal",
            command=library_canvas.xview,
        )
        library_canvas.configure(xscrollcommand=x_scroll.set)

        inner = tk.Frame(library_canvas, bg=PANEL)
        window_id = library_canvas.create_window((0, 0), window=inner, anchor="nw")

        def update_scroll_region(_event=None) -> None:
            library_canvas.configure(scrollregion=library_canvas.bbox("all"))

        inner.bind("<Configure>", update_scroll_region)
        library_canvas.bind(
            "<Configure>",
            lambda event: library_canvas.itemconfigure(window_id, height=event.height),
        )

        library_canvas.pack(fill="both", expand=True, padx=12, pady=(2, 0))
        self._bind_mousewheel_to_canvas(library_canvas, horizontal=True)
        x_scroll.pack(fill="x", padx=12, pady=(0, 3))

        # 150 px cards allow approximately ten thumbnails across a 1600 px screen.
        card_width = 150
        thumb_size = (142, 86)

        # The lower library shows original, unannotated photographs in the same
        # authoritative order as the upper inspection sequence. Unsequenced
        # photos remain available at the end in original import order.
        sequenced_items = self._sequence_photos()
        sequenced_indices = {index for index, _photo in sequenced_items}
        unsequenced_items = [
            (idx, photo)
            for idx, photo in enumerate(self.photos)
            if not self._is_demo_photo(photo) and idx not in sequenced_indices
        ]
        library_items = sequenced_items + unsequenced_items

        if not library_items:
            tk.Label(
                inner,
                text="Import photos or drag them into DamageScope AI.",
                bg=PANEL,
                fg=MUTED,
                font=("Segoe UI", 9),
            ).pack(side="left", padx=14, pady=34)

        for display_number, (idx, photo) in enumerate(library_items, start=1):
            selected = idx == self.library_selected_index
            in_sequence = photo.sequence_position is not None
            border = ACCENT if selected else (GREEN if in_sequence else BORDER)

            item = tk.Frame(
                inner,
                bg=PANEL,
                width=card_width,
                height=108,
            )
            item.pack(side="left", padx=4, pady=2)
            item.pack_propagate(False)

            image = self._load_thumb(photo.image_path, thumb_size)
            label = tk.Label(
                item,
                image=image,
                bg=PANEL,
                highlightthickness=3,
                highlightbackground=border,
                cursor="hand2",
            )
            label.image = image
            label.pack()

            caption = photo.filename
            text_label = tk.Label(
                item,
                text=caption[:24],
                bg=PANEL,
                fg=TEXT,
                font=("Segoe UI", 7),
                cursor="hand2",
            )
            text_label.pack(fill="x")

            number = tk.Label(
                item,
                text=str(display_number),
                bg="#071724",
                fg="white",
                font=("Segoe UI Semibold", 7),
            )
            number.place(x=4, y=4)

            if in_sequence:
                marker = tk.Label(
                    item,
                    text="âœ“",
                    bg=GREEN,
                    fg="#07111b",
                    font=("Segoe UI Semibold", 7),
                )
                marker.place(relx=1.0, x=-18, y=4)

            for widget in (item, label, text_label):
                widget.bind("<Button-1>", lambda event, i=idx: self.select_library_photo(i))
                widget.bind("<Double-Button-1>", lambda event, i=idx: self.add_photo_to_sequence(i))

    def select_library_photo(self, index: int) -> None:
        if not self.photos:
            return
        self.library_selected_index = index
        self.show_photo(index)
        self._rebuild_filmstrip()

    def _next_sequence_position(self) -> int:
        positions = [
            int(photo.sequence_position)
            for photo in self.photos
            if photo.sequence_position is not None
        ]
        return max(positions, default=0) + 1

    def add_selected_to_sequence(self) -> None:
        if self.library_selected_index is None:
            messagebox.showinfo(
                "DamageScope AI",
                "Select a photo from the bottom Photo Library first.",
            )
            return
        self.add_photo_to_sequence(self.library_selected_index)

    def add_photo_to_sequence(self, index: int) -> None:
        if not (0 <= index < len(self.photos)):
            return
        photo = self.photos[index]
        if photo.sequence_position is None:
            photo.sequence_position = self._next_sequence_position()
            if not photo.sequence_label:
                photo.sequence_label = photo.title.split(". ", 1)[-1]
            self.project_dirty = True
            self._normalize_sequence_positions()
            self._save_session()
        self.current_index = index
        self.library_selected_index = index
        self._refresh_all_views(select_index=index)
        self.analysis_status.configure(text="Photo added to inspection sequence.")

    def remove_selected_from_sequence(self) -> None:
        index = self.library_selected_index
        if index is None or not (0 <= index < len(self.photos)):
            messagebox.showinfo(
                "DamageScope AI",
                "Select a photo from the bottom Photo Library first.",
            )
            return
        photo = self.photos[index]
        if photo.sequence_position is None:
            return
        photo.sequence_position = None
        photo.sequence_label = ""
        self.project_dirty = True
        self._normalize_sequence_positions()
        self._save_session()
        self._refresh_all_views(select_index=index)
        self.analysis_status.configure(text="Photo removed from inspection sequence.")

    def move_sequence_item(self, delta: int) -> None:
        """Move the currently displayed photo exactly one sequence slot.

        The center preview is the authoritative selection.  Using
        ``library_selected_index`` here caused a stale filmstrip selection to be
        moved instead, which could look like the photo jumped to the bottom.
        """
        if not self.photos or not (0 <= self.current_index < len(self.photos)):
            messagebox.showinfo(
                "DamageScope AI",
                "Select a sequenced photo first.",
            )
            return

        index = self.current_index
        photo = self.photos[index]
        if photo.sequence_position is None:
            messagebox.showinfo(
                "DamageScope AI",
                "That photo is not yet in the inspection sequence.",
            )
            return

        ordered_indices = [photo_index for photo_index, _ in self._sequence_photos()]
        try:
            current_position = ordered_indices.index(index)
        except ValueError:
            return

        # Move Up/Down always means one slot per click.
        step = -1 if delta < 0 else 1
        target_position = current_position + step
        if target_position < 0 or target_position >= len(ordered_indices):
            return

        ordered_indices[current_position], ordered_indices[target_position] = (
            ordered_indices[target_position],
            ordered_indices[current_position],
        )
        for position, photo_index in enumerate(ordered_indices, start=1):
            self.photos[photo_index].sequence_position = position

        self.project_dirty = True
        self.library_selected_index = index
        self._save_session()
        self._refresh_all_views(select_index=index)
        self.analysis_status.configure(
            text=f"Photo moved one position {'up' if step < 0 else 'down'} in the sequence."
        )

    def _normalize_sequence_positions(self) -> None:
        sequenced = self._sequence_photos()
        for position, (_index, photo) in enumerate(sequenced, start=1):
            photo.sequence_position = position

    def _refresh_sequence_position_entry(self) -> None:
        if not hasattr(self, "sequence_position_var"):
            return
        if not self.photos or not (0 <= self.current_index < len(self.photos)):
            self.sequence_position_var.set("")
            return
        photo = self.photos[self.current_index]
        self.sequence_position_var.set(
            "" if photo.sequence_position is None else str(photo.sequence_position)
        )

    def _apply_sequence_position_from_entry(self, _event=None) -> str:
        if not self.photos or not (0 <= self.current_index < len(self.photos)):
            self._refresh_sequence_position_entry()
            return "break"

        raw_value = self.sequence_position_var.get().strip()
        if not raw_value:
            self._refresh_sequence_position_entry()
            return "break"

        try:
            requested_position = int(raw_value)
        except ValueError:
            messagebox.showwarning(
                "DamageScope AI",
                "Enter a whole photo-sequence number, such as 2.",
            )
            self._refresh_sequence_position_entry()
            return "break"

        current_photo = self.photos[self.current_index]
        sequenced_indices = [index for index, _photo in self._sequence_photos()]

        if current_photo.sequence_position is None:
            current_photo.sequence_position = len(sequenced_indices) + 1
            if not current_photo.sequence_label:
                current_photo.sequence_label = current_photo.title.split(". ", 1)[-1]
            sequenced_indices.append(self.current_index)

        ordered_indices = [index for index, _photo in self._sequence_photos()]
        if self.current_index in ordered_indices:
            ordered_indices.remove(self.current_index)

        requested_position = max(1, min(requested_position, len(ordered_indices) + 1))
        ordered_indices.insert(requested_position - 1, self.current_index)

        for position, photo_index in enumerate(ordered_indices, start=1):
            self.photos[photo_index].sequence_position = position

        self.project_dirty = True
        self.library_selected_index = self.current_index
        self._save_session()
        self._refresh_all_views(select_index=self.current_index)
        self.analysis_status.configure(
            text=f"Photo moved directly to sequence position {requested_position}."
        )
        self._write_audit(
            "photo_sequence_position_changed",
            {
                "photo_index": self.current_index,
                "new_sequence_position": requested_position,
            },
        )
        return "break"

    def _build_right_panel(self) -> None:
        tk.Label(
            self.right,
            text="DAMAGE ASSESSMENT SUMMARY",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w", padx=18, pady=(10, 6))

        self.category_var = tk.StringVar()
        self.component_var = tk.StringVar()
        self.damage_var = tk.StringVar()
        self.severity_var = tk.StringVar()
        self.include_var = tk.BooleanVar(value=True)

        self.classification_options = {
            "Unreviewed": ["Not Classified"],
            "Property Identification": [
                "Mailbox / Address",
                "House Number",
                "Street View",
                "Front Property Overview",
            ],
            "Elevation": [
                "Front Elevation",
                "Front Right Corner",
                "Right Elevation",
                "Right Rear Corner",
                "Rear Elevation",
                "Left Rear Corner",
                "Left Elevation",
                "Left Front Corner",
                "Garage Elevation",
                "Detached Structure Elevation",
                "Unknown Elevation",
            ],
            "Roofing": [
                "Roof Overview",
                "Roof Covering / Shingles",
                "Ridge",
                "Valley",
                "Eave",
                "Rake",
                "Flashing",
                "Roof Vent",
                "Pipe Jack",
                "Chimney",
                "Other Roofing",
            ],
            "Exterior Component": [
                "Windows / Screens",
                "Exterior Door",
                "Gutters",
                "Downspout",
                "Siding",
                "Fascia",
                "Soffit",
                "Fence",
                "Deck / Porch",
                "Other Exterior Component",
            ],
            "HVAC": [
                "AC Condenser",
                "Heat Pump",
                "Package Unit",
                "Other HVAC",
            ],
            "Interior": [
                "Interior Overview",
                "Ceiling",
                "Wall",
                "Flooring",
                "Cabinetry",
                "Interior Door",
                "Other Interior",
            ],
            "Site / Other": [
                "Tree / Vegetation",
                "Detached Building",
                "Contents",
                "Debris",
                "Other",
            ],
        }

        tk.Label(
            self.right,
            text="Category",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=18)
        self.category_combo = ttk.Combobox(
            self.right,
            textvariable=self.category_var,
            values=list(self.classification_options),
            state="readonly",
            style="Dark.TCombobox",
        )
        self.category_combo.pack(fill="x", padx=18, pady=(3, 9))
        self.category_combo.bind("<<ComboboxSelected>>", self._on_category_changed)

        tk.Label(
            self.right,
            text="Classification / Elevation",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=18)
        self.component_combo = ttk.Combobox(
            self.right,
            textvariable=self.component_var,
            values=self.classification_options["Unreviewed"],
            state="readonly",
            style="Dark.TCombobox",
        )
        self.component_combo.pack(fill="x", padx=18, pady=(3, 9))

        for label_text, var, values in [
            ("Damage Type", self.damage_var, [
                *VALID_DAMAGE_TYPES,
            ]),
        ]:
            tk.Label(
                self.right,
                text=label_text,
                bg=PANEL,
                fg=TEXT,
                font=("Segoe UI Semibold", 9),
            ).pack(anchor="w", padx=18)
            combo = ttk.Combobox(
                self.right,
                textvariable=var,
                values=values,
                state="readonly",
                style="Dark.TCombobox",
            )
            combo.pack(fill="x", padx=18, pady=(3, 9))

        conf = tk.Frame(self.right, bg=PANEL)
        tk.Label(
            conf, text="Confidence", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 9)
        ).pack(side="left")
        self.confidence_label = tk.Label(
            conf, text="â€”", bg=PANEL, fg=GREEN, font=("Segoe UI Semibold", 10)
        )
        self.confidence_label.pack(side="right")

        grade_row = tk.Frame(self.right, bg=PANEL)
        tk.Label(
            grade_row, text="Forensic Grade", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 9)
        ).pack(side="left")
        self.forensic_grade_label = tk.Label(
            grade_row, text="â€”", bg=PANEL, fg=ORANGE, font=("Segoe UI Semibold", 11)
        )
        self.forensic_grade_label.pack(side="right")

        tk.Checkbutton(
            self.right,
            text="Include in Report",
            variable=self.include_var,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", padx=18, pady=(6, 8))

        self.detailed_findings_frame = tk.Frame(self.right, bg=PANEL)
        self.detailed_findings_frame.pack(fill="x")

        tk.Frame(
            self.detailed_findings_frame, bg=BORDER, height=1
        ).pack(fill="x", padx=18)
        tk.Label(
            self.detailed_findings_frame,
            text="DETAILED FINDINGS",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=18, pady=(10, 4))

        self.observation = tk.Text(
            self.detailed_findings_frame,
            height=4,
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            wrap="word",
            font=("Segoe UI", 9),
            padx=8,
            pady=8,
        )
        self.observation.pack(fill="x", padx=18)

        # Keep the save controls directly beneath Detailed Findings so they
        # remain visible on smaller screens and at common Windows scaling levels.
        save_row = tk.Frame(self.detailed_findings_frame, bg=PANEL)
        save_row.pack(fill="x", padx=18, pady=(6, 4))
        self._button(
            save_row,
            "Save Details",
            self.save_details,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._button(
            save_row,
            "Save Correction",
            self.save_correction_and_lock,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        self._button(
            self.detailed_findings_frame,
            "ðŸŽ¤ Dictate Observation / Annotation Notes",
            lambda: self.start_windows_voice_typing(self.observation),
        ).pack(fill="x", padx=18, pady=(2, 6))

        tk.Label(
            self.right,
            text="Actions",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=18, pady=(8, 4))

        tk.Label(
            self.right,
            text="Annotation Engine",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=18, pady=(6, 6))

        annotation_row_1 = tk.Frame(self.right, bg=PANEL)
        annotation_row_1.pack(fill="x", padx=18)
        self._button(annotation_row_1, "Circle", lambda: self.set_annotation_mode("circle")).pack(
            side="left", fill="x", expand=True, padx=(0, 3)
        )
        self._button(annotation_row_1, "Arrow", lambda: self.set_annotation_mode("arrow")).pack(
            side="left", fill="x", expand=True, padx=3
        )
        self._button(annotation_row_1, "Line", lambda: self.set_annotation_mode("line")).pack(
            side="left", fill="x", expand=True, padx=3
        )
        self._button(annotation_row_1, "Label", lambda: self.set_annotation_mode("label")).pack(
            side="left", fill="x", expand=True, padx=(3, 0)
        )

        annotation_row_2 = tk.Frame(self.right, bg=PANEL)
        annotation_row_2.pack(fill="x", padx=18, pady=(6, 0))
        self._button(annotation_row_2, "Undo", self.undo_annotation).pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        self._button(annotation_row_2, "Clear", self.clear_annotations).pack(
            side="left", fill="x", expand=True, padx=4
        )
        self._button(annotation_row_2, "Lock", self.toggle_annotation_lock).pack(
            side="left", fill="x", expand=True, padx=(4, 0)
        )

        annotation_row_3 = tk.Frame(self.right, bg=PANEL)
        annotation_row_3.pack(fill="x", padx=18, pady=(6, 0))
        self._button(annotation_row_3, "Save Expert Annotation", self.save_expert_annotation_lesson).pack(
            side="left", fill="x", expand=True
        )

        tk.Checkbutton(
            self.right,
            text="Developer: Show AI candidate regions in red",
            variable=self.show_ai_ghost_annotations,
            command=self._refresh_preview,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", padx=18, pady=(8, 0))

        tk.Checkbutton(
            self.right,
            text="Show annotations",
            variable=self.annotations_visible,
            command=self._refresh_preview,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", padx=18, pady=(8, 0))

        self.annotation_status = tk.Label(
            self.right,
            text="Mode: Select a tool",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
        )
        self.annotation_status.pack(anchor="w", padx=18, pady=(4, 8))

    def _build_footer(self) -> None:
        footer = tk.Frame(
            self, bg="#0b1d2e", height=34, highlightthickness=1, highlightbackground=BORDER
        )
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        self.footer_left = tk.Label(
            footer, text="", bg="#0b1d2e", fg=TEXT, font=("Segoe UI", 8)
        )
        self.footer_left.pack(side="left", padx=12)
        tk.Label(
            footer, text="â—  Ready", bg="#0b1d2e", fg=GREEN, font=("Segoe UI", 9)
        ).pack(side="right", padx=16)

    def _load_thumb(self, path: Path, size: tuple[int, int]) -> ImageTk.PhotoImage:
        key = f"{path.resolve()}:{size}"
        if key not in self.image_cache:
            try:
                image = self._open_oriented_image(path)
            except Exception:
                image = Image.new("RGB", size, (30, 45, 60))
            image.thumbnail(size, Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", size, (18, 38, 54))
            canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
            self.image_cache[key] = ImageTk.PhotoImage(canvas)
        return self.image_cache[key]

    def _draw_clarification_banner(self, image: Image.Image) -> None:
        """Render a high-visibility diagonal inspector-review banner over the photo."""
        from PIL import ImageFont

        width, height = image.size
        banner_height = max(72, int(height * 0.18))
        banner_width = int(width * 1.35)
        overlay = Image.new("RGBA", (banner_width, banner_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle((0, 0, banner_width, banner_height), fill=(255, 205, 25, 245), outline=(120, 80, 0, 255), width=max(3, height // 180))
        try:
            title_font = ImageFont.truetype("arialbd.ttf", max(22, height // 20))
            body_font = ImageFont.truetype("arial.ttf", max(15, height // 31))
        except Exception:
            title_font = body_font = None
        pad = max(18, height // 30)
        draw.text((pad, max(4, banner_height * 0.10)), "NEEDS CLARIFICATION", fill=(20, 20, 20, 255), font=title_font)
        draw.text((pad, banner_height * 0.56), "Please clarify damage in this photo.", fill=(35, 35, 35, 255), font=body_font)
        rotated = overlay.rotate(12, expand=True, resample=Image.Resampling.BICUBIC)
        x = int((width - rotated.width) * 0.50)
        y = -int(rotated.height * 0.18)
        image.paste(rotated, (x, y), rotated)

    def _create_assessment_card(self, photo: PhotoRecord, target_size: tuple[int, int]) -> Image.Image:
        """Render the locked DamageScope AI identification/report card.

        The same renderer is used by the live identification screen and the PDF
        report so the customer sees the exact same visual result in both places.
        The original image is never altered; all graphics are overlays.
        """
        width, height = target_size
        width = max(1200, width)
        height = max(720, height)

        card = Image.new("RGB", (width, height), (3, 17, 28))
        draw = ImageDraw.Draw(card)

        bg = (3, 17, 28)
        panel = (5, 27, 43)
        panel_2 = (7, 38, 60)
        border = (46, 76, 96)
        white = (244, 248, 251)
        muted = (177, 193, 205)
        blue = (0, 174, 239)
        green = (95, 205, 48)
        yellow = (255, 214, 0)
        red = (242, 33, 33)
        black = (8, 10, 12)

        try:
            from PIL import ImageFont
            title_font = ImageFont.truetype("arialbd.ttf", max(19, height // 35))
            section_font = ImageFont.truetype("arialbd.ttf", max(15, height // 47))
            field_font = ImageFont.truetype("arial.ttf", max(13, height // 55))
            field_bold = ImageFont.truetype("arialbd.ttf", max(13, height // 55))
            callout_title = ImageFont.truetype("arialbd.ttf", max(19, height // 34))
            callout_body = ImageFont.truetype("arial.ttf", max(14, height // 48))
            callout_bold = ImageFont.truetype("arialbd.ttf", max(14, height // 48))
            footer_font = ImageFont.truetype("arialbd.ttf", max(11, height // 65))
        except Exception:
            title_font = section_font = field_font = field_bold = None
            callout_title = callout_body = callout_bold = footer_font = None

        margin = max(8, width // 220)
        header_h = max(52, height // 13)
        footer_h = max(34, height // 22)
        right_w = int(width * 0.265)
        gap = max(10, width // 150)
        left_x = margin
        left_w = width - right_w - gap - (margin * 2)
        right_x = left_x + left_w + gap
        content_top = header_h + margin
        content_bottom = height - footer_h - margin

        # Header
        draw.rectangle((margin, margin, width - margin, header_h), fill=bg, outline=border, width=2)
        draw.text((margin + 18, margin + 12), "DAMAGE SCOPE", fill=white, font=title_font)
        ds_w = draw.textlength("DAMAGE SCOPE", font=title_font)
        draw.text((margin + 22 + ds_w, margin + 12), " AI", fill=blue, font=title_font)
        heading = "AI DAMAGE IDENTIFICATION & ASSESSMENT"
        draw.text((left_x + int(left_w * 0.35), margin + 12), heading, fill=white, font=title_font)

        # Left photo panel.
        draw.rectangle((left_x, content_top, left_x + left_w, content_bottom), fill=panel, outline=border, width=2)
        image_box = (left_x + 2, content_top + 2, left_x + left_w - 2, content_bottom - 2)
        source = self._open_oriented_image(photo.image_path)
        if photo.rotation_degrees:
            source = source.rotate(-photo.rotation_degrees, expand=True, resample=Image.Resampling.BICUBIC)

        # Draw annotations directly on the working copy. AI-training arrows are red;
        # production circles remain yellow. Distributed Hail Spatter remains clean.
        if photo.review_status == "Needs Clarification" or photo.training_banner:
            self._draw_clarification_banner(source)
        if self.show_ai_ghost_annotations.get() and photo.ai_annotations:
            self._draw_annotations_on_image(
                source,
                [a for a in photo.ai_annotations if not a.get("converted_to_editable")],
                ghost=True,
            )
        if photo.annotations:
            self._draw_annotations_on_image(source, photo.annotations)

        source.thumbnail((image_box[2] - image_box[0], image_box[3] - image_box[1]), Image.Resampling.LANCZOS)
        px = image_box[0] + ((image_box[2] - image_box[0] - source.width) // 2)
        py = image_box[1] + ((image_box[3] - image_box[1] - source.height) // 2)
        card.paste(source, (px, py))
        self._assessment_photo_box = (px, py, source.width, source.height, width, height)

        # Forensic callout box over the upper-left portion of the photo.
        damage_type = (photo.damage_type or "Finding").strip()
        observation = (photo.observation or "").replace("\n", " ").strip()
        callout_w = int(left_w * 0.31)
        callout_h = min(int((content_bottom - content_top) * 0.46), max(250, height // 3))
        callout_x = left_x + 14
        callout_y = content_top + 14
        draw.rectangle(
            (callout_x, callout_y, callout_x + callout_w, callout_y + callout_h),
            fill=black,
            outline=yellow,
            width=max(2, height // 350),
        )
        cy = callout_y + 18
        draw.text((callout_x + 18, cy), damage_type.upper(), fill=yellow, font=callout_title)
        cy += max(45, height // 16)

        callout_lines: list[tuple[str, bool]] = []
        component = (photo.component or "component").strip()
        if photo.review_status == "Needs Clarification":
            callout_lines = [
                (f"Component: {component}", False),
                (observation or "Potential condition detected. Additional inspection or photographs are required.", True),
            ]
        else:
            callout_lines = [
                (f"Component: {component}", False),
                (observation or "No confirmed damage narrative entered.", False),
            ]

        import textwrap as _tw
        max_chars = max(23, int(callout_w / max(9, height / 75)))
        for text, emphasized in callout_lines:
            for line in _tw.wrap(text, width=min(38, max_chars)):
                if cy > callout_y + callout_h - 30:
                    break
                draw.text(
                    (callout_x + 18, cy),
                    line,
                    fill=yellow if emphasized else white,
                    font=callout_bold if emphasized else callout_body,
                )
                cy += max(22, height // 42)
            cy += max(8, height // 100)

        # Right assessment rail.
        draw.rectangle((right_x, content_top, width - margin, content_bottom), fill=panel, outline=border, width=2)
        rx1 = right_x + 12
        rx2 = width - margin - 12
        y = content_top + 14
        draw.text((rx1, y), "DAMAGE ASSESSMENT SUMMARY", fill=white, font=section_font)
        y += max(42, height // 16)

        fields = [
            ("Component", component),
            ("Classification / Elevation", photo.category or "â€”"),
            ("Damage Type", damage_type),
            ("Confidence", f"{int(photo.confidence)}%" if photo.confidence else "â€”"),
        ]
        row_h = max(38, height // 17)
        value_x = rx1 + int((rx2 - rx1) * 0.49)
        for label, value in fields:
            draw.rectangle((rx1, y, rx2, y + row_h), fill=panel_2, outline=border, width=1)
            draw.text((rx1 + 10, y + 10), f"{label}:", fill=white, font=field_font)
            value_color = green if label == "Confidence" and photo.confidence >= 80 else white
            draw.text((value_x, y + 10), str(value)[:34], fill=value_color, font=field_bold)
            y += row_h + 4

        # Observation panel.
        obs_h = max(90, height // 8)
        draw.rectangle((rx1, y + 4, rx2, y + 4 + obs_h), fill=panel_2, outline=border, width=1)
        draw.text((rx1 + 10, y + 14), "Observation:", fill=white, font=field_font)
        oy = y + 42
        for line in _tw.wrap(observation or "â€”", width=38)[:4]:
            draw.text((rx1 + 14, oy), line, fill=white, font=field_font)
            oy += max(18, height // 58)
        y += obs_h + 18

        # Annotation legend (training mode only).
        if self.training_mode.get() and damage_type == "Hail Impact":
            legend_h = max(92, height // 8)
            draw.rectangle((rx1, y, rx2, y + legend_h), fill=panel, outline=border, width=1)
            draw.text((rx1 + 10, y + 10), "ANNOTATION LEGEND (TRAINING MODE)", fill=white, font=field_bold)
            ly = y + 42
            r = max(9, height // 70)
            draw.ellipse((rx1 + 14, ly - r, rx1 + 14 + 2 * r, ly + r), outline=yellow, width=3)
            draw.text((rx1 + 48, ly - 9), "AI impact center / learning target", fill=white, font=field_font)
            ly += 34
            draw.line((rx1 + 15, ly, rx1 + 48, ly), fill=red, width=5)
            draw.polygon(((rx1 + 15, ly), (rx1 + 28, ly - 7), (rx1 + 28, ly + 7)), fill=red)
            draw.text((rx1 + 58, ly - 9), "Arrow points to impact center", fill=white, font=field_font)
            y += legend_h + 14

        # Evidence checklist.
        remaining = content_bottom - y - 8
        if remaining > 100:
            draw.rectangle((rx1, y, rx2, content_bottom - 8), fill=panel, outline=border, width=1)
            draw.text((rx1 + 10, y + 10), "EVIDENCE CHECKLIST", fill=white, font=field_bold)
            evidence = ["Soft Metal Damage", "Dents", "Impact Pattern", "Hail Signature", "Location Consistent"]
            ey = y + 42
            for item in evidence:
                if ey > content_bottom - 30:
                    break
                draw.text((rx1 + 14, ey), item, fill=white, font=field_font)
                draw.text((rx2 - 22, ey), "âœ“", fill=green, font=field_bold)
                ey += max(23, height // 40)

        # Footer mirrors screen/report identity.
        draw.rectangle((margin, height - footer_h, width - margin, height - margin), fill=bg, outline=border, width=1)
        draw.text((margin + 18, height - footer_h + 9), "ANALYSIS ENGINE: DAMAGESCOPE AI", fill=green, font=footer_font)
        mode_text = "TRAINING MODE: ON (ANNOTATION LEARNING)" if self.training_mode.get() else "PRODUCTION MODE"
        draw.text((left_x + int(left_w * 0.43), height - footer_h + 9), f"â€¢  {mode_text}", fill=green, font=footer_font)
        draw.text((right_x + 14, height - footer_h + 9), "ORIGINAL IMAGE PRESERVED", fill=green, font=footer_font)
        return card

    def _refresh_preview(self) -> None:
        if not self.photos or not self.preview_label.winfo_exists():
            self.preview_label.configure(image="", text="Import photos to begin.")
            self._preview_geometry = {}
            return

        photo = self.photos[self.current_index]
        path = photo.image_path
        if not path.exists():
            self.preview_label.configure(image="", text=f"Missing image:\n{path}")
            self._preview_geometry = {}
            return

        width = max(500, self.preview_frame.winfo_width() - 16)
        height = max(340, self.preview_frame.winfo_height() - 16)
        # The center screen is now a professional assessment card. The original
        # remains untouched; every mark is rendered as an overlay.
        assessment = self._create_assessment_card(photo, (width, height))
        assessment.thumbnail((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (width, height), (3, 16, 25))
        offset_x = (width-assessment.width)//2
        offset_y = (height-assessment.height)//2
        canvas.paste(assessment, (offset_x, offset_y))
        box = getattr(self, "_assessment_photo_box", None)
        if box:
            px, py, pw, ph, card_w, card_h = box
            scale = assessment.width / card_w if card_w else 1.0
            self._preview_geometry = {
                "canvas_width": float(width),
                "canvas_height": float(height),
                "image_x": float(offset_x + px * scale),
                "image_y": float(offset_y + py * scale),
                "image_width": float(pw * scale),
                "image_height": float(ph * scale),
                "original_width": float(pw),
                "original_height": float(ph),
            }
        else:
            self._preview_geometry = {}
        tk_img = ImageTk.PhotoImage(canvas)
        self.preview_label.configure(image=tk_img, text="")
        self.preview_label.image = tk_img

    def _draw_annotations_on_image(self, image: Image.Image, annotations: list[dict], ghost: bool = False) -> None:
        draw = ImageDraw.Draw(image)
        line_width = max(7, round(min(image.size) * 0.012))
        ghost_color = "#ff3b30"
        circle_radius = max(18, round(min(image.size) * 0.055))

        for annotation_index, annotation in enumerate(annotations):
            kind = annotation.get("type")
            if kind == "circle":
                x = int(float(annotation.get("x", 0.5)) * image.width)
                y = int(float(annotation.get("y", 0.5)) * image.height)
                r = int(float(annotation.get("radius", 0.04)) * min(image.size))
                r = max(circle_radius, r)
                draw.ellipse(
                    (x - r, y - r, x + r, y + r),
                    outline=ghost_color if ghost else "#ffd21f",
                    width=line_width,
                )

            elif kind == "rectangle":
                x1 = int(float(annotation.get("x1", 0.25)) * image.width)
                y1 = int(float(annotation.get("y1", 0.25)) * image.height)
                x2 = int(float(annotation.get("x2", 0.75)) * image.width)
                y2 = int(float(annotation.get("y2", 0.75)) * image.height)
                draw.rectangle(
                    (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)),
                    outline=ghost_color if ghost else "#ffd21f",
                    width=line_width,
                )

            elif kind == "line":
                x1 = int(float(annotation.get("x1", 0.25)) * image.width)
                y1 = int(float(annotation.get("y1", 0.25)) * image.height)
                x2 = int(float(annotation.get("x2", 0.75)) * image.width)
                y2 = int(float(annotation.get("y2", 0.75)) * image.height)
                draw.line((x1, y1, x2, y2), fill=ghost_color if ghost else "white", width=line_width)

            elif kind == "arrow":
                x1 = int(float(annotation.get("x1", 0.25)) * image.width)
                y1 = int(float(annotation.get("y1", 0.25)) * image.height)
                x2 = int(float(annotation.get("x2", 0.75)) * image.width)
                y2 = int(float(annotation.get("y2", 0.75)) * image.height)
                draw.line((x1, y1, x2, y2), fill=ghost_color if ghost else "#f22121", width=line_width)

                dx, dy = x2 - x1, y2 - y1
                length = max((dx * dx + dy * dy) ** 0.5, 1.0)
                ux, uy = dx / length, dy / length
                arrow_size = max(16, round(min(image.size) * 0.035))
                px, py = -uy, ux
                p1 = (x2, y2)
                p2 = (
                    int(x2 - ux * arrow_size + px * arrow_size * 0.45),
                    int(y2 - uy * arrow_size + py * arrow_size * 0.45),
                )
                p3 = (
                    int(x2 - ux * arrow_size - px * arrow_size * 0.45),
                    int(y2 - uy * arrow_size - py * arrow_size * 0.45),
                )
                draw.polygon((p1, p2, p3), fill=ghost_color if ghost else "#f22121")

            elif kind == "label":
                x = int(float(annotation.get("x", 0.5)) * image.width)
                y = int(float(annotation.get("y", 0.5)) * image.height)
                text = str(annotation.get("text", "Finding"))
                bbox = draw.multiline_textbbox((x, y), text, spacing=4)
                padding = max(8, round(min(image.size) * 0.012))
                box = (
                    bbox[0] - padding,
                    bbox[1] - padding,
                    bbox[2] + padding,
                    bbox[3] + padding,
                )
                possible = "possible" in text.lower() or "clarif" in text.lower()
                draw.rounded_rectangle(
                    box,
                    radius=7,
                    fill=(18, 18, 18) if possible else (4, 32, 56),
                    outline="#ffd21f" if possible else "white",
                    width=max(3, line_width // 2),
                )
                draw.multiline_text((x, y), text, fill="#ffd21f" if possible else "white", spacing=4)

            if (not ghost and self.photos and self.selected_annotation_index == annotation_index
                    and annotations is self.photos[self.current_index].annotations):
                handle_color = "#1e90ff"
                handle_r = max(6, line_width)
                points: list[tuple[int,int]] = []
                if kind in {"line","arrow","rectangle"}:
                    points = [
                        (int(float(annotation.get("x1",.25))*image.width), int(float(annotation.get("y1",.25))*image.height)),
                        (int(float(annotation.get("x2",.75))*image.width), int(float(annotation.get("y2",.75))*image.height)),
                    ]
                elif kind == "circle":
                    cx=int(float(annotation.get("x",.5))*image.width); cy=int(float(annotation.get("y",.5))*image.height)
                    r=int(float(annotation.get("radius",.04))*min(image.size))
                    points=[(cx,cy),(cx+r,cy)]
                elif kind == "label":
                    points=[(int(float(annotation.get("x",.5))*image.width), int(float(annotation.get("y",.5))*image.height))]
                for hx,hy in points:
                    draw.rectangle((hx-handle_r,hy-handle_r,hx+handle_r,hy+handle_r), fill="white", outline=handle_color, width=max(2,line_width//3))

    def set_annotation_mode(self, mode: str) -> None:
        if mode == "select":
            self.annotation_mode = "select"
            self.annotation_pending_point = None
            self.annotation_status.configure(
                text="Select mode â€” click an annotation, then drag to move or resize it.",
                fg=GREEN,
            )
            return
        if not self.photos:
            messagebox.showwarning("DamageScope AI", "Open a photo before adding annotations.")
            return
        if self.photos[self.current_index].annotations_locked:
            messagebox.showwarning(
                "DamageScope AI",
                "Annotations are locked for this photo. Click Lock to unlock them.",
            )
            return

        self.annotation_mode = mode
        self.annotation_pending_point = None
        messages = {
            "arrow": "Arrow â€” click start, then click target",
            "line": "Line â€” click start, then click end",
            "circle": "Circle â€” click center, then click edge",
            "rectangle": "Rectangle â€” click one corner, then the opposite corner",
            "label": "Text â€” click location, then enter wording",
            "erase": "Erase â€” click near the annotation to remove",
        }
        self.annotation_status.configure(text=messages.get(mode, f"Mode: {mode}"), fg="#23bcff")

    def toggle_training_banner(self) -> None:
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        photo.training_banner = not photo.training_banner
        self.project_dirty = True
        self._save_session()
        self._refresh_preview()
        self.annotation_status.configure(text=("Training caution banner ON." if photo.training_banner else "Training caution banner OFF."), fg=ORANGE if photo.training_banner else GREEN)

    def rotate_current_photo(self, delta: int) -> None:
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        photo.rotation_degrees = (int(photo.rotation_degrees or 0) + delta) % 360
        self.project_dirty = True
        self._save_session()
        self.image_cache.clear()
        self._refresh_preview()
        self.annotation_status.configure(text=f"Photo rotated to {photo.rotation_degrees}Â°.", fg=GREEN)

    def _annotation_center(self, annotation: dict) -> tuple[float, float]:
        kind = annotation.get("type")
        if kind in {"circle", "label"}:
            return float(annotation.get("x", 0.5)), float(annotation.get("y", 0.5))
        return (
            (float(annotation.get("x1", 0.5)) + float(annotation.get("x2", 0.5))) / 2,
            (float(annotation.get("y1", 0.5)) + float(annotation.get("y2", 0.5))) / 2,
        )

    @staticmethod
    def _distance_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        dx, dy = x2 - x1, y2 - y1
        denom = dx * dx + dy * dy
        if denom <= 1e-12:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / denom))
        qx, qy = x1 + t * dx, y1 + t * dy
        return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5

    def _annotation_hit_test(
        self,
        point: tuple[float, float],
        annotations: list[dict] | None = None,
    ) -> tuple[int | None, str | None]:
        """Return the closest selectable annotation and edit action.

        The optional annotation list lets Training Mode hit-test the original AI
        reference layer as well as the inspector-editable overlay layer.
        """
        if not self.photos:
            return None, None
        x, y = point
        if annotations is None:
            annotations = self.photos[self.current_index].annotations
        best: tuple[float, int, str] | None = None
        endpoint_threshold = 0.035
        object_threshold = 0.055
        for index in range(len(annotations) - 1, -1, -1):
            annotation = annotations[index]
            kind = annotation.get("type")
            candidates: list[tuple[float, str]] = []
            if kind in {"line", "arrow"}:
                x1, y1 = float(annotation.get("x1", .5)), float(annotation.get("y1", .5))
                x2, y2 = float(annotation.get("x2", .5)), float(annotation.get("y2", .5))
                d1 = ((x-x1)**2+(y-y1)**2)**.5
                d2 = ((x-x2)**2+(y-y2)**2)**.5
                if d1 <= endpoint_threshold:
                    candidates.append((d1, "endpoint1"))
                if d2 <= endpoint_threshold:
                    candidates.append((d2, "endpoint2"))
                candidates.append((self._distance_to_segment(x, y, x1, y1, x2, y2), "move"))
            elif kind == "rectangle":
                x1, y1 = float(annotation.get("x1", .25)), float(annotation.get("y1", .25))
                x2, y2 = float(annotation.get("x2", .75)), float(annotation.get("y2", .75))
                corners = [("corner1", x1, y1), ("corner2", x2, y2)]
                for action, px, py in corners:
                    d = ((x-px)**2+(y-py)**2)**.5
                    if d <= endpoint_threshold:
                        candidates.append((d, action))
                left, right = sorted((x1, x2)); top, bottom = sorted((y1, y2))
                if left <= x <= right and top <= y <= bottom:
                    candidates.append((0.0, "move"))
                else:
                    edge_d = min(abs(x-left), abs(x-right), abs(y-top), abs(y-bottom))
                    candidates.append((edge_d, "move"))
            elif kind == "circle":
                cx,cy=float(annotation.get("x",.5)),float(annotation.get("y",.5))
                r=float(annotation.get("radius",.04))
                d=((x-cx)**2+(y-cy)**2)**.5
                if abs(d-r) <= endpoint_threshold:
                    candidates.append((abs(d-r),"resize"))
                if d <= r + object_threshold:
                    candidates.append((0.0 if d <= r else d-r,"move"))
            elif kind == "label":
                cx,cy=float(annotation.get("x",.5)),float(annotation.get("y",.5))
                # Labels are selectable from a generous box around their anchor.
                dx, dy = abs(x-cx), abs(y-cy)
                if dx <= 0.18 and dy <= 0.10:
                    candidates.append((max(dx/0.18, dy/0.10) * 0.02,"move"))
                else:
                    candidates.append((((x-cx)**2+(y-cy)**2)**.5,"move"))
            for distance, action in candidates:
                if best is None or distance < best[0]:
                    best=(distance,index,action)
        if best and best[0] <= object_threshold:
            return best[1], best[2]
        return None, None

    def _on_preview_drag_start(self, event: tk.Event) -> None:
        point = self._preview_click_to_normalized(event)
        if point is None:
            return
        if self.annotation_mode == "select":
            photo = self.photos[self.current_index]

            # Expert teaching sessions must be editable. Unlocking here avoids a
            # confusing no-op when a previously verified photo is reopened.
            if photo.annotations_locked:
                photo.annotations_locked = False
                self.annotation_status.configure(
                    text="Annotations unlocked for this teaching correction.",
                    fg=ORANGE,
                )

            index, action = self._annotation_hit_test(point, photo.annotations)

            # AI marks may be displayed from a separate red ghost/reference
            # layer. If the inspector selects one, clone it into the editable
            # overlay and retain the exact original as the before-state lesson.
            if index is None and photo.ai_annotations:
                ai_index, ai_action = self._annotation_hit_test(point, photo.ai_annotations)
                if ai_index is not None:
                    original_ai = dict(photo.ai_annotations[ai_index])
                    editable = dict(original_ai)
                    editable["source"] = "ai_reference"
                    editable["source_ai_index"] = ai_index
                    editable["original_ai_annotation"] = dict(original_ai)
                    photo.annotations.append(editable)
                    index = len(photo.annotations) - 1
                    action = ai_action or "move"
                    # Hide only the converted AI ghost to avoid a duplicate red
                    # mark underneath the editable inspector copy.
                    photo.ai_annotations[ai_index]["converted_to_editable"] = True
                    self.project_dirty = True
                    self._save_session()
                    self.annotation_status.configure(
                        text="AI annotation converted to editable teaching object â€” drag it now.",
                        fg=GREEN,
                    )

            self.selected_annotation_index = index
            self.annotation_edit_action = action
            self.annotation_edit_start = point
            if index is not None:
                self.annotation_edit_original = dict(photo.annotations[index])
                self.annotation_status.configure(
                    text="Annotation selected â€” drag to reposition or resize.",
                    fg="#23bcff",
                )
            else:
                self.annotation_edit_original = None
                self.annotation_status.configure(
                    text="No annotation selected. Click directly on its line, edge, arrow, circle, or text box.",
                    fg=MUTED,
                )
            self._refresh_preview()
            return
        if self.annotation_mode in {"line", "arrow", "circle", "rectangle"}:
            self.annotation_drag_start = point

    def _on_preview_drag_motion(self, event: tk.Event) -> None:
        """Live-preview moving/resizing of the selected annotation."""
        if self.annotation_mode != "select" or not self.photos:
            return
        if self.selected_annotation_index is None or self.annotation_edit_original is None or self.annotation_edit_start is None:
            return
        photo = self.photos[self.current_index]
        if photo.annotations_locked or self.selected_annotation_index >= len(photo.annotations):
            return
        end = self._preview_click_to_normalized(event)
        if end is None:
            return
        original = self.annotation_edit_original
        annotation = photo.annotations[self.selected_annotation_index]
        sx, sy = self.annotation_edit_start
        ex, ey = end
        dx, dy = ex - sx, ey - sy
        action = self.annotation_edit_action or "move"
        kind = annotation.get("type")
        if action == "move":
            if kind in {"circle", "label"}:
                annotation["x"] = max(0.0, min(1.0, float(original.get("x", .5)) + dx))
                annotation["y"] = max(0.0, min(1.0, float(original.get("y", .5)) + dy))
            else:
                annotation["x1"] = max(0.0, min(1.0, float(original.get("x1", .25)) + dx))
                annotation["y1"] = max(0.0, min(1.0, float(original.get("y1", .25)) + dy))
                annotation["x2"] = max(0.0, min(1.0, float(original.get("x2", .75)) + dx))
                annotation["y2"] = max(0.0, min(1.0, float(original.get("y2", .75)) + dy))
        elif action in {"endpoint1", "corner1"}:
            annotation["x1"], annotation["y1"] = ex, ey
        elif action in {"endpoint2", "corner2"}:
            annotation["x2"], annotation["y2"] = ex, ey
        elif action == "resize" and kind == "circle":
            cx, cy = float(original.get("x", .5)), float(original.get("y", .5))
            annotation["radius"] = max(.01, min(.5, ((ex-cx)**2+(ey-cy)**2)**.5))
        self._refresh_preview()

    def _on_preview_drag_end(self, event: tk.Event) -> None:
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        end = self._preview_click_to_normalized(event)
        if end is None:
            return

        if self.annotation_mode == "select":
            if self.selected_annotation_index is None or self.annotation_edit_original is None or self.annotation_edit_start is None:
                return
            if photo.annotations_locked:
                self.annotation_status.configure(text="Annotations locked.", fg=ORANGE)
                return
            index=self.selected_annotation_index
            if index >= len(photo.annotations):
                return
            original=dict(self.annotation_edit_original)
            annotation=photo.annotations[index]
            sx,sy=self.annotation_edit_start; ex,ey=end
            dx,dy=ex-sx,ey-sy
            action=self.annotation_edit_action or "move"
            kind=annotation.get("type")
            if action == "move":
                if kind in {"circle","label"}:
                    annotation["x"]=max(0,min(1,float(original.get("x",.5))+dx))
                    annotation["y"]=max(0,min(1,float(original.get("y",.5))+dy))
                else:
                    annotation["x1"]=max(0,min(1,float(original.get("x1",.25))+dx))
                    annotation["y1"]=max(0,min(1,float(original.get("y1",.25))+dy))
                    annotation["x2"]=max(0,min(1,float(original.get("x2",.75))+dx))
                    annotation["y2"]=max(0,min(1,float(original.get("y2",.75))+dy))
            elif action in {"endpoint1","corner1"}:
                annotation["x1"],annotation["y1"]=ex,ey
            elif action in {"endpoint2","corner2"}:
                annotation["x2"],annotation["y2"]=ex,ey
            elif action == "resize" and kind == "circle":
                cx,cy=float(original.get("x",.5)),float(original.get("y",.5))
                annotation["radius"]=max(.01,min(.5,((ex-cx)**2+(ey-cy)**2)**.5))
            self.annotation_redo_stack.setdefault(id(photo), []).clear()
            self.project_dirty=True
            self._save_session()
            self._refresh_preview()
            self.annotation_status.configure(text="Annotation updated and ready to save as a learning correction.", fg=GREEN)
            return

        if self.annotation_mode not in {"line", "arrow", "circle", "rectangle"} or self.annotation_drag_start is None:
            return
        start = self.annotation_drag_start
        self.annotation_drag_start = None
        if photo.annotations_locked:
            return
        x1,y1=start; x2,y2=end
        mode=self.annotation_mode
        if mode == "circle":
            photo.annotations.append({"type":"circle","x":(x1+x2)/2,"y":(y1+y2)/2,"radius":max(abs(x2-x1),abs(y2-y1))/2})
        elif mode == "rectangle":
            photo.annotations.append({"type":"rectangle","x1":x1,"y1":y1,"x2":x2,"y2":y2})
        else:
            photo.annotations.append({"type":mode,"x1":x1,"y1":y1,"x2":x2,"y2":y2})
        self.annotation_redo_stack.setdefault(id(photo), []).clear()
        self.project_dirty=True
        self._save_session()
        self._refresh_preview()
        self.annotation_status.configure(text=f"{mode.title()} added. Draw another or choose Select.", fg=GREEN)

    def _on_preview_double_click(self, event: tk.Event) -> None:
        if self.annotation_mode != "select" or not self.photos:
            return
        point=self._preview_click_to_normalized(event)
        if point is None:
            return
        index,_action=self._annotation_hit_test(point)
        photo=self.photos[self.current_index]
        if index is None or index >= len(photo.annotations):
            return
        annotation=photo.annotations[index]
        if annotation.get("type") != "label":
            return
        updated=simpledialog.askstring("DamageScope AI", "Edit annotation label:", initialvalue=str(annotation.get("text","")), parent=self)
        if updated is None:
            return
        annotation["text"]=updated.strip()
        self.selected_annotation_index=index
        self.project_dirty=True
        self._save_session()
        self._refresh_preview()
        self.annotation_status.configure(text="Annotation label updated.", fg=GREEN)

    def _delete_selected_annotation(self, _event=None) -> None:
        if not self.photos or self.selected_annotation_index is None:
            return
        photo=self.photos[self.current_index]
        if photo.annotations_locked:
            self.annotation_status.configure(text="Annotations locked.", fg=ORANGE)
            return
        index=self.selected_annotation_index
        if 0 <= index < len(photo.annotations):
            removed=photo.annotations.pop(index)
            self.annotation_redo_stack.setdefault(id(photo), []).append(removed)
            self.selected_annotation_index=None
            self.project_dirty=True
            self._save_session()
            self._refresh_preview()
            self.annotation_status.configure(text="Selected annotation deleted.", fg=GREEN)

    def toggle_ai_ghost(self) -> None:
        self.show_ai_ghost_annotations.set(not self.show_ai_ghost_annotations.get())
        self._refresh_preview()
        state = "shown" if self.show_ai_ghost_annotations.get() else "hidden"
        self.annotation_status.configure(text=f"AI ghost annotations {state}.", fg=GREEN)

    def _preview_click_to_normalized(self, event: tk.Event) -> tuple[float, float] | None:
        geometry = self._preview_geometry
        if not geometry:
            return None

        x = float(event.x) - geometry["image_x"]
        y = float(event.y) - geometry["image_y"]
        if x < 0 or y < 0 or x > geometry["image_width"] or y > geometry["image_height"]:
            return None

        return (
            max(0.0, min(1.0, x / geometry["image_width"])),
            max(0.0, min(1.0, y / geometry["image_height"])),
        )

    def _on_preview_click(self, event: tk.Event) -> None:
        if not self.photos or not self.annotation_mode:
            return

        photo = self.photos[self.current_index]
        if photo.annotations_locked:
            self.annotation_status.configure(text="Annotations locked.", fg=ORANGE)
            return

        point = self._preview_click_to_normalized(event)
        if point is None:
            self.annotation_status.configure(text="Click inside the displayed photo.", fg=ORANGE)
            return

        x, y = point
        if self.annotation_mode in {"circle", "rectangle", "line", "arrow"}:
            # These tools are handled by click-and-drag bindings.
            return
        if self.annotation_mode in {"circle", "rectangle"}:
            active_mode = self.annotation_mode
            if self.annotation_pending_point is None:
                self.annotation_pending_point = (x, y)
                self.annotation_status.configure(text=f"{active_mode.title()} start saved â€” click the opposite point.", fg="#23bcff")
                return
            x1, y1 = self.annotation_pending_point
            if active_mode == "circle":
                radius = max(abs(x - x1), abs(y - y1), 0.015)
                photo.annotations.append({"type": "circle", "x": x1, "y": y1, "radius": radius})
            else:
                photo.annotations.append({"type": "rectangle", "x1": x1, "y1": y1, "x2": x, "y2": y})
            self.annotation_pending_point = None
            self.annotation_mode = None
            self.annotation_redo_stack.setdefault(id(photo), []).clear()
            self.annotation_status.configure(text=f"{active_mode.title()} added.", fg=GREEN)

        elif self.annotation_mode in {"arrow", "line"}:
            active_mode = self.annotation_mode
            if self.annotation_pending_point is None:
                self.annotation_pending_point = (x, y)
                self.annotation_status.configure(
                    text="Arrow start saved â€” click the target.",
                    fg="#23bcff",
                )
                return
            x1, y1 = self.annotation_pending_point
            photo.annotations.append(
                {"type": active_mode, "x1": x1, "y1": y1, "x2": x, "y2": y}
            )
            self.annotation_redo_stack.setdefault(id(photo), []).clear()
            self.annotation_pending_point = None
            self.annotation_mode = None
            self.annotation_status.configure(text=f"{active_mode.title()} added.", fg=GREEN)

        elif self.annotation_mode == "label":
            label_text = simpledialog.askstring(
                "DamageScope AI",
                "Enter annotation label:",
                parent=self,
            )
            if not label_text:
                self.annotation_status.configure(text="Label cancelled.", fg=MUTED)
                self.annotation_mode = None
                return
            photo.annotations.append(
                {"type": "label", "x": x, "y": y, "text": label_text.strip()}
            )
            self.annotation_redo_stack.setdefault(id(photo), []).clear()
            self.annotation_mode = None
            self.annotation_status.configure(text="Label added.", fg=GREEN)

        elif self.annotation_mode == "erase":
            if not photo.annotations:
                self.annotation_status.configure(text="Nothing to erase.", fg=MUTED)
                self.annotation_mode = None
                return
            def center(annotation):
                if "x" in annotation and "y" in annotation:
                    return float(annotation["x"]), float(annotation["y"])
                return ((float(annotation.get("x1", 0.5)) + float(annotation.get("x2", 0.5))) / 2,
                        (float(annotation.get("y1", 0.5)) + float(annotation.get("y2", 0.5))) / 2)
            nearest_index = min(range(len(photo.annotations)), key=lambda i: (center(photo.annotations[i])[0]-x)**2 + (center(photo.annotations[i])[1]-y)**2)
            removed = photo.annotations.pop(nearest_index)
            self.annotation_redo_stack.setdefault(id(photo), []).append(removed)
            self.annotation_mode = None
            self.annotation_status.configure(text="Annotation erased.", fg=GREEN)

        self.project_dirty = True
        self._save_session()
        self._refresh_preview()

    def save_expert_annotation_lesson(self) -> None:
        """Save the inspector-drawn annotation as an expert-verified learning example."""
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        if not photo.image_path.exists():
            messagebox.showwarning("DamageScope AI", "The source photo is unavailable.")
            return
        if not photo.annotations:
            messagebox.showwarning(
                "DamageScope AI",
                "Draw at least one line, circle, arrow, or label before saving the lesson.",
            )
            return

        annotation_changes = []
        for item in photo.annotations:
            original_ai = item.get("original_ai_annotation")
            if isinstance(original_ai, dict):
                annotation_changes.append({
                    "before": dict(original_ai),
                    "after": {
                        key: value for key, value in item.items()
                        if key not in {"original_ai_annotation"}
                    },
                    "change_type": "AI_ANNOTATION_EDIT",
                })

        correction = {
            "category": photo.category,
            "component": photo.component,
            "damage_type": photo.damage_type,
            "observation": photo.observation,
            "review_status": photo.review_status or "Confirmed",
            "annotation_teaching": True,
            "annotation_count": len(photo.annotations),
            "annotation_changes": annotation_changes,
        }
        original = dict(photo.ai_prediction or {})
        original["annotations"] = [dict(item) for item in photo.ai_annotations]
        try:
            record_id = self.learning_engine.record_correction(
                photo_path=photo.image_path,
                filename=photo.filename,
                ai_prediction=original,
                expert_correction=correction,
                annotations=[dict(item) for item in photo.annotations],
                inspection_id=self.project_metadata.get("project_name", ""),
                claim_number=self.customer_info.get("claim_number", ""),
                reviewer=self.customer_info.get("inspector_name", "") or "Inspector",
                model=self._active_model_label(),
            )
            photo.annotation_learning_status = "Expert Verified"
            photo.annotation_learning_record_id = record_id
            photo.annotations_locked = True
            self.project_dirty = True
            self._save_session()
            self._write_audit(
                "expert_annotation_lesson",
                {
                    "record_id": record_id,
                    "filename": photo.filename,
                    "ai_annotation_count": len(photo.ai_annotations),
                    "expert_annotation_count": len(photo.annotations),
                },
            )
            self.annotation_status.configure(
                text=f"Expert annotation saved to Learning Center â€” {record_id}",
                fg=GREEN,
            )
            self.analysis_status.configure(
                text="Annotation lesson saved and locked as Expert Verified."
            )
        except Exception as exc:
            messagebox.showerror(
                "DamageScope AI",
                f"The annotation lesson could not be saved.\n\n{exc}",
            )

    def undo_annotation(self) -> None:
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        if photo.annotations_locked:
            messagebox.showwarning("DamageScope AI", "Annotations are locked.")
            return
        if not photo.annotations:
            self.annotation_status.configure(text="Nothing to undo.", fg=MUTED)
            return
        removed = photo.annotations.pop()
        self.annotation_redo_stack.setdefault(id(photo), []).append(removed)
        self.project_dirty = True
        self._save_session()
        self._refresh_preview()
        self.annotation_status.configure(text="Last annotation removed.", fg=GREEN)

    def redo_annotation(self) -> None:
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        if photo.annotations_locked:
            messagebox.showwarning("DamageScope AI", "Annotations are locked.")
            return
        stack = self.annotation_redo_stack.setdefault(id(photo), [])
        if not stack:
            self.annotation_status.configure(text="Nothing to redo.", fg=MUTED)
            return
        photo.annotations.append(stack.pop())
        self.project_dirty = True
        self._save_session()
        self._refresh_preview()
        self.annotation_status.configure(text="Annotation restored.", fg=GREEN)

    def clear_annotations(self) -> None:
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        if photo.annotations_locked:
            messagebox.showwarning("DamageScope AI", "Annotations are locked.")
            return
        if not photo.annotations:
            return
        if not messagebox.askyesno(
            "DamageScope AI",
            "Clear all annotations from this photo?",
        ):
            return
        photo.annotations.clear()
        self.project_dirty = True
        self._save_session()
        self._refresh_preview()
        self.annotation_status.configure(text="Annotations cleared.", fg=GREEN)

    def toggle_annotation_lock(self) -> None:
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        photo.annotations_locked = not photo.annotations_locked
        self.project_dirty = True
        self._save_session()
        state = "locked" if photo.annotations_locked else "unlocked"
        self.annotation_status.configure(
            text=f"Annotations {state}.",
            fg=GREEN if photo.annotations_locked else "#23bcff",
        )

    def _refresh_all_views(self, select_index: int | None = None) -> None:
        if select_index is not None:
            if self.photos:
                self.current_index = max(0, min(select_index, len(self.photos) - 1))
            else:
                self.current_index = 0

        self.image_cache.clear()
        self._rebuild_cards()
        self._rebuild_filmstrip()
        self._update_counters()

        if self.photos:
            self.show_photo(self.current_index)
        else:
            self.photo_counter.configure(text="Photo 0 of 0")
            self._refresh_sequence_position_entry()
            self.preview_label.configure(image="", text="Import photos to begin.")
            for label in self.info_labels:
                label.configure(text="")
            self.observation.delete("1.0", "end")

    def _update_counters(self) -> None:
        real_photos = self._real_photos()
        total = len(real_photos)
        report = sum(1 for p in real_photos if p.include)
        not_used = total - report
        analyzed = sum(
            1 for p in real_photos
            if p.damage_type not in {"Not Analyzed", ""}
        )

        sequence_total = len(self._sequence_photos())
        self.sequence_title.configure(text=f"Inspection Sequence ({sequence_total})")
        self.header_count.configure(text=f"Report photos: {report}    Not Used: {not_used}")

        if not real_photos:
            self.summary_label.configure(
                text="â—  Waiting for photo import",
                fg=MUTED,
            )
        elif sequence_total:
            self.summary_label.configure(
                text=f"â—  Sequence Active â€” {sequence_total} assigned",
                fg=GREEN,
            )
        elif analyzed == 0:
            self.summary_label.configure(
                text="â—  0 assigned â€” run Analyze All",
                fg=ORANGE,
            )
        else:
            self.summary_label.configure(
                text="â—  Analysis complete â€” sequence awaiting assignment",
                fg=ORANGE,
            )

        self.footer_left.configure(
            text=f"Photos Imported: {total}     Analyzed: {analyzed}     "
                 f"Report Photos: {report}     Not Used: {not_used}     "
                 f"Estimated AI Cost: ${self.ai_usage_session['estimated_cost']:.4f}     "
                 f"Model: {self._active_model_label()}"
        )

    def show_photo(self, index: int) -> None:
        if not self.photos:
            return
        self.selected_annotation_index = None
        self.annotation_edit_original = None
        self.current_index = index % len(self.photos)
        self.user_settings["last_photo_index"] = self.current_index
        self._save_user_settings()
        photo = self.photos[self.current_index]

        self.photo_counter.configure(text=f"Photo {self.current_index + 1} of {len(self.photos)}")
        self._refresh_sequence_position_entry()
        category = photo.category if photo.category in self.classification_options else "Unreviewed"
        self.category_var.set(category)
        self.component_combo.configure(
            values=self.classification_options.get(category, ["Not Classified"])
        )
        component_choices = self.classification_options.get(category, ["Not Classified"])
        component = photo.component if photo.component in component_choices else component_choices[0]
        self.component_var.set(component)
        self.damage_var.set(photo.damage_type)
        self.severity_var.set(photo.severity)
        self.include_var.set(photo.include)
        self.confidence_label.configure(text=f"{photo.confidence}%" if photo.confidence else "â€”")
        self.forensic_grade_label.configure(text=photo.forensic_grade or "â€”")

        self.observation.delete("1.0", "end")
        observation_text = photo.observation.strip()
        self.observation.insert("1.0", observation_text)

        context_components = {
            "Front Property Overview",
            "Front Elevation",
            "Front Right Corner",
            "Right Elevation",
            "Right Rear Corner",
            "Rear Elevation",
            "Left Rear Corner",
            "Left Elevation",
            "Left Front Corner",
            "Garage Elevation",
            "Detached Structure Elevation",
            "Unknown Elevation",
        }
        suppress_detailed_findings = (
            not observation_text
            and (photo.component in context_components or photo.damage_type in {"None", "Not Analyzed"})
        )
        if suppress_detailed_findings:
            if self.detailed_findings_frame.winfo_manager():
                self.detailed_findings_frame.pack_forget()
        elif not self.detailed_findings_frame.winfo_manager():
            if hasattr(self, "evidence_heading"):
                self.detailed_findings_frame.pack(fill="x", before=self.evidence_heading)
            else:
                self.detailed_findings_frame.pack(fill="x")
        if hasattr(self, "annotation_status"):
            lock_text = "LOCKED" if photo.annotations_locked else "editable"
            self.annotation_status.configure(
                text=(f"Annotations: {len(photo.annotations)} â€” {lock_text}" + (" â€” EXPERT VERIFIED" if photo.annotation_learning_status == "Expert Verified" else "")),
                fg=GREEN if photo.annotations_locked else MUTED,
            )

        path = photo.image_path
        try:
            with Image.open(path) as image:
                width, height = image.size
            size_mb = path.stat().st_size / (1024 * 1024)
            modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%d-%b-%Y %I:%M%p")
        except Exception:
            width = height = 0
            size_mb = 0.0
            modified = "Unknown"

        self.info_labels[0].configure(
            text=f"File Name:     {photo.filename}\n"
                 f"Date Taken:    {modified}\n"
                 f"Location:      Not Assigned\n"
                 f"Dimensions:    {width} x {height}\n"
                 f"Size:          {size_mb:.2f} MB"
        )
        self.info_labels[1].configure(
            text=f"Category:      {photo.category}\n"
                 f"Component:     {photo.component}\n"
                 f"Damage Type:   {photo.damage_type}\n"
                 f"Severity:      {photo.severity}\n"
                 f"Confidence:    {photo.confidence if photo.confidence else 'â€”'}"
        )
        self.info_labels[2].configure(text=photo.observation)

        self._rebuild_cards()
        self._rebuild_filmstrip()
        self.after(30, self._refresh_preview)

    def _on_category_changed(self, _event=None) -> None:
        category = self.category_var.get() or "Unreviewed"
        choices = self.classification_options.get(category, ["Not Classified"])
        self.component_combo.configure(values=choices)
        if self.component_var.get() not in choices:
            self.component_var.set(choices[0])

    def save_correction_and_lock(self) -> None:
        """Save an expert correction without making the UI permanently uneditable."""
        self.save_details()
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        photo.review_status = "Confirmed" if photo.damage_type not in {
            "â€” Select Damage Type â€”", "None", "Not Analyzed", "Other"
        } else photo.review_status
        self.project_dirty = True
        self.status_var.set("Correction saved to the Forensic Learning Center. Editing remains available.")
        self._refresh_preview()

    def save_details(self) -> None:
        if not self.photos:
            return
        photo = self.photos[self.current_index]
        before = {
            "category": photo.category,
            "component": photo.component,
            "damage_type": photo.damage_type,
            "observation": photo.observation,
            "review_status": photo.review_status,
        }

        photo.category = self.category_var.get()
        photo.component = self.component_var.get()
        photo.damage_type = self.damage_var.get()
        photo.include = self.include_var.get()
        photo.observation = self.observation.get("1.0", "end").strip()

        if photo.damage_type == "Hail Impact" and not photo.observation:
            photo.observation = "Localized impact-related deformation observed."
        elif photo.damage_type == "Hail Spatter" and not photo.observation:
            photo.observation = "Distributed impact-related spatter observed."
        elif photo.damage_type == "Missing Shingle":
            lower_observation = (photo.observation or "").lower()
            if (
                not photo.observation
                or "caused by high wind" in lower_observation
                or "caused by wind" in lower_observation
                or "due to wind" in lower_observation
            ):
                photo.observation = "Missing shingle observed. Cause of loss requires additional inspection."
        elif photo.damage_type == "Wind Crease" and not photo.observation:
            photo.observation = "Crease consistent with wind stress on shingle."

        if photo.damage_type == "â€” Select Damage Type â€”":
            photo.review_status = "Needs Clarification"
            if not photo.observation:
                photo.observation = "Potential damage detected. Inspector clarification requested."
        elif photo.damage_type == "None":
            photo.review_status = "No Finding"
            photo.annotations = []
        elif photo.damage_type not in {"Not Analyzed", "Possible Hail", "Possible Wind", "Possible Impact", "Other"}:
            photo.review_status = "Confirmed"

        after = {
            "category": photo.category,
            "component": photo.component,
            "damage_type": photo.damage_type,
            "observation": photo.observation,
            "review_status": photo.review_status,
        }
        changed = before != after
        self.project_dirty = True

        if changed and photo.image_path.exists():
            original_prediction = photo.ai_prediction or before
            try:
                record_id = self.learning_engine.record_correction(
                    photo_path=photo.image_path,
                    filename=photo.filename,
                    ai_prediction=original_prediction,
                    expert_correction=after,
                    annotations=photo.annotations,
                    inspection_id=self.project_metadata.get("project_name", ""),
                    claim_number=self.customer_info.get("claim_number", ""),
                    reviewer=self.customer_info.get("inspector", "") or self.project_metadata.get("project_name", ""),
                    model=self._active_model_label(),
                )
                photo.learning_record_id = record_id
                photo.correction_count += 1
                self._write_audit("forensic_learning_correction", {
                    "record_id": record_id,
                    "filename": photo.filename,
                    "before": original_prediction,
                    "after": after,
                })
            except Exception as exc:
                self._write_audit("forensic_learning_error", {"filename": photo.filename, "error": str(exc)})

        self._save_session()
        self._update_counters()
        self.show_photo(self.current_index)
        if changed:
            self.analysis_status.configure(text="Correction saved to the Forensic Learning Center.")
        else:
            self.analysis_status.configure(text="Details saved.")

    def set_category(self, category: str, component: str) -> None:
        if not self.photos:
            return
        self.category_var.set(category)
        self.component_var.set(component)
        self.save_details()

    def move_photo(self, delta: int) -> None:
        self.move_sequence_item(delta)

    def _renumber_titles(self) -> None:

        for idx, photo in enumerate(self.photos, start=1):
            base = photo.title.split(". ", 1)[1] if ". " in photo.title else Path(photo.filename).stem
            photo.title = f"{idx}. {base}"

    def _unique_destination(self, original_name: str) -> Path:
        stem = Path(original_name).stem
        suffix = Path(original_name).suffix.lower()
        candidate = IMPORTED_DIR / f"{stem}{suffix}"
        counter = 2
        while candidate.exists():
            candidate = IMPORTED_DIR / f"{stem}_{counter}{suffix}"
            counter += 1
        return candidate

    def _enable_global_drag_drop(self) -> None:
        """Make the entire application window accept files and folders at any time."""
        if not DND_AVAILABLE:
            self.after(
                250,
                lambda: self.analysis_status.configure(
                    text="Drag-and-drop unavailable until tkinterdnd2 is installed."
                ),
            )
            return

        def register_tree(widget: tk.Misc) -> None:
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_files_dropped)
                widget.dnd_bind(
                    "<<DropEnter>>",
                    lambda event: self.analysis_status.configure(
                        text="Release to import photos."
                    ),
                )
                widget.dnd_bind(
                    "<<DropLeave>>",
                    lambda event: self.analysis_status.configure(
                        text="Ready."
                    ),
                )
            except Exception:
                pass

            for child in widget.winfo_children():
                register_tree(child)

        register_tree(self)

    def _on_files_dropped(self, event) -> str:
        try:
            dropped_items = list(self.tk.splitlist(event.data))
        except Exception:
            dropped_items = [event.data]

        files = self._expand_import_sources(dropped_items)
        if not files:
            messagebox.showinfo(
                "DamageScope AI",
                "No supported image files were found in the dropped selection.",
            )
            return "break"

        self._import_photo_paths(files, source_label="drag-and-drop")
        return "break"

    def _expand_import_sources(self, sources) -> list[str]:
        supported = {
            ".jpg", ".jpeg", ".png", ".webp", ".bmp",
            ".tif", ".tiff", ".heic", ".heif",
        }
        discovered: list[str] = []
        seen: set[str] = set()

        for raw_item in sources:
            path = Path(str(raw_item).strip().strip("{}"))
            if path.is_dir():
                candidates = sorted(
                    candidate
                    for candidate in path.rglob("*")
                    if candidate.is_file() and candidate.suffix.lower() in supported
                )
            elif path.is_file() and path.suffix.lower() in supported:
                candidates = [path]
            else:
                candidates = []

            for candidate in candidates:
                resolved = str(candidate.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    discovered.append(resolved)

        return discovered

    def _import_photo_paths(self, files, source_label: str = "Import Photos") -> None:
        if not files:
            return

        imported_count = 0
        failed: list[str] = []

        self.photos = [
            photo for photo in self.photos
            if not self._is_demo_photo(photo)
        ]
        self.current_index = 0
        self.library_selected_index = 0
        first_new_index = len(self.photos)

        for photo in self.photos:
            if photo.damage_type in {"Not Analyzed", ""}:
                photo.sequence_position = None
                photo.sequence_label = ""

        for file_name in files:
            source = Path(file_name)
            try:
                with Image.open(source) as test_image:
                    test_image.verify()

                destination = self._unique_destination(source.name)
                shutil.copy2(source, destination)

                title = (
                    f"{len(self.photos) + 1}. "
                    f"{source.stem.replace('_', ' ').replace('-', ' ').strip()}"
                )
                self.photos.append(
                    PhotoRecord(
                        title=title,
                        filename=destination.name,
                        category="Unreviewed",
                        component="Not Classified",
                        damage_type="Not Analyzed",
                        severity="None",
                        confidence=0,
                        include=True,
                        observation="Imported. Awaiting analysis.",
                        source_path=str(destination),
                        imported=True,
                        sequence_position=None,
                        sequence_label="",
                    )
                )
                imported_count += 1
            except Exception as exc:
                failed.append(f"{source.name}: {exc}")

        self.project_dirty = True
        self._save_session()
        self.analysis_status.configure(
            text=f"Imported {imported_count} photo(s) by {source_label}. Ready for Analyze All."
        )
        self._write_audit(
            "photos_imported",
            {"count": imported_count, "source": source_label},
        )
        self._refresh_all_views(
            select_index=first_new_index if imported_count else self.current_index
        )

        if failed:
            messagebox.showwarning(
                "DamageScope AI",
                f"Imported {imported_count} photo(s).\n\n"
                f"{len(failed)} file(s) could not be imported:\n"
                + "\n".join(failed[:8]),
            )
        elif imported_count:
            messagebox.showinfo(
                "DamageScope AI",
                f"Imported {imported_count} photo(s).\n"
                "The Inspection Sequence remains empty until Analyze All is run.",
            )

    def import_photos(self) -> None:
        files = filedialog.askopenfilenames(
            title="Import Photos",
            filetypes=[
                ("Supported Images", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.heic *.heif"),
                ("JPEG Images", "*.jpg *.jpeg"),
                ("PNG Images", "*.png"),
                ("HEIC Images", "*.heic *.heif"),
                ("All Files", "*.*"),
            ],
        )
        self._import_photo_paths(files, source_label="Import Photos")

    def clear_photos(self) -> None:
        if not self.photos:
            return
        confirmed = messagebox.askyesno(
            "DamageScope AI",
            "Clear the current photo list?\n\n"
            "Imported image files will remain in the project folder.",
        )
        if not confirmed:
            return
        self.photos.clear()
        self.project_dirty = True
        self._save_session()
        self._refresh_all_views(select_index=0)
        self.analysis_status.configure(text="Photo list cleared.")


    def _render_report_image(self, photo: PhotoRecord, output_path: Path) -> Path:
        # Each report image uses the same approved assessment-card standard seen
        # in the center review screen. Generate PDF continues placing two per page.
        image = self._create_assessment_card(photo, (1600, 1000))
        image.save(output_path, format="JPEG", quality=94)
        return output_path

    def _wrap_report_text(self, text: str, max_chars: int = 92) -> list[str]:
        lines: list[str] = []
        for paragraph in (text or "").splitlines() or [""]:
            wrapped = textwrap.wrap(paragraph, width=max_chars) or [""]
            lines.extend(wrapped)
        return lines

    def _batch_readiness_summary(self) -> dict:
        real_photos = [photo for photo in self.photos if not self._is_demo_photo(photo)]
        total = len(real_photos)
        analyzed = sum(
            1 for photo in real_photos
            if photo.damage_type not in {"Not Analyzed", ""}
        )
        classified = sum(
            1 for photo in real_photos
            if photo.category not in {"Unreviewed", ""}
            and photo.component not in {"Not Classified", ""}
        )
        annotated = sum(1 for photo in real_photos if bool(photo.annotations))
        report_photos = sum(1 for photo in real_photos if photo.include)
        return {
            "total": total,
            "analyzed": analyzed,
            "classified": classified,
            "annotated": annotated,
            "report_photos": report_photos,
        }

    def generate_pdf(self) -> None:
        readiness = self._batch_readiness_summary()
        incomplete = (
            readiness["analyzed"] < readiness["total"]
            or readiness["classified"] < readiness["total"]
        )
        if readiness["total"] and incomplete:
            proceed = messagebox.askyesno(
                "DamageScope AI",
                (
                    "The inspection is not fully ready for reporting.\n\n"
                    f"Photos: {readiness['total']}\n"
                    f"Analyzed: {readiness['analyzed']}\n"
                    f"Classified: {readiness['classified']}\n"
                    f"Annotated: {readiness['annotated']}\n\n"
                    "Generate the report anyway?"
                ),
            )
            if not proceed:
                return

        report_photos = [photo for photo in self.photos if photo.include]
        if not report_photos:
            messagebox.showwarning(
                "DamageScope AI",
                "There are no photos marked Include in Report.",
            )
            return

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfgen import canvas
        except ImportError:
            messagebox.showerror(
                "DamageScope AI",
                "ReportLab is required.\nRun: py -m pip install reportlab",
            )
            return

        project_name = (
            self.project_metadata.get("project_name", "DamageScope Inspection").strip()
            or "DamageScope Inspection"
        )
        default_name = project_name.replace(" ", "_") + "_Photo_Report.pdf"
        selected = filedialog.asksaveasfilename(
            title="Generate DamageScope PDF Report",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF Report", "*.pdf")],
        )
        if not selected:
            return

        output_pdf = Path(selected)
        temp_dir = CLAIMS_REPORTS_DIR / "_report_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        page_width, page_height = letter
        margin = 36
        header_height = 58
        footer_height = 24
        usable_height = page_height - (margin * 2) - header_height - footer_height
        slot_height = usable_height / 2
        content_width = page_width - (margin * 2)

        pdf = canvas.Canvas(str(output_pdf), pagesize=letter)
        pdf.setTitle(f"{project_name} - DamageScope AI Photo Report")
        pdf.setAuthor("DamageScope AI")

        generated_images: list[Path] = []

        try:
            for page_start in range(0, len(report_photos), 2):
                page_photos = report_photos[page_start:page_start + 2]

                pdf.setFillColorRGB(0.03, 0.10, 0.17)
                pdf.rect(0, page_height - header_height, page_width, header_height, fill=1, stroke=0)
                pdf.setFillColorRGB(1, 1, 1)
                pdf.setFont("Helvetica-Bold", 16)
                pdf.drawString(margin, page_height - 27, "DamageScope AI")
                pdf.setFont("Helvetica", 9)
                pdf.drawRightString(
                    page_width - margin,
                    page_height - 24,
                    project_name,
                )
                claim_number = self.project_metadata.get("claim_number", "")
                address = self.project_metadata.get("property_address", "")
                meta_line = " | ".join(value for value in [claim_number, address] if value)
                if meta_line:
                    pdf.drawRightString(
                        page_width - margin,
                        page_height - 39,
                        meta_line[:100],
                    )

                for slot_index, photo in enumerate(page_photos):
                    slot_top = page_height - header_height - margin - (slot_index * slot_height)
                    slot_bottom = slot_top - slot_height + 8

                    title_y = slot_top - 2
                    pdf.setFillColorRGB(0.05, 0.12, 0.19)
                    pdf.setFont("Helvetica-Bold", 10)
                    pdf.drawString(margin, title_y, photo.title[:80])

                    finding = f"{photo.category} | {photo.component} | {photo.damage_type}"
                    pdf.setFont("Helvetica", 8)
                    pdf.setFillColorRGB(0.20, 0.30, 0.38)
                    pdf.drawRightString(page_width - margin, title_y, finding[:95])

                    text_area_height = 50
                    image_top = title_y - 10
                    image_bottom = slot_bottom + text_area_height
                    max_image_height = max(80, image_top - image_bottom)

                    temp_image = temp_dir / f"report_{page_start + slot_index + 1}.jpg"
                    self._render_report_image(photo, temp_image)
                    generated_images.append(temp_image)

                    with Image.open(temp_image) as image:
                        img_width, img_height = image.size

                    scale = min(content_width / img_width, max_image_height / img_height)
                    draw_width = img_width * scale
                    draw_height = img_height * scale
                    draw_x = margin + ((content_width - draw_width) / 2)
                    draw_y = image_bottom + ((max_image_height - draw_height) / 2)

                    pdf.setStrokeColorRGB(0.45, 0.50, 0.55)
                    pdf.rect(draw_x - 1, draw_y - 1, draw_width + 2, draw_height + 2, fill=0, stroke=1)
                    pdf.drawImage(
                        ImageReader(str(temp_image)),
                        draw_x,
                        draw_y,
                        width=draw_width,
                        height=draw_height,
                        preserveAspectRatio=True,
                        mask="auto",
                    )

                    observation = photo.observation or ""
                    if observation.strip():
                        observation_lines = self._wrap_report_text(observation, max_chars=100)[:4]
                        text_y = slot_bottom + 38
                        pdf.setFillColorRGB(0.05, 0.10, 0.15)
                        pdf.setFont("Helvetica-Bold", 8)
                        pdf.drawString(margin, text_y, "Observation / Evidence:")
                        pdf.setFont("Helvetica", 7.5)
                        line_y = text_y - 11
                        for line in observation_lines:
                            pdf.drawString(margin + 8, line_y, line[:115])
                            line_y -= 9

                    pdf.setStrokeColorRGB(0.80, 0.82, 0.84)
                    pdf.line(margin, slot_bottom, page_width - margin, slot_bottom)

                pdf.setFont("Helvetica", 7)
                pdf.setFillColorRGB(0.35, 0.40, 0.45)
                page_number = (page_start // 2) + 1
                pdf.drawString(margin, 18, f"Generated by DamageScope AI | Page {page_number}")
                pdf.drawRightString(
                    page_width - margin,
                    18,
                    f"Report photos: {len(report_photos)}",
                )
                pdf.showPage()

            pdf.save()
        except Exception as exc:
            try:
                pdf.save()
            except Exception:
                pass
            messagebox.showerror(
                "DamageScope AI",
                f"PDF generation failed:\n{exc}",
            )
            return
        finally:
            for temp_image in generated_images:
                try:
                    temp_image.unlink()
                except OSError:
                    pass

        self.analysis_status.configure(text="PDF report generated.")
        self._write_audit("pdf_generated", {"output": str(output_pdf), "photos": len(report_photos)})
        messagebox.showinfo(
            "DamageScope AI",
            f"PDF report generated successfully:\n{output_pdf}",
        )


    def _sync_manifest(self) -> dict:
        project_id = self.project_metadata.get("project_id")
        if not project_id:
            project_id = str(uuid.uuid4())
            self.project_metadata["project_id"] = project_id

        revision = int(self.project_metadata.get("revision", 0)) + 1
        self.project_metadata["revision"] = revision
        self.project_metadata["last_modified"] = datetime.now().isoformat(timespec="seconds")

        return {
            "format": "DamageScope Sync Package",
            "sync_version": "1.0",
            "package_id": str(uuid.uuid4()),
            "project_id": project_id,
            "revision": revision,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": "desktop",
            "app_version": "0.3.1",
            "project_name": self.project_metadata.get("project_name", "Untitled Inspection"),
            "photo_count": len(self.photos),
        }

    def export_sync_package(self) -> None:
        if not self.photos and not self.project_metadata:
            messagebox.showwarning("DamageScope AI", "There is no active project to export.")
            return

        if self.current_project_file == SESSION_FILE:
            if not self.save_project_as():
                return
        else:
            self._save_session(show_status=False)

        manifest = self._sync_manifest()
        safe_name = (
            self.project_metadata.get("project_name", "DamageScope_Project")
            .strip()
            .replace(" ", "_")
            or "DamageScope_Project"
        )
        default_name = f"{safe_name}_R{manifest['revision']:03d}.dscope-sync"

        selected = filedialog.asksaveasfilename(
            title="Export Desktop / Mobile Sync Package",
            defaultextension=".dscope-sync",
            initialfile=default_name,
            filetypes=[("DamageScope Sync Package", "*.dscope-sync")],
        )
        if not selected:
            return

        destination = Path(selected)
        temp_dir = APP_DIR / "_sync_temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True)

        project_copy = temp_dir / "project.dscope"
        project_copy.write_text(
            json.dumps(self._project_payload(), indent=2),
            encoding="utf-8",
        )
        (temp_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        photos_dir = temp_dir / "photos"
        photos_dir.mkdir()
        copied = 0
        for photo in self.photos:
            source = photo.image_path
            if not source.exists():
                continue
            target = photos_dir / photo.filename
            counter = 2
            while target.exists():
                target = photos_dir / f"{Path(photo.filename).stem}_{counter}{Path(photo.filename).suffix}"
                counter += 1
            shutil.copy2(source, target)
            copied += 1

        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(temp_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(temp_dir).as_posix())

        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.copy2(destination, SYNC_OUTBOX_DIR / destination.name)

        self.project_dirty = True
        self._save_session(show_status=False)
        self.analysis_status.configure(text=f"Sync package exported â€” revision {manifest['revision']}.")
        self._write_audit(
            "sync_exported",
            {
                "package": str(destination),
                "revision": manifest["revision"],
                "photos": copied,
            },
        )
        messagebox.showinfo(
            "DamageScope AI",
            f"Sync package exported successfully:\n{destination}\n\n"
            f"Revision: {manifest['revision']}\nPhotos: {copied}",
        )

    def import_sync_package(self) -> None:
        selected = filedialog.askopenfilename(
            title="Import Desktop / Mobile Sync Package",
            filetypes=[("DamageScope Sync Package", "*.dscope-sync"), ("All Files", "*.*")],
        )
        if not selected:
            return

        package_path = Path(selected)
        extract_dir = SYNC_INBOX_DIR / f"{package_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                archive.extractall(extract_dir)

            manifest_path = extract_dir / "manifest.json"
            project_path = extract_dir / "project.dscope"
            if not manifest_path.exists() or not project_path.exists():
                raise ValueError("The package is missing manifest.json or project.dscope.")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload = json.loads(project_path.read_text(encoding="utf-8"))

            incoming_project_id = manifest.get("project_id", "")
            incoming_revision = int(manifest.get("revision", 0))
            current_project_id = self.project_metadata.get("project_id", "")
            current_revision = int(self.project_metadata.get("revision", 0))

            if current_project_id and incoming_project_id == current_project_id and incoming_revision <= current_revision:
                proceed = messagebox.askyesno(
                    "DamageScope AI",
                    f"This package is revision {incoming_revision}, while the open project is "
                    f"revision {current_revision}.\n\nImport anyway?",
                )
                if not proceed:
                    return

            if self.project_dirty and not self._confirm_discard_or_save():
                return

            imported_photos: list[PhotoRecord] = []
            photos_dir = extract_dir / "photos"
            target_dir = IMPORTED_DIR / f"sync_{incoming_project_id[:8] or 'project'}"
            target_dir.mkdir(parents=True, exist_ok=True)

            for item in payload.get("photos", []):
                record = PhotoRecord(**item)
                source = photos_dir / record.filename
                if source.exists():
                    target = target_dir / record.filename
                    if target.exists():
                        target = target_dir / f"{target.stem}_{uuid.uuid4().hex[:6]}{target.suffix}"
                    shutil.copy2(source, target)
                    record.filename = target.name
                    record.source_path = str(target)
                    record.imported = True
                imported_photos.append(record)

            self.project_metadata = payload.get("project", {})
            self.project_metadata["project_id"] = incoming_project_id
            self.project_metadata["revision"] = incoming_revision
            self.photos = imported_photos
            self.current_index = 0
            self.current_project_file = SESSION_FILE
            self.project_dirty = True

            self._refresh_all_views(select_index=0)
            self._update_project_identity()
            self._save_session(show_status=False)
            self.analysis_status.configure(
                text=f"Sync package imported â€” revision {incoming_revision}."
            )
            self._write_audit(
                "sync_imported",
                {
                    "package": str(package_path),
                    "revision": incoming_revision,
                    "source": manifest.get("source", "unknown"),
                },
            )
            messagebox.showinfo(
                "DamageScope AI",
                f"Sync package imported successfully.\n\n"
                f"Project: {manifest.get('project_name', 'Unknown')}\n"
                f"Revision: {incoming_revision}\n"
                f"Photos: {len(imported_photos)}",
            )
        except Exception as exc:
            messagebox.showerror("DamageScope AI", f"Could not import sync package:\n{exc}")

    def open_sync_folders(self) -> None:
        try:
            import os
            os.startfile(SYNC_OUTBOX_DIR)
        except Exception:
            messagebox.showinfo(
                "DamageScope AI",
                f"Sync Outbox:\n{SYNC_OUTBOX_DIR}\n\nSync Inbox:\n{SYNC_INBOX_DIR}",
            )

    def open_sync_manager(self) -> None:
        window = tk.Toplevel(self)
        window.title("DamageScope AI â€” Desktop / Mobile Sync")
        window.geometry("620x430")
        window.configure(bg=BG)
        window.transient(self)
        window.grab_set()

        tk.Label(
            window,
            text="Desktop / Mobile Synchronization",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 17),
        ).pack(anchor="w", padx=24, pady=(20, 6))

        tk.Label(
            window,
            text="Package-based synchronization is active now. Direct device-to-device "
                 "transport will connect to the same package format when the mobile app is ready.",
            bg=BG,
            fg=MUTED,
            justify="left",
            wraplength=560,
        ).pack(anchor="w", padx=24, pady=(0, 14))

        panel = tk.Frame(window, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        panel.pack(fill="both", expand=True, padx=24, pady=(0, 18))

        project_id = self.project_metadata.get("project_id", "Not assigned")
        revision = self.project_metadata.get("revision", 0)
        details = (
            f"Project: {self.project_metadata.get('project_name', 'Untitled Inspection')}\n"
            f"Project ID: {project_id}\n"
            f"Current revision: {revision}\n"
            f"Photos: {len(self.photos)}\n\n"
            f"Outbox: {SYNC_OUTBOX_DIR}\n"
            f"Inbox: {SYNC_INBOX_DIR}"
        )
        tk.Label(
            panel,
            text=details,
            bg=PANEL,
            fg=TEXT,
            justify="left",
            anchor="nw",
            font=("Segoe UI", 10),
        ).pack(fill="both", expand=True, padx=18, pady=18)

        buttons = tk.Frame(window, bg=BG)
        buttons.pack(fill="x", padx=24, pady=(0, 20))
        self._button(buttons, "Export Package", lambda: [window.destroy(), self.export_sync_package()]).pack(side="right")
        self._button(buttons, "Import Package", lambda: [window.destroy(), self.import_sync_package()]).pack(side="right", padx=(0, 8))
        self._button(buttons, "Close", window.destroy).pack(side="right", padx=(0, 8))

    def stub(self) -> None:
        messagebox.showinfo(
            "DamageScope AI",
            "This framework module is ready for the next integration sprint.",
        )


if __name__ == "__main__":
    app = DamageScopeApp()
    app.mainloop()


