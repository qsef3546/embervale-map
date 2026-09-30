#!/usr/bin/env python3
"""사용법에 넣을 화면 그림에 번호 주석을 그린다.

캡처한 화면과, 화면 안 요소들의 위치를 적은 JSON 을 받아
빨간 테두리와 번호 동그라미를 얹어 webp 로 내보낸다.

JSON 모양
  {"viewport": [1280, 820],
   "boxes": [["1", [x, y, w, h]], ["2", [x, y, w, h]], ...]}

좌표는 브라우저에서 잰 그대로(CSS 픽셀) 넣으면 된다.
캡처가 그보다 작아도 비율을 맞춰 알아서 줄인다.

사용
  python tools/annotate_guide.py shot.jpg boxes.json guide/craft.webp
"""
import json
import sys

from PIL import Image, ImageDraw, ImageFont

RED = (226, 60, 60)
WHITE = (255, 255, 255)
PAD = 3          # 테두리를 요소보다 살짝 넓게
RADIUS = 6       # 모서리 둥글기
BADGE = 11       # 번호 동그라미 반지름


def load_font(size):
    for path in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/malgunbd.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    shot, spec_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    spec = json.load(open(spec_path, encoding="utf-8"))
    im = Image.open(shot).convert("RGB")
    vw, vh = spec["viewport"]
    s = im.width / vw                      # 캡처가 줄어든 비율

    d = ImageDraw.Draw(im)
    font = load_font(13)

    for label, (x, y, w, h) in spec["boxes"]:
        x0, y0 = x * s - PAD, y * s - PAD
        x1, y1 = (x + w) * s + PAD, (y + h) * s + PAD
        # 화면 밖으로 나간 요소는 보이는 데까지만 그린다
        x0, y0 = max(1, x0), max(1, y0)
        x1, y1 = min(im.width - 2, x1), min(im.height - 2, y1)
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        d.rounded_rectangle([x0, y0, x1, y1], radius=RADIUS, outline=RED, width=2)

        # 번호는 왼쪽 테두리에 걸치게. 낮은 상자는 글씨를 가리니 바깥에 두고,
        # 화면 끝에 붙으면 안으로 밀어 넣는다
        cx = x0 - BADGE - 2 if (y1 - y0) < 44 else x0
        cx = max(BADGE + 1, cx)
        cy = min(max(BADGE + 1, (y0 + y1) / 2), im.height - BADGE - 1)
        d.ellipse([cx - BADGE, cy - BADGE, cx + BADGE, cy + BADGE], fill=RED)
        tb = d.textbbox((0, 0), label, font=font)
        d.text((cx - (tb[2] - tb[0]) / 2, cy - (tb[3] - tb[1]) / 2 - tb[1]),
               label, font=font, fill=WHITE)

    im.save(out, "WEBP", quality=88, method=6)
    print("%s  %dx%d  %.0f KB" % (out, im.width, im.height,
                                  __import__("os").path.getsize(out) / 1024))


if __name__ == "__main__":
    main()
