import pytest

from reviewlens.data.loader import InvalidCSVError, load_reviews, to_chain_inputs
from tests.conftest import SAMPLE_FULL, SAMPLE_SMALL

HEADER = "review_id,date,platform,rating,review_text\n"


def test_brief_sample_loads():
    res = load_reviews(str(SAMPLE_SMALL))
    assert list(res.df["review_id"]) == ["R-1041", "R-1042", "R-1043"]
    assert res.dropped == []


def test_missing_column_raises():
    with pytest.raises(InvalidCSVError, match="review_text"):
        load_reviews(b"review_id,date,platform,rating\nR-1,2026-10-01,Google,5\n")


def test_empty_and_duplicate_rows_are_dropped_with_reason():
    csv = HEADER + "R-1,2026-10-01,Google,5,Good\nR-2,2026-10-01,Google,5,\nR-1,2026-10-02,Zomato,1,Dup\n"
    res = load_reviews(csv.encode())
    assert list(res.df["review_id"]) == ["R-1"]
    assert {d["reason"] for d in res.dropped} == {"empty review_text", "duplicate review_id"}


def test_bad_rating_is_kept_with_warning():
    res = load_reviews((HEADER + "R-1,2026-10-01,Google,9,Okay\n").encode())
    assert len(res.df) == 1 and res.df["rating"].isna().all()
    assert res.warnings
    assert to_chain_inputs(res.df)[0]["rating"] == "?"


def test_bom_and_tamil_round_trip():
    text = "பிரியாணி சுவையாக இருந்தது"
    res = load_reviews((HEADER + f"R-1,2026-10-01,Zomato,5,{text}\n").encode("utf-8-sig"))
    assert res.df.loc[0, "review_text"] == text


def test_header_case_and_whitespace_tolerated():
    res = load_reviews(b" Review_ID ,Date,Platform,Rating,Review_Text\nR-1 ,2026-10-01,Google,5, Nice \n")
    assert res.df.loc[0, "review_id"] == "R-1" and res.df.loc[0, "review_text"] == "Nice"


def test_all_rows_empty_raises():
    with pytest.raises(InvalidCSVError):
        load_reviews((HEADER + "R-1,2026-10-01,Google,5,\n").encode())


def test_full_sample_has_200_plus_rows():
    res = load_reviews(str(SAMPLE_FULL))
    assert len(res.df) >= 200
    assert len(res.dropped) == 3
