#!/usr/bin/env python3
"""도감에 없는 아이템 아이콘을 위키에서 받아 tools/cache-icons.json 에 모은다.

도감(재료 도감 HTML)이 아이콘을 주는 건 416종뿐이다. 레시피 트리와 할 일
총합에 뜨는 재료·가공품은 그보다 많아서, 빠진 것만 위키에서 채운다.

사용
  python tools/fetch_icons.py                 # 재료·가공품만 (기본)
  python tools/fetch_icons.py --scope all     # 전부
  python tools/fetch_icons.py --retry-missing # 지난번에 못 찾은 것 다시 시도
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache-icons.json")
API = "https://enshrouded.wiki.gg/api.php"
UA = "embervale-map-databuilder/1.0 (+https://github.com/qsef3546/embervale-map)"
SIZE = 40
BATCH = 50


def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if raw else json.load(r)


def api(**kw):
    kw.setdefault("format", "json")
    return get(API + "?" + urllib.parse.urlencode(kw))


def targets(scope):
    """아이콘을 붙일 아이템 이름 목록."""
    src = open(os.path.join(ROOT, "recipes.js"), encoding="utf-8").read()
    data = json.loads(src.split("window.EMBC=", 1)[1].rsplit(";", 1)[0])
    names = [it["n"] for it in data["items"]]
    if scope == "all":
        return names
    # 재료로 쓰이는 것 + 원자재 = 트리와 총합에 뜨는 것들
    raw = data["cats"].index("원자재")
    keep = {i for r in data["recipes"] for i, _ in r["i"]}
    keep |= {i for i, it in enumerate(data["items"]) if it["c"] == raw}
    return [names[i] for i in sorted(keep)]


def to_webp(blob):
    im = Image.open(io.BytesIO(blob))
    im.seek(0) if getattr(im, "is_animated", False) else None
    im = im.convert("RGBA")
    im.thumbnail((SIZE, SIZE), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "WEBP", quality=82, method=6)
    return base64.b64encode(out.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["ingredients", "all"], default="ingredients")
    ap.add_argument("--retry-missing", action="store_true")
    args = ap.parse_args()

    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    icons = cache.get("icons", {})
    missing = set(cache.get("missing", []))
    if args.retry_missing:
        missing = set()

    have = set(icons)
    # 도감이 이미 주는 것은 건너뛴다
    if os.path.exists(os.path.join(ROOT, "icons.js")):
        src = open(os.path.join(ROOT, "icons.js"), encoding="utf-8").read()
        have |= set(json.loads(src.split("window.EMBI=", 1)[1].rsplit(";", 1)[0]))

    todo = [n for n in targets(args.scope) if n not in have and n not in missing]
    print("대상 %d종" % len(todo))
    if not todo:
        return

    ok = fail = 0
    for b in range(0, len(todo), BATCH):
        chunk = todo[b:b + BATCH]
        titles = "|".join("File:%s.png" % n.lstrip(":") for n in chunk)
        try:
            d = api(action="query", titles=titles, prop="imageinfo",
                    iiprop="url", iiurlwidth=str(SIZE))
        except Exception as e:
            print("  배치 실패: %s" % e)
            time.sleep(10)
            continue

        # 정규화된 제목 → 원래 이름
        back = {"File:%s.png" % n.lstrip(":"): n for n in chunk}
        for norm in d["query"].get("normalized", []):
            if norm["from"] in back:
                back[norm["to"]] = back[norm["from"]]

        for p in d["query"]["pages"].values():
            name = back.get(p["title"])
            if name is None:
                continue
            ii = p.get("imageinfo")
            if not ii:
                missing.add(name)
                fail += 1
                continue
            try:
                # GIF 썸네일은 위키가 500을 내는 일이 있어 원본으로 물러선다
                try:
                    blob = get(ii[0]["thumburl"], raw=True)
                except Exception:
                    blob = get(ii[0]["url"], raw=True)
                icons[name] = to_webp(blob)
                ok += 1
            except Exception as e:
                print("  %s 변환 실패: %s" % (name, e))
                missing.add(name)
                fail += 1
            time.sleep(0.4)

        sys.stderr.write("\r  받음 %d, 없음 %d" % (ok, fail))
        json.dump({"icons": icons, "missing": sorted(missing)},
                  open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(1.5)

    sys.stderr.write("\n")
    size = sum(len(v) for v in icons.values())
    print("받음 %d · 위키에도 없음 %d · 캐시 총 %d종 (%.2f MB)"
          % (ok, fail, len(icons), size / 1e6))
    if missing:
        print("없는 것: %s" % ", ".join(sorted(missing)[:30]))


if __name__ == "__main__":
    main()
