# Virtual Health Assistant (Streamlit + Clean Architecture)

A safe, structured virtual health assistant built with Streamlit and Clean Architecture. It collects symptoms, checks red flags, and provides possible explanations, urgency guidance, recommended specialists, and local doctor search via a pluggable provider (Google Places or mock).

Important: This is NOT medical advice or a diagnosis.

## Features
- Mistral API for LLM reasoning (JSON output validated with Pydantic)
- Clean Architecture layers (domain, application, infrastructure, presentation)
- Red flags and vulnerable populations emphasis
- Local doctors search (Google Places adapter or mock fallback)
- No chat storage by default; optional opt-in toggle
- Streamlit UI with chat bubbles, sidebar settings, and reset

## Project Structure
```
src/
  domain/
    models.py
    rules.py
  application/
    use_cases.py
    ports.py
    schemas.py
  infrastructure/
    llm/
      mistral_client.py
    doctor_search/
      google_places.py
      mock_search.py
    config.py
  presentation/
    streamlit_app.py
app.py
.streamlit/secrets.toml.example
README.md
pyproject.toml
```

## Requirements
- Python 3.10+
- Mistral API key
- Optional: Google Places API key (for real local doctor results)

## Setup

### 1) Install dependencies
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e .
```

Alternatively:
```bash
pip install -r requirements.txt  # if using requirements.txt instead of pyproject
```

### 2) Configure secrets (preferred: Streamlit secrets)
Create `.streamlit/secrets.toml` (do not commit real keys) based on the provided example:

- `.streamlit/secrets.toml.example`:
```
# Copy to .streamlit/secrets.toml and fill values
MISTRAL_API_KEY = "YOUR_MISTRAL_KEY"
MISTRAL_MODEL = "mistral-large-latest"
GOOGLE_PLACES_API_KEY = "YOUR_GOOGLE_PLACES_KEY" # optional
```

#### Environment variables (fallback)
If not using Streamlit secrets, you can set environment variables:
- `MISTRAL_API_KEY`
- `MISTRAL_MODEL` (optional; default `mistral-large-latest`)
- `GOOGLE_PLACES_API_KEY` (optional)

On Windows (PowerShell):
```powershell
$env:MISTRAL_API_KEY="YOUR_MISTRAL_KEY"
$env:MISTRAL_MODEL="mistral-large-latest"
$env:GOOGLE_PLACES_API_KEY="YOUR_PLACES_KEY"
```

### 3) Run locally
```bash
streamlit run app.py
```

## Streamlit Cloud Deployment
1. Push this repo to GitHub (exclude secrets).
2. In Streamlit Cloud, add the app (entrypoint `app.py`).
3. In the app settings, set Secrets using the same keys as `.streamlit/secrets.toml`:
   - `MISTRAL_API_KEY`
   - `MISTRAL_MODEL` (optional)
   - `GOOGLE_PLACES_API_KEY` (optional)

## Safety Behavior
- Always displays a safety disclaimer.
- Checks for red flags (chest pain, difficulty breathing, fainting, severe bleeding, stroke signs, suicidal thoughts, etc.).
- If vulnerable (child, pregnant, elderly, immunocompromised), urgency escalates sooner.
- Never claims certainty; provides possible explanations.

## Data & Privacy
- No chat logs stored by default.
- Optional opt-in toggle to store chats locally (not implemented by default; extend as needed).

## Development Notes
- Clean Architecture separates domain (rules), application (use cases/ports/schemas), infrastructure (adapters), and presentation (UI).
- LLM returns strict JSON; parsed and validated with Pydantic; one repair attempt on invalid JSON.

## Testing
A minimal unit test skeleton is provided under `tests/`. To run tests:
```bash
pytest -q
```

## Troubleshooting
- Missing Mistral key: App shows an error with setup steps.
- Missing Google Places key: Doctor search uses mock adapter and explains how to enable real results.
- Ensure your Python environment uses 3.10+.

## License
No license is set; do not commit real API keys. Replace with your own secrets management in production.