import os
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from appimage import AppImageError, integrate_appimage, launch_appimage, scan_appimages
from downloads import DownloadManager, DownloadTask, format_size, format_speed
from settings import load_settings, save_settings

THEMES = {
    "dark": {
        "root": "#0f172a",
        "panel": "#111827",
        "card": "#0b1220",
        "line": "#1f2937",
        "text": "#e2e8f0",
        "muted": "#94a3b8",
        "entry": "#020617",
        "entry_fg": "#dbeafe",
        "accent": "#2563eb",
        "accent_hover": "#3b82f6",
        "accent_press": "#1d4ed8",
        "accent_text": "#eff6ff",
        "select": "#2563eb",
    },
    "light": {
        "root": "#f1f5f9",
        "panel": "#ffffff",
        "card": "#f8fafc",
        "line": "#dbe3ee",
        "text": "#0f172a",
        "muted": "#475569",
        "entry": "#ffffff",
        "entry_fg": "#0f172a",
        "accent": "#2563eb",
        "accent_hover": "#3b82f6",
        "accent_press": "#1d4ed8",
        "accent_text": "#eff6ff",
        "select": "#93c5fd",
    },
}


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=120, height=34, radius=14):
        super().__init__(parent, width=width, height=height, bd=0, highlightthickness=0, relief="flat", cursor="hand2")
        self.command = command
        self.text = text
        self.width = width
        self.height = height
        self.radius = radius
        self.enabled = True
        self.pressed = False
        self.colors = {
            "bg": "#2563eb",
            "hover": "#3b82f6",
            "press": "#1d4ed8",
            "fg": "#eff6ff",
            "container": "#0f172a",
            "disabled": "#475569",
        }
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def configure_theme(self, palette, container_bg):
        self.colors.update(
            {
                "bg": palette["accent"],
                "hover": palette["accent_hover"],
                "press": palette["accent_press"],
                "fg": palette["accent_text"],
                "container": container_bg,
            }
        )
        self._draw()

    def _rounded(self, color):
        w, h, r = self.width, self.height, self.radius
        self.create_arc(0, 0, 2 * r, 2 * r, start=90, extent=90, fill=color, outline=color)
        self.create_arc(w - 2 * r, 0, w, 2 * r, start=0, extent=90, fill=color, outline=color)
        self.create_arc(0, h - 2 * r, 2 * r, h, start=180, extent=90, fill=color, outline=color)
        self.create_arc(w - 2 * r, h - 2 * r, w, h, start=270, extent=90, fill=color, outline=color)
        self.create_rectangle(r, 0, w - r, h, fill=color, outline=color)
        self.create_rectangle(0, r, w, h - r, fill=color, outline=color)

    def _draw(self):
        self.delete("all")
        self.configure(bg=self.colors["container"])
        if not self.enabled:
            color = self.colors["disabled"]
        elif self.pressed:
            color = self.colors["press"]
        else:
            color = self.colors["bg"]
        self._rounded(color)
        self.create_text(self.width // 2, self.height // 2, text=self.text, fill=self.colors["fg"], font=("Adwaita Sans", 10, "bold"))

    def _on_enter(self, _event):
        if self.enabled and not self.pressed:
            self.delete("all")
            self.configure(bg=self.colors["container"])
            self._rounded(self.colors["hover"])
            self.create_text(self.width // 2, self.height // 2, text=self.text, fill=self.colors["fg"], font=("Adwaita Sans", 10, "bold"))

    def _on_leave(self, _event):
        self.pressed = False
        self._draw()

    def _on_press(self, _event):
        self.pressed = True
        self._draw()

    def _on_release(self, _event):
        run = self.pressed
        self.pressed = False
        self._draw()
        if run:
            self.command()


class AppHub:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("App Hub")
        self.root.geometry("1120x720")
        self.root.minsize(980, 620)

        self.settings = load_settings()
        self.theme_var = tk.StringVar(value=self.settings.get("theme", "dark"))

        self.downloads = DownloadManager()
        self.download_url_var = tk.StringVar()
        self.download_name_var = tk.StringVar()

        self.scan_dirs_var = tk.StringVar(value=", ".join(self.settings.get("appimage_scan_dirs", [])))

        self._build_ui()
        self.apply_theme(self.theme_var.get())
        self.refresh_appimages()
        self._poll_downloads()

    def _build_ui(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = tk.Frame(self.root, padx=14, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        self.title = tk.Label(header, text="App Hub", font=("Adwaita Sans", 22, "bold"))
        self.title.grid(row=0, column=0, sticky="w")
        self.subtitle = tk.Label(header, text="Download Manager + AppImage Launcher", font=("Adwaita Sans", 10))
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.theme_box = ttk.Combobox(header, textvariable=self.theme_var, values=("dark", "light"), state="readonly", width=10, style="App.TCombobox")
        self.theme_box.grid(row=0, column=2, rowspan=2, sticky="e")
        self.theme_box.bind("<<ComboboxSelected>>", self._on_theme_change)

        self.tabs = ttk.Notebook(self.root)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))

        self._build_download_tab()
        self._build_appimage_tab()

        self.status_var = tk.StringVar(value="Ready")
        self.status = tk.Label(self.root, textvariable=self.status_var, anchor="w", padx=14, pady=8, font=("Adwaita Sans", 10))
        self.status.grid(row=2, column=0, sticky="ew")

    def _build_download_tab(self):
        tab = tk.Frame(self.tabs)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        self.tabs.add(tab, text="Downloads")

        top = tk.Frame(tab, padx=12, pady=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        tk.Label(top, text="URL", font=("Adwaita Sans", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.url_entry = ttk.Entry(top, textvariable=self.download_url_var, style="App.TEntry")
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 10))

        tk.Label(top, text="Filename", font=("Adwaita Sans", 10, "bold")).grid(row=0, column=2, sticky="w")
        self.name_entry = ttk.Entry(top, textvariable=self.download_name_var, style="App.TEntry")
        self.name_entry.grid(row=0, column=3, sticky="ew", padx=(8, 0))

        actions = tk.Frame(tab, padx=12, pady=6)
        actions.grid(row=1, column=0, sticky="ew")

        self.btn_add = RoundedButton(actions, "Add Download", self.add_download, width=118)
        self.btn_add.pack(side="left")
        self.btn_pause = RoundedButton(actions, "Pause", self.pause_download, width=88)
        self.btn_pause.pack(side="left", padx=6)
        self.btn_resume = RoundedButton(actions, "Resume", self.resume_download, width=88)
        self.btn_resume.pack(side="left", padx=6)
        self.btn_cancel = RoundedButton(actions, "Cancel", self.cancel_download, width=88)
        self.btn_cancel.pack(side="left", padx=6)
        self.btn_remove = RoundedButton(actions, "Remove", self.remove_download, width=88)
        self.btn_remove.pack(side="left", padx=6)
        self.btn_open_dl = RoundedButton(actions, "Open Folder", self.open_download_folder, width=112)
        self.btn_open_dl.pack(side="right")

        table_frame = tk.Frame(tab, padx=12, pady=6)
        table_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.download_tree = ttk.Treeview(
            table_frame,
            columns=("name", "status", "progress", "speed", "size"),
            show="headings",
            style="App.Treeview",
        )
        for col, title, width in (
            ("name", "File", 360),
            ("status", "Status", 110),
            ("progress", "Progress", 130),
            ("speed", "Speed", 120),
            ("size", "Size", 170),
        ):
            self.download_tree.heading(col, text=title)
            self.download_tree.column(col, width=width, anchor="w")
        self.download_tree.grid(row=0, column=0, sticky="nsew")

        s = ttk.Scrollbar(table_frame, orient="vertical", command=self.download_tree.yview)
        self.download_tree.configure(yscrollcommand=s.set)
        s.grid(row=0, column=1, sticky="ns")

    def _build_appimage_tab(self):
        tab = tk.Frame(self.tabs)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        self.tabs.add(tab, text="AppImages")

        top = tk.Frame(tab, padx=12, pady=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        tk.Label(top, text="Scan Dirs (comma-separated)", font=("Adwaita Sans", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.scan_entry = ttk.Entry(top, textvariable=self.scan_dirs_var, style="App.TEntry")
        self.scan_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        actions = tk.Frame(tab, padx=12, pady=6)
        actions.grid(row=1, column=0, sticky="ew")
        self.btn_scan = RoundedButton(actions, "Refresh List", self.refresh_appimages, width=110)
        self.btn_scan.pack(side="left")
        self.btn_launch = RoundedButton(actions, "Launch", self.launch_selected_appimage, width=88)
        self.btn_launch.pack(side="left", padx=6)
        self.btn_integrate = RoundedButton(actions, "Integrate", self.integrate_selected_appimage, width=95)
        self.btn_integrate.pack(side="left", padx=6)
        self.btn_open_apps = RoundedButton(actions, "Open Apps Dir", self.open_apps_dir, width=112)
        self.btn_open_apps.pack(side="right")

        table_frame = tk.Frame(tab, padx=12, pady=6)
        table_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.app_tree = ttk.Treeview(
            table_frame,
            columns=("name", "path", "size", "executable"),
            show="headings",
            style="App.Treeview",
        )
        for col, title, width in (
            ("name", "App", 220),
            ("path", "Path", 520),
            ("size", "Size", 120),
            ("executable", "Executable", 100),
        ):
            self.app_tree.heading(col, text=title)
            self.app_tree.column(col, width=width, anchor="w")
        self.app_tree.grid(row=0, column=0, sticky="nsew")

        s = ttk.Scrollbar(table_frame, orient="vertical", command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=s.set)
        s.grid(row=0, column=1, sticky="ns")

    def _on_theme_change(self, _event=None):
        self.apply_theme(self.theme_var.get())

    def apply_theme(self, theme_name: str):
        if theme_name not in THEMES:
            theme_name = "dark"
        self.theme_var.set(theme_name)
        self.settings["theme"] = theme_name
        save_settings(self.settings)

        p = THEMES[theme_name]
        self.style.configure(
            "App.TEntry",
            fieldbackground=p["entry"],
            foreground=p["entry_fg"],
            bordercolor=p["line"],
            insertcolor=p["entry_fg"],
            padding=6,
            font=("Adwaita Sans", 10),
        )
        self.style.configure(
            "App.TCombobox",
            fieldbackground=p["entry"],
            foreground=p["entry_fg"],
            bordercolor=p["line"],
            arrowsize=14,
            padding=4,
            font=("Adwaita Sans", 10),
        )
        self.style.map("App.TCombobox", fieldbackground=[("readonly", p["entry"])], foreground=[("readonly", p["entry_fg"])])
        self.style.configure(
            "App.Treeview",
            background=p["card"],
            fieldbackground=p["card"],
            foreground=p["text"],
            rowheight=28,
            borderwidth=0,
            font=("Adwaita Sans", 10),
        )
        self.style.map("App.Treeview", background=[("selected", p["select"])], foreground=[("selected", p["text"])])

        self.root.configure(bg=p["root"])
        self.title.configure(bg=p["root"], fg=p["text"])
        self.subtitle.configure(bg=p["root"], fg=p["muted"])
        self.status.configure(bg=p["root"], fg=p["muted"])

        for btn in (
            self.btn_add,
            self.btn_pause,
            self.btn_resume,
            self.btn_cancel,
            self.btn_remove,
            self.btn_open_dl,
            self.btn_scan,
            self.btn_launch,
            self.btn_integrate,
            self.btn_open_apps,
        ):
            btn.configure_theme(p, btn.master.cget("bg"))

    def add_download(self):
        url = self.download_url_var.get().strip()
        name = self.download_name_var.get().strip() or None
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a download URL.")
            return

        download_dir = Path(self.settings.get("download_dir", str(Path.home() / "Downloads"))).expanduser()

        def on_update(_task: DownloadTask):
            pass

        task = self.downloads.add(url, download_dir, name, on_update=on_update)
        self.status_var.set(f"Started {task.target_path.name}")
        self.download_url_var.set("")
        self.download_name_var.set("")

    def _selected_download_id(self) -> str | None:
        selected = self.download_tree.selection()
        return selected[0] if selected else None

    def pause_download(self):
        tid = self._selected_download_id()
        if not tid:
            return
        task = self.downloads.get(tid)
        if task:
            task.pause()

    def resume_download(self):
        tid = self._selected_download_id()
        if not tid:
            return
        task = self.downloads.get(tid)
        if task:
            task.resume()

    def cancel_download(self):
        tid = self._selected_download_id()
        if not tid:
            return
        task = self.downloads.get(tid)
        if task:
            task.cancel()

    def remove_download(self):
        tid = self._selected_download_id()
        if not tid:
            return
        self.downloads.remove(tid)

    def open_download_folder(self):
        p = Path(self.settings.get("download_dir", str(Path.home() / "Downloads"))).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        self._open_path(p)

    def _poll_downloads(self):
        current_ids = set(self.download_tree.get_children())
        tasks = self.downloads.list_tasks()

        for task in tasks:
            progress = "-"
            if task.total_bytes and task.total_bytes > 0:
                pct = (task.downloaded_bytes / task.total_bytes) * 100
                progress = f"{pct:.1f}%"
            size = f"{format_size(task.downloaded_bytes)} / {format_size(task.total_bytes)}"
            values = (
                task.target_path.name,
                task.status,
                progress,
                format_speed(task.speed_bps),
                size,
            )
            if task.task_id in current_ids:
                self.download_tree.item(task.task_id, values=values)
            else:
                self.download_tree.insert("", "end", iid=task.task_id, values=values)

        task_ids = {t.task_id for t in tasks}
        for orphan in current_ids - task_ids:
            self.download_tree.delete(orphan)

        self.root.after(300, self._poll_downloads)

    def _scan_dirs(self) -> list[str]:
        raw = self.scan_dirs_var.get().strip()
        dirs = [item.strip() for item in raw.split(",") if item.strip()]
        if not dirs:
            dirs = [str(Path.home() / "Applications")]
        self.settings["appimage_scan_dirs"] = dirs
        save_settings(self.settings)
        return dirs

    def refresh_appimages(self):
        dirs = self._scan_dirs()
        entries = scan_appimages(dirs)

        for item in self.app_tree.get_children():
            self.app_tree.delete(item)

        for entry in entries:
            self.app_tree.insert(
                "",
                "end",
                iid=str(entry.path),
                values=(
                    entry.name,
                    str(entry.path),
                    format_size(entry.size),
                    "yes" if entry.executable else "no",
                ),
            )

        self.status_var.set(f"Found {len(entries)} AppImage files")

    def _selected_appimage_path(self) -> Path | None:
        selected = self.app_tree.selection()
        if not selected:
            return None
        return Path(selected[0])

    def launch_selected_appimage(self):
        path = self._selected_appimage_path()
        if not path:
            return
        try:
            launch_appimage(path)
            self.status_var.set(f"Launched {path.name}")
        except AppImageError as exc:
            messagebox.showerror("Launch Failed", str(exc))

    def integrate_selected_appimage(self):
        path = self._selected_appimage_path()
        if not path:
            return

        managed_dir = Path(self.settings.get("managed_appimage_dir", str(Path.home() / "Applications"))).expanduser()
        try:
            target = integrate_appimage(path, managed_dir)
            self.status_var.set(f"Integrated {target.name} into {managed_dir}")
            self.refresh_appimages()
        except AppImageError as exc:
            messagebox.showerror("Integrate Failed", str(exc))

    def open_apps_dir(self):
        managed_dir = Path(self.settings.get("managed_appimage_dir", str(Path.home() / "Applications"))).expanduser()
        managed_dir.mkdir(parents=True, exist_ok=True)
        self._open_path(managed_dir)

    def _open_path(self, path: Path):
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open Failed", str(exc))
