"""Execute the training notebooks in order and save them with their outputs.

Usage: python training/scripts/k3_run_notebooks.py [first [last]]   (numbers, default 1 19)
Each notebook runs in a fresh kernel; the run stops at the first failing notebook.
"""
import sys
import time
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient

NB = Path(__file__).resolve().parents[2] / "training" / "notebooks"


def main():
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 19
    files = [p for p in sorted(NB.glob("[0-9][0-9]_*.ipynb")) if first <= int(p.name[:2]) <= last]
    t0 = time.time()
    for i, p in enumerate(files, 1):
        t = time.time()
        nb = nbformat.read(p, as_version=4)
        km = KernelManager(kernel_name="python3", ip="127.0.0.1")  # loopback only
        NotebookClient(nb, km=km, timeout=1800, resources={"metadata": {"path": str(NB)}}).execute()
        nbformat.write(nb, p)
        print(f"[{i}/{len(files)}] {p.name}: OK in {time.time() - t:.0f} s "
              f"({p.stat().st_size / 2**20:.1f} MB, total {(time.time() - t0) / 60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
