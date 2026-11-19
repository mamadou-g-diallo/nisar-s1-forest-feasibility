"""Authenticated, resumable downloads from NASA Earthdata / ASF with visible progress.

Credentials come from ``~/.netrc`` (never read or printed here). Works for any HTTPS product URL
returned by :mod:`nisar_s1.search` (NISAR, Sentinel-1, and later ROSE-L if hosted by ASF).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

import requests

_CHUNK = 4 * 2**20


def earthdata_session() -> requests.Session:
    """A ``requests`` session that follows Earthdata Login redirects using ``~/.netrc``."""
    import earthaccess
    earthaccess.login(strategy="netrc")
    return earthaccess.get_requests_https_session()


def _fmt_bytes(n: float) -> str:
    return f"{n / 2**30:.2f} GB" if n >= 2**30 else f"{n / 2**20:.0f} MB"


def download_file(url: str, dest: Path, session: requests.Session, expected_bytes: int | None = None,
                  label: str = "", report_every_s: float = 30.0, retries: int = 5) -> Path:
    """Download ``url`` to ``dest`` (resumes from ``dest.part``). Prints a progress line every
    ``report_every_s`` seconds (percent, size, speed, ETA) so long runs can be monitored from a log.
    """
    dest = Path(dest)
    if dest.exists() and (expected_bytes is None or dest.stat().st_size == expected_bytes):
        print(f"{label} {dest.name}: already present", flush=True)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        done = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={done}-"} if done else {}
        try:
            with session.get(url, stream=True, headers=headers, timeout=120) as r:
                if r.status_code == 416:  # range not satisfiable: file complete
                    break
                r.raise_for_status()
                if done and r.status_code != 206:  # server ignored the range: restart
                    done = 0
                total = expected_bytes or (done + int(r.headers.get("Content-Length", 0))) or None
                t0, last, start_done = time.time(), time.time(), done
                with open(part, "ab" if done else "wb") as f:
                    for chunk in r.iter_content(_CHUNK):
                        f.write(chunk)
                        done += len(chunk)
                        now = time.time()
                        if now - last >= report_every_s:
                            speed = (done - start_done) / max(now - t0, 1e-6)
                            pct = f"{100 * done / total:5.1f}%" if total else "  ?  "
                            eta = f"ETA {((total - done) / speed) / 60:5.1f} min" if total and speed else ""
                            print(f"{label} {dest.name[:60]}: {pct} {_fmt_bytes(done)}"
                                  f"{' / ' + _fmt_bytes(total) if total else ''} "
                                  f"{speed / 2**20:.1f} MB/s {eta}", flush=True)
                            last = now
            break
        except (requests.RequestException, OSError) as e:
            print(f"{label} {dest.name}: attempt {attempt}/{retries} failed ({type(e).__name__}), retrying",
                  flush=True)
            time.sleep(10 * attempt)
    else:
        raise RuntimeError(f"download failed after {retries} attempts: {url}")
    if expected_bytes is not None and part.stat().st_size != expected_bytes:
        raise RuntimeError(f"size mismatch for {dest.name}: {part.stat().st_size} != {expected_bytes}")
    part.rename(dest)
    print(f"{label} {dest.name}: done ({_fmt_bytes(dest.stat().st_size)})", flush=True)
    return dest


def download_many(items: Iterable[tuple[str, Path, int | None]], session: requests.Session | None = None
                  ) -> list[Path]:
    """Download ``(url, dest, expected_bytes)`` items one after another with an ``[i/N]`` counter."""
    items = list(items)
    session = session or earthdata_session()
    t0, out = time.time(), []
    for i, (url, dest, size) in enumerate(items, 1):
        out.append(download_file(url, dest, session, size, label=f"[{i}/{len(items)}]"))
        print(f"[{i}/{len(items)}] elapsed {(time.time() - t0) / 60:.1f} min", flush=True)
    return out


class HttpRangeFile:
    """Read-only, seekable file over HTTPS using byte-range requests (authenticated session).

    The Earthdata redirect is resolved once; every ``read`` is then a single range request.
    Used to pull selected members out of large remote zip archives (e.g. one Sentinel-1 sub-swath).
    """

    def __init__(self, url: str, session: requests.Session):
        r = session.get(url, headers={"Range": "bytes=0-0"}, timeout=120)
        r.raise_for_status()
        self.url, self.session = r.url, session
        self.size = int(r.headers["Content-Range"].split("/")[1])
        self.pos = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        for attempt in range(5):
            try:
                r = self.session.get(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"},
                                     timeout=300)
                r.raise_for_status()
                break
            except requests.RequestException:
                time.sleep(10 * (attempt + 1))
        else:
            raise RuntimeError("range request failed")
        self.pos += len(r.content)
        return r.content


def extract_safe_subset(url: str, out_dir: Path, swath: str, pols=("vv", "vh"),
                        session: requests.Session | None = None, label: str = "") -> Path:
    """Extract a reduced Sentinel-1 SAFE from a remote SLC zip: manifest, support/preview files,
    and only the annotation, calibration, noise and measurement files of one sub-swath
    (``swath`` = ``iw1``/``iw2``/``iw3``) and the given polarisations. About 1/3 of the full download.
    Returns the path of the ``.SAFE`` directory (completed atomically via a ``.part`` folder).
    """
    import shutil
    import zipfile

    session = session or earthdata_session()
    f = HttpRangeFile(url, session)
    z = zipfile.ZipFile(f)
    names = z.namelist()
    safe = names[0].split("/")[0]
    dest, tmp = Path(out_dir) / safe, Path(out_dir) / (safe + ".part")
    if dest.exists():
        print(f"{label} {safe}: already present", flush=True)
        return dest
    keep = []
    for n in names:
        base = n.rsplit("/", 1)[-1].lower()
        if n.endswith("/"):
            continue
        in_swath = f"-{swath}-" in base and any(f"-{p}-" in base for p in pols)
        if "/measurement/" in n or "/annotation/" in n:
            if in_swath:
                keep.append(n)
        else:
            keep.append(n)  # manifest.safe, support/ schemas, preview/
    total = sum(z.getinfo(n).compress_size for n in keep)
    print(f"{label} {safe}: {len(keep)} files, {total / 2**30:.2f} GB compressed "
          f"(full zip {f.size / 2**30:.2f} GB)", flush=True)
    t0, done, last = time.time(), 0, time.time()
    for n in keep:
        target = tmp.parent / n.replace(safe, safe + ".part", 1)
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(n) as src, open(target, "wb") as dst:
            while True:
                b = src.read(_CHUNK)
                if not b:
                    break
                dst.write(b)
                now = time.time()
                if now - last >= 30:
                    cur = min(max(f.pos - z.getinfo(n).header_offset, 0), z.getinfo(n).compress_size)
                    print(f"{label} {safe[:40]}: {100 * (done + cur) / total:4.0f}% done, "
                          f"{(done + cur) / 2**20 / (now - t0):.1f} MB/s, now "
                          f"{n.rsplit('/', 1)[-1][:30]}, {(now - t0) / 60:.1f} min elapsed", flush=True)
                    last = now
        done += z.getinfo(n).compress_size
    shutil.move(str(tmp), str(dest))
    print(f"{label} {safe}: done in {(time.time() - t0) / 60:.1f} min", flush=True)
    return dest
