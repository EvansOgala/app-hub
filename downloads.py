import os
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class DownloadTask:
    task_id: str
    url: str
    target_path: Path
    status: str = "queued"
    total_bytes: int | None = None
    downloaded_bytes: int = 0
    speed_bps: float = 0.0
    error: str = ""
    created_at: float = field(default_factory=time.time)

    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _pause_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _on_update: Callable[["DownloadTask"], None] | None = field(default=None, init=False, repr=False)

    def start(self, on_update: Callable[["DownloadTask"], None]):
        if self._thread and self._thread.is_alive():
            return
        self._on_update = on_update
        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(target=self._run, args=(on_update,), daemon=True)
        self._thread.start()

    def pause(self):
        if self.status in {"downloading", "queued"}:
            self._pause_event.set()
            self.status = "pausing"
            if self._on_update:
                self._on_update(self)

    def resume(self):
        if self.status in {"paused", "pausing"}:
            self._pause_event.clear()
            self.status = "queued"
            if self._on_update:
                self._on_update(self)
                self.start(self._on_update)

    def cancel(self):
        self._stop_event.set()
        self._pause_event.clear()
        self.status = "canceled"
        if self._on_update:
            self._on_update(self)

    def _run(self, on_update: Callable[["DownloadTask"], None]):
        self.status = "downloading"
        on_update(self)
        chunk_size = 64 * 1024

        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                self.status = "paused"
                self.speed_bps = 0.0
                on_update(self)
                return

            try:
                self.target_path.parent.mkdir(parents=True, exist_ok=True)
                downloaded = self.target_path.stat().st_size if self.target_path.exists() else 0
                self.downloaded_bytes = downloaded

                request = urllib.request.Request(self.url)
                if downloaded > 0:
                    request.add_header("Range", f"bytes={downloaded}-")

                start_time = time.time()
                start_bytes = downloaded

                with urllib.request.urlopen(request, timeout=20) as resp:
                    length_header = resp.headers.get("Content-Length")
                    if length_header:
                        partial_total = int(length_header)
                        if downloaded > 0 and resp.status == 206:
                            self.total_bytes = downloaded + partial_total
                        else:
                            self.total_bytes = partial_total
                    mode = "ab" if downloaded > 0 else "wb"
                    with self.target_path.open(mode) as out:
                        while not self._stop_event.is_set():
                            if self._pause_event.is_set():
                                self.status = "paused"
                                self.speed_bps = 0.0
                                on_update(self)
                                return
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            out.write(chunk)
                            self.downloaded_bytes += len(chunk)
                            elapsed = max(0.001, time.time() - start_time)
                            self.speed_bps = (self.downloaded_bytes - start_bytes) / elapsed
                            on_update(self)

                if self._stop_event.is_set():
                    self.status = "canceled"
                    on_update(self)
                    return
                if self._pause_event.is_set():
                    self.status = "paused"
                    self.speed_bps = 0.0
                    on_update(self)
                    return

                if self.total_bytes is None or self.downloaded_bytes >= self.total_bytes:
                    self.status = "completed"
                    self.speed_bps = 0.0
                    on_update(self)
                    return

            except Exception as exc:  # noqa: BLE001
                self.status = "failed"
                self.error = str(exc)
                self.speed_bps = 0.0
                on_update(self)
                return


class DownloadManager:
    def __init__(self):
        self._tasks: dict[str, DownloadTask] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def list_tasks(self) -> list[DownloadTask]:
        with self._lock:
            return list(self._tasks.values())

    def get(self, task_id: str) -> DownloadTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def add(self, url: str, download_dir: Path, filename: str | None, on_update: Callable[[DownloadTask], None]) -> DownloadTask:
        with self._lock:
            self._counter += 1
            task_id = f"task-{self._counter}"

        if not filename:
            parsed = urllib.parse.urlparse(url)
            name = Path(parsed.path).name or f"download-{int(time.time())}.bin"
        else:
            name = filename.strip()

        target = download_dir / name
        task = DownloadTask(task_id=task_id, url=url, target_path=target)
        with self._lock:
            self._tasks[task_id] = task
        task.start(on_update)
        return task

    def remove(self, task_id: str):
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return
        if task.status in {"downloading", "queued", "paused"}:
            task.cancel()
        with self._lock:
            self._tasks.pop(task_id, None)


def format_speed(speed_bps: float) -> str:
    if speed_bps <= 0:
        return "-"
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    value = speed_bps
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} GB/s"


def format_size(num: int | None) -> str:
    if num is None:
        return "-"
    value = float(num)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"
