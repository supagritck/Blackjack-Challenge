"""
Download the open-source SVG card deck from hayeah/playing-cards-assets (MIT licence)
into web/static/cards/.

Run from the project root:
    python scripts/download_cards.py

The deck contains 52 card faces + 1 generated back = 53 files.
File naming:  ace_of_spades.svg, 2_of_clubs.svg, jack_of_hearts.svg, back.svg
Source:       https://github.com/hayeah/playing-cards-assets  (MIT licence)
"""
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/hayeah/playing-cards-assets/master/svg-cards"
OUT_DIR  = Path(__file__).parent.parent / "web" / "static" / "cards"

RANKS = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10",
         "jack", "queen", "king"]
SUITS = ["clubs", "diamonds", "hearts", "spades"]

# Simple blue card back generated locally — no external file needed
BACK_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 169.075 244.64">
  <rect width="169.075" height="244.64" rx="10" ry="10" fill="#1a3a8c"/>
  <rect x="6" y="6" width="157.075" height="232.64" rx="7" ry="7"
        fill="none" stroke="#ffffff" stroke-width="2" stroke-opacity="0.4"/>
  <pattern id="diag" patternUnits="userSpaceOnUse" width="12" height="12"
            patternTransform="rotate(45)">
    <line x1="0" y1="0" x2="0" y2="12" stroke="#ffffff" stroke-width="1"
          stroke-opacity="0.12"/>
  </pattern>
  <rect x="10" y="10" width="149.075" height="224.64" rx="5" ry="5"
        fill="url(#diag)"/>
  <text x="84.5" y="132" font-family="serif" font-size="48" fill="#ffffff"
        fill-opacity="0.25" text-anchor="middle" dominant-baseline="middle">♠</text>
</svg>
"""


def download(filename: str) -> bool:
    dest = OUT_DIR / filename
    if dest.exists():
        print(f"  skip  {filename}")
        return True
    url = f"{BASE_URL}/{filename}"
    try:
        urllib.request.urlretrieve(url, dest)
        print(f"  ok    {filename}")
        return True
    except urllib.error.URLError as exc:
        print(f"  FAIL  {filename}  ({exc})", file=sys.stderr)
        return False


def write_back() -> None:
    dest = OUT_DIR / "back.svg"
    if dest.exists():
        print("  skip  back.svg")
        return
    dest.write_text(BACK_SVG, encoding="utf-8")
    print("  ok    back.svg  (generated)")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading SVG card deck to: {OUT_DIR}\n")

    failures = 0
    for suit in SUITS:
        for rank in RANKS:
            if not download(f"{rank}_of_{suit}.svg"):
                failures += 1
    write_back()

    total = len(RANKS) * len(SUITS) + 1
    done  = total - failures
    print(f"\n{done}/{total} files ready in {OUT_DIR}")
    if failures:
        print(f"{failures} card face(s) failed — CSS fallback will be used for those.")
    else:
        print("All done. Restart uvicorn and refresh the browser.")


if __name__ == "__main__":
    main()
