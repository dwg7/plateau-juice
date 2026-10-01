"""建築物CityGMLから属性だけを抽出し、建物単位のフラットなParquetにする。

幾何(ポリゴン)とGMLの個体識別子(gml:id, buildingID)は出力しない。位置は
lod0RoofEdgeの最初のリングの頂点平均(重心近似)の緯度経度と、タイル名(3次メッシュコード)のみ。
欠損センチネル値(9999, -9999, 0001, コードリストの「不明」)はNULLに変換する(DECISIONS D4)。
`attr_surveyed`: 用途・用途地域・階数・建築年のいずれかが判明していればTrue(D5)。
使い方: .venv/bin/python scripts/extract-attributes.py [--limit N]
"""
import argparse, re, sys
from multiprocessing import Pool
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "citygml" / "udx" / "bldg"
OUT = ROOT / "data" / "processed"

def tag(name):  # 最初の出現の値
    return re.compile(rf"<{name}(?:\s[^>]*)?>([^<]*)</{name}>")
SINGLE = {  # 列名: (タグ, 型, 不明を表す値)
    "bldg_class": ("bldg:class", str, {"9999"}),
    "usage": ("bldg:usage", str, {"461"}),
    "year_of_construction": ("bldg:yearOfConstruction", int, {1}),
    "measured_height": ("bldg:measuredHeight", float, {-9999}),
    "storeys_above": ("bldg:storeysAboveGround", int, {9999}),
    "storeys_below": ("bldg:storeysBelowGround", int, {9999}),
    "structure_type": ("uro:buildingStructureType", str, {"611"}),
    "fireproof_type": ("uro:fireproofStructureType", str, {"1011"}),
    "org_usage2": ("uro:orgUsage2", str, {"99"}),
    "zone_type": ("uro:districtsAndZonesType", str, {"99"}),
    "site_area": ("uro:siteArea", float, {-9999}),
    "total_floor_area": ("uro:totalFloorArea", float, {-9999}),
    "footprint_area": ("uro:buildingFootprintArea", float, {-9999}),
    "coverage_rate": ("uro:specifiedBuildingCoverageRate", float, {-9999}),
    "floor_area_rate": ("uro:specifiedFloorAreaRate", float, {-9999}),
    "survey_year": ("uro:surveyYear", int, {9999}),
}
SINGLE_RE = {k: (tag(t), typ, unk) for k, (t, typ, unk) in SINGLE.items()}
RISK_RE = re.compile(r"<uro:([A-Z]\w*RiskAttribute)>(.*?)</uro:\1>", re.S)
DEPTH_RE, RANK_RE = tag("uro:depth"), tag("uro:rank")
ROOF_RE = re.compile(r"<bldg:lod0RoofEdge>.*?<gml:posList[^>]*>([^<]*)</gml:posList>", re.S)
FOOT_RE = re.compile(r"<bldg:lod0FootPrint>.*?<gml:posList[^>]*>([^<]*)</gml:posList>", re.S)

def cast(v, typ, unk):
    try: x = typ(v.strip())
    except ValueError: return None
    return None if x in unk or (typ is float and x < 0 and -9999 in unk) else x

def parse_building(b, tile):
    r = {"tile": tile}
    for k, (rx, typ, unk) in SINGLE_RE.items():
        m = rx.search(b); r[k] = cast(m.group(1), typ, unk) if m else None
    m = ROOF_RE.search(b) or FOOT_RE.search(b)
    r["lat"] = r["lon"] = None
    if m:
        v = [float(x) for x in m.group(1).split()]
        pts = list(zip(v[0::3], v[1::3]))
        if pts: r["lat"] = sum(p[0] for p in pts) / len(pts); r["lon"] = sum(p[1] for p in pts) / len(pts)
    r["has_lod2"] = "<bldg:lod2Solid" in b or "<bldg:lod2MultiSurface" in b
    risks = RISK_RE.findall(b)
    r["risk_types"] = ",".join(sorted({n for n, _ in risks})) or None
    for n, label in (("RiverFloodingRiskAttribute", "flood"),):
        items = [body for nm, body in risks if nm == n]
        depths = [float(m.group(1)) for body in items if (m := DEPTH_RE.search(body))]
        ranks = [int(m.group(1)) for body in items if (m := RANK_RE.search(body)) and m.group(1).strip().isdigit()]
        r[f"{label}_n"] = len(items)
        r[f"{label}_max_depth"] = max(depths) if depths else None
        r[f"{label}_max_rank"] = max(ranks) if ranks else None
    r["n_risk_other"] = sum(1 for n, _ in risks if n != "RiverFloodingRiskAttribute")
    return r

def process(path):
    tile = path.name.split("_")[0]
    text = path.read_text(encoding="utf8")
    chunks = text.split("<bldg:Building ")[1:]
    rows = [parse_building(c.split("</bldg:Building>")[0], tile) for c in chunks]
    df = pd.DataFrame(rows)
    df["attr_surveyed"] = df[["usage", "zone_type", "storeys_above", "year_of_construction"]].notna().any(axis=1)
    return df

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int); a = ap.parse_args()
    files = sorted(SRC.glob("*_bldg_*.gml"))[: a.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    with Pool(4) as p:
        dfs = []
        for i, df in enumerate(p.imap_unordered(process, files), 1):
            dfs.append(df)
            if i % 50 == 0 or i == len(files): print(f"{i}/{len(files)}", flush=True)
    df = pd.concat(dfs, ignore_index=True).sort_values(["tile", "lat", "lon"]).reset_index(drop=True)
    for c in ["bldg_class", "usage", "structure_type", "fireproof_type", "org_usage2", "zone_type", "tile", "risk_types"]:
        df[c] = df[c].astype("category")
    for c in ["year_of_construction", "storeys_above", "storeys_below", "survey_year", "flood_max_rank"]:
        df[c] = df[c].astype("Int64")
    df.to_parquet(OUT / "sapporo_buildings.parquet", index=False)
    print(len(df), "buildings ->", OUT / "sapporo_buildings.parquet")
