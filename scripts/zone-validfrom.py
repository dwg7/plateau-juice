"""不一致の原因が「建物属性(調査2019年)後の用途地域の変更」かを、urfポリゴンの施行日(validFrom)で確かめる。
不一致A(zone_type≠urf_zone、境界から30m以上)の棟が入るポリゴンと、一致する棟のポリゴンで、validFromの分布を比べる。出力: notes/zone-validfrom.md
"""
import re
from pathlib import Path
import numpy as np, pandas as pd
from shapely import STRtree, points
from shapely.geometry import Polygon
R = Path(__file__).resolve().parent.parent
URF = R / "data/raw/citygml/udx/urf"
FEAT = re.compile(r"<urf:UseDistrict gml:id=[^>]*>(.*?)</urf:UseDistrict>", re.S)
def g1(tag, b):
    m = re.search(rf"<urf:{tag}(?:\s[^>]*)?>([^<]*)</urf:{tag}>", b); return m.group(1).strip() if m else None
def ring(s):
    v = np.array(s.split(), dtype=float); v = v.reshape(-1, 3 if len(v) % 3 == 0 else 2); return [(x[1], x[0]) for x in v]
polys, meta = [], []
for f in sorted(URF.glob("*.gml")):
    for b in FEAT.findall(f.read_text(encoding="utf8")):
        for pb in re.findall(r"<gml:Polygon[^>]*>(.*?)</gml:Polygon>", b, re.S):
            e = re.search(r"<gml:exterior>.*?<gml:posList[^>]*>([^<]*)</gml:posList>", pb, re.S)
            if e:
                polys.append(Polygon(ring(e.group(1)), [ring(i) for i in re.findall(r"<gml:interior>.*?<gml:posList[^>]*>([^<]*)</gml:posList>", pb, re.S)]).buffer(0))
                meta.append({"code": g1("function", b), "validFrom": g1("validFrom", b), "validType": g1("validFromType", b), "finalNotif": g1("finalNotificationDate", b)})
M = pd.DataFrame(meta); tree = STRtree(polys)
df = pd.read_parquet(R / "data/processed/sapporo_buildings_urf.parquet")
p = df[df.attr_surveyed & df.urf_zone.notna() & df.zone_type.notna()].copy()
p["mm"] = p.zone_type.astype("string") != p.urf_zone.astype("string")
p = p[(p.zone_boundary_dist_m >= 30) | ~p.mm]
sub = pd.concat([p[p.mm], p[~p.mm].sample(20000, random_state=0)])  # 一致側は2万棟を無作為抽出
pi, gi = tree.query(points(sub.lon.to_numpy(), sub.lat.to_numpy()), predicate="within")
first = {}
for a, b in zip(pi, gi): first.setdefault(a, b)
sub = sub.iloc[list(first.keys())].copy(); sub["gid"] = list(first.values())
for c in ["validFrom", "validType", "finalNotif"]: sub[c] = sub.gid.map(M[c])
sub["施行年"] = sub.validFrom.str[:4]
out = ["# 用途地域の不一致と、ポリゴンの施行日(validFrom)\n", f"不一致A(境界から30m以上): {int(sub.mm.sum()):,}棟。一致側: 無作為2万棟。建物属性の調査年は2019年、urfの作成は2021年。\n",
       "## validFromの年(棟数)\n", pd.crosstab(sub.施行年, sub.mm.map({True: "不一致", False: "一致"})).to_markdown(), "",
       "## 不一致の棟が入るポリゴンの validFromType(1=?)とfinalNotificationDate(年)\n",
       pd.crosstab(sub.validType.fillna("NULL"), sub.mm.map({True: "不一致", False: "一致"})).to_markdown(), "",
       pd.crosstab(sub.finalNotif.str[:4].fillna("NULL"), sub.mm.map({True: "不一致", False: "一致"})).to_markdown(), ""]
(R / "notes/zone-validfrom.md").write_text("\n".join(out), encoding="utf8"); print("\n".join(out))
