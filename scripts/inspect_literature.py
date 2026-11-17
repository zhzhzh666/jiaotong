"""Extract local evidence without altering original PDFs. No method inference."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from pypdf import PdfReader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    destination = args.root / ".cache/literature"
    destination.mkdir(parents=True, exist_ok=True)
    inventory = []
    for path in sorted(args.root.glob("*.pdf")):
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        (destination / (path.stem + ".txt")).write_text("\n".join(f"\n=== PDF PAGE {i + 1} ===\n{page}" for i, page in enumerate(pages)), encoding="utf-8")
        with path.open("rb") as stream:
            digest = sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        item = {"filename": path.name, "pages": len(pages), "size_bytes": path.stat().st_size,
                "sha256": digest.hexdigest(), "doi_candidates": sorted(set(re.findall(r"10\.\d{4,9}/[^\s<>]+", "\n".join(pages[:2])))),
                "text_extraction": "pypdf; mathematical glyphs require page verification"}
        inventory.append(item)
        print(json.dumps(item, ensure_ascii=False))
    (destination / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
