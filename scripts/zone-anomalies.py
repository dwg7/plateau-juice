"""棟単位の分析: 棟が立つ用途地域ポリゴン(urf_zone)ごとの用途構成と、その地域で統計的に少ない用途の棟を抽出する。
母集団: attr_surveyed=True かつ urf_zone あり。法令適合性の判断はしない(既存不適格・許可・面積要件などは見ない)。
出力: notes/zone-anomalies.md, notes/zone-anomalies-map.html, data/processed/zone_anomalies.csv
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapkit
import pandas as pd

R = Path(__file__).resolve().parent.parent
def codelist(name):
    x = (R / f"data/raw/citygml/codelists/{name}.xml").read_text(encoding="utf8")
    return {n: d for d, n in re.findall(r"<gml:description>([^<]*)</gml:description>\s*<gml:name>([^<]*)</gml:name>", x)}
USAGE = codelist("Building_usage"); ZONE = codelist("Common_districtsAndZonesType")
df = pd.read_parquet(R / "data/processed/sapporo_buildings_urf.parquet")
p = df[df.attr_surveyed & df.urf_zone.notna()].copy()
p["用途"] = p.usage.astype("string").map(USAGE).fillna("不明")
p["地域"] = p.urf_zone.map(ZONE)
p["zone_code"] = p.urf_zone.astype(int)
out = [f"# 用途地域ポリゴン別の用途構成と「その地域で少ない用途」の棟\n", f"母集団: 属性あり かつ urf_zone あり {len(p):,}棟。法令適合の判断はしない(既存不適格・許可・面積要件を見ていない)。\n"]
t = pd.crosstab(p.zone_code.map(lambda c: ZONE[str(c)]), p.用途)
order = [ZONE[str(i)] for i in range(1, 14) if ZONE[str(i)] in t.index]
cols = t.sum().sort_values(ascending=False).index[:9]
out += ["## 用途地域 × 用途(行%、上位用途)\n", (t.div(t.sum(axis=1), axis=0) * 100).round(1).loc[order, cols].assign(棟数=t.sum(axis=1)).to_markdown(), ""]
# 低層住居専用地域(1,2)に立つ、住宅系以外の用途
low = p[p.zone_code.isin([1, 2])]
res = {"住宅", "共同住宅", "店舗等併用住宅", "文教厚生施設", "作業所併用住宅"}
odd = low[~low.用途.isin(res | {"不明"})].copy()
out += [f"## 低層住居専用地域(第1種・第2種)内で、住宅系・学校等以外の用途の棟: {len(odd):,}棟 / {len(low):,}棟 ({len(odd)/len(low):.2%})\n",
        odd.用途.value_counts().to_frame("棟数").to_markdown(), ""]
# 規模(運輸倉庫・工場が小規模な車庫・倉庫ではないかの確認)
for u in ["運輸倉庫施設", "工場", "業務施設", "商業施設"]:
    q = odd[odd.用途 == u]
    out += [f"- 低層住居専用地域内の{u}: 延べ面積の中央値 {q.total_floor_area.median():.0f}㎡、建築面積の中央値 {q.footprint_area.median():.0f}㎡、高さの中央値 {q.measured_height.median():.1f}m、1,000㎡超 {(q.total_floor_area > 1000).sum()}棟"]
out += [""]
# 4階以上
hi = low[low.storeys_above >= 4]
out += [f"低層住居専用地域内の4階以上: {len(hi):,}棟({len(hi)/len(low):.2%})。用途別: {hi.用途.value_counts().head(5).to_dict()}", ""]
# 住居系全般(1-8)の工場・倉庫
res_z = p[p.zone_code <= 8]
for u in ["工場", "運輸倉庫施設"]:
    q = res_z[res_z.用途 == u]
    out += [f"住居系地域(1〜8)内の{u}: {len(q):,}棟、地域別: {q.地域.value_counts().head(5).to_dict()}"]
out += [""]
# 空間的集中(タイル)
fl = odd[odd.用途.isin(["工場", "運輸倉庫施設"])]
tt = fl.groupby("tile", observed=True).size().sort_values(ascending=False).head(12)
out += [f"## 低層住居専用地域内の工場・運輸倉庫 {len(fl):,}棟の分布(上位タイル)\n", tt.to_frame("棟数").assign(lat=lambda d: fl.groupby("tile", observed=True).lat.mean().reindex(d.index).round(3), lon=lambda d: fl.groupby("tile", observed=True).lon.mean().reindex(d.index).round(3)).to_markdown(), ""]
cols_out = ["tile", "lat", "lon", "地域", "用途", "storeys_above", "structure_type", "year_of_construction", "total_floor_area", "footprint_area", "measured_height", "zone_type"]
odd[cols_out].to_csv(R / "data/processed/zone_anomalies.csv", index=False, encoding="utf8")
# 属性zone_typeとの食い違い
mm = p[p.zone_type.astype("string") != p.urf_zone.astype("string")]
out += [f"## 参考: 建物属性 zone_type とポリゴンの食い違い {len(mm):,}棟({len(mm)/len(p):.1%})のうち、この棟単位の外れ値に該当: {int(odd.index.isin(mm.index).sum()):,}棟", ""]
(R / "notes/zone-anomalies.md").write_text("\n".join(out), encoding="utf8"); print("\n".join(out))
pts = odd[odd.用途.isin(["工場", "運輸倉庫施設", "業務施設", "商業施設"])]
C = {"工場": "#e41a1c", "運輸倉庫施設": "#ff7f00", "業務施設": "#377eb8", "商業施設": "#4daf4a"}
feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(r.lon, 5), round(r.lat, 5)]},
          "properties": {"color": C[r.用途], "popup": f"{r.用途}<br>{r.地域}<br>地上{int(r.storeys_above) if pd.notna(r.storeys_above) else '?'}階"}} for r in pts.itertuples()]
legend = "<b>低層住居専用地域(1・2種)内の非住宅系</b>" + "".join(f'<br><i style="background:{c}"></i>{u}' for u, c in C.items()) + "<br><small>点は棟の重心(クリックで詳細)</small>"
(R / "notes/zone-anomalies-map.html").write_text(mapkit.page("低層住居専用地域内の非住宅系", legend, feats, "point", zoom=10.5), encoding="utf8")
