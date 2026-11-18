"""Catalogue search (ASF) for Sentinel-1 and NISAR products, returned as tidy DataFrames.

The functions are sensor-agnostic where possible: :func:`results_to_frame` works on any
``asf_search`` result set, so a future ROSE-L collection only needs a new thin wrapper.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, Sequence

import asf_search as asf
import pandas as pd
from shapely import wkt as shp_wkt
from shapely.geometry import shape

NISAR_PRODUCT_TYPES = ("RSLC", "RIFG", "RUNW", "ROFF", "GSLC", "GCOV", "GUNW", "GOFF")
_TS = re.compile(r"\d{8}T\d{6}")

# Common columns kept from ASF properties (missing ones become NaN).
_BASE_COLS = [
    "sceneName", "platform", "processingLevel", "collectionName", "startTime", "stopTime",
    "flightDirection", "pathNumber", "frameNumber", "orbit", "polarization",
    "mainBandPolarization", "sideBandPolarization", "rangeBandwidth", "frameCoverage",
    "beamModeType", "productionConfiguration", "crid", "pgeVersion",
]


def results_to_frame(results: Iterable, aoi_wkt: str | None = None) -> pd.DataFrame:
    """Flatten ``asf_search`` results into a DataFrame.

    Adds the main file size (``size_mb``), the URL and, if ``aoi_wkt`` is given, the fraction
    of the AOI covered by each footprint (``aoi_cover``).
    """
    aoi = shp_wkt.loads(aoi_wkt) if aoi_wkt else None
    rows = []
    for r in results:
        p = r.properties
        row = {c: p.get(c) for c in _BASE_COLS}
        for c in ("mainBandPolarization", "sideBandPolarization", "rangeBandwidth"):
            if isinstance(row[c], list):
                row[c] = "+".join(row[c]) if c != "rangeBandwidth" else ",".join(row[c])
        main_file = p.get("fileName") or (p["url"].rsplit("/", 1)[-1] if p.get("url") else None)
        sizes = p.get("bytes")
        if isinstance(sizes, dict) and main_file in sizes:
            row["size_mb"] = sizes[main_file]["bytes"] / 1e6
        elif isinstance(sizes, (int, float)):
            row["size_mb"] = sizes / 1e6
        else:
            row["size_mb"] = None
        row["url"] = p.get("url")
        if aoi is not None and r.geometry:
            row["aoi_cover"] = round(shape(r.geometry).intersection(aoi).area / aoi.area, 3)
        rows.append(row)
    df = pd.DataFrame(rows)
    for c in ("startTime", "stopTime"):
        if c in df:
            df[c] = pd.to_datetime(df[c], utc=True)
    return df.sort_values("startTime").reset_index(drop=True) if len(df) else df


def search_s1(aoi_wkt: str, start: str | datetime, end: str | datetime,
              processing_level: str = "SLC", beam_mode: str = "IW",
              max_results: int = 2000) -> pd.DataFrame:
    """Search Sentinel-1 scenes (default IW SLC) intersecting ``aoi_wkt``."""
    res = asf.search(dataset=asf.DATASET.SENTINEL1, processingLevel=processing_level,
                     beamMode=beam_mode, intersectsWith=aoi_wkt, start=start, end=end,
                     maxResults=max_results)
    return results_to_frame(res, aoi_wkt)


def search_nisar(aoi_wkt: str, start: str | datetime, end: str | datetime,
                 product_types: Sequence[str] = ("GCOV", "GUNW"),
                 max_results: int = 2000) -> pd.DataFrame:
    """Search NISAR products of the given types intersecting ``aoi_wkt``.

    Columns parsed from the file name are added by :func:`parse_nisar_name`.
    """
    frames = []
    for pt in product_types:
        res = asf.search(dataset=asf.DATASET.NISAR, processingLevel=pt,
                         intersectsWith=aoi_wkt, start=start, end=end, maxResults=max_results)
        df = results_to_frame(res, aoi_wkt)
        if len(df):
            parsed = df["sceneName"].apply(parse_nisar_name).apply(pd.Series)
            frames.append(pd.concat([df, parsed], axis=1))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def parse_nisar_name(name: str) -> dict:
    """Parse a NISAR granule name.

    Examples::

        NISAR_L2_PR_GCOV_035_072_A_026_2005_DHDH_M_<start>_<stop>_P05036_N_F_J_001
        NISAR_L2_PR_GUNW_033_037_D_064_034_4000_SH_<ref_start>_<ref_stop>_<sec_start>_<sec_stop>_...

    Returns the product type, cycle(s), track, direction, frame, the bandwidth code
    (e.g. ``2005`` = 20 MHz main + 5 MHz side band), the polarisation code
    (``DH`` dual-pol HH/HV, ``SH`` single HH, ...), acquisition dates and, for
    interferometric products, the temporal baseline in days.
    """
    t = name.split("_")
    out: dict = {"product": t[3], "cycle": int(t[4]), "track": int(t[5]),
                 "direction": t[6], "frame": int(t[7])}
    stamps = [datetime.strptime(s, "%Y%m%dT%H%M%S") for s in _TS.findall(name)]
    if out["product"] in ("RIFG", "RUNW", "ROFF", "GUNW", "GOFF"):
        out.update(sec_cycle=int(t[8]), bw_code=t[9], pol_code=t[10],
                   ref_date=stamps[0].date(), sec_date=stamps[2].date(),
                   baseline_days=round((stamps[2] - stamps[0]).total_seconds() / 86400))
    else:
        out.update(bw_code=t[8], pol_code=t[9], ref_date=stamps[0].date())
    return out


def revisit_summary(df: pd.DataFrame, group_cols: Sequence[str],
                    time_col: str = "startTime") -> pd.DataFrame:
    """Per acquisition geometry: number of acquisitions, first/last date and median revisit (days)."""
    def _agg(g: pd.DataFrame) -> pd.Series:
        days = g[time_col].dt.normalize().drop_duplicates().sort_values()
        gaps = days.diff().dt.days.dropna()
        return pd.Series({
            "n_acq": len(days),
            "first": days.min().date(),
            "last": days.max().date(),
            "median_revisit_d": gaps.median() if len(gaps) else None,
            "min_revisit_d": gaps.min() if len(gaps) else None,
        })
    return df.groupby(list(group_cols)).apply(_agg, include_groups=False).reset_index()
