"""notes/*.html の地図ページ共通部。背景は hfu/stars の bvmap-starlight(MapLibre GL JS 6.11.1、ESM)。

features: GeoJSONのFeatureのリスト。properties に color(塗り/点の色), line(枠の色、任意), lw(枠の太さ、任意), popup(HTML)。
kind: "polygon"(塗りつぶしの矩形等)または "point"(円)。
"""
import json

STYLE_URL = "https://stars.optgeo.org/style/bvmap-starlight.json"
MAPLIBRE = "6.11.1"

def page(title, legend_html, features, kind="polygon", center=(141.35, 43.06), zoom=10):
    fc = {"type": "FeatureCollection", "features": features}
    layers = {
        # 塗りは最初の道路・建築物レイヤーの直前に入れ、道路・建物・注記の下にする
        "polygon": """const before = map.getStyle().layers.find(l => l['source-layer']==='RdCL' || l['source-layer']==='BldA')?.id;
  map.addLayer({id:'f',type:'fill',source:'d',paint:{'fill-color':['get','color'],'fill-opacity':0.6}}, before);
  map.addLayer({id:'l',type:'line',source:'d',paint:{'line-color':['coalesce',['get','line'],['get','color']],'line-width':['coalesce',['get','lw'],0.5]}}, before);""",
        "point": """map.addLayer({id:'f',type:'circle',source:'d',paint:{'circle-color':['get','color'],'circle-radius':4,'circle-opacity':0.85,'circle-stroke-width':1,'circle-stroke-color':['get','color']}});""",
    }[kind]
    return f"""<!doctype html><meta charset=utf-8><title>{title}</title>
<link rel=stylesheet href="https://cdn.jsdelivr.net/npm/maplibre-gl@{MAPLIBRE}/dist/maplibre-gl.css">
<style>html,body,#m{{height:100%;margin:0}}.l{{position:absolute;z-index:2;right:10px;top:10px;background:#fffd;padding:8px 10px;font:13px sans-serif;border-radius:4px;max-width:260px}}
.l i{{display:inline-block;width:14px;height:14px;vertical-align:middle;margin-right:4px}}</style>
<div id=m></div><div class=l>{legend_html}</div>
<script type="module">
import * as ml from 'https://cdn.jsdelivr.net/npm/maplibre-gl@{MAPLIBRE}/dist/maplibre-gl.mjs';
const maplibregl = ml.default ?? ml;
const D = {json.dumps(fc, ensure_ascii=False)};
const map = new maplibregl.Map({{container:'m', style:'{STYLE_URL}', center:[{center[0]},{center[1]}], zoom:{zoom}}});
map.addControl(new maplibregl.NavigationControl());
map.on('load', () => {{
  map.addSource('d', {{type:'geojson', data:D}});
  {layers}
  map.on('click','f', e => new maplibregl.Popup().setLngLat(e.lngLat).setHTML(e.features[0].properties.popup).addTo(map));
  map.on('mouseenter','f',()=>map.getCanvas().style.cursor='pointer'); map.on('mouseleave','f',()=>map.getCanvas().style.cursor='');
  const b = new maplibregl.LngLatBounds(); D.features.forEach(f => {{ const g=f.geometry; (g.type==='Point'?[g.coordinates]:g.coordinates[0]).forEach(c=>b.extend(c)); }});
  map.fitBounds(b, {{padding:30, animate:false}});
}});
</script>"""

def rect(b):  # [南, 西, 北, 東] -> GeoJSON Polygon
    s, w, n, e = b
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}
