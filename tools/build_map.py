#!/usr/bin/env python3
"""지도 데이터(data.js) 생성기 / 위키 갱신 점검기.

입력
  1. enshrouded.wiki.gg DataMaps 페이지 `Map:Embervale/*` — 마커 좌표·이름·설명
  2. tools/map.ko.json — 영문 이름·설명 → 한글 (손으로 채우는 사전)

사용
  python tools/build_map.py --check     # 위키가 data.js 와 달라졌는지만 본다 (파일을 쓰지 않음)
                                        #   exit 0 = 같음, 10 = 달라짐
  python tools/build_map.py             # 캐시(tools/cache-map/)로 data.js 재생성, 캐시가 없으면 받는다
  python tools/build_map.py --refetch   # 위키에서 다시 받아 재생성

새 마커의 이름·설명이 map.ko.json 에 없으면 영문 그대로 들어가고, 목록을 tools/map.untranslated.json 에 남긴다.
그 파일의 값을 채워 map.ko.json 에 옮긴 뒤 다시 실행하면 된다.
"""
import argparse
import base64
import collections
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache-map")
KO = os.path.join(HERE, "map.ko.json")
UNTRANSLATED = os.path.join(HERE, "map.untranslated.json")
OUT = os.path.join(ROOT, "data.js")

WIKI = "https://enshrouded.wiki.gg"
UA = "embervale-map-databuilder/1.0 (+https://github.com/qsef3546/embervale-map)"
ROOT_PAGE = "Map:Embervale"
GROUP_PAGES = ["Map:Embervale/Groups", "Map:Embervale/Lore-Groups"]

