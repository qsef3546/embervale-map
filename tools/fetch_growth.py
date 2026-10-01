#!/usr/bin/env python3
"""묘목이 어느 흙에서 얼마나 빨리 자라는지 위키에서 받아 cache-growth.json 에 모은다.

위키의 Growth 절은 두 가지 표 형식을 쓴다.
  새 형식  | 흙 || 선호도 || 시간   (줄마다 흙 하나)
  옛 형식  머리글에 흙을 늘어놓고 그 아래 한 줄에 시간만

사용
  python tools/fetch_growth.py
  python tools/fetch_growth.py --refetch
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
CACHE = os.path.join(HERE, "cache-growth.json")
API = "https://enshrouded.wiki.gg/api.php"
UA = "embervale-map-databuilder/1.0 (+https://github.com/qsef3546/embervale-map)"

CLEAN = [
    (re.compile(r"\{\{item\+icon\|([^}|]*)[^}]*\}\}"), r"\1"),
    (re.compile(r"\[\[([^\]|]*\|)?([^\]]*)\]\]"), r"\2"),
    (re.compile(r"\{\{PAGENAME\}\}"), "이 묘목"),
    (re.compile(r"'{2,}"), ""),
]


def api(**kw):
    kw.setdefault("format", "json")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw),
                                 headers={"User-Agent": UA})
    return json.load(urllib.request.urlopen(req, timeout=60))


def clean(s):
    for pat, rep in CLEAN:
        s = pat.sub(rep, s)
    return " ".join(s.split())


def parse_growth(text):
    # 문서마다 제목이 "Growth" 또는 "Growth Time" 으로 갈린다
    m = re.search(r"==\s*Growth(?:\s+Time)?\s*==(.*?)(\n==[^=]|\Z)", text, re.S)
    if not m:
        return None
    body = m.group(1)
    out = {}

    ground = re.search(r"require\s+([A-Za-z ]+?)\s+to grow", body)
    if ground:
        out["need"] = ground.group(1).strip()
    stages = re.search(r"through\s+(\d+)\s+growth stages?", body)
    if stages:
        out["stages"] = int(stages.group(1))

    tbl = re.search(r"\{\|(.*?)\|\}", body, re.S)
    if not tbl:
        return out or None
    rows = [r.strip() for r in tbl.group(1).split("|-")]
    soils = []

    # 새 형식: | 흙 || 선호도 || 시간
    for r in rows:
        for line in r.split("\n"):
            line = line.strip()
            if not line.startswith("|") or line.startswith("|+") or line.startswith("!"):
                continue
            cells = [clean(c) for c in re.split(r"\|\||\!\!", line.lstrip("|"))]
            if len(cells) == 3 and cells[1] in ("Preferred", "Neutral", "Reduced", "N/A"):
                soils.append([cells[0], cells[1], cells[2]])
    if soils:
        out["soils"] = soils
        return out

    # 옛 형식: 머리글 흙 목록 + 시간 한 줄
    heads, times = [], []
    for r in rows:
        for line in r.split("\n"):
            line = line.strip()
            if line.startswith("!"):
                heads += [clean(c) for c in re.split(r"\!\!", line.lstrip("!")) if clean(c)]
            elif line.startswith("|") and not line.startswith("|+"):
                times += [clean(c) for c in re.split(r"\|\|", line.lstrip("|"))]
    if heads and times and len(heads) == len(times):
        for s, t in zip(heads, times):
            soils.append([s, None, t])
        out["soils"] = soils
    return out or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    args = ap.parse_args()

    src = open(os.path.join(ROOT, "recipes.js"), encoding="utf-8").read()
    data = json.loads(src.split("window.EMBC=", 1)[1].rsplit(";", 1)[0])
    names = [it["n"] for it in data["items"]
             if it["n"].endswith(("Seedling", "Sapling"))]

    cache = {} if args.refetch or not os.path.exists(CACHE) \
        else json.load(open(CACHE, encoding="utf-8"))
    todo = [n for n in names if n not in cache]
    print("묘목 %d · 받을 것 %d" % (len(names), len(todo)))

    for b in range(0, len(todo), 40):
        chunk = todo[b:b + 40]
        try:
            d = api(action="query", titles="|".join(chunk), prop="revisions",
                    rvprop="content", rvslots="main", redirects="1")
        except Exception as e:
            print("  배치 실패: %s" % e)
            time.sleep(10)
            continue
        q = d.get("query", {})
        back = {n: n for n in chunk}
        for arr in ("normalized", "redirects"):
            for r in q.get(arr, []):
                if r["from"] in back:
                    back[r["to"]] = back[r["from"]]
        for p in q.get("pages", {}).values():
            name = back.get(p.get("title"))
            if name is None:
                continue
            rev = (p.get("revisions") or [{}])[0]
            txt = (rev.get("slots", {}).get("main", {}) or {}).get("*", "")
            cache[name] = parse_growth(txt) or {}
        for n in chunk:
            cache.setdefault(n, {})
        sys.stderr.write("\r  %d/%d" % (min(b + 40, len(todo)), len(todo)))
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(2)
    sys.stderr.write("\n")

    have = [v for v in cache.values() if v.get("soils")]
    print("흙 정보 있는 묘목 %d / %d" % (len(have), len(cache)))
    print("  자라는 땅 조건 %d · 성장 단계 %d"
          % (sum(1 for v in cache.values() if v.get("need")),
             sum(1 for v in cache.values() if v.get("stages"))))


if __name__ == "__main__":
    main()
