# App Hub (Starter)

A Python desktop app with:
- Download Manager (queue, pause/resume/cancel)
- AppImage scanner/launcher/integrator

## Run

```bash
cd /home/evans/Documents/app-hub
python3 main.py
```

## Notes

- AppImage integration writes desktop entries to `~/.local/share/applications`.
- Download target is configured in settings (`~/.config/app_hub/settings.json`).
