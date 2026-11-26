"""Check that every ``nisar_s1`` name imported by the study scripts and notebooks exists in the
installed package (the study pins a release in ``requirements.txt``).

Usage: python tools/check_imports.py   (from the repository root). Exit code 1 on a missing name.
"""

import ast
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sources():
    for study in ("vosges", "morvan", "sechilienne", "training"):
        for p in sorted((ROOT / study / "scripts").rglob("*.py")):
            yield p, p.read_text(encoding="utf-8")
    for p in sorted((ROOT / "training" / "notebooks").glob("*.ipynb")):
        nb = json.loads(p.read_text(encoding="utf-8"))
        code = []
        for c in nb["cells"]:
            if c["cell_type"] == "code":
                src = "".join(c["source"])
                code.append("\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith(("!", "%"))))
        yield p, "\n".join(code)


def imported_names(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "nisar_s1":
            for a in node.names:
                yield node.module, a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] == "nisar_s1":
                    yield a.name, None


def main() -> int:
    import nisar_s1

    print(f"nisar_s1 {nisar_s1.__version__} from {nisar_s1.__file__}")
    missing, n = [], 0
    for path, text in sources():
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            missing.append(f"{path.relative_to(ROOT)}: syntax error {e}")
            continue
        for module, name in imported_names(tree):
            n += 1
            try:
                mod = importlib.import_module(module)
                if name and name != "*" and not hasattr(mod, name):
                    importlib.import_module(f"{module}.{name}")  # submodule
            except ImportError:
                missing.append(f"{path.relative_to(ROOT)}: {module}{'.' + name if name else ''}")
    print(f"{n} imports checked")
    for m in missing:
        print("MISSING", m)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
