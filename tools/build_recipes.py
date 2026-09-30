#!/usr/bin/env python3
"""제작 데이터(recipes.js, icons.js) 생성기.

입력
  1. enshrouded.wiki.gg Cargo `Ingredients` 테이블 — 레시피 그래프
  2. Enshrouded 재료 도감 HTML — 한글명·아이콘·획득처
  3. tools/names.ko.json — 손으로 채우는 한글명 사전 (도감보다 우선)

사용
  python tools/build_recipes.py --dogam "재료도감.html"
  python tools/build_recipes.py --dogam "재료도감.html" --refetch
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache-ingredients.json")
NAMES = os.path.join(HERE, "names.ko.json")

API = "https://enshrouded.wiki.gg/api.php"
UA = "embervale-map-databuilder/1.0 (+https://github.com/qsef3546/embervale-map)"
FIELDS = "CraftedItem,CraftedQuantity,SourceItem,SourceQuantity,Crafter,Workshop,Workshop2"

# 작업대·제작자 → 분류. 위에서부터 먼저 걸리는 것을 쓴다.
CAT_RULES = [
    ("장식·건축", {"Decoration Workbench", "Table Saw", "Carpenter",
                "Masonry Tools", "Kiln", "Mill"}),
    ("요리·음료", {"Kitchen", "Cooking Station", "Coffee Brewery",
                "Butter Churn", "Drying Rack", "Beehive Smoker"}),
    ("물약·연금", {"Alchemy Station", "Laboratory", "Alchemist",
                "Ectoplasm Press", "Athanor"}),
    ("장비·무기", {"Blacksmith", "Forge", "Blast Furnace", "Hunter",
                "Loom", "Grinding Stones", "Charcoal Kiln"}),
    ("농사·씨앗", {"Farmer", "Seedbed", "Almanac of Plants and Seedlings", "Fisher"}),
]
CATS = [c for c, _ in CAT_RULES] + ["기타", "원자재"]

# 도감의 지역명을 지도(data.js)가 쓰는 공식 한국어 표기로 맞춘다.
BIOME_KO = {
    "킨들웨이스트": "불타는 황무지",
    "노마드 하이랜드": "유목민 고원",
    "레벨웃드": "레벨우드",
    "알바네브 정상": "알바네브 봉우리",
}
CAT_OTHER = len(CATS) - 2
CAT_RAW = len(CATS) - 1


def api(**kw):
    kw.setdefault("format", "json")
    url = API + "?" + urllib.parse.urlencode(kw)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.load(urllib.request.urlopen(req, timeout=60))


def fetch_ingredients():
    """Cargo 테이블 전량을 페이지 단위로 받는다. 위키가 레이트 리밋을 걸면 쉬었다 재시도."""
    total = int(api(action="cargoquery", tables="Ingredients",
                    fields="COUNT(*)=c")["cargoquery"][0]["title"]["c"])
    rows, off, stall = [], 0, 0
    while off < total:
        d = api(action="cargoquery", tables="Ingredients", fields=FIELDS,
                limit="500", offset=str(off), order_by="CraftedItem,SourceItem")
        if "error" in d:
            stall += 1
            if stall > 8:
                raise SystemExit("위키 응답 실패: %s" % d["error"].get("code"))
            time.sleep(10)
            continue
        batch = [r["title"] for r in d["cargoquery"]]
        if not batch:
            break
        rows += batch
        off += len(batch)
        sys.stderr.write("\r  위키 %d/%d" % (off, total))
        time.sleep(2.5)
    sys.stderr.write("\n")
    return rows


def load_dogam(path):
    """재료 도감 HTML의 JSON 블록을 꺼낸다."""
    html = open(path, encoding="utf-8").read()
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit("도감 HTML에서 데이터 블록을 찾지 못했습니다")
    return json.loads(m.group(1))


def group_recipes(rows):
    """행 단위 재료 목록을 (결과물, 제작자, 작업대) 별 레시피로 묶는다."""
    grouped = OrderedDict()
    for r in rows:
        key = (r["CraftedItem"], r["Crafter"], r["Workshop"], r["Workshop2"])
        g = grouped.setdefault(key, {"qty": int(r["CraftedQuantity"] or 1),
                                     "ing": OrderedDict()})
        # 같은 재료가 두 번 실린 행이 몇 건 있다 — 큰 수량을 남긴다
        q = int(r["SourceQuantity"] or 0)
        g["ing"][r["SourceItem"]] = max(q, g["ing"].get(r["SourceItem"], 0))
    return grouped


def build_items(names, crafted, shops, dg, manual):
    biomes, types = [], []
    items = []
    for n in names:
        it = {"n": n, "c": CAT_RAW}
        if n in crafted:
            s = shops[n]
            it["c"] = next((i for i, (_, keys) in enumerate(CAT_RULES) if s & keys), CAT_OTHER)

        e = dg.get(n)
        ko = manual.get(n) or (e or {}).get("kn")
        if ko and ko != n:
            it["k"] = ko

        if e:
            if e.get("r"):
                it["r"] = e["r"]
            if e.get("l"):
                it["l"] = int(e["l"])
            if e.get("d"):
                it["d"] = e["d"]
            eb = [BIOME_KO.get(b, b) for b in e.get("b") or []]
            for b in eb:
                if b not in biomes:
                    biomes.append(b)
            if eb:
                it["b"] = [biomes.index(b) for b in eb]
            for t in e.get("t") or []:
                if t not in types:
                    types.append(t)
            if e.get("t"):
                it["t"] = [types.index(t) for t in e["t"]]
            world = [s[1] for s in e.get("src") or [] if s[0] == "world" and s[1]]
            drop = [s[1] for s in e.get("src") or [] if s[0] == "drop" and s[1]]
            if world:
                it["w"] = world
            if drop:
                it["dr"] = drop
            mobs = [p.get("c") for p in e.get("p") or [] if p.get("c")]
            if mobs:
                it["m"] = mobs
        items.append(it)
    return items, biomes, types


HEADER = """/*! 엠버베일 한글 지도 — 제작 데이터
 * 레시피: The Official Enshrouded Wiki (https://enshrouded.wiki.gg) Cargo `Ingredients`
 * 한글명·아이콘·획득 정보는 이 저장소에서 가공했습니다.
 * 라이선스: CC BY-NC-SA 3.0 (https://creativecommons.org/licenses/by-nc-sa/3.0/)
 * Enshrouded 콘텐츠의 권리는 Keen Games GmbH에 있습니다. */
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dogam", required=True, help="재료 도감 HTML 경로")
    ap.add_argument("--refetch", action="store_true", help="위키에서 레시피를 다시 받는다")
    args = ap.parse_args()

    if args.refetch or not os.path.exists(CACHE):
        rows = fetch_ingredients()
        json.dump(rows, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    else:
        rows = json.load(open(CACHE, encoding="utf-8"))
    print("레시피 행 %d" % len(rows))

    dogam = load_dogam(args.dogam)
    dg = {e["n"]: e for e in dogam}
    print("도감 항목 %d" % len(dogam))

    manual = json.load(open(NAMES, encoding="utf-8")) if os.path.exists(NAMES) else {}
    print("수동 사전 %d" % len(manual))

    grouped = group_recipes(rows)
    crafted = {k[0] for k in grouped}
    sources = {s for g in grouped.values() for s in g["ing"]}
    names = sorted(crafted | sources)

    shops = defaultdict(set)
    for (item, crafter, w1, w2) in grouped:
        shops[item] |= {x for x in (crafter, w1, w2) if x}

    idx = {n: i for i, n in enumerate(names)}
    crafters = sorted({k[1] for k in grouped if k[1]})
    shopnames = sorted({x for k in grouped for x in (k[2], k[3]) if x})
    ci = {c: i for i, c in enumerate(crafters)}
    si = {s: i for i, s in enumerate(shopnames)}

    items, biomes, types = build_items(names, crafted, shops, dg, manual)

    recipes = []
    for (item, crafter, w1, w2), g in grouped.items():
        rec = {"o": idx[item], "q": g["qty"],
               "i": [[idx[s], q] for s, q in g["ing"].items()]}
        if crafter:
            rec["c"] = ci[crafter]
        ws = [si[x] for x in (w1, w2) if x]
        if ws:
            rec["w"] = ws
        recipes.append(rec)

    out = {
        "source": "The Official Enshrouded Wiki (enshrouded.wiki.gg) Cargo `Ingredients`"
                  " — CC BY-NC-SA 3.0, 한글명·획득 정보 가공",
        "cats": CATS, "crafters": crafters, "shops": shopnames,
        "biomes": biomes, "types": types,
        "items": items, "recipes": recipes,
    }
    with open(os.path.join(ROOT, "recipes.js"), "w", encoding="utf-8") as f:
        f.write(HEADER)
        f.write("window.EMBC=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")

    icons = {n: dg[n]["i"] for n in names if n in dg and dg[n].get("i")}
    with open(os.path.join(ROOT, "icons.js"), "w", encoding="utf-8") as f:
        f.write("/*! 아이템 아이콘 (webp/base64) — 출처·라이선스는 recipes.js와 같습니다. */\n")
        f.write("window.EMBI=" + json.dumps(icons, ensure_ascii=False, separators=(",", ":")) + ";\n")

    named = sum(1 for i in items if "k" in i)
    print("\n아이템 %d (한글명 %d, %.0f%%) · 레시피 %d · 아이콘 %d"
          % (len(items), named, 100 * named / len(items), len(recipes), len(icons)))
    for i, c in enumerate(CATS):
        grp = [x for x in items if x["c"] == i]
        if grp:
            print("  %-6s %5d  한글 %4d" % (c, len(grp), sum(1 for x in grp if "k" in x)))


if __name__ == "__main__":
    main()
