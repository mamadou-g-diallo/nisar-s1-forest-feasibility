"""Offline tests for nisar_s1.search (no network)."""
from datetime import date

from nisar_s1.config import bbox_to_wkt
from nisar_s1.search import parse_nisar_name


def test_parse_gcov():
    d = parse_nisar_name("NISAR_L2_PR_GCOV_035_072_A_026_2005_DHDH_M_20261110T042757_"
                         "20261110T042832_P05036_N_F_J_001")
    assert (d["product"], d["track"], d["direction"], d["frame"]) == ("GCOV", 72, "A", 26)
    assert (d["bw_code"], d["pol_code"], d["ref_date"]) == ("2005", "DHDH", date(2026, 11, 10))


def test_parse_gunw_baseline_rounded():
    d = parse_nisar_name("NISAR_L2_PR_GUNW_033_037_D_064_034_4000_SH_20261014T183420_"
                         "20261014T183424_20261026T183420_20261026T183425_P05036_N_P_J_001")
    assert (d["product"], d["pol_code"], d["baseline_days"]) == ("GUNW", "SH", 12)
    assert d["sec_date"] == date(2026, 10, 26)


def test_bbox_to_wkt_closed():
    w = bbox_to_wkt([0, 0, 1, 1])
    assert w.startswith("POLYGON((0 0") and w.endswith("0 0))")
