import logging
from typing import List

import requests

from src.application.ports import DoctorSearchPort
from src.domain.models import DoctorResult
from src.infrastructure.config import Settings


logger = logging.getLogger(__name__)


class GooglePlacesDoctorSearchAdapter(DoctorSearchPort):
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.api_key = self.settings.google_places_api_key

    def search_specialists(self, specialty: str, location_query: str, limit: int = 5) -> List[DoctorResult]:
        if not self.api_key:
            logger.warning("Google Places API key missing; doctor search disabled.")
            return []

        # Text Search API
        query = f"{specialty} specialist in {location_query}"
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "key": self.api_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.exception("Places TextSearch failed: %s", e)
            return []

        results = data.get("results", [])[:limit]
        doctor_results: List[DoctorResult] = []

        for r in results:
            name = r.get("name")
            rating = r.get("rating")
            address = r.get("formatted_address")
            place_id = r.get("place_id")
            maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None

            phone = None
            if place_id:
                # Place Details to get phone
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                dparams = {
                    "place_id": place_id,
                    "fields": "formatted_phone_number",
                    "key": self.api_key,
                }
                try:
                    dresp = requests.get(details_url, params=dparams, timeout=10)
                    dresp.raise_for_status()
                    dd = dresp.json()
                    phone = dd.get("result", {}).get("formatted_phone_number")
                except Exception:
                    pass

            doctor_results.append(
                DoctorResult(
                    name=name,
                    specialty=specialty,
                    rating=rating,
                    address=address,
                    phone=phone,
                    maps_url=maps_url,
                )
            )

        return doctor_results
