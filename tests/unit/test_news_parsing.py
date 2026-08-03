from nfl_analytics.news import classify, name_tag


def test_classify_injury():
    assert classify("Star QB out 4-6 weeks with ankle sprain", "") == "injury"


def test_classify_trade():
    assert classify("Cowboys trade for veteran edge rusher", "") == "trade-signing"


def test_classify_general_fallback():
    assert classify("Ten takeaways from Sunday's slate", "") == "general"


def test_name_tag_matches_full_names():
    idx = {"patrick mahomes": "00-0033873", "josh allen": "00-0034857"}
    hits = name_tag("Patrick Mahomes and Josh Allen duel again", idx)
    assert set(hits) == {"00-0033873", "00-0034857"}


def test_name_tag_no_partial_word_matches():
    idx = {"josh allen": "00-0034857"}
    assert name_tag("Joshua Allentown wins award", idx) == []
