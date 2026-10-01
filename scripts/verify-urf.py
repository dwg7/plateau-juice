"""仮説F1の検証: 属性の充実(attr_surveyed)は市街化区域と対応するか。zone_typeと用途地域ポリゴンは一致するか。出力: notes/urf-verification.md"""
import pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parent.parent
df = pd.read_parquet(R / "data/processed/sapporo_buildings_urf.parquet")
df["zone_type"] = df["zone_type"].astype("string"); df["urf_zone"] = df["urf_zone"].astype("string")
lab = {"22": "市街化区域", "23": "市街化調整区域", "99": "不明"}
df["区域区分"] = df.area_class.map(lab).fillna("区域区分ポリゴン外")
out = ["# urf結合による検証(F1)\n"]
t = pd.crosstab(df["区域区分"], df.attr_surveyed, margins=True)
t.columns = ["属性なし", "属性あり", "計"]; t["属性あり率"] = (t["属性あり"] / t["計"]).map("{:.1%}".format)
out += ["## 区域区分 × 属性の有無(棟数)\n", t.to_markdown(), ""]
out += ["## 都市計画区域内外\n", pd.crosstab(df.urban_planning_area, df.attr_surveyed).to_markdown(), ""]
# 市街化区域内で属性がない棟
inu = df[df.area_class == "22"]
out += [f"## 市街化区域内の属性なし棟: {(~inu.attr_surveyed).sum():,}棟 / {len(inu):,}棟 ({(~inu.attr_surveyed).mean():.1%})\n"]
out += ["規模(measured_height)の中央値(m): " + ", ".join(f"{k} {v:.1f}" for k, v in inu.groupby("attr_surveyed").measured_height.median().items()),
        "bldg_class別の属性あり率:\n", inu.groupby(inu.bldg_class.astype("string").fillna("NULL")).attr_surveyed.agg(["size", "mean"]).round(3).to_markdown(), ""]
# 用途地域: 建物属性 zone_type と urf_zone の一致
s = df[df.zone_type.notna()]
out += [f"## 建物属性 zone_type と用途地域ポリゴン(urf_zone)の一致(zone_typeあり {len(s):,}棟)\n",
        f"- 一致: {(s.zone_type == s.urf_zone).sum():,} ({(s.zone_type == s.urf_zone).mean():.1%})",
        f"- 不一致(urf_zoneあり): {((s.zone_type != s.urf_zone) & s.urf_zone.notna()).sum():,}",
        f"- urf_zone なし(ポリゴン外): {s.urf_zone.isna().sum():,}", ""]
mm = s[(s.zone_type != s.urf_zone) & s.urf_zone.notna()]
out += ["不一致の上位(zone_type → urf_zone):\n", mm.groupby(["zone_type", "urf_zone"]).size().sort_values(ascending=False).head(15).to_frame("棟数").to_markdown(), ""]
# 属性がない棟の用途地域ポリゴンの有無
n = df[~df.attr_surveyed]
out += [f"## 属性なし棟({len(n):,})の urf_zone あり率: {n.urf_zone.notna().mean():.1%}(用途地域のある場所なのに属性がない棟)", ""]
out += ["## 属性なし棟の区域区分内訳\n", n["区域区分"].value_counts().to_frame("棟数").to_markdown()]
(R / "notes/urf-verification.md").write_text("\n".join(out), encoding="utf8"); print("\n".join(out))
