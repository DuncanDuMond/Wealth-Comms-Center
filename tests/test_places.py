import pytest
from wealth_command_center.places import search_places


@pytest.mark.parametrize("query,timezone", [("東京", "Asia/Tokyo"), ("北京", "Asia/Shanghai"),
    ("กรุงเทพ", "Asia/Bangkok"), ("서울", "Asia/Seoul"), ("Hà Nội", "Asia/Bangkok")])
def test_multilingual_offline_cities(query, timezone):
    matches = search_places(query)
    assert matches
    if query != "Hà Nội":
        assert any(city["timezone"] == timezone for city in matches)
    else:
        assert any(city["country_code"] == "VN" for city in matches)
    assert all(city["precision"] == "city center" for city in matches)


def test_bounded_and_empty_search():
    assert len(search_places("a")) <= 12
    assert search_places("") == []
    assert search_places("x"*81) == []
