from __future__ import annotations

import os
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from appimage import AppImageEntry, AppImageError, integrate_appimage, launch_appimage, scan_appimages
from downloads import DownloadManager, DownloadTask, format_size, format_speed
from gtk_style import THEMES, install_css
from settings import load_settings, save_settings


class AppHubApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.evans.AppHub")
        self.window: Gtk.ApplicationWindow | None = None
        self.css_provider: Gtk.CssProvider | None = None

        self.settings = load_settings()
        self.theme_name = self.settings.get("theme", "dark")
        if self.theme_name not in THEMES:
            self.theme_name = "dark"

        self.downloads = DownloadManager()
        self.appimage_entries: list[AppImageEntry] = []
        self.download_rows: dict[str, Gtk.ListBoxRow] = {}
        self.app_rows: dict[str, Gtk.ListBoxRow] = {}

        self.download_url_entry: Gtk.Entry | None = None
        self.download_name_entry: Gtk.Entry | None = None
        self.scan_dirs_entry: Gtk.Entry | None = None
        self.status_label: Gtk.Label | None = None
        self.theme_dropdown: Gtk.DropDown | None = None
        self.download_list: Gtk.ListBox | None = None
        self.app_list: Gtk.ListBox | None = None

    def do_activate(self):
        if self.window is None:
            self._build_ui()
            self.refresh_appimages()
            GLib.timeout_add(300, self._poll_downloads)
        self.window.present()

    def _build_ui(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("App Hub")
        self.window.set_default_size(1120, 720)
        self.window.set_size_request(980, 620)

        self.css_provider = install_css(self.window, self.theme_name)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(12)
        root.set_margin_end(12)
        self.window.set_child(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.add_css_class("toolbar")
        header.add_css_class("section")
        header.set_margin_bottom(2)
        header.set_hexpand(True)
        header.set_margin_top(2)
        header.set_margin_bottom(6)
        header.set_margin_start(2)
        header.set_margin_end(2)
        root.append(header)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        titles.set_hexpand(True)
        header.append(titles)

        title = Gtk.Label(label="App Hub")
        title.set_xalign(0.0)
        title.add_css_class("title-1")
        titles.append(title)

        subtitle = Gtk.Label(label="GTK4 download manager and AppImage launcher")
        subtitle.set_xalign(0.0)
        subtitle.add_css_class("dim-label")
        titles.append(subtitle)

        theme_model = Gtk.StringList.new(["dark", "light"])
        self.theme_dropdown = Gtk.DropDown(model=theme_model)
        self.theme_dropdown.set_valign(Gtk.Align.CENTER)
        self.theme_dropdown.set_selected(0 if self.theme_name == "dark" else 1)
        self.theme_dropdown.connect("notify::selected", self._on_theme_changed)
        header.append(self.theme_dropdown)

        notebook = Gtk.Notebook()
        notebook.set_hexpand(True)
        notebook.set_vexpand(True)
        root.append(notebook)

        notebook.append_page(self._build_download_tab(), Gtk.Label(label="Downloads"))
        notebook.append_page(self._build_appimage_tab(), Gtk.Label(label="AppImages"))

        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_xalign(0.0)
        self.status_label.add_css_class("dim-label")
        root.append(self.status_label)

    def _build_download_tab(self) -> Gtk.Widget:
        tab = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        top = Gtk.Grid(column_spacing=10, row_spacing=8)
        top.add_css_class("section")
        top.set_margin_top(2)
        top.set_margin_bottom(2)
        top.set_margin_start(2)
        top.set_margin_end(2)
        tab.append(top)

        url_label = Gtk.Label(label="URL")
        url_label.set_xalign(0.0)
        top.attach(url_label, 0, 0, 1, 1)
        self.download_url_entry = Gtk.Entry()
        self.download_url_entry.set_hexpand(True)
        top.attach(self.download_url_entry, 1, 0, 1, 1)

        name_label = Gtk.Label(label="Filename")
        name_label.set_xalign(0.0)
        top.attach(name_label, 2, 0, 1, 1)
        self.download_name_entry = Gtk.Entry()
        self.download_name_entry.set_hexpand(True)
        top.attach(self.download_name_entry, 3, 0, 1, 1)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.add_css_class("section")
        tab.append(actions)

        for label, callback, primary in (
            ("Add Download", self.add_download, True),
            ("Pause", self.pause_download, False),
            ("Resume", self.resume_download, False),
            ("Cancel", self.cancel_download, False),
            ("Remove", self.remove_download, False),
        ):
            btn = Gtk.Button(label=label)
            btn.connect("clicked", callback)
            btn.add_css_class("pill" if primary else "flat-pill")
            actions.append(btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        actions.append(spacer)

        open_btn = Gtk.Button(label="Open Folder")
        open_btn.add_css_class("flat-pill")
        open_btn.connect("clicked", self.open_download_folder)
        actions.append(open_btn)

        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.add_css_class("card")
        tab.append(scroller)

        self.download_list = Gtk.ListBox()
        self.download_list.add_css_class("boxed-list")
        self.download_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller.set_child(self.download_list)
        return tab

    def _build_appimage_tab(self) -> Gtk.Widget:
        tab = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        top = Gtk.Grid(column_spacing=10, row_spacing=8)
        top.add_css_class("section")
        top.set_margin_top(2)
        top.set_margin_bottom(2)
        top.set_margin_start(2)
        top.set_margin_end(2)
        tab.append(top)

        scan_label = Gtk.Label(label="Scan Dirs (comma-separated)")
        scan_label.set_xalign(0.0)
        top.attach(scan_label, 0, 0, 1, 1)

        self.scan_dirs_entry = Gtk.Entry()
        self.scan_dirs_entry.set_hexpand(True)
        self.scan_dirs_entry.set_text(", ".join(self.settings.get("appimage_scan_dirs", [])))
        top.attach(self.scan_dirs_entry, 1, 0, 1, 1)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.add_css_class("section")
        tab.append(actions)

        for label, callback, primary in (
            ("Refresh List", self.refresh_appimages, True),
            ("Launch", self.launch_selected_appimage, False),
            ("Integrate", self.integrate_selected_appimage, False),
        ):
            btn = Gtk.Button(label=label)
            btn.connect("clicked", callback)
            btn.add_css_class("pill" if primary else "flat-pill")
            actions.append(btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        actions.append(spacer)

        open_btn = Gtk.Button(label="Open Apps Dir")
        open_btn.add_css_class("flat-pill")
        open_btn.connect("clicked", self.open_apps_dir)
        actions.append(open_btn)

        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.add_css_class("card")
        tab.append(scroller)

        self.app_list = Gtk.ListBox()
        self.app_list.add_css_class("boxed-list")
        self.app_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller.set_child(self.app_list)
        return tab

    def _on_theme_changed(self, _dropdown: Gtk.DropDown, _param: object):
        if self.theme_dropdown is None:
            return
        selected = self.theme_dropdown.get_selected_item()
        if selected is None:
            return
        theme_name = selected.get_string()
        self.apply_theme(theme_name)

    def apply_theme(self, theme_name: str):
        if theme_name not in THEMES:
            theme_name = "dark"
        self.theme_name = theme_name
        self.settings["theme"] = theme_name
        save_settings(self.settings)
        if self.window is None:
            return
        self.css_provider = install_css(self.window, theme_name)

    def add_download(self, _button: Gtk.Button | None = None):
        if self.download_url_entry is None or self.download_name_entry is None:
            return
        url = self.download_url_entry.get_text().strip()
        name = self.download_name_entry.get_text().strip() or None
        if not url:
            self._show_message("Missing URL", "Please enter a download URL.")
            return

        download_dir = Path(self.settings.get("download_dir", str(Path.home() / "Downloads"))).expanduser()
        task = self.downloads.add(url, download_dir, name, on_update=lambda _task: None)
        self._set_status(f"Started {task.target_path.name}")
        self.download_url_entry.set_text("")
        self.download_name_entry.set_text("")

    def _selected_download_id(self) -> str | None:
        if self.download_list is None:
            return None
        row = self.download_list.get_selected_row()
        if row is None:
            return None
        return row.get_name()

    def pause_download(self, _button: Gtk.Button | None = None):
        tid = self._selected_download_id()
        task = self.downloads.get(tid) if tid else None
        if task:
            task.pause()

    def resume_download(self, _button: Gtk.Button | None = None):
        tid = self._selected_download_id()
        task = self.downloads.get(tid) if tid else None
        if task:
            task.resume()

    def cancel_download(self, _button: Gtk.Button | None = None):
        tid = self._selected_download_id()
        task = self.downloads.get(tid) if tid else None
        if task:
            task.cancel()

    def remove_download(self, _button: Gtk.Button | None = None):
        tid = self._selected_download_id()
        if tid:
            self.downloads.remove(tid)

    def open_download_folder(self, _button: Gtk.Button | None = None):
        download_dir = Path(self.settings.get("download_dir", str(Path.home() / "Downloads"))).expanduser()
        download_dir.mkdir(parents=True, exist_ok=True)
        self._open_path(download_dir)

    def _poll_downloads(self) -> bool:
        tasks = self.downloads.list_tasks()
        current_ids = set(self.download_rows)

        for task in tasks:
            if task.task_id not in self.download_rows:
                row = self._make_download_row(task)
                self.download_rows[task.task_id] = row
                if self.download_list is not None:
                    self.download_list.append(row)
            self._update_download_row(self.download_rows[task.task_id], task)

        task_ids = {task.task_id for task in tasks}
        for orphan in current_ids - task_ids:
            row = self.download_rows.pop(orphan)
            if self.download_list is not None:
                self.download_list.remove(row)

        return True

    def _make_download_row(self, task: DownloadTask) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_name(task.task_id)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_margin_top(6)
        outer.set_margin_bottom(6)
        outer.set_margin_start(8)
        outer.set_margin_end(8)
        row.set_child(outer)

        title = Gtk.Label()
        title.set_xalign(0.0)
        title.add_css_class("title-4")
        outer.append(title)

        meta = Gtk.Label()
        meta.set_xalign(0.0)
        meta.add_css_class("dim-label")
        outer.append(meta)

        detail = Gtk.Label()
        detail.set_xalign(0.0)
        detail.set_wrap(True)
        outer.append(detail)

        row._title_label = title  # type: ignore[attr-defined]
        row._meta_label = meta  # type: ignore[attr-defined]
        row._detail_label = detail  # type: ignore[attr-defined]
        self._update_download_row(row, task)
        return row

    def _update_download_row(self, row: Gtk.ListBoxRow, task: DownloadTask):
        progress = "-"
        if task.total_bytes and task.total_bytes > 0:
            pct = (task.downloaded_bytes / task.total_bytes) * 100
            progress = f"{pct:.1f}%"
        size = f"{format_size(task.downloaded_bytes)} / {format_size(task.total_bytes)}"
        row._title_label.set_text(task.target_path.name)  # type: ignore[attr-defined]
        row._meta_label.set_text(f"Status: {task.status}   Progress: {progress}   Speed: {format_speed(task.speed_bps)}")  # type: ignore[attr-defined]
        row._detail_label.set_text(f"Saved to {task.target_path}   Size: {size}")  # type: ignore[attr-defined]

    def _scan_dirs(self) -> list[str]:
        raw = self.scan_dirs_entry.get_text().strip() if self.scan_dirs_entry is not None else ""
        dirs = [item.strip() for item in raw.split(",") if item.strip()]
        if not dirs:
            dirs = [str(Path.home() / "Applications")]
        self.settings["appimage_scan_dirs"] = dirs
        save_settings(self.settings)
        return dirs

    def refresh_appimages(self, _button: Gtk.Button | None = None):
        dirs = self._scan_dirs()
        self.appimage_entries = scan_appimages(dirs)
        if self.app_list is None:
            return
        for row in list(self.app_rows.values()):
            self.app_list.remove(row)
        self.app_rows.clear()

        for entry in self.appimage_entries:
            row = self._make_appimage_row(entry)
            self.app_rows[str(entry.path)] = row
            self.app_list.append(row)

        self._set_status(f"Found {len(self.appimage_entries)} AppImage files")

    def _make_appimage_row(self, entry: AppImageEntry) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_name(str(entry.path))

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_margin_top(6)
        outer.set_margin_bottom(6)
        outer.set_margin_start(8)
        outer.set_margin_end(8)
        row.set_child(outer)

        title = Gtk.Label(label=entry.name)
        title.set_xalign(0.0)
        outer.append(title)

        meta = Gtk.Label(label=f"Path: {entry.path}")
        meta.set_xalign(0.0)
        meta.set_wrap(True)
        meta.add_css_class("dim-label")
        outer.append(meta)

        detail = Gtk.Label(label=f"Size: {format_size(entry.size)}   Executable: {'yes' if entry.executable else 'no'}")
        detail.set_xalign(0.0)
        outer.append(detail)
        return row

    def _selected_appimage_path(self) -> Path | None:
        if self.app_list is None:
            return None
        row = self.app_list.get_selected_row()
        if row is None:
            return None
        return Path(row.get_name())

    def launch_selected_appimage(self, _button: Gtk.Button | None = None):
        path = self._selected_appimage_path()
        if path is None:
            return
        try:
            launch_appimage(path)
            self._set_status(f"Launched {path.name}")
        except AppImageError as exc:
            self._show_message("Launch Failed", str(exc))

    def integrate_selected_appimage(self, _button: Gtk.Button | None = None):
        path = self._selected_appimage_path()
        if path is None:
            return
        managed_dir = Path(self.settings.get("managed_appimage_dir", str(Path.home() / "Applications"))).expanduser()
        try:
            target = integrate_appimage(path, managed_dir)
            self._set_status(f"Integrated {target.name} into {managed_dir}")
            self.refresh_appimages()
        except AppImageError as exc:
            self._show_message("Integrate Failed", str(exc))

    def open_apps_dir(self, _button: Gtk.Button | None = None):
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
            self._show_message("Open Failed", str(exc))

    def _show_message(self, title: str, body: str):
        if self.window is None:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            text=title,
            secondary_text=body,
        )
        dialog.connect("response", lambda d, _r: d.close())
        dialog.present()

    def _set_status(self, text: str):
        if self.status_label is not None:
            self.status_label.set_text(text)
