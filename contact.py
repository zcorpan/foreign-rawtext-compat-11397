"""Contact sheet of review crops: contact.py OUT.png CROP..."""
import sys
from PIL import Image, ImageDraw
files = sys.argv[2:]
tiles = []
for f in files:
    im = Image.open(f); im.thumbnail((900, 280))
    t = Image.new("RGB", (900, 305), "white"); t.paste(im, (0, 25)); ImageDraw.Draw(t).text((5, 5), f.split("/")[-1], fill="black")
    tiles.append(t)
rows = (len(tiles) + 1) // 2
sheet = Image.new("RGB", (1800, 305 * rows), "white")
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 2) * 900, (i // 2) * 305))
sheet.save(sys.argv[1])
