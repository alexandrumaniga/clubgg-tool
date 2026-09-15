r"""Generate Paul's Book PWA icons (a poker chip in the app palette) into public/.
Run once; re-run only if the mark changes.  python make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

PUB = Path(__file__).parent / "public"
BG = (14, 17, 18, 255)        # --bg terminal
TEAL = (217, 164, 65, 255)   # --a amber (disc)
CREAM = (215, 222, 220, 255) # --text (notches + centre)


def chip(size, bg=BG, pad=0.38):
    """Poker chip: teal disc, 6 cream rim notches, cream centre."""
    S = size * 4                      # supersample then downscale for AA
    im = Image.new("RGBA", (S, S), bg)
    d = ImageDraw.Draw(im)
    c = S / 2
    R = S * pad
    box = [c - R, c - R, c + R, c + R]
    d.ellipse(box, fill=TEAL)
    # cream wedges from centre to rim, every 60deg
    for i in range(6):
        a = i * 60
        d.pieslice(box, a - 11, a + 11, fill=CREAM)
    # cover the inner part of the wedges -> only rim notches remain
    r2 = R * 0.74
    d.ellipse([c - r2, c - r2, c + r2, c + r2], fill=TEAL)
    # centre disc
    r3 = R * 0.44
    d.ellipse([c - r3, c - r3, c + r3, c + r3], fill=CREAM)
    r4 = R * 0.30
    d.ellipse([c - r4, c - r4, c + r4, c + r4], fill=TEAL)
    return im.resize((size, size), Image.LANCZOS)


def main():
    PUB.mkdir(exist_ok=True)
    # standard icons (transparent-ish dark ground)
    for s in (192, 512):
        chip(s).save(PUB / f"icon-{s}.png")
    # maskable: chip smaller so it survives the safe-zone crop
    chip(512, pad=0.30).save(PUB / "icon-maskable-512.png")
    # apple touch icon must be opaque
    chip(180).convert("RGB").save(PUB / "icon-180.png")
    # favicon
    chip(64).save(PUB / "favicon.png")
    for f in sorted(PUB.glob("icon*.png")) + [PUB / "favicon.png"]:
        print(f"  {f.name}  {f.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
