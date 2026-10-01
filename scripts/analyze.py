"""用途×構造×建築年の集計。母集団は attr_surveyed=True(DECISIONS D9、D11)。出力: notes/crosstab.md"""
import re
from pathlib import Path
import pandas as pd

R = Path(__file__).resolve().parent.parent

def codelist(name):
    x = (R / f"data/raw/citygml/codelists/{name}.xml").read_text(encoding="utf8")
    return {n: d for d, n in re.findall(r"<gml:description>([^<]*)</gml:description>\s*<gml:name>([^<]*)</gml:name>", x)}

USAGE = codelist("Building_usage"); STRUCT = codelist("BuildingDetailAttribute_buildingStructureType")
df = pd.read_parquet(R / "data/processed/sapporo_buildings_urf.parquet")
pop = df[df.attr_surveyed].copy()
pop["用途"] = pop.usage.astype("string").map(USAGE)
pop["構造"] = pop.structure_type.astype("string").map(STRUCT)
pop["年代"] = (pop.year_of_construction // 10 * 10).astype("Int64").astype("string").where(pop.year_of_construction.notna()) + "s"
pop.loc[pop.year_of_construction < 1950, "年代"] = "〜1949"
ORDER = ["〜1949"] + [f"{d}s" for d in range(1950, 2020, 10)]

def pct(t): return (t.div(t.sum(axis=1), axis=0) * 100).round(1)
out = [f"# 用途×構造×建築年の集計\n", f"母集団: attr_surveyed=True {len(pop):,}棟(全{len(df):,}棟の{len(pop)/len(df):.1%})。",
       "市街化区域内の主たる建物(おおむね高さ5m超)の統計として読むこと(D11)。\n"]
out += ["## 母集団内の各軸の非NULL率\n", pd.DataFrame({"非NULL率": [pop[c].notna().mean() for c in ["用途", "構造", "年代"]]}, index=["用途", "構造", "年代"]).map("{:.1%}".format).to_markdown(), ""]
out += ["## 用途(棟数)\n", pop.用途.fillna("(不明)").astype(str).value_counts().to_frame("棟数").to_markdown(), ""]
out += ["## 構造(棟数)\n", pop.構造.fillna("(不明)").astype(str).value_counts().to_frame("棟数").to_markdown(), ""]
out += ["## 建築年代(棟数)\n", pop.年代.fillna("(不明)").astype(str).value_counts().reindex(ORDER + ["(不明)"]).to_frame("棟数").to_markdown(), ""]
c = pop.dropna(subset=["用途", "構造", "年代"]).astype({"用途": str, "構造": str, "年代": str})
out += [f"完全ケース(用途・構造・年代すべて判明): {len(c):,}棟({len(c)/len(pop):.1%})\n"]
top = c.用途.value_counts().head(6).index
t = pd.crosstab(c.用途, c.構造); out += ["## 用途 × 構造(棟数)\n", t.loc[t.sum(axis=1).sort_values(ascending=False).index].to_markdown(), ""]
out += ["## 用途 × 構造(行%)\n", pct(t).loc[t.sum(axis=1).sort_values(ascending=False).index].to_markdown(), ""]
t = pd.crosstab(c.構造, c.年代)[ORDER]; out += ["## 構造 × 建築年代(行%、建築年代別の構造構成は下表の列%)\n", pct(t).to_markdown(), "",
     "### 建築年代ごとの構造構成(列%)\n", (t.div(t.sum()) * 100).round(1).to_markdown(), ""]
t = pd.crosstab(c.用途, c.年代)[ORDER]; out += ["## 用途 × 建築年代(棟数、上位用途)\n", t.loc[t.sum(axis=1).sort_values(ascending=False).index[:8]].to_markdown(), "",
     "### 建築年代ごとの用途構成(列%、上位用途)\n", (t.div(t.sum()) * 100).round(1).loc[t.sum(axis=1).sort_values(ascending=False).index[:8]].to_markdown(), ""]
g = c.groupby(["用途", "構造", "年代"]).size().sort_values(ascending=False)
out += ["## 3軸の組み合わせ 上位25\n", g.head(25).to_frame("棟数").assign(割合=lambda d: (d.棟数 / len(c) * 100).round(1)).to_markdown(), "",
        f"組み合わせの総数: {len(g)}(上位25で{g.head(25).sum()/len(c):.1%}、上位100で{g.head(100).sum()/len(c):.1%})"]
(R / "notes/crosstab.md").write_text("\n".join(out), encoding="utf8"); print("\n".join(out))
