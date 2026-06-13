from __future__ import annotations


def main() -> None:
    try:
        from ui import AppHubApp
    except Exception as exc:
        print(exc)
        raise SystemExit(1)

    app = AppHubApp()
    app.run(None)


if __name__ == "__main__":
    main()
