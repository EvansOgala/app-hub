# App Hub

App Hub is a Python desktop utility with a GTK4 interface for managing direct downloads and local AppImage files.

## Features

- GTK4 desktop UI with light and dark themes
- Download manager with pause, resume, cancel, and remove actions
- AppImage scanning across configurable directories
- AppImage launching and desktop integration helpers
- Persistent local settings for theme and scan directories

## Runtime Dependencies

- Python 3
- GTK4
- PyGObject

On Arch Linux:

```bash
sudo pacman -S --needed python python-gobject gtk4
```

## Run From Source

```bash
cd ~/Documents/app-hub
python3 main.py
```

## Packaging

This repository now includes an AUR-ready `app-hub-git` package:

- [PKGBUILD](./PKGBUILD)
- [.SRCINFO](./.SRCINFO)

To build it locally on Arch Linux:

```bash
cd ~/Documents/app-hub
makepkg -si
```

## Notes

- AppImage integration writes desktop entries to `~/.local/share/applications`.
- Download target is configured in settings at `~/.config/app_hub/settings.json`.
- The launcher installed by the package runs the installed copy under `/usr/lib/app-hub/`.

## License

MIT
