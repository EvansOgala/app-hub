import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class AppImageError(Exception):
    pass


@dataclass
class AppImageEntry:
    path: Path
    name: str
    size: int
    executable: bool


def scan_appimages(scan_dirs: list[str]) -> list[AppImageEntry]:
    entries: list[AppImageEntry] = []
    seen: set[Path] = set()

    for raw in scan_dirs:
        base = Path(raw).expanduser()
        if not base.exists() or not base.is_dir():
            continue

        for child in base.rglob("*.AppImage"):
            if child in seen:
                continue
            seen.add(child)
            try:
                st = child.stat()
            except OSError:
                continue
            entries.append(
                AppImageEntry(
                    path=child,
                    name=child.stem,
                    size=st.st_size,
                    executable=os.access(child, os.X_OK),
                )
            )

    entries.sort(key=lambda e: e.name.lower())
    return entries


def ensure_executable(path: Path):
    try:
        mode = path.stat().st_mode
        path.chmod(mode | 0o111)
    except OSError as exc:
        raise AppImageError(str(exc)) from exc


def launch_appimage(path: Path):
    if not path.exists():
        raise AppImageError(f"File not found: {path}")
    ensure_executable(path)
    try:
        subprocess.Popen([str(path)])
    except OSError as exc:
        raise AppImageError(str(exc)) from exc


def integrate_appimage(path: Path, managed_dir: Path) -> Path:
    if not path.exists():
        raise AppImageError(f"File not found: {path}")

    managed_dir.mkdir(parents=True, exist_ok=True)
    target = managed_dir / path.name
    try:
        if path.resolve() != target.resolve():
            shutil.copy2(path, target)
        ensure_executable(target)
    except OSError as exc:
        raise AppImageError(str(exc)) from exc

    desktop_dir = Path.home() / ".local" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    desktop_path = desktop_dir / f"apphub-{target.stem.lower().replace(' ', '-')}.desktop"

    desktop_content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={target.stem}\n"
        f"Exec={target}\n"
        "Terminal=false\n"
        f"Icon={target}\n"
        "Categories=Utility;\n"
    )
    try:
        desktop_path.write_text(desktop_content, encoding="utf-8")
    except OSError as exc:
        raise AppImageError(str(exc)) from exc

    return target
