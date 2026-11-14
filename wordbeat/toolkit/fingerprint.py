import argparse
import hashlib
from pathlib import Path

SKIP = {"node_modules", "__pycache__", ".git", ".DS_Store"}


def files(root: Path):
    if not root.exists():
        return
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and not SKIP.intersection(path.relative_to(root).parts):
            yield path


ap = argparse.ArgumentParser(description="Print one SHA-256 over the contents of files and directories.")
ap.add_argument("paths", nargs="*")
a = ap.parse_args()

digest = hashlib.sha256()
for name in a.paths:
    root = Path(name)
    digest.update(f"\0{name}\0{root.exists()}".encode())
    for path in files(root):
        digest.update(str(path.relative_to(root) if root.is_dir() else path.name).encode())
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
print(digest.hexdigest())
