"""タイル(3次メッシュ)ごとの属性構成(用途・構造・年代・階数)で地区をクラスタリングし、用途地域と突き合わせる。
母集団: attr_surveyed=True の棟(D9、D11)。タイルは地区の特徴を見るための補助的な集約単位。
出力: notes/clusters.md, notes/cluster-map.html, data/processed/tile_clusters.csv
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapkit
import numpy as np, pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

R = Path(__file__).resolve().parent.parent
MIN_N = 100  # タイルあたりの最小棟数
def codelist(name):
    x = (R / f"data/raw/citygml/codelists/{name}.xml").read_text(encoding="utf8")
    return {n: d for d, n in re.findall(r"<gml:description>([^<]*)</gml:description>\s*<gml:name>([^<]*)</gml:name>", x)}
USAGE = codelist("Building_usage"); ZONE = codelist("Common_districtsAndZonesType")
df = pd.read_parquet(R / "data/processed/sapporo_buildings_urf.parquet")
p = df[df.attr_surveyed].copy()
p["用途"] = p.usage.astype("string").map(USAGE).fillna("不明")
main = ["住宅", "共同住宅", "店舗等併用住宅", "業務施設", "商業施設", "文教厚生施設", "運輸倉庫施設", "工場"]
p["用途g"] = p.用途.where(p.用途.isin(main), "その他")
p["構造g"] = p.structure_type.astype("string").map({"601": "木造", "612": "簡易耐火", "613": "耐火"}).fillna("不明")
y = p.year_of_construction
p["年代g"] = pd.cut(y, [0, 1969, 1979, 1989, 1999, 2009, 2100], labels=["〜1960s", "1970s", "1980s", "1990s", "2000s", "2010s"]).astype("string").fillna("不明")
p["z"] = p.zone_type.astype("string")
share = lambda col: pd.crosstab(p.tile, p[col], normalize="index").add_prefix(col + ":")
n = p.groupby("tile", observed=True).size()
F = pd.concat([share("用途g"), share("構造g"), share("年代g")], axis=1)
F["階数平均"] = p.groupby("tile", observed=True).storeys_above.apply(lambda s: s.astype(float).mean())
F["4階以上率"] = p.groupby("tile", observed=True).storeys_above.apply(lambda s: (s.astype(float) >= 4).mean())
F = F[n >= MIN_N].drop(columns=[c for c in F if c.endswith(":不明")]).fillna(0)
X = StandardScaler().fit_transform(F)
sil = {k: silhouette_score(X, KMeans(k, n_init=20, random_state=0).fit_predict(X)) for k in range(3, 9)}
k = max(sil, key=sil.get)
F["cluster"] = KMeans(k, n_init=50, random_state=0).fit_predict(X)
# 用途地域(建物属性zone_type)の最頻値とグループ
def zg(c): c = int(c); return "住居系" if c <= 8 else "商業系" if c in (9, 10) else "工業系"
dom = p.groupby("tile", observed=True).z.agg(lambda s: s.mode().iat[0] if s.notna().any() else None)
F["主たる用途地域"] = dom.reindex(F.index).map(ZONE)
F["地域系統"] = dom.reindex(F.index).map(lambda c: zg(c) if pd.notna(c) else None)
F["棟数"] = n.reindex(F.index)
out = [f"# タイルのクラスタリング(属性構成による地区の区分)\n", f"対象: 属性あり棟が{MIN_N}棟以上のタイル {len(F)}(全604のうち)。特徴量: 用途・構造・年代の構成比、階数平均、4階以上率。標準化してKMeans。",
       "シルエット係数: " + ", ".join(f"k={a}: {b:.3f}" for a, b in sil.items()) + f" → k={k}を採用(最大のものを機械的に選択)\n"]
prof = F.groupby("cluster").mean(numeric_only=True)
cols = ["用途g:住宅", "用途g:共同住宅", "用途g:店舗等併用住宅", "用途g:業務施設", "用途g:商業施設", "用途g:工場", "用途g:運輸倉庫施設", "構造g:木造", "構造g:耐火", "年代g:〜1960s", "年代g:1970s", "年代g:1980s", "年代g:2000s", "年代g:2010s", "階数平均", "4階以上率"]
prof = prof[[c for c in cols if c in prof]]
prof.insert(0, "タイル数", F.groupby("cluster").size()); prof.insert(1, "棟数計", F.groupby("cluster").棟数.sum())
out += ["## クラスタの特徴(構成比の平均)\n", prof.round(3).to_markdown(), ""]
ct = pd.crosstab(F.cluster, F.地域系統.fillna("不明")); out += ["## クラスタ × 主たる用途地域の系統(タイル数)\n", ct.to_markdown(), ""]
ct2 = pd.crosstab(F.cluster, F.主たる用途地域.fillna("不明")); out += ["## クラスタ × 主たる用途地域(タイル数)\n", ct2.to_markdown(), ""]
# 不一致候補: クラスタの最頻系統と異なる系統のタイル
major = ct.idxmax(axis=1)
F["クラスタ多数派系統"] = F.cluster.map(major)
mm = F[(F.地域系統.notna()) & (F.地域系統 != F.クラスタ多数派系統)]
out += [f"## 不一致候補: タイルの用途地域系統が、そのクラスタの多数派系統と異なる({len(mm)}タイル)\n"]
lat = p.groupby("tile", observed=True).lat.mean(); lon = p.groupby("tile", observed=True).lon.mean()
mm = mm.assign(lat=lat.reindex(mm.index).round(3), lon=lon.reindex(mm.index).round(3))
out += [mm[["cluster", "クラスタ多数派系統", "地域系統", "主たる用途地域", "棟数", "lat", "lon"]].sort_values("棟数", ascending=False).head(25).to_markdown(), ""]
F.drop(columns=["クラスタ多数派系統"]).to_csv(R / "data/processed/tile_clusters.csv", encoding="utf8")
(R / "notes/clusters.md").write_text("\n".join(out), encoding="utf8"); print("\n".join(out))
# 地図
def bounds(c):
    c = str(c); a, u, q, v, r, w = int(c[:2]), int(c[2:4]), int(c[4]), int(c[5]), int(c[6]), int(c[7])
    s = a / 1.5 + q * 5 / 60 + r * 30 / 3600; wst = 100 + u + v * 7.5 / 60 + w * 45 / 3600
    return [s, wst, s + 30 / 3600, wst + 45 / 3600]
mmset = set(mm.index)
PAL = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#a65628", "#f781bf", "#999999"]
feats = [{"type": "Feature", "geometry": mapkit.rect(bounds(i)), "properties": {"color": PAL[int(r.cluster)], "line": "#000" if i in mmset else PAL[int(r.cluster)], "lw": 2.5 if i in mmset else 0.5,
          "popup": f"タイル {i}<br>クラスタ{int(r.cluster)}<br>主たる用途地域: {r.主たる用途地域}<br>{int(r.棟数)}棟"}} for i, r in F.iterrows()]
legend = "<b>属性構成によるクラスタ</b><br><small>太い黒枠=用途地域の系統がクラスタ多数派と異なるタイル</small>" + "".join(f'<br><i style="background:{PAL[k]}"></i>クラスタ{k}' for k in range(k))
(R / "notes/cluster-map.html").write_text(mapkit.page("札幌 タイルのクラスタ", legend, feats, zoom=10.5), encoding="utf8")
