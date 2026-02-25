import tkinter as tk

from ui import AppHub


def main():
    root = tk.Tk()
    try:
        root.tk.call("wm", "class", root._w, "AppHub")
    except tk.TclError:
        pass
    AppHub(root)
    root.mainloop()


if __name__ == "__main__":
    main()
