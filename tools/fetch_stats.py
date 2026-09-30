#!/usr/bin/env python3
"""아이템 페이지에서 설명과 옵션(스탯·효과)을 긁어 tools/cache-stats.json 에 모은다.

위키는 스탯을 Cargo 가 아니라 페이지 본문 템플릿에 담고 있다.
  {{Item Infobox}}  설명 · 종류 · 등급 · 레벨 · 겹치기
  {{ItemStats}}     지속시간 · 효과 (음식·물약) · 피해 · 내구도 …
  {{Weapon Stats}}  무기 종류 · 레벨 · 공격 속도 · 퍽
  {{Armor Stats}}   물리/마법 저항 · 효과

사용
  python tools/fetch_stats.py
  python tools/fetch_stats.py --refetch
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache-stats.json")
API = "https://enshrouded.wiki.gg/api.php"
UA = "embervale-map-databuilder/1.0 (+https://github.com/qsef3546/embervale-map)"
BATCH = 50

# {{템플릿}} 에서 값을 그대로 가져올 항목
INFOBOX = ["description", "Type", "Rarity", "Level", "Stack Size", "Source"]
STAT_KEYS = [
    "Duration", "Damage", "Healing", "Durability", "Block", "Parry Power",
    "Range", "Speed", "Stamina per Second", "Stamina Cost", "Mana Cost",
    "Cast Time", "Damage Type", "Element Type", "Fishing Strength",
    "Fishing Endurance", "Physical", "Cutting", "Magical",
    "weaponType", "level", "attackSpeed", "drawSpeed", "arrowSpeed",
    "parryPower", "source",
]


def api(**kw):
    kw.setdefault("format", "json")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw),
                                 headers={"User-Agent": UA})
    return json.load(urllib.request.urlopen(req, timeout=60))


def templates(text, name):
    """{{name | a= 1 | b= 2}} 를 찾아 {a: '1', b: '2'} 로 돌려준다."""
    out = []
    pat = re.compile(r"\{\{\s*" + name.replace(" ", "[ _]") + r"\s*(\||\})", re.I)
    for m in pat.finditer(text):
        i, depth = m.end() - 1, 1
        while i < len(text) and depth:
            if text.startswith("{{", i):
                depth += 1
                i += 2
            elif text.startswith("}}", i):
                depth -= 1
                i += 2
            else:
                i += 1
        body = text[m.end() - 1:i - 2]
        args, buf, lvl = {}, "", 0
        for ch in body:
            if ch in "{[":
                lvl += 1
            elif ch in "}]":
                lvl -= 1
            if ch == "|" and lvl <= 0:
                if "=" in buf:
                    k, v = buf.split("=", 1)
                    args[k.strip()] = v.strip()
                buf = ""
            else:
                buf += ch
        if "=" in buf:
            k, v = buf.split("=", 1)
            args[k.strip()] = v.strip()
        out.append(args)
    return out


def clean(v):
    v = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", v)   # [[a|b]] → b
    v = re.sub(r"\{\{[^}]*\}\}", "", v)                      # 남은 템플릿 제거
    v = re.sub(r"<[^>]+>", "", v)
    v = re.sub(r"'{2,}", "", v)
    return " ".join(v.split())


def parse_page(text):
    out = {}
    boxes = (templates(text, "Item Infobox") + templates(text, "Armor Infobox")
             + templates(text, "Weapon Infobox"))
    for b in boxes:
        for k in INFOBOX:
            if b.get(k) and k not in out:
                out[k] = clean(b[k])

    stats, effects, perks = {}, [], []
    for b in (templates(text, "ItemStats") + templates(text, "Armor Stats")
              + templates(text, "Weapon Stats")):
        for k, v in b.items():
            v = clean(v)
            if not v:
                continue
            if re.fullmatch(r"Effects?\d*", k):
                if v not in effects:
                    effects.append(v)
            elif k == "perks":
                for p in v.split(","):
                    p = p.strip()
                    if p:
                        perks.append(p)
            elif k in STAT_KEYS and k not in stats:
                stats[k] = v
    if stats:
        out["stats"] = stats
    if effects:
        out["effects"] = effects
    if perks:
        out["perks"] = perks
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    args = ap.parse_args()

    src = open(os.path.join(ROOT, "recipes.js"), encoding="utf-8").read()
    data = json.loads(src.split("window.EMBC=", 1)[1].rsplit(";", 1)[0])
    names = [it["n"] for it in data["items"]]

    cache = {} if args.refetch or not os.path.exists(CACHE) \
        else json.load(open(CACHE, encoding="utf-8"))
    todo = [n for n in names if n not in cache]
    print("아이템 %d · 받을 것 %d" % (len(names), len(todo)))

    for b in range(0, len(todo), BATCH):
        chunk = todo[b:b + BATCH]
        try:
            d = api(action="query", titles="|".join(n.lstrip(":") for n in chunk),
                    prop="revisions", rvprop="content", rvslots="main", redirects="1")
        except Exception as e:
            print("  배치 실패: %s" % e)
            time.sleep(10)
            continue

        q = d.get("query", {})
        back = {n.lstrip(":"): n for n in chunk}
        for arr, a, bkey in (("normalized", "from", "to"), ("redirects", "from", "to")):
            for r in q.get(arr, []):
                if r[a] in back:
                    back[r[bkey]] = back[r[a]]

        for p in q.get("pages", {}).values():
            name = back.get(p.get("title"))
            if name is None:
                continue
            rev = (p.get("revisions") or [{}])[0]
            text = (rev.get("slots", {}).get("main", {}) or {}).get("*", "")
            cache[name] = parse_page(text) if text else {}
        for n in chunk:            # 없는 페이지도 표시해 두고 다시 받지 않는다
            cache.setdefault(n, {})

        sys.stderr.write("\r  %d/%d" % (min(b + BATCH, len(todo)), len(todo)))
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(2)
    sys.stderr.write("\n")

    have = {k: v for k, v in cache.items() if v}
    print("내용 있는 아이템 %d / %d" % (len(have), len(cache)))
    print("  설명 %d · 스탯 %d · 효과 %d · 퍽 %d"
          % (sum(1 for v in have.values() if v.get("description")),
             sum(1 for v in have.values() if v.get("stats")),
             sum(1 for v in have.values() if v.get("effects")),
             sum(1 for v in have.values() if v.get("perks"))))


if __name__ == "__main__":
    main()