# ── 분류 ─────────────────────────────────────────────────────────────
S1, S2, S3, S4, S5 = "주요 장소", "거점·자원", "수집품", "기록", "기타"
# 위키 그룹 id: (한글명, 섹션, 글리프, 색, 기본 표시, 진행 추적, 작은 아이콘)
GROUPS = {
    "Ancient_Spire":  ("고대 첨탑", S1, "spire", "#7cc4e4", 1, 1, 0),
    "Flame_Shrine":   ("화염 성소", S1, "flame", "#ef7a45", 1, 1, 0),
    "Sun_Temple":     ("태양 사원", S1, "sun", "#f0c24b", 1, 1, 0),
    "Night_Sanctum":  ("밤의 성소", S1, "moon", "#8fa3e8", 1, 1, 0),
    "Ancient_Vault":  ("고대 금고", S1, "vault", "#d9b35a", 1, 1, 0),
    "Ancient_Obelisk": ("고대 오벨리스크", S1, "obelisk", "#b8c7d6", 1, 1, 0),
    "Elixir_Well":    ("영약 우물", S1, "drop", "#6fd0b8", 1, 1, 0),
    "Shroud_Root":    ("어둠의 안개 뿌리", S1, "star", "#b08cf0", 1, 1, 0),
    "Balefire":       ("봉화", S1, "bale", "#ff9a5c", 1, 1, 0),
    "Hollow_Halls":   ("망자의 전당", S1, "hall", "#c58be0", 1, 1, 0),
    "Hidden_Temple":  ("기타 던전", S1, "door", "#d06a6a", 1, 0, 0),
    "Tomb":           ("숨겨진 무덤", S1, "cross", "#bba77c", 1, 1, 0),
    "Shroud_Lair":    ("어둠의 안개 소굴", S1, "skull", "#9d6fd6", 1, 0, 0),
    "Cave_Passage":   ("동굴 통로", S1, "cave", "#a9a592", 0, 0, 0),
    "Gem_Forge":      ("보석 세공소", S2, "gem", "#5fd0e8", 1, 0, 0),
    "Village":        ("마을", S2, "house", "#e8d27a", 1, 0, 0),
    "Camp":           ("야영지", S2, "tent", "#c9b38a", 0, 0, 0),
    "Farm":           ("농장", S2, "wheat", "#a6cf6b", 0, 0, 0),
    "Mine":           ("광산", S2, "pick", "#b5a08a", 0, 0, 0),
    "Enemy_Camp":     ("적 야영지", S2, "swords", "#e25555", 0, 0, 0),
    "Fossil":         ("화석", S3, "shell", "#e0c49a", 0, 1, 1),
    "Music_Sheet":    ("악보", S3, "note", "#f2a0c0", 0, 1, 1),
    "QueenPikemeadStatuePiece": ("파이크미드 여왕 조각상 조각", S3, "statue", "#d8d0c0", 0, 1, 1),
    "AlchemistWallHanging": ("연금술사의 벽걸이 장식", S3, "banner", "#7fd6a0", 0, 1, 1),
    "CyclopsSkeleton": ("사이클롭스 해골", S3, "bone", "#e8e2d0", 0, 1, 1),
    "WallTapestry":   ("벽 태피스트리", S3, "banner", "#d88f6a", 0, 1, 1),
    "DragonsMapPiece": ("용의 지도 조각", S3, "mappiece", "#e0b060", 0, 1, 1),
    "DrakRelief":     ("드락 부조", S3, "relief", "#a0b8a0", 0, 1, 1),
    "LoreGeneral":    ("일반", S4, "book", "#c8c0a8", 0, 1, 1),
    "LoreAncientsandtheFlame": ("고대인과 화염", S4, "book", "#f0a060", 0, 1, 1),
    "LoreTheShroudElixirandElixirWell": ("어둠의 안개·영약", S4, "book", "#b090e8", 0, 1, 1),
    "LoreScavengers": ("약탈자", S4, "book", "#d08070", 0, 1, 1),
    "LoreVukahandWildlife": ("부카와 야생동물", S4, "book", "#a0c880", 0, 1, 1),
    "LoreNoblesandHistory": ("귀족과 역사", S4, "book", "#e0c870", 0, 1, 1),
    "LoreRevelwood":  ("레벨우드", S4, "book", "#70b080", 0, 1, 1),
    "LoreNomadHighlands": ("유목민 고원", S4, "book", "#c0b880", 0, 1, 1),
    "LoreKindlewastes": ("불타는 황무지", S4, "book", "#e0a860", 0, 1, 1),
    "LoreHollow":     ("망자", S4, "book", "#c58be0", 0, 1, 1),
    "LoreAlbaneveSummits": ("알바네브 봉우리", S4, "book", "#c8d8e8", 0, 1, 1),
    "LoreVeilwaterBasin": ("베일워터 분지", S4, "book", "#70c0b8", 0, 1, 1),
    "LoreDrak":       ("드락", S4, "book", "#a0b8a0", 0, 1, 1),
    "QuestLocation":  ("퀘스트 위치", S5, "quest", "#ffd257", 1, 0, 0),
}
# 처음 보는 위키 그룹은 이 모양으로 넣고 경고한다
UNKNOWN_GROUP = (None, S5, "quest", "#9aa0ad", 1, 0, 0)

# 지역: id, 한글, 영문, 바탕색, 설명·이름·id 에서 지역을 알아보는 패턴
REGIONS = [
    ("spring", "스프링랜드", "Springlands", [112, 146, 78], r"Springlands|Low Meadows"),
    ("revel", "레벨우드", "Revelwood", [60, 104, 68], r"Revelwood"),
    ("nomad", "유목민 고원", "Nomad Highlands", [150, 146, 98], r"Nomad Highlands"),
    ("kindle", "불타는 황무지", "Kindlewastes", [198, 156, 92], r"Kindlewastes"),
    ("alba", "알바네브 봉우리", "Albaneve Summits", [206, 213, 222], r"Albaneve"),
    ("veil", "베일워터 분지", "Veilwater Basin", [78, 134, 128], r"Veilwater"),
    ("black", "검은 수렁", "Blackmire", [80, 90, 74], r"Blackmire"),
    ("cradle", "재의 요람", "Cinder's Cradle", [112, 70, 62], r"Cinder['’]s Cradle"),  # 1.0 신규
]
LORE_GROUP_REGION = {"LoreRevelwood": "revel", "LoreNomadHighlands": "nomad", "LoreKindlewastes": "kindle",
                     "LoreAlbaneveSummits": "alba", "LoreVeilwaterBasin": "veil"}

