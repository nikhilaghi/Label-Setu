# Label Setu Backend

FastAPI backend for the Label Setu AI-assisted Legal Metrology compliance workflow.

## Architecture

React frontend -> FastAPI -> EasyOCR -> spaCy/regex extraction -> deterministic Legal Metrology rules -> evidence/regions -> officer review.

Persistence is intentionally in-memory/local for the SIH prototype. No MongoDB, PostgreSQL, SQLAlchemy, Motor, PyMongo, Redis, or external LLM is required.

## Run on Windows CMD

```cmd
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -m uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`
Health: `http://127.0.0.1:8000/api/health`

## Demo accounts

Officer:
- `officer@labelsetu.gov.in`
- `password123`

Customer:
- `customer@labelsetu.gov.in`
- `customer123`

The login response uses the frontend contract: `token` + `user`.

## Main API groups

### Auth
- `POST /api/auth/login`
- `GET /api/auth/me`
- `PUT /api/auth/password`

### Inspections
- `POST /api/inspections`
- `GET /api/inspections`
- `GET /api/inspections/{inspection_id}`
- `GET /api/inspections/{inspection_id}/status`
- `GET /api/inspections/{inspection_id}/image`
- `GET /api/inspections/{inspection_id}/evidence`

### Review
- `GET /api/inspections/{inspection_id}/review`
- `PUT /api/inspections/{inspection_id}/review`
- `POST /api/inspections/{inspection_id}/review/submit`

Final assessment values match the new frontend: `compliant`, `further_review`, `non_compliant`.
Final review status is `REVIEWED`.

### Dashboard
- `GET /api/dashboard/summary`

### Settings
- `GET /api/settings`
- `PUT /api/settings`

Settings are stored per user in memory.

### Complaints
- `GET /api/complaints`
- `POST /api/complaints`
- `GET /api/complaints/{complaint_id}`
- `PUT /api/complaints/{complaint_id}`
- `DELETE /api/complaints/{complaint_id}`
- `POST /api/complaints/{complaint_id}/status`
- `POST /api/complaints/{complaint_id}/evidence`
- `GET /api/complaints/notifications`

### Customer portal
- `GET /api/customer/inspections`
- `GET /api/customer/inspections/{inspection_id}`
- `GET /api/customer/products`
- `GET /api/customer/reports`

## Verification

```cmd
python -m compileall app
python test_backend.py
```

`test_backend.py` covers health/auth/settings/compliance/inspection contract/review workflow/history/dashboard and the customer complaint workflow. EasyOCR must be installed for the image-pipeline tests.

## OCR extraction safeguards

The inspection pipeline is context-aware rather than treating every OCR token as a declaration:
- MRP is accepted only when a numeric amount appears on the MRP line; an MRP label with no amount is flagged rather than borrowing a number from another field.
- Net quantity prioritizes explicit net-weight/quantity text and resolves multipacks such as `5 x 100 g = 500 g` to the printed total.
- Manufacturer/packer/importer values are taken from explicit entity labels; ingredient text is never used as a manufacturer fallback.
- Packing/expiry dates must pass strict date validation. spaCy NER is not allowed to turn OCR noise such as `wnth` into a date.
- Batch/lot values must look like real alphanumeric codes and are rejected when they are ordinary words.
- Consumer-care extraction prefers complete toll-free/phone numbers and emails on contact-labelled lines.
- OCR boxes are reconstructed into logical visual lines so labels and values detected as separate EasyOCR boxes can still be matched.
- Font/readability remains an officer-review signal; OCR confidence is not treated as proof of statutory physical font size.
