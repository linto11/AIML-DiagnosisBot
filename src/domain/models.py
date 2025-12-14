from typing import List, Optional
from pydantic import BaseModel, Field, validator


class Demographics(BaseModel):
    age: Optional[int] = Field(None, ge=0, le=120)
    sex: Optional[str] = Field(None, description="Male/Female/Other/Prefer not to say")
    is_child: bool = False
    is_pregnant: bool = False
    is_elderly: bool = False
    is_immunocompromised: bool = False


class SymptomIntake(BaseModel):
    chief_complaint: Optional[str] = None
    duration: Optional[str] = None
    severity_scale: Optional[int] = Field(None, ge=0, le=10)
    onset: Optional[str] = None
    fever: Optional[bool] = None
    pain_scale: Optional[int] = Field(None, ge=0, le=10)
    triggers: List[str] = []
    relevant_history: List[str] = []
    meds: List[str] = []
    allergies: List[str] = []
    demographics: Demographics = Demographics()
    red_flag_answers: dict = {}

    @validator("chief_complaint")
    def validate_complaint(cls, v: Optional[str]):
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class RedFlagsResult(BaseModel):
    triggered: List[str] = []
    emergency: bool = False


class DoctorResult(BaseModel):
    name: str
    specialty: Optional[str] = None
    rating: Optional[float] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    maps_url: Optional[str] = None
