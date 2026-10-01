"""全タイルでの属性充実度(非NULL率)を集計する。出力: notes/coverage.md"""
import pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parent.parent
df = pd.read_parquet(R / "data/processed/sapporo_buildings.parquet")
cols = ["usage", "org_usage2", "year_of_construction", "storeys_above", "storeys_below", "structure_type",
        "fireproof_type", "zone_type", "total_floor_area", "site_area", "footprint_area", "measured_height",
        "coverage_rate", "floor_area_rate"]
out = [f"# 属性充実度(全{len(df):,}棟、{df.tile.nunique()}タイル)\n", "| 属性 | 非NULL率 |\n|---|---|"]
out += [f"| {c} | {df[c].notna().mean():.1%} |" for c in cols]
out += [f"\n`attr_surveyed`(用途・用途地域・階数・建築年のいずれか判明): {df.attr_surveyed.mean():.1%} ({df.attr_surveyed.sum():,}棟)",
        f"LOD2あり: {df.has_lod2.sum():,}棟", f"洪水リスク属性あり(flood_n>0): {(df.flood_n>0).sum():,}棟 ({(df.flood_n>0).mean():.1%})",
        f"洪水以外のリスク属性: {(df.n_risk_other>0).sum():,}棟",
        "\n## 属性が部分的にのみ埋まる棟(D5の「全か無か」仮説の検証)\n"]
k = df[["usage", "zone_type", "storeys_above", "year_of_construction"]].notna().sum(axis=1)
out += ["| 判明している項目数(0-4) | 棟数 | 割合 |\n|---|---|---|"] + [f"| {i} | {(k==i).sum():,} | {(k==i).mean():.1%} |" for i in range(5)]
t = df.groupby("tile", observed=True).attr_surveyed.agg(["size", "mean"])
out += ["\n## タイル別の充実率分布(attr_surveyed)\n", f"タイル数 {len(t)}: 100%のタイル {(t['mean']==1).sum()}、0%のタイル {(t['mean']==0).sum()}、"
        f"中間(0%超100%未満) {((t['mean']>0)&(t['mean']<1)).sum()}", "\n" + t["mean"].describe().round(3).to_frame("充実率").to_markdown()]
for c in ["usage", "structure_type", "zone_type", "bldg_class"]:
    out += [f"\n## {c} の値の分布(NULL含む)\n", df[c].value_counts(dropna=False).head(15).to_frame("棟数").to_markdown()]
out += ["\n## 建築年代(10年区切り)\n", (df.year_of_construction // 10 * 10).astype("object").where(df.year_of_construction.notna(), "NULL").astype(str).value_counts().sort_index().to_frame("棟数").to_markdown()]
(R / "notes").mkdir(exist_ok=True); (R / "notes/coverage.md").write_text("\n".join(out), encoding="utf8")
print("\n".join(out))
