from pathlib import Path
import tkinter as tk
from ui.app import InstinctApp


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

def main() -> None:
    root = tk.Tk()
    InstinctApp(root, DATA_DIR)
    root.mainloop()

if __name__ == "__main__":
    main()