from typing import List

from src.application.ports import DoctorSearchPort
from src.domain.models import DoctorResult


class MockDoctorSearchAdapter(DoctorSearchPort):
    def search_specialists(self, specialty: str, location_query: str, limit: int = 5) -> List[DoctorResult]:
        sample = [
            DoctorResult(
                name=f"{specialty.title()} Clinic {i+1}",
                specialty=specialty,
                rating=4.2 + (i % 2) * 0.3,
                address=f"123 Example St, {location_query}",
                phone="(000) 000-0000",
                maps_url="https://maps.google.com",
            )
            for i in range(limit)
        ]
        return sample
