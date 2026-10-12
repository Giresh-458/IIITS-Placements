from src.normalization.date_normalizer import normalize_dates

def test_indian_date_format():
    ev_date, _, _, _, _, _ = normalize_dates("03-10-2026", "")
    assert ev_date == "2026-10-03"
    
def test_written_date_format():
    ev_date, _, _, _, _, _ = normalize_dates("28th September 2026", "")
    assert ev_date == "2026-09-28"

def test_written_date_no_th():
    ev_date, _, _, _, _, _ = normalize_dates("29 September 2026", "")
    assert ev_date == "2026-09-29"
    
def test_iso_preservation():
    ev_date, _, _, _, _, _ = normalize_dates("", "", raw_iso="2026-05-10")
    assert ev_date == "2026-05-10"

def test_malformed_garbage():
    ev_date, _, _, _, _, _ = normalize_dates("5 b2103", "")
    assert ev_date is None

def test_context_year_recovery():
    ev_date, _, _, _, _, _ = normalize_dates("05th October", "Campus drive 2026")
    assert ev_date == "2026-10-05"