BOUNDS = [1600, 9800, 400, 8300]   # 위키 좌표 x0, x1, y0, y1 (y 는 위쪽이 큼). 마커가 넘으면 넓힌다
PAD, RASTER_N, LAND_RADIUS = 700, 220, 520

# 게임 공식 한국어판 표기로 용어 통일 (번역을 새로 넣을 때도 같은 기준을 지키게)
OFFICIAL = [
    ("슈라우드에 잠긴", "어둠의 안개에 뒤덮인"), ("슈라우드에 뒤덮인", "어둠의 안개에 뒤덮인"),
    ("슈라우드 뿌리", "어둠의 안개 뿌리"), ("슈라우드 소굴", "어둠의 안개 소굴"), ("슈라우드", "어둠의 안개"),
    ("엘릭서 우물", "영약 우물"), ("엘릭서", "영약"), ("할로우 홀", "망자의 전당"),
    ("밤의 성역", "밤의 성소"), ("화염 성역", "화염 성소"), ("태양 신전", "태양 사원"),
    ("보석 대장간", "보석 세공소"), ("베일파이어", "봉화"), ("불꽃의 자손", "화염의 후예"),
    ("봄의 땅", "스프링랜드"), ("레블우드", "레벨우드"), ("알바네브 산맥", "알바네브 봉우리"),
    ("킨들웨이스트", "불타는 황무지"), ("블랙마이어", "검은 수렁"), ("신더스 크레이들", "재의 요람"),
]
PARTICLES = [("으로", "로"), ("은", "는"), ("이", "가"), ("을", "를"), ("과", "와")]


def has_batchim(ch):
    return "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0


def officialize(s):
    for old, new in OFFICIAL:
        if old not in s:
            continue
        out, i = [], 0
        while True:
            j = s.find(old, i)
            if j < 0:
                out.append(s[i:])
                break
            out.append(s[i:j] + new)
            i = j + len(old)
            for a, b in PARTICLES:   # 바뀐 단어 뒤 조사를 받침에 맞춘다
                hit = next((c for c in (a, b) if s.startswith(c, i)
                            and (i + len(c) == len(s) or not "가" <= s[i + len(c)] <= "힣")), None)
                if hit:
                    out.append(a if has_batchim(new[-1]) else b)
                    i += len(hit)
                    break
        s = "".join(out)
    s = re.sub(r"(?<![가-힣])펠 (?=[가-힣])", "어둠의 ", s)
    fix = {"": "", "이": "이", "가": "이", "을": "을", "를": "을", "은": "은", "는": "은",
           "과": "과", "와": "과", "의": "의", "들": "들"}
    s = re.sub(r"(?<![가-힣])펠(이|가|을|를|은|는|과|와|의|들)?(?![가-힣])",
               lambda m: "어둠의 적" + fix[m.group(1) or ""], s)
    return s.replace("망자 이브", "망자의 전야")


def clean(s):
    """위키 마크업 제거: [[대상|표시]] → 표시, [[대상]] → 대상, '''굵게''' → 굵게"""
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    return s.replace("'''", "").replace("''", "")


# ── 위키 ─────────────────────────────────────────────────────────────
def fetch_page(title):
    url = WIKI + "/wiki/" + urllib.parse.quote(title) + "?action=raw"
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
        except Exception as e:
            if attempt == 5:
                raise SystemExit("위키에서 %s 를 받지 못했습니다: %s" % (title, e))
            time.sleep(8)


