from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .models import GeoPoint


class KakaoLocalError(RuntimeError):
    pass


class KakaoLocalClient:
    base_url = "https://dapi.kakao.com"

    def __init__(self, rest_api_key: str, timeout: float = 10.0) -> None:
        self.rest_api_key = rest_api_key
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{self.base_url}{path}?{query}",
            headers={"Authorization": f"KakaoAK {self.rest_api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise KakaoLocalError(f"Kakao API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise KakaoLocalError(f"Kakao API request failed: {exc}") from exc

    def geocode(self, address: str) -> GeoPoint | None:
        payload = self._get("/v2/local/search/address.json", {"query": address, "size": 1})
        documents = payload.get("documents", [])
        if not documents:
            return None

        first = documents[0]
        return GeoPoint(
            address=first.get("address_name") or address,
            latitude=float(first["y"]),
            longitude=float(first["x"]),
            source="kakao",
        )

    def keyword_geocode(self, query: str) -> GeoPoint | None:
        payload = self._get("/v2/local/search/keyword.json", {"query": query, "size": 1})
        documents = payload.get("documents", [])
        if not documents:
            return None

        first = documents[0]
        address = (
            first.get("road_address_name")
            or first.get("address_name")
            or first.get("place_name")
            or query
        )
        return GeoPoint(
            address=address,
            latitude=float(first["y"]),
            longitude=float(first["x"]),
            source="kakao-keyword",
        )

    def search_category(
        self,
        category_group_code: str,
        point: GeoPoint,
        radius_m: int,
        size: int = 15,
    ) -> list[dict[str, Any]]:
        payload = self._get(
            "/v2/local/search/category.json",
            {
                "category_group_code": category_group_code,
                "x": point.longitude,
                "y": point.latitude,
                "radius": radius_m,
                "sort": "distance",
                "size": size,
            },
        )
        return list(payload.get("documents", []))
