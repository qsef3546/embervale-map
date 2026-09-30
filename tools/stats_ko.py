#!/usr/bin/env python3
"""옵션(스탯·효과·종류) 이름을 한글로 옮긴다. build_recipes.py 가 쓴다."""
import re

STAT_KO = {
    "Physical": "물리 저항", "Magical": "마법 저항", "Cutting": "절삭 저항",
    "Duration": "지속시간", "Damage": "피해", "Element Type": "속성",
    "Damage Type": "속성", "Durability": "내구도", "Mana Cost": "마나 소모",
    "Cast Time": "시전 시간", "Stamina Cost": "기력 소모",
    "Stamina per Second": "초당 기력", "Block": "막기", "Parry Power": "쳐내기",
    "parryPower": "쳐내기", "Range": "사거리", "Speed": "속도", "Healing": "치유",
    "Fishing Strength": "낚시 힘", "Fishing Endurance": "낚시 지구력",
    "weaponType": "무기 종류", "level": "레벨", "attackSpeed": "공격 속도",
    "drawSpeed": "당기는 속도", "arrowSpeed": "화살 속도", "source": "획득",
}
# 물리/마법/절삭은 방어구에서만 저항이라 순서를 앞에 둔다
STAT_ORDER = ["weaponType", "level", "Physical", "Magical", "Cutting", "Damage",
              "Element Type", "Damage Type", "Healing", "Duration", "attackSpeed",
              "drawSpeed", "arrowSpeed", "Speed", "Range", "Block", "Parry Power",
              "parryPower", "Cast Time", "Mana Cost", "Stamina Cost",
              "Stamina per Second", "Durability", "Fishing Strength",
              "Fishing Endurance", "source"]

ELEMENT_KO = {"Blunt": "타격", "Cutting": "절삭", "Piercing": "관통", "Fire": "화염",
              "Ice": "냉기", "Heal": "치유", "Poison": "독", "Shock": "전격",
              "Shroud": "어둠의 안개"}

TYPE_KO = {
    "Arm Armor": "팔 방어구", "Arm Cosmetic": "팔 치장", "Arrow": "화살", "Bow": "활",
    "Bow Ammo": "활 탄약", "Bow Ammunition": "활 탄약", "Bow ammo": "활 탄약",
    "Building Materials": "건축 자재", "Building Tool": "건축 도구",
    "Collectible": "수집품", "Comfort": "안락", "Construction Tools": "건설 도구",
    "Consumable": "소모품", "Consumables": "소모품", "Daggers": "단검",
    "Doors": "문", "Equipment": "장비", "Essential": "필수품",
    "Fishing Baits": "낚시 미끼", "Flame Altar": "화염 제단",
    "Foot Armor": "발 방어구", "Foot Cosmetic": "발 치장", "Furniture": "가구",
    "Generic Item": "일반 아이템", "Glider": "글라이더", "Grappling Hook": "갈고리",
    "Head Armor": "머리 방어구", "Head Cosmetic": "머리 치장", "Hearth": "화로",
    "Level 1 Workbench": "1단계 작업대", "Lower Body Armor": "하체 방어구",
    "Lower Body Cosmetic": "하체 치장", "Material": "재료", "Materials": "재료",
    "Mid-range Weapon": "중거리 무기", "Miscellaneous": "기타",
    "One-handed Axe": "한손 도끼", "One-handed Club": "한손 곤봉",
    "One-handed Sword": "한손 검", "Overgrowth Material": "증식 자재",
    "Potted Plant": "화분 식물", "Resources": "자원", "Roof Materials": "지붕 자재",
    "Secret Doors": "비밀 문", "Seedlings": "묘목", "Shield": "방패",
    "Spell": "주문", "Spells": "주문", "Staff": "지팡이",
    "Terrain Materials": "지형 자재", "Throwable": "투척물", "Tools": "도구",
    "Upper Body Armor": "상체 방어구", "Upper Body Cosmetic": "상체 치장",
    "Wand": "마법봉", "Weapon": "무기",
    "Two-handed Axe": "양손 도끼", "Two-handed Sword": "양손 검",
    "Two-handed Club": "양손 곤봉", "Two-Handed Hammer": "양손 망치",
}

