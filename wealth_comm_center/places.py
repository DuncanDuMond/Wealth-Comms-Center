"""Offline multilingual city lookup. No personal query is sent to a geocoder."""
from functools import lru_cache
import unicodedata


def normalized(text):
    return unicodedata.normalize("NFKC", text).casefold().strip()


@lru_cache(maxsize=1)
def cities():
    import geonamescache
    catalog = geonamescache.GeonamesCache(min_city_population=15000)
    countries = catalog.get_countries()
    return [(city, {normalized(alias) for alias in [city["name"], *city.get("alternatenames", [])]},
             countries.get(city["countrycode"], {}).get("name", city["countrycode"]))
            for city in catalog.get_cities().values()]


def search_places(query: str) -> list[dict]:
    query = normalized(query)
    if not query or len(query) > 80:
        return []
    matches = []
    for city, aliases, country in cities():
        exact = query in aliases
        if exact or any(alias.startswith(query) for alias in aliases):
            matches.append((not exact, -city["population"], {
                "id": city["geonameid"], "name": city["name"], "country": country,
                "country_code": city["countrycode"], "latitude": city["latitude"],
                "longitude": city["longitude"], "timezone": city["timezone"],
                "source": "GeoNames via geonamescache 3.0.2", "precision": "city center",
            }))
    matches.sort(key=lambda match: match[:2])
    return [item[2] for item in matches[:12]]
