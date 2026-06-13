from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from appimage import AppImageEntry, AppImageError, integrate_appimage, launch_appimage, scan_appimages
from downloads import DownloadManager, DownloadTask, format_size, format_speed
from qt_style import THEMES, apply_qt_theme
from settings import load_settings, save_settings


class AppHubApp(QApplication):
    def __init__(self):
        super().__init__(sys.argv)
        self.setApplicationName("App Hub")
        self.setApplicationDisplayName("App Hub")
        self.setOrganizationName("Evans")

        self.settings = load_settings()
        self.theme_name = self.settings.get("theme", "dark")
        if self.theme_name not in THEMES:
            self.theme_name = "dark"

        self.downloads = DownloadManager()
        self.appimage_entries: list[AppImageEntry] = []
        self.download_rows: dict[str, QListWidgetItem] = {}
        self.app_rows: dict[str, QListWidgetItem] = {}

        self.window: QMainWindow | None = None
        self.download_url_entry: QLineEdit | None = None
        self.download_name_entry: QLineEdit | None = None
        self.scan_dirs_entry: QLineEdit | None = None
        self.status_label: QLabel | None = None
        self.theme_dropdown: QComboBox | None = None
        self.download_list: QListWidget | None = None
        self.app_list: QListWidget | None = None
        self.stack: QStackedWidget | None = None
        self.nav_buttons: list[QPushButton] = []

        self._build_ui()
        self.refresh_appimages()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_downloads)
        self.poll_timer.start(300)

    def run(self, _argv: list[str] | None = None) -> int:
        if self.window is not None:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()
        return self.exec()

    def _build_ui(self):
        self.window = QMainWindow()
        self.window.setWindowTitle("App Hub")
        self.window.resize(1120, 720)
        self.window.setMinimumSize(980, 620)

        apply_qt_theme(self, self.theme_name)

        root = QWidget()
        root.setObjectName("appRoot")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.window.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 14, 12, 12)
        side_layout.setSpacing(8)
        shell.addWidget(sidebar)

        brand = QLabel("App Hub")
        brand.setObjectName("brandTitle")
        side_layout.addWidget(brand)

        for index, (label, page_name) in enumerate((("Downloads", "downloads"), ("AppImages", "appimages"))):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setProperty("pageName", page_name)
            button.clicked.connect(lambda _checked=False, page=index: self._set_page(page))
            side_layout.addWidget(button)
            self.nav_buttons.append(button)

        side_layout.addSpacing(10)
        line = QFrame()
        line.setObjectName("sidebarLine")
        line.setFrameShape(QFrame.Shape.HLine)
        side_layout.addWidget(line)

        theme_label = QLabel("Theme")
        theme_label.setObjectName("sidebarLabel")
        side_layout.addWidget(theme_label)

        self.theme_dropdown = QComboBox()
        self.theme_dropdown.addItems(["dark", "light"])
        self.theme_dropdown.setCurrentText(self.theme_name)
        self.theme_dropdown.currentTextChanged.connect(self.apply_theme)
        side_layout.addWidget(self.theme_dropdown)

        side_layout.addStretch(1)

        quit_button = QPushButton("Quit")
        quit_button.setObjectName("navButton")
        quit_button.clicked.connect(lambda _checked=False: self.quit())
        side_layout.addWidget(quit_button)

        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 22, 26, 18)
        content_layout.setSpacing(16)
        shell.addWidget(content, 1)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("App Hub")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Qt download manager and AppImage launcher")
        subtitle.setObjectName("mutedText")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block, 1)
        content_layout.addLayout(header)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_download_page())
        self.stack.addWidget(self._build_appimage_page())

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        content_layout.addWidget(self.status_label)

        self._set_page(0)

    def _set_page(self, index: int):
        if self.stack is not None:
            self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

    def _build_download_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        form = QFrame()
        form.setObjectName("panel")
        form_layout = QGridLayout(form)
        form_layout.setContentsMargins(14, 14, 14, 14)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(8)
        layout.addWidget(form)

        form_layout.addWidget(QLabel("URL"), 0, 0)
        self.download_url_entry = QLineEdit()
        self.download_url_entry.setPlaceholderText("https://example.com/file.AppImage")
        form_layout.addWidget(self.download_url_entry, 0, 1)

        form_layout.addWidget(QLabel("Filename"), 0, 2)
        self.download_name_entry = QLineEdit()
        self.download_name_entry.setPlaceholderText("Optional")
        form_layout.addWidget(self.download_name_entry, 0, 3)
        form_layout.setColumnStretch(1, 3)
        form_layout.setColumnStretch(3, 2)

        actions = self._action_bar(
            (
                ("Add Download", self.add_download, True),
                ("Pause", self.pause_download, False),
                ("Resume", self.resume_download, False),
                ("Cancel", self.cancel_download, False),
                ("Remove", self.remove_download, False),
            ),
            ("Open Folder", self.open_download_folder, False),
        )
        layout.addWidget(actions)

        self.download_list = QListWidget()
        self.download_list.setObjectName("resultList")
        self.download_list.setSpacing(8)
        layout.addWidget(self.download_list, 1)
        return page

    def _build_appimage_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        form = QFrame()
        form.setObjectName("panel")
        form_layout = QGridLayout(form)
        form_layout.setContentsMargins(14, 14, 14, 14)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(8)
        layout.addWidget(form)

        form_layout.addWidget(QLabel("Scan directories"), 0, 0)
        self.scan_dirs_entry = QLineEdit()
        self.scan_dirs_entry.setText(", ".join(self.settings.get("appimage_scan_dirs", [])))
        form_layout.addWidget(self.scan_dirs_entry, 0, 1)
        form_layout.setColumnStretch(1, 1)

        actions = self._action_bar(
            (
                ("Refresh List", self.refresh_appimages, True),
                ("Launch", self.launch_selected_appimage, False),
                ("Integrate", self.integrate_selected_appimage, False),
            ),
            ("Open Apps Dir", self.open_apps_dir, False),
        )
        layout.addWidget(actions)

        self.app_list = QListWidget()
        self.app_list.setObjectName("resultList")
        self.app_list.setSpacing(8)
        layout.addWidget(self.app_list, 1)
        return page

    def _action_bar(self, buttons: tuple[tuple[str, object, bool], ...], trailing: tuple[str, object, bool]) -> QFrame:
        bar = QFrame()
        bar.setObjectName("actionBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for label, callback, primary in buttons:
            button = QPushButton(label)
            button.setProperty("primary", primary)
            button.clicked.connect(lambda _checked=False, cb=callback: cb())
            layout.addWidget(button)

        layout.addStretch(1)
        label, callback, primary = trailing
        button = QPushButton(label)
        button.setProperty("primary", primary)
        button.clicked.connect(lambda _checked=False, cb=callback: cb())
        layout.addWidget(button)
        return bar

    def apply_theme(self, theme_name: str):
        if theme_name not in THEMES:
            theme_name = "dark"
        self.theme_name = theme_name
        self.settings["theme"] = theme_name
        save_settings(self.settings)
        apply_qt_theme(self, theme_name)

    def add_download(self):
        if self.download_url_entry is None or self.download_name_entry is None:
            return
        url = self.download_url_entry.text().strip()
        name = self.download_name_entry.text().strip() or None
        if not url:
            self._show_message("Missing URL", "Please enter a download URL.")
            return

        download_dir = Path(self.settings.get("download_dir", str(Path.home() / "Downloads"))).expanduser()
        task = self.downloads.add(url, download_dir, name, on_update=lambda _task: None)
        self._set_status(f"Started {task.target_path.name}")
        self.download_url_entry.clear()
        self.download_name_entry.clear()

    def _selected_download_id(self) -> str | None:
        if self.download_list is None:
            return None
        item = self.download_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def pause_download(self):
        tid = self._selected_download_id()
        task = self.downloads.get(tid) if tid else None
        if task:
            task.pause()

    def resume_download(self):
        tid = self._selected_download_id()
        task = self.downloads.get(tid) if tid else None
        if task:
            task.resume()

    def cancel_download(self):
        tid = self._selected_download_id()
        task = self.downloads.get(tid) if tid else None
        if task:
            task.cancel()

    def remove_download(self):
        tid = self._selected_download_id()
        if tid:
            self.downloads.remove(tid)

    def open_download_folder(self):
        download_dir = Path(self.settings.get("download_dir", str(Path.home() / "Downloads"))).expanduser()
        download_dir.mkdir(parents=True, exist_ok=True)
        self._open_path(download_dir)

    def _poll_downloads(self):
        tasks = self.downloads.list_tasks()
        current_ids = set(self.download_rows)

        for task in tasks:
            if task.task_id not in self.download_rows:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, task.task_id)
                self.download_rows[task.task_id] = item
                if self.download_list is not None:
                    self.download_list.addItem(item)
                    self.download_list.setItemWidget(item, self._make_download_row())
            self._update_download_row(self.download_rows[task.task_id], task)

        task_ids = {task.task_id for task in tasks}
        for orphan in current_ids - task_ids:
            item = self.download_rows.pop(orphan)
            if self.download_list is not None:
                self.download_list.takeItem(self.download_list.row(item))

    def _make_download_row(self) -> QWidget:
        return self._make_result_row()

    def _update_download_row(self, item: QListWidgetItem, task: DownloadTask):
        widget = self.download_list.itemWidget(item) if self.download_list is not None else None
        if widget is None:
            return
        progress = "-"
        if task.total_bytes and task.total_bytes > 0:
            pct = (task.downloaded_bytes / task.total_bytes) * 100
            progress = f"{pct:.1f}%"
        size = f"{format_size(task.downloaded_bytes)} / {format_size(task.total_bytes)}"
        title = widget.findChild(QLabel, "rowTitle")
        meta = widget.findChild(QLabel, "rowMeta")
        detail = widget.findChild(QLabel, "rowDetail")
        if title is not None:
            title.setText(task.target_path.name)
        if meta is not None:
            meta.setText(f"Status: {task.status}   Progress: {progress}   Speed: {format_speed(task.speed_bps)}")
        if detail is not None:
            detail.setText(f"Saved to {task.target_path}   Size: {size}")
        item.setSizeHint(widget.sizeHint())

    def _scan_dirs(self) -> list[str]:
        raw = self.scan_dirs_entry.text().strip() if self.scan_dirs_entry is not None else ""
        dirs = [item.strip() for item in raw.split(",") if item.strip()]
        if not dirs:
            dirs = [str(Path.home() / "Applications")]
        self.settings["appimage_scan_dirs"] = dirs
        save_settings(self.settings)
        return dirs

    def refresh_appimages(self):
        dirs = self._scan_dirs()
        self.appimage_entries = scan_appimages(dirs)
        if self.app_list is None:
            return
        self.app_list.clear()
        self.app_rows.clear()

        for entry in self.appimage_entries:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(entry.path))
            row = self._make_appimage_row(entry)
            item.setSizeHint(row.sizeHint())
            self.app_rows[str(entry.path)] = item
            self.app_list.addItem(item)
            self.app_list.setItemWidget(item, row)

        self._set_status(f"Found {len(self.appimage_entries)} AppImage files")

    def _make_appimage_row(self, entry: AppImageEntry) -> QWidget:
        row = self._make_result_row()
        title = row.findChild(QLabel, "rowTitle")
        meta = row.findChild(QLabel, "rowMeta")
        detail = row.findChild(QLabel, "rowDetail")
        if title is not None:
            title.setText(entry.name)
        if meta is not None:
            meta.setText(f"Path: {entry.path}")
        if detail is not None:
            detail.setText(f"Size: {format_size(entry.size)}   Executable: {'yes' if entry.executable else 'no'}")
        return row

    def _make_result_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("resultRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title = QLabel()
        title.setObjectName("rowTitle")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title)

        meta = QLabel()
        meta.setObjectName("rowMeta")
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        meta.setWordWrap(True)
        layout.addWidget(meta)

        detail = QLabel()
        detail.setObjectName("rowDetail")
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail.setWordWrap(True)
        layout.addWidget(detail)

        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return row

    def _selected_appimage_path(self) -> Path | None:
        if self.app_list is None:
            return None
        item = self.app_list.currentItem()
        if item is None:
            return None
        return Path(item.data(Qt.ItemDataRole.UserRole))

    def launch_selected_appimage(self):
        path = self._selected_appimage_path()
        if path is None:
            return
        try:
            launch_appimage(path)
            self._set_status(f"Launched {path.name}")
        except AppImageError as exc:
            self._show_message("Launch Failed", str(exc))

    def integrate_selected_appimage(self):
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
            self._show_message("Open Failed", str(exc))

    def _show_message(self, title: str, body: str):
        if self.window is None:
            return
        QMessageBox.information(self.window, title, body)

    def _set_status(self, text: str):
        if self.status_label is not None:
            self.status_label.setText(text)
