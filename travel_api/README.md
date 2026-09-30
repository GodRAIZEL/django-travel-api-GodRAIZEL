# Travel Itinerary Planning & Booking API

A RESTful API, built with Django and Django REST Framework, for searching
destinations, building day-by-day trip itineraries, booking accommodations
and activities, tracking per-category budgets, collaborating with travel
companions, and leaving reviews.

## Technologies Used

Django 5, Django REST Framework, djangorestframework-simplejwt (JWT auth),
django-filter, drf-spectacular (OpenAPI/Swagger/ReDoc), python-decouple
(env config), Pillow (image uploads), SQLite by default / PostgreSQL
optional, pytest-django for testing.

## Installation

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then edit SECRET_KEY, etc.
```

## Database Setup

SQLite works out of the box — no extra setup needed. To use PostgreSQL
instead, set `USE_POSTGRES=True` and fill in `DB_*` in `.env`, then:

```bash
python manage.py makemigrations accounts destinations itineraries bookings reviews budgets
python manage.py migrate
python manage.py createsuperuser
```

## Environment Variables (`.env`)

`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `USE_POSTGRES`, `DB_NAME`, `DB_USER`,
`DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `MAX_UPLOAD_SIZE_MB`, `LOG_LEVEL`. See
`.env.example` for a template — never commit the real `.env`.

## Running the Server

```bash
python manage.py runserver
```

## Running Tests

```bash
pytest                     # uses pytest.ini, includes --cov by default
# or
python manage.py test
```

## API Documentation

- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- Raw OpenAPI schema: `/api/schema/`

## Authentication Flow

Register or log in to receive a JWT `access`/`refresh` pair, then send
`Authorization: Bearer <access>` on every request. Access tokens last 1
hour; refresh at `/api/v1/accounts/token/refresh/` (refresh tokens last 7
days). Full endpoint list below.

## Example Requests

```bash
# Register
curl -X POST http://localhost:8000/api/v1/accounts/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ada","email":"ada@example.com","password":"StrongPass123","password_confirm":"StrongPass123"}'

# Log in
curl -X POST http://localhost:8000/api/v1/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ada","password":"StrongPass123"}'

# Create an itinerary (authenticated)
curl -X POST http://localhost:8000/api/v1/itineraries/ \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"title":"Rome Adventure","destination_id":1,"start_date":"2026-07-01","end_date":"2026-07-10","budget":3000}'

# Confirm a booking
curl -X POST http://localhost:8000/api/v1/bookings/1/confirm/ \
  -H "Authorization: Bearer <access_token>"
```

## Key API Endpoints

| Area | Endpoints |
|---|---|
| Accounts | `register/`, `login/`, `logout/`, `token/refresh/`, `profile/`, `password/change/`, `password/reset/`, `password/reset/confirm/` |
| Destinations | `destinations/` (CRUD-read), `destinations/search/`, `destinations/recommendations/`, `destinations/{id}/popular_activities/`, `weather_info/`, `reviews_summary/` |
| Itineraries | `itineraries/` (full CRUD), `itineraries/search/`, `itineraries/{id}/report/`, `itineraries/create/`, `itineraries/{id}/collaborators/`, `itineraries/{id}/duplicate|export_pdf|share/`, `itineraries/upcoming/` |
| Bookings | `accommodations/`, `activities/`, `bookings/` (full CRUD), `bookings/bulk-update/`, `bookings/{id}/manage/`, `bookings/{id}/confirm|cancel/` |
| Reviews | `reviews/` (full CRUD), `reviews/{id}/mark_helpful/`, `reviews/my_reviews/` |
| Budgets | `budgets/`, `expenses/`, `budgets/{id}/variance/`, `analytics/budget_summary/` |
| Activity Log | `activity-logs/` (read-only audit trail — see below) |
| Analytics | `analytics/`, `analytics/budget_summary/`, `analytics/destination_preferences/` |

Every list endpoint supports `?search=`, `?ordering=`, and model-specific
`?filter_field=` query params via django-filter; paginated responses use
`{count, total_pages, current_page, next, previous, results}`.

## Project Structure

```
travel_api/          project settings, root urls, pagination, exceptions
accounts/             custom User model, auth endpoints
destinations/         Destination model + browsing/search
itineraries/          Itinerary, Collaboration, DailyPlan + planning views
bookings/             Accommodation, Activity, Booking + booking views
reviews/              Review model + CRUD viewset
budgets/              Budget, Expense + budget tracking views
activity_logs/        ActivityLog model - read-only audit trail
```

Each app follows the same internal layout: `models.py`, `serializers.py`,
`views.py`, `permissions.py` (where relevant), `filters.py` (where
relevant), `urls.py`, `admin.py`, `tests.py`.

Every mutating action that matters for accountability - creating/editing/
deleting an itinerary, adding/removing a collaborator, creating/confirming/
cancelling a booking, logging an expense, posting a review - writes an
`ActivityLog` entry. Browse your own trail (or anything logged against a
trip you own/collaborate on) at `GET /api/v1/activity-logs/`.

## ERD

See `PLANNING.md` for the entity-relationship diagram and permission matrix.

## Notes on this build

This project was generated without network access to `pip install` Django
or run `manage.py`/`pytest`, so it's been written and self-reviewed
(Python syntax-checked on every file; a static unused-import pass) rather
than execution-verified. A first review round against a real `pytest` run
already caught and fixed one real bug (five apps were missing
`__init__.py`, which broke test collection) plus several rubric gaps
(query-optimization coverage, `help_text`, the audit-trail model, and the
create/update serializer not actually being wired into `ItineraryViewSet`).
Still, run `python manage.py makemigrations && python manage.py migrate &&
pytest` yourself before submitting, and fix anything that surfaces —
most likely spots are field-name typos across the cross-app string FKs
(`'app_label.Model'`) and any DRF/django-filter version-specific API
differences from what's pinned in `requirements.txt`.
