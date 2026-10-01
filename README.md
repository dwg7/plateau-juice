# plateau-juice

国土交通省 [Project PLATEAU](https://www.mlit.go.jp/plateau/) の3D都市モデル(札幌市、令和2年度)の建築物から、**立体形状と個体識別子を切り離し、属性(用途・構造・建築年・階数・災害リスク等)だけを取り出して**統計的に眺める試みです。

**サイト: <https://dwg7.unopengis.org/plateau-juice/>**(空間ID `z/x/y` の格子で、属性の充実率や用途構成などを地図で見られます)

## わかったこと(札幌市、646,474棟)

詳細と根拠は [`notes/findings.md`](notes/findings.md) にあります。

- **属性が付いているのは約6割(391,841棟)**。主に市街化区域内の主たる建物で、市街化調整区域と、高さ約5m以下の小さな建物にはほとんど付いていません。ここでの割合は「属性のある建物」の中のものです。
- **「木造の住宅」が主役**: 属性のある建物の約76%が住宅、81%が木造。最頻の組み合わせは「住宅×木造×1980年代」(17%)。耐火造は新しい建物ほど増えます。
- **用途地域と建物の実態は大筋で合う**。建物属性の用途地域と、都市計画ポリゴンとが食い違う棟は2.7%。境界付近を除いても残る食い違いの多くは、2019年の用途地域の変更による時点のずれと見られます(推論。札幌市の変更履歴との照合は未実施)。

## 方針と範囲

- スコープは「**意味論的な属性の価値をどこまで引き出せるか**」に限ります。PLATEAUの予算や費用対効果の議論には立ち入りません。
- 幾何(形状)と個体識別子(GMLの `gml:id` など)は保持しません。位置は、棟の重心の緯度経度と、空間ID(`z/x/y`)のセルだけです。
- 公式の用途地域を前提の正解とは扱わず、実態との差も観察の対象にします。
- 方針の詳細は [`CLAUDE.md`](CLAUDE.md)、意思決定の記録は [`DECISIONS.md`](DECISIONS.md) と [`docs/decisions/`](docs/decisions/) にあります。

## 再現手順

Python 3.9 以降。元データ(約8GB)は、zip 全体ではなく、必要なファイルだけを HTTP Range で取得します。

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fetch-plateau.py          # 建築物・都市計画・コードリストを data/raw/ へ(約7.5GB)
.venv/bin/python scripts/extract-attributes.py     # 属性だけを Parquet 化 → data/processed/
.venv/bin/python scripts/urf-join.py               # 都市計画ポリゴンと空間結合
.venv/bin/python scripts/grid.py                   # 空間ID(z=17)の集計 → docs/data/grid.json
```

| スクリプト | 内容 |
|---|---|
| `fetch-plateau.py`、`remote_zip.py` | CityGMLの zip から必要なファイルだけを取得 |
| `extract-attributes.py` | 建築物の属性を、欠損値(`9999`など)を NULL にして Parquet 化 |
| `urf-join.py` | 棟の重心を、区域区分・用途地域のポリゴンと結合 |
| `coverage.py`、`analyze.py` | 属性の充実度、用途×構造×建築年の集計 |
| `verify-urf.py`、`boundary-sensitivity.py`、`zone-validfrom.py` | 用途地域との突き合わせと、不一致の原因の検証 |
| `cluster.py`、`zone-anomalies.py` | タイル単位のクラスタリング、用途地域別の用途構成 |
| `grid.py` | 空間IDのセルごとの集計(サイトのデータ) |
| `coverage-map.py`、`mapkit.py` | `notes/` の地図ページの生成 |

`data/` は `.gitignore` 済みです。サイトのローカル確認は、`docs/` を静的サーバで配信するだけです(`python3 -m http.server --directory docs`)。

## リポジトリ構成

```
CLAUDE.md        プロジェクトの文脈と方針(引き継ぎ文書)
DECISIONS.md     意思決定ログ
docs/            公開サイト(index.html、data/grid.json)と ADR(decisions/)
notes/           発見の記録(findings.md)と、各分析の出力
scripts/         取得・抽出・分析・集計のスクリプト
```

## データの出典とライセンス

- 出典: 国土交通省 Project PLATEAU「3D都市モデル(令和2年度)札幌市」([G空間情報センター](https://www.geospatial.jp/ckan/dataset/plateau-01100-sapporo-shi-2020))を加工して作成。[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.ja) ほか(政府標準利用規約 第2.0版など)から選択できます。
- 背景地図: [bvmap-starlight](https://github.com/hfu/stars)(国土地理院最適化ベクトルタイル)。
- このリポジトリのコードと文書: [CC0 1.0](LICENSE)。

## 注意

- 原典資料の位置・作成時期の違いにより、データが現状を正確に反映していない場合があります(PLATEAU側の注意書き)。
- 「属性のある建物」は、札幌の建物全体の代表ではありません(上記のとおり偏りがあります)。統計は、その範囲内の傾向として読んでください。
- 分析の一部(現場感覚での検証、不一致箇所の解釈)は、人の手による確認が必要で、未完了のものがあります。
