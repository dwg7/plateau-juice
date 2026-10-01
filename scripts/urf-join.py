"""建物の重心(lat/lon)を都市計画決定情報(udx/urf)のポリゴンと空間結合し、区域情報の列を足す。

追加列:
  urban_planning_area : 都市計画区域内か(bool)
  area_class          : 区域区分 22=市街化区域, 23=市街化調整区域, 99=不明, NULL=区域区分ポリゴン外
  urf_zone            : 用途地域ポリゴンのコード(1-13、建物属性zone_typeと同じコード体系)。NULL=用途地域ポリゴン外
  zone_boundary_dist_m: 重心から、入っている用途地域ポリゴンの境界までの距離(m、札幌付近の局所近似)。境界付近の見かけ上の不一致の除外に使う
ポリゴンは結合の計算にだけ使い、出力には残さない(幾何は保持しない方針)。
出力: data/processed/sapporo_buildings_urf.parquet
"""
import re
from pathlib import Path
import numpy as np, pandas as pd
from shapely import STRtree, points
from shapely.geometry import Polygon
from shapely.ops import transform

LAT0 = 43.06
KX, KY = 111320 * np.cos(np.radians(LAT0)), 110950  # 度→m(札幌付近の局所近似)
def to_m(x, y, z=None): return (x * KX, y * KY)

R = Path(__file__).resolve().parent.parent
URF = R / "data/raw/citygml/udx/urf"
FEAT = re.compile(r"<urf:(UrbanPlanningArea|AreaClassification|UseDistrict) gml:id=[^>]*>(.*?)</urf:\1>", re.S)
FUNC = re.compile(r"<urf:function [^>]*>([^<]*)</urf:function>")
POLY = re.compile(r"<gml:Polygon[^>]*>(.*?)</gml:Polygon>", re.S)
EXT = re.compile(r"<gml:exterior>.*?<gml:posList[^>]*>([^<]*)</gml:posList>", re.S)
INT = re.compile(r"<gml:interior>.*?<gml:posList[^>]*>([^<]*)</gml:posList>", re.S)

def ring(s):
    v = np.array(s.split(), dtype=float)
    d = 3 if len(v) % 3 == 0 else 2
    v = v.reshape(-1, d)
    return [(x[1], x[0]) for x in v]  # (lon, lat)

def load(kind):
    polys, codes = [], []
    for f in sorted(URF.glob("*.gml")):
        for k, body in FEAT.findall(f.read_text(encoding="utf8")):
            if k != kind: continue
            code = FUNC.search(body).group(1).strip()
            for p in POLY.findall(body):
                e = EXT.search(p)
                if e: polys.append(Polygon(ring(e.group(1)), [ring(i) for i in INT.findall(p)]).buffer(0)); codes.append(code)
    return polys, codes

def assign(pts, kind, want_dist=False, pts_x=None, pts_y=None):
    polys, codes = load(kind)
    tree = STRtree(polys)
    pi, gi = tree.query(pts, predicate="within")  # (点index, ポリゴンindex)
    out = np.full(len(pts), None, dtype=object)
    for p, g in zip(pi, gi):
        if out[p] is None: out[p] = codes[g]
    print(f"{kind}: ポリゴン{len(polys)}, コード別 {pd.Series(codes).value_counts().to_dict()}")
    if not want_dist: return out
    # 重心から、入っているポリゴンの境界までの距離(m)
    pm = [transform(to_m, g).boundary for g in polys]
    dist = np.full(len(pts), np.nan)
    first = {}
    for p_, g_ in zip(pi, gi): first.setdefault(p_, g_)
    from shapely import distance
    idx = np.fromiter(first.keys(), int); gidx = np.fromiter(first.values(), int)
    ptm = points(pts_x[idx] * KX, pts_y[idx] * KY)
    dist[idx] = [distance(a, pm[g]) for a, g in zip(ptm, gidx)]
    return out, dist

if __name__ == "__main__":
    df = pd.read_parquet(R / "data/processed/sapporo_buildings.parquet")
    ok = df.lat.notna() & df.lon.notna()
    pts = points(df.loc[ok, "lon"].to_numpy(), df.loc[ok, "lat"].to_numpy())
    for col, kind in (("urban_planning_area", "UrbanPlanningArea"), ("area_class", "AreaClassification")):
        df[col] = None; df.loc[ok, col] = assign(pts, kind)
    zone, dist = assign(pts, "UseDistrict", True, df.loc[ok, "lon"].to_numpy(), df.loc[ok, "lat"].to_numpy())
    df["urf_zone"] = None; df.loc[ok, "urf_zone"] = zone
    df["zone_boundary_dist_m"] = np.nan; df.loc[ok, "zone_boundary_dist_m"] = dist
    df["urban_planning_area"] = df["urban_planning_area"].notna()
    df.to_parquet(R / "data/processed/sapporo_buildings_urf.parquet", index=False)
    print(len(df), "buildings; 重心なし", (~ok).sum())
