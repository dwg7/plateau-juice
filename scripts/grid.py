"""棟の重心を空間ID(z=18、表記 z/x/y)のセルに割り当て、セルごとの属性集計(件数ベース)を docs/data/grid.json に出力する。
件数のまま持つことで、z=17・16・15 へはブラウザ側(docs/index.html)で親セルへ足し合わせるだけで集約できる(空間IDは入れ子)。
棟の座標・個体識別子は出力しない。セルごとの合計値のみ。用途地域は最新のポリゴン `urf_zone`(D18)。
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parent.parent
Z = 18
df = pd.read_parquet(R / "data/processed/sapporo_buildings_urf.parquet")
n = 2 ** Z
df["x"] = np.floor((df.lon + 180) / 360 * n).astype(int)
la = np.radians(df.lat)
df["y"] = np.floor((1 - np.log(np.tan(la) + 1 / np.cos(la)) / np.pi) / 2 * n).astype(int)
s = df.attr_surveyed
u = df.usage.astype("string").fillna("")
st = df.structure_type.astype("string").fillna("")
df["n"] = 1
df["ns"] = s.astype(int)  # 属性あり(調査対象)
df["res"] = (s & u.isin(["411", "412", "413", "415"])).astype(int)    # 住宅・共同住宅・店舗等併用住宅・作業所併用住宅
df["apt"] = (s & (u == "412")).astype(int)
df["comm"] = (s & u.isin(["401", "402"])).astype(int)                  # 業務・商業
df["ind"] = (s & u.isin(["431", "441"])).astype(int)                   # 運輸倉庫・工場
df["st_known"] = df.structure_type.notna().astype(int)
df["st_fire"] = (st == "613").astype(int)
df["st_wood"] = (st == "601").astype(int)
df["yr_n"] = df.year_of_construction.notna().astype(int)
df["yr_sum"] = df.year_of_construction.astype("float").fillna(0)
df["fl_n"] = df.storeys_above.notna().astype(int)
df["fl_sum"] = df.storeys_above.astype("float").fillna(0)
df["fl_ge4"] = (df.storeys_above.astype("float") >= 4).astype(int)
zz = pd.to_numeric(df.urf_zone, errors="coerce")
df["zn_n"] = (s & zz.notna()).astype(int)
df["zn_res"] = (s & zz.between(1, 8)).astype(int)    # 住居系(第1種低層〜田園住居)
df["zn_com"] = (s & zz.isin([9, 10])).astype(int)    # 商業系(近隣商業・商業)
df["zn_ind"] = (s & zz.isin([11, 12, 13])).astype(int)  # 工業系(準工業・工業・工業専用)
cols = ["n", "ns", "res", "apt", "comm", "ind", "st_known", "st_fire", "st_wood", "yr_n", "yr_sum", "fl_n", "fl_sum", "fl_ge4", "zn_n", "zn_res", "zn_com", "zn_ind"]
g = df.groupby(["x", "y"], as_index=False)[cols].sum().sort_values(["x", "y"])
out = {"z": Z, "fields": ["x", "y"] + cols, "note": "セル(空間ID z/x/y)ごとの件数ベース集計。座標・個体識別子は含まない。母集団の定義は notes/findings.md を参照。"}
for c in ["x", "y"] + cols: out[c] = [round(float(v), 1) if c in ("yr_sum", "fl_sum") else int(v) for v in g[c]]
(R / "docs/data/grid.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf8")
print(len(g), "cells;", "size", (R / "docs/data/grid.json").stat().st_size // 1024, "KB; 棟数合計", int(g.n.sum()), "属性あり", int(g.ns.sum()))
print("セルあたり属性あり棟≥30:", int((g.ns >= 30).sum()), " 検算 zn_n=", int(g.zn_n.sum()), " ns=", int(g.ns.sum()))