EFFECT_KO = {
    "Health": "체력", "Health Regeneration": "체력 재생", "Stamina": "기력",
    "Stamina Regeneration": "기력 재생", "Stamina Regemeration": "기력 재생",
    "Stamina Recharge": "기력 재생", "Mana": "마나", "Mana Regeneration": "마나 재생",
    "Mana per second": "초당 마나", "Frost Resistance": "냉기 저항",
    "Ice Resistance": "냉기 저항", "Fire Resistance": "화염 저항",
    "Poison Resistance": "독 저항", "Poison resistance": "독 저항",
    "Shock Resistance": "전격 저항", "Shroud Resistance": "어둠의 안개 저항",
    "Maximum Oxygen": "최대 산소", "Melee Damage": "근접 피해",
    "Ranged Damage": "원거리 피해", "Ranged damage": "원거리 피해",
    "Magic Damage": "마법 피해", "Magic damage": "마법 피해",
    "Dagger Damage": "단검 피해", "Bow Damage": "활 피해",
    "Staff Damage": "지팡이 피해", "Wand Damage": "마법봉 피해",
    "One-Handed Melee Damage": "한손 근접 피해",
    "Two-Handed Melee Damage": "양손 근접 피해",
    "Critical Strike Damage": "치명타 피해", "Critical Strike Chance": "치명타 확률",
    "Melee Critical Strike Chance": "근접 치명타 확률",
    "Ranged Critical Strike Chance": "원거리 치명타 확률",
    "Magical Critical Strike Chance": "마법 치명타 확률",
    "Skillshot Damage": "스킬샷 피해", "Backstabbing Damage": "배후 공격 피해",
    "Backstabbing damage": "배후 공격 피해", "Sneak Attack Damage": "은신 공격 피해",
    "Sneak Speed": "은신 이동 속도", "Sprint Speed": "질주 속도",
    "Swim Sprint Speed": "수영 질주 속도",
    "Merciless Attack Damage": "무자비한 공격 피해",
    "Merciless Strike Damage": "무자비한 공격 피해", "Healing": "치유",
    "Healing Per Second": "초당 치유", "Healing per second": "초당 치유",
    "HP Restored": "체력 회복", "MP Restored": "마나 회복",
    "Revive Heal Percentage": "부활 회복량", "Block": "막기",
    "Parry Power": "쳐내기", "Constitution": "체격", "Endurance": "지구력",
    "Metal Mining Strength": "금속 채굴 힘", "Stone Mining Strength": "암석 채굴 힘",
    "Time in the Shroud": "어둠의 안개 체류 시간",
    "Time In The Shroud": "어둠의 안개 체류 시간",
    "Time in the shroud": "어둠의 안개 체류 시간",
    "Wet Duration Reduction": "젖음 지속 감소",
    "Health Regeneration Delay": "체력 재생 지연",
    "Mana Regeneration Delay": "마나 재생 지연",
    "Stamina Regeneration Delay": "기력 재생 지연",
    "Revive Duration": "부활 시간", "Rested": "휴식",
    "Stamina Depletion Swim Sprinting": "수영 질주 기력 소모",
    "Life Leech Chance against Hollow": "망자 상대 생명 흡수 확률",
    "Fell Curse Protection": "펠 저주 보호", "Hemotoxin Protection": "혈액독 보호",
    "Blazing Skin": "타오르는 피부", "Cure poison": "독 해제", "Remedied": "치료됨",
    "Provides light around consumer": "주변을 밝힘",
    "Fire Magic Damage while Enshrouded": "안개 속 화염 마법 피해",
    "Ranged Damage while Enshrouded": "안개 속 원거리 피해",
    "Two-Handed Melee Damage while Enshrouded": "안개 속 양손 근접 피해",
    "Damage against Drak": "드락 상대 피해",
    "Damage against Hollow": "망자 상대 피해",
    "Damage against Scavengers": "약탈자 상대 피해",
    "Damage against Magical enemies": "마법형 적 상대 피해",
    "Damage against Melee enemies": "근접형 적 상대 피해",
    "Damage Against Melee enemies": "근접형 적 상대 피해",
    "Damage against Melee Foes": "근접형 적 상대 피해",
    "Damage against Ranged enemies": "원거리형 적 상대 피해",
    "Damage against Wildlife and Wildbeasts": "야생동물 상대 피해",
    "Damage against shroud": "어둠의 안개 상대 피해",
}

