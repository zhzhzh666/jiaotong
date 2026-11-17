"""Render only selected formula pages for visual verification, using local originals."""
from pathlib import Path
import pymupdf

SELECTIONS = {
    "1-s2.0-S1361920916308367-main.pdf": [7, 8],
    "1-s2.0-S1361920923003255-main.pdf": [6, 7],
    "1-s2.0-S1361920924003110-main.pdf": [4],
    "land-13-01894.pdf": [7, 11, 12],
    "典型设计暴雨下深圳市内涝空间分异与承灾体风险评估.pdf": [2, 3],
}

destination = Path(".cache/literature/pages")
destination.mkdir(parents=True, exist_ok=True)
for name, pages in SELECTIONS.items():
    with pymupdf.open(name) as document:
        for number in pages:
            document[number - 1].get_pixmap(dpi=110).save(destination / f"{Path(name).stem}_p{number}.png")
print(f"Rendered {sum(map(len, SELECTIONS.values()))} local reference pages")
