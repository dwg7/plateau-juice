"""境界付近の見かけ上の不一致を除いて、用途地域の不一致を再計算する。出力: notes/boundary-sensitivity.md
不一致A: 建物属性 zone_type と用途地域ポリゴン urf_zone の食い違い(F2)
不一致B: 低層住居専用地域(1・2種)内の非住宅系(F5)
重心から、入っているポリゴンの境界までの距離(zone_boundary_dist_m)が d m 未満の棟を除外した場合の件数を、dごとに示す。
"""
import re
from pathlib import Path
import pandas as pd
R = Path(__file__).resolve().parent.parent
def codelist(name):
    x = (R / f"data/raw/citygml/codelists/{name}.xml").read_text(encoding="utf8")
    return {n: d for d, n in re.findall(r"<gml:description>([^<]*)</gml:description>\s*<gml:name>([^<]*)</gml:name>", x)}
USAGE = codelist("Building_usage"); ZONE = codelist("Common_districtsAndZonesType")
df = pd.read_parquet(R / "data/processed/sapporo_buildings_urf.parquet")
p = df[df.attr_surveyed & df.urf_zone.notna()].copy()
p["用途"] = p.usage.astype("string").map(USAGE).fillna("不明")
p["d"] = p.zone_boundary_dist_m
out = ["# 境界付近を除外した不一致の再計算\n", f"母集団: 属性あり かつ 用途地域ポリゴンあり {len(p):,}棟。`d` = 重心から入っているポリゴンの境界までの距離(m、局所近似)。\n",
       "## 棟の境界距離の分布(m)\n", p.d.describe(percentiles=[.05, .1, .25, .5, .75, .9]).round(1).to_frame("d").to_markdown(), ""]
A = p[p.zone_type.notna() & (p.zone_type.astype("string") != p.urf_zone.astype("string"))]
low = p[p.urf_zone.astype(int).isin([1, 2])]
res = {"住宅", "共同住宅", "店舗等併用住宅", "文教厚生施設", "作業所併用住宅", "不明"}
B = low[~low.用途.isin(res)]; Bbig = B[B.total_floor_area > 1000]
rows = []
for d in [0, 10, 20, 30, 50, 100]:
    rows.append({"除外距離 d(m)": d, "不一致A(zone_type≠ポリゴン)": int((A.d >= d).sum()), "A残存率": f"{(A.d >= d).mean():.1%}",
                 "不一致B(低層内の非住宅系)": int((B.d >= d).sum()), "B残存率": f"{(B.d >= d).mean():.1%}", "B大規模(>1000㎡)": int((Bbig.d >= d).sum())})
out += ["## 除外距離ごとの不一致の残存\n", pd.DataFrame(rows).to_markdown(index=False), ""]
# 不一致Aの内訳: d>=30m で残るもの
A30 = A[A.d >= 30]
out += [f"## 不一致A: 境界から30m以上離れても残る {len(A30):,}棟\n", "上位の組み合わせ(zone_type → urf_zone):\n",
        A30.groupby(["zone_type", "urf_zone"]).size().sort_values(ascending=False).head(10).to_frame("棟数").to_markdown(), ""]
tt = A30.groupby("tile", observed=True).size().sort_values(ascending=False)
out += [f"タイル数 {len(tt)}、上位5タイルで {tt.head(5).sum()/len(A30):.0%}。上位:\n", tt.head(8).to_frame("棟数").assign(
        lat=lambda x: A30.groupby("tile", observed=True).lat.mean().reindex(x.index).round(3), lon=lambda x: A30.groupby("tile", observed=True).lon.mean().reindex(x.index).round(3)).to_markdown(), ""]
# 不一致B大規模で残るもの
Bk = Bbig[Bbig.d >= 30].sort_values("total_floor_area", ascending=False)
out += [f"## 不一致B(大規模、>1000㎡): 境界から30m以上離れて残る {len(Bk)}棟(全{len(Bbig)}棟中)\n",
        Bk.head(15)[["tile", "lat", "lon", "urf_zone", "用途", "storeys_above", "total_floor_area", "d"]].assign(
            urf_zone=lambda x: x.urf_zone.map(ZONE), lat=lambda x: x.lat.round(4), lon=lambda x: x.lon.round(4), d=lambda x: x.d.round(0)).to_markdown(index=False), ""]
(R / "notes/boundary-sensitivity.md").write_text("\n".join(out), encoding="utf8"); print("\n".join(out))