# 숫자·기호·단위를 앞에서 떼어 낸다. 남는 말이 효과 이름이다.
NUM = re.compile(r"^\s*([+\-−]?)\s*([\d.]+(?::\d+)?)\s*(%|s\b|min\.?|m\b)?\s*(.*)$")
UNIT_KO = {"%": "%", "s": "초", "min": "분", "min.": "분", "m": "분"}


def effect(text):
    """'+ 12 Health Regeneration' → ('체력 재생', '+12')"""
    m = NUM.match(text)
    if not m:
        return EFFECT_KO.get(text.strip(), text.strip()), ""
    sign, num, unit, rest = m.groups()
    rest = rest.strip()
    # 'min Wet Duration Reduction' 처럼 단위가 이름 앞에 붙어 있는 경우
    for u in ("min.", "min", "s", "m"):
        if not unit and rest.startswith(u + " "):
            unit, rest = u, rest[len(u) + 1:].strip()
            break
    label = EFFECT_KO.get(rest, rest)
    val = ("−" if sign in "-−" else "+") + num + (UNIT_KO.get(unit, unit or ""))
    return label, val


def element(v):
    """'CuttingPiercingPoison' / 'Cutting/Blunt' → '절삭·관통·독'"""
    parts = re.findall(r"[A-Z][a-z]+", v) or [v]
    return "·".join(dict.fromkeys(ELEMENT_KO.get(p, p) for p in parts))


SOURCE_KO = {"Craftable": "제작 가능", "Looted": "전리품",
             "Lore Weapon, Craftable": "전설 무기 · 제작 가능"}
PERK_KO = {"Brutal": "잔혹", "Cutting Damage": "절삭 피해", "Health Leech": "생명 흡수",
           "Magic Fire Damage": "마법 화염 피해", "Piercing Damage": "관통 피해",
           "Renewal": "재생"}
# 0.6s → 0.6초, 10min → 10분, 1h → 1시간, Instant → 즉시
TIME_RE = re.compile(r"^([\d.:]+)\s*(s|m|min|h)$", re.I)


def perk(p):
    return PERK_KO.get(p, p)


def timeval(v):
    if v.strip().lower() == "instant":
        return "즉시"
    m = TIME_RE.match(v.strip())
    if m:
        unit = {"s": "초", "m": "분", "min": "분", "h": "시간"}[m.group(2).lower()]
        return m.group(1) + unit
    return v


def stat(key, value):
    label = STAT_KO.get(key, key)
    if key in ("Element Type", "Damage Type"):
        value = element(value)
    elif key == "weaponType":
        value = TYPE_KO.get(value, value)
    elif key == "source":
        value = SOURCE_KO.get(value, value)
    elif key in ("Duration", "attackSpeed", "drawSpeed", "arrowSpeed", "Cast Time"):
        value = timeval(value)
    return label, value


def stats_list(d):
    """정해 둔 순서대로 (이름, 값) 목록을 만든다."""
    out, seen = [], set()
    for k in STAT_ORDER:
        if k in d and k not in seen:
            seen.add(k)
            out.append(stat(k, d[k]))
    for k, v in d.items():
        if k not in seen:
            out.append(stat(k, v))
    return out
