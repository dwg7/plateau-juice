"""札幌市PLATEAU CityGMLのzipから、必要なファイルだけをHTTP Rangeで取得する。

zip全体(約2.7GB)ではなく、udx/bldg(建築物)、udx/urf(都市計画)、codelists、README等のみ取得する(テクスチャ画像は除く)。
既に同サイズのファイルがあればスキップ(再開可能)。
使い方: python scripts/fetch-plateau.py [--prefix udx/bldg/ ...] [--workers 8]
"""
import argparse, struct, sys, zlib, urllib.request, io, zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

URL = ("https://assets.cms.plateau.reearth.io/assets/be/3b8cfb-5459-4f9d-b08c-fb4ab72fbdbd/"
       "01100_sapporo-shi_city_2020_citygml_7_op.zip")
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "citygml"
DEFAULT_PREFIXES = ["udx/bldg/", "udx/urf/", "codelists/", "metadata/", "README.md"]

def get_range(start, end, retries=5):
    for i in range(retries):
        try:
            req = urllib.request.Request(URL, headers={"Range": f"bytes={start}-{end}"})
            return urllib.request.urlopen(req, timeout=120).read()
        except Exception:
            if i == retries - 1: raise

def central_directory():
    size = int(urllib.request.urlopen(urllib.request.Request(URL, method="HEAD")).headers["Content-Length"])
    tail = get_range(size - 4 * 1024 * 1024, size - 1)  # 末尾4MBに中央ディレクトリが収まる
    off = size - len(tail)
    class R(io.RawIOBase):
        pos = 0
        def seekable(s): return True
        def readable(s): return True
        def tell(s): return s.pos
        def seek(s, o, w=0): s.pos = o if w == 0 else s.pos + o if w == 1 else size + o; return s.pos
        def readinto(s, b):
            d = tail[s.pos - off: s.pos - off + len(b)]; b[:len(d)] = d; s.pos += len(d); return len(d)
    return zipfile.ZipFile(io.BufferedReader(R())).infolist()

def fetch(info):
    dest = OUT / info.filename
    if dest.exists() and dest.stat().st_size == info.file_size: return info.file_size
    n = len(info.filename.encode("utf8"))
    raw = get_range(info.header_offset, info.header_offset + 30 + n + 512 + info.compress_size - 1)
    nlen, elen = struct.unpack("<HH", raw[26:30])
    body = raw[30 + nlen + elen: 30 + nlen + elen + info.compress_size]
    data = body if info.compress_type == 0 else zlib.decompress(body, -15)
    assert len(data) == info.file_size, info.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part"); tmp.write_bytes(data); tmp.rename(dest)
    return info.file_size

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--prefix", nargs="*", default=DEFAULT_PREFIXES)
    ap.add_argument("--workers", type=int, default=8); a = ap.parse_args()
    todo = [i for i in central_directory() if not i.is_dir() and not i.filename.lower().endswith((".jpg", ".png")) and any(i.filename.startswith(p) for p in a.prefix)]
    print(f"{len(todo)} files, {sum(i.file_size for i in todo)/1e9:.2f} GB uncompressed", flush=True)
    done = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for k, _ in enumerate(ex.map(fetch, todo), 1):
            if k % 20 == 0 or k == len(todo): print(f"{k}/{len(todo)}", flush=True)