def fetch_all():
    """루트 페이지의 include 를 따라 필요한 페이지를 모두 받는다. {제목: JSON}"""
    pages = {ROOT_PAGE: fetch_page(ROOT_PAGE)}
    for t in pages[ROOT_PAGE].get("include", []) + GROUP_PAGES:
        if t not in pages:
            time.sleep(1.5)
            pages[t] = fetch_page(t)
    return pages


def cache_path(title):
    return os.path.join(CACHE, title.replace(":", "_").replace("/", "_") + ".json")


def load_cache():
    pages = {}
    root = json.load(open(cache_path(ROOT_PAGE), encoding="utf-8"))
    pages[ROOT_PAGE] = root
    for t in root.get("include", []) + GROUP_PAGES:
        pages[t] = json.load(open(cache_path(t), encoding="utf-8"))
    return pages


def save_cache(pages):
    os.makedirs(CACHE, exist_ok=True)
    for t, d in pages.items():
        json.dump(d, open(cache_path(t), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def collect(pages):
    """마커 목록과 위키 그룹 이름."""
    wiki_groups = {}
    for d in pages.values():
        wiki_groups.update(d.get("groups") or {})
    markers = []
    for t in pages[ROOT_PAGE].get("include", []):
        for g, lst in (pages[t].get("markers") or {}).items():
            for m in lst:
                markers.append({"g": g, **m})
    return markers, wiki_groups


# ── data.js 와 비교 ──────────────────────────────────────────────────
def load_site():
    t = open(OUT, encoding="utf-8").read()
    return json.loads(t[t.index("window.EMB=") + 11:].rstrip().rstrip(";"))


def diff_against_site(markers):
    site = load_site()
    old = {m[0]: (m[1], m[2], m[3], site["str"][m[4]][0] if m[4] >= 0 else "") for m in site["markers"]}
    new = {m["id"]: (m["g"], m["x"], m["y"], clean(m.get("name") or "")) for m in markers}
    return {
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "moved": sorted(k for k in set(new) & set(old) if new[k][:3] != old[k][:3]),
        "renamed": sorted(k for k in set(new) & set(old) if new[k][3] != old[k][3]),
        "new_groups": sorted({m["g"] for m in markers} - set(GROUPS)),
        "count": (len(old), len(new)),
    }


# ── 지역 분류·지형 래스터 ─────────────────────────────────────────────
def classify(markers):
    ids = [r[0] for r in REGIONS]
    lab = {}
    for m in markers:
        if m["g"] in LORE_GROUP_REGION:
            lab[m["id"]] = LORE_GROUP_REGION[m["g"]]
            continue
        t = " ".join(str(m.get(k) or "") for k in ("description", "name", "id"))
        hits = {rid for rid, _, _, _, pat in REGIONS if re.search(pat, t)}
        if len(hits) == 1:
            lab[m["id"]] = hits.pop()
    L = [(m["x"], m["y"], lab[m["id"]]) for m in markers if m["id"] in lab]

    def knn(x, y, k=7):
        near = sorted(L, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)[:k]
        c = collections.Counter()
        for px, py, r in near:
            c[r] += 1 / (1 + math.hypot(px - x, py - y))
        return c.most_common(1)[0][0]

    region = {m["id"]: lab.get(m["id"]) or knn(m["x"], m["y"]) for m in markers}
    for m in markers:   # 주변 대다수와 홀로 다른 라벨은 이웃을 따른다
        if m["id"] in lab:
            k = knn(m["x"], m["y"], 9)
            if k != region[m["id"]]:
                near = sorted(L, key=lambda p: (p[0] - m["x"]) ** 2 + (p[1] - m["y"]) ** 2)[1:9]
                if sum(1 for p in near if p[2] == region[m["id"]]) <= 1:
                    region[m["id"]] = k
    print("지역 라벨 %d/%d (나머지는 이웃으로 추정) %s" % (len(lab), len(markers), dict(collections.Counter(region.values()))))
    return region, ids


def raster(markers, region, ids):
    # 마커가 기존 경계 300 안쪽까지 붙을 때만 그 방향으로 넓힌다 (재의 요람처럼 새 지역이 바깥에 생길 때)
    x0, x1, y0, y1 = BOUNDS
    mx0, mx1 = min(m["x"] for m in markers), max(m["x"] for m in markers)
    my0, my1 = min(m["y"] for m in markers), max(m["y"] for m in markers)
    if mx0 < x0 + 300: x0 = mx0 - PAD
    if mx1 > x1 - 300: x1 = mx1 + PAD
    if my0 < y0 + 300: y0 = my0 - PAD
    if my1 > y1 - 300: y1 = my1 + PAD
    N = RASTER_N
    pts = [(m["x"], m["y"], region[m["id"]]) for m in markers]
    cell, CS = collections.defaultdict(list), 400
    for p in pts:
        cell[(int(p[0] // CS), int(p[1] // CS))].append(p)
    grid = bytearray(N * N)
    for j in range(N):
        wy = y1 - (j + .5) / N * (y1 - y0)
        for i in range(N):
            wx = x0 + (i + .5) / N * (x1 - x0)
            cx, cy = int(wx // CS), int(wy // CS)
            near = [p for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2) for p in cell.get((cx + dx, cy + dy), [])]
            if not near:
                continue
            near.sort(key=lambda p: (p[0] - wx) ** 2 + (p[1] - wy) ** 2)
            if math.hypot(near[0][0] - wx, near[0][1] - wy) > LAND_RADIUS:
                continue
            c = collections.Counter()
            for p in near[:6]:
                c[p[2]] += 1 / (1 + math.hypot(p[0] - wx, p[1] - wy))
            grid[j * N + i] = ids.index(c.most_common(1)[0][0]) + 1

    def neigh(g, i, j):
        return [g[b * N + a] for a in (i - 1, i, i + 1) for b in (j - 1, j, j + 1) if 0 <= a < N and 0 <= b < N]
    for _ in range(3):   # 구멍 메우기
        g2 = bytearray(grid)
        for j in range(N):
            for i in range(N):
                if grid[j * N + i] == 0:
                    nb = [v for v in neigh(grid, i, j) if v]
                    if len(nb) >= 5:
                        g2[j * N + i] = collections.Counter(nb).most_common(1)[0][0]
        grid = g2
    g2 = bytearray(grid)   # 과반 필터로 경계 매끄럽게
    for j in range(N):
        for i in range(N):
            if grid[j * N + i]:
                nb = [v for v in neigh(grid, i, j) if v]
                g2[j * N + i] = collections.Counter(nb).most_common(1)[0][0]
    grid = g2
    centers = {}
    for rid in ids:
        xs = sorted(p[0] for p in pts if p[2] == rid)
        ys = sorted(p[1] for p in pts if p[2] == rid)
        if xs:
            centers[rid] = [xs[len(xs) // 2], ys[len(ys) // 2], len(xs)]
    return {"bounds": [x0, x1, y0, y1], "n": N, "ids": ids,
            "grid": base64.b64encode(bytes(grid)).decode(), "centers": centers}


# ── 생성 ─────────────────────────────────────────────────────────────
def build(pages, out_path):
    markers, wiki_groups = collect(pages)
    ko = json.load(open(KO, encoding="utf-8")) if os.path.exists(KO) else {}
    region, ids = classify(markers)
    ras = raster(markers, region, ids)

    used = {m["g"] for m in markers}
    unknown = sorted(used - set(GROUPS))
    if unknown:
        print("처음 보는 위키 그룹 %d개 — '기타'로 넣었습니다. GROUPS 에 자리를 잡아 주세요: %s" % (len(unknown), unknown))
    order = list(GROUPS) + unknown
    groups = []
    for gid in order:
        if gid not in used:
            continue
        en = (wiki_groups.get(gid, {}).get("name") or gid).replace("Lore: ", "")
        v = GROUPS.get(gid) or ((ko.get(en) or en),) + UNKNOWN_GROUP[1:]
        groups.append({"id": gid, "ko": v[0], "en": en, "sec": v[1], "glyph": v[2], "color": v[3],
                       "def": bool(v[4]), "track": bool(v[5]), "small": bool(v[6])})

    regions = {rid: {"ko": k, "en": e, "rgb": rgb, "c": ras["centers"].get(rid)} for rid, k, e, rgb, _ in REGIONS}

    strs, idx, missing = [], {}, {}

    def si(s):
        if not s:
            return -1
        en = clean(s)
        if en not in idx:
            idx[en] = len(strs)
            k = ko.get(en)
            if k is None:
                missing[en] = ""
            strs.append([en, officialize(k) if k and k != en else ""])
        return idx[en]
    rows = [[m["id"], m["g"], m["x"], m["y"], si(m.get("name")), si(m.get("description")),
             region[m["id"]], m.get("article") or ""] for m in markers]

    data = {"source": "The Official Enshrouded Wiki (enshrouded.wiki.gg) — CC BY-NC-SA 3.0, 한국어 번역·가공",
            "groups": groups, "regions": regions, "raster": ras, "str": strs, "markers": rows}
    header = ("/*! 엠버베일 한글 지도 데이터\n"
              " * 마커 좌표·이름·설명: The Official Enshrouded Wiki 기여자 (https://enshrouded.wiki.gg/wiki/Map)\n"
              " * 한국어 번역·지역 분류·지형 래스터는 이 저장소에서 가공했습니다.\n"
              " * 라이선스: CC BY-NC-SA 3.0 (https://creativecommons.org/licenses/by-nc-sa/3.0/)\n"
              " * Enshrouded 콘텐츠의 권리는 Keen Games GmbH에 있습니다. */\n")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "window.EMB=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    if missing:
        json.dump(missing, open(UNTRANSLATED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("번역 없는 문장 %d개 → %s 에 채워 map.ko.json 으로 옮기세요" % (len(missing), os.path.relpath(UNTRANSLATED, ROOT)))
    elif os.path.exists(UNTRANSLATED):
        os.remove(UNTRANSLATED)
    print("그룹 %d · 마커 %d · 문장 %d (한글 %d) → %s" % (len(groups), len(rows), len(strs),
          sum(1 for s in strs if s[1] or s[0] in ko), os.path.relpath(out_path, ROOT)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="위키와 data.js 차이만 보고 아무 파일도 쓰지 않는다")
    ap.add_argument("--refetch", action="store_true", help="위키에서 다시 받는다")
    ap.add_argument("--out", default=OUT, help="출력 경로 (기본: data.js)")
    args = ap.parse_args()

    if args.check:
        pages = fetch_all()
        markers, _ = collect(pages)
        d = diff_against_site(markers)
        changed = any(d[k] for k in ("added", "removed", "moved", "renamed", "new_groups"))
        print("위키 지도 페이지: %s" % ", ".join(pages[ROOT_PAGE].get("include", [])))
        print("마커: 사이트 %d · 위키 %d" % d["count"])
        for k, label in (("added", "추가"), ("removed", "삭제"), ("moved", "이동·분류 변경"),
                         ("renamed", "이름 변경"), ("new_groups", "새 그룹")):
            print("  %s %d%s" % (label, len(d[k]), (" — " + ", ".join(d[k][:15])) if d[k] else ""))
        print("결과: %s" % ("달라짐 — 재생성이 필요합니다" if changed else "같음"))
        sys.exit(10 if changed else 0)

    if args.refetch or not os.path.exists(cache_path(ROOT_PAGE)):
        pages = fetch_all()
        save_cache(pages)
    else:
        pages = load_cache()
    build(pages, args.out)


if __name__ == "__main__":
    main()
