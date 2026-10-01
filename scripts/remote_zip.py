"""HTTP Range経由でzipの一覧・個別ファイル取得を行う補助(全体をDLせずに中身を確認する用)。"""
import io, sys, urllib.request, zipfile

class HttpRangeFile(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method="HEAD")
        self.size = int(urllib.request.urlopen(req).headers["Content-Length"])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def read(self, n=-1):
        if n < 0: n = self.size - self.pos
        if n == 0 or self.pos >= self.size: return b""
        end = min(self.pos + n, self.size) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        data = urllib.request.urlopen(req).read()
        self.pos += len(data)
        return data
    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)

def open_zip(url): return zipfile.ZipFile(io.BufferedReader(HttpRangeFile(url), 1 << 20))

if __name__ == "__main__":
    z = open_zip(sys.argv[1])
    for i in z.infolist(): print(i.file_size, i.filename)
