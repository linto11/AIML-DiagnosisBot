import os
import logging

try:
    import streamlit as st  # type: ignore
    _HAS_STREAMLIT = True
except Exception:
    _HAS_STREAMLIT = False

logger = logging.getLogger(__name__)


def get_secret(name: str, default: str | None = None) -> str | None:
    # Prefer Streamlit secrets if available
    if _HAS_STREAMLIT:
        try:
            if name in st.secrets:
                return str(st.secrets.get(name))
        except Exception:
            pass
    # Fallback to environment variables
    return os.environ.get(name, default)


class Settings:
    @property
    def mistral_api_key(self) -> str | None:
        return get_secret("MISTRAL_API_KEY")

    @property
    def mistral_model(self) -> str:
        return get_secret("MISTRAL_MODEL", "mistral-large-latest") or "mistral-large-latest"

    @property
    def google_places_api_key(self) -> str | None:
        return get_secret("GOOGLE_PLACES_API_KEY")
