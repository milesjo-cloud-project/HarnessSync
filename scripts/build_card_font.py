"""Subset an OFL Noto Sans CJK font for translated achievement cards.

Run after adding translated card copy or a language. Requires fonttools only
at build time: python scripts/build_card_font.py /path/to/NotoSansCJKjp-Regular.otf
Source and licensing are documented in harnesssync/assets/README.md.
"""

import json
import string
import sys
from pathlib import Path

from fontTools import subset

root = Path(__file__).resolve().parents[1]
text = string.printable + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝŒÆŸàáâãäåçèéêëìíîïñòóôõöùúûüýœæÿ"
for path in (root / "harnesssync/locales").glob("*.json"):
    data = json.loads(path.read_text(encoding="utf-8"))
    text += "".join(data) + "".join(data.values())
options = subset.Options()
options.name_IDs = ["*"]
font = subset.load_font(sys.argv[1], options)
subsetter = subset.Subsetter(options=options)
subsetter.populate(text=text)
subsetter.subset(font)
output = root / "harnesssync/assets/card-font.otf"
output.parent.mkdir(exist_ok=True)
subset.save_font(font, str(output), options)
print(f"Wrote {output.stat().st_size:,} byte card font")
