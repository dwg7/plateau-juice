"""タイル(3次メッシュ)別の属性充実率を、単独のHTML地図(Leaflet)として notes/coverage-map.html に出力する。"""
import sys
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapkit
R = Path(__file__).resolve().parent.parent
df = pd.read_parquet(R / "data/processed/sapporo_buildings.parquet")
t = df.groupby("tile", observed=True).agg(n=("attr_surveyed", "size"), cov=("attr_surveyed", "mean")).reset_index()
def bounds(code):  # 3次メッシュコード -> (南, 西, 北, 東)
    c = str(code); p, u, q, v, r, w = int(c[:2]), int(c[2:4]), int(c[4]), int(c[5]), int(c[6]), int(c[7])
    s = p / 1.5 + q * 5 / 60 + r * 30 / 3600; wst = 100 + u + v * 7.5 / 60 + w * 45 / 3600
    return [s, wst, s + 30 / 3600, wst + 45 / 3600]
def color(c): return "#d7191c" if c == 0 else "#fdae61" if c < .4 else "#a6d96a" if c < .6 else "#1a9641"
feats = [{"type": "Feature", "geometry": mapkit.rect(bounds(r.tile)), "properties": {"color": color(r.cov), "popup": f"タイル {r.tile}<br>{r.n}棟<br>充実率 {r.cov*100:.1f}%"}} for r in t.itertuples()]
legend = ("<b>属性調査の範囲(attr_surveyed率)</b><br><i style=\"background:#d7191c\"></i>0%(範囲外)<br><i style=\"background:#fdae61\"></i>1〜40%<br>"
          "<i style=\"background:#a6d96a\"></i>40〜60%<br><i style=\"background:#1a9641\"></i>60%超<br><small>タイルをクリックで詳細</small>")
(R / "notes").mkdir(exist_ok=True)
(R / "notes/coverage-map.html").write_text(mapkit.page("札幌 属性充実率(タイル別)", legend, feats), encoding="utf8")
z = t[t["cov"] == 0]
print(f"範囲外 {len(z)} タイル / {z.n.sum():,}棟")
