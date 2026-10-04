# Question Review Platform

A small Django REST API for importing generated questions, serving eligible practice questions, recording free-text answers, and letting teachers review them. Questions have **no answer key**. Every new attempt stays pending until a teacher marks it correct or incorrect.

## Run with Docker Compose

Copy `.env.example` to `.env` and replace the secret key and database password. Docker Compose runs Django and PostgreSQL. The app container runs `migrate` whenever it starts.

```bash
cp .env.example .env
docker compose build
```

Migration files are intentionally absent because this project requires you to create them manually. Generate them before starting the app; the temporary bind mount writes the files into this repository:

```bash
docker compose run --rm -v "$PWD:/app" web python manage.py makemigrations accounts question_bank practice
docker compose up --build
```

Create sample groups, users, two skills, fifteen questions, and three attempts:

```bash
docker compose exec web python manage.py seed_demo --password 'choose-a-demo-password'
```

The sample accounts are `teacher1`, `student1`, `student2`, and `student3`. The supplied password is used only when an account is first created. Public registration creates a student account; create teacher accounts through the seed command or Django admin.

Run the tests after creating migrations:

```bash
docker compose exec web python manage.py test accounts question_bank practice
```

## Authentication

Use `Authorization: Bearer <access-token>` for protected endpoints.

| Method | Endpoint | Input | Result |
|---|---|---|---|
| POST | `/api/auth/register/` | `{"username":"student4","password":"safe-pass-123","grade":3}` | New student and access/refresh JWTs |
| POST | `/api/auth/login/` | `{"username":"student1","password":"..."}` | Access/refresh JWTs |
| POST | `/api/auth/refresh/` | `{"refresh":"..."}` | New access JWT |

Students and teachers are Django `Group` records. Their model permissions are assigned by the class based `RoleService`. The API checks both group membership and the required Django permission. The seed command sets up both groups; registration also sets them up when creating a student.

## API

| Method | Endpoint | Role | Purpose |
|---|---|---|---|
| POST | `/api/questions/import/` | Teacher | Import an upstream JSON array with per-item results |
| GET | `/api/practice/next/?skill=two_digit_addition` | Student | Get one eligible question |
| POST | `/api/attempts/` | Student | Submit a free-text answer |
| GET | `/api/attempts/pending/` | Teacher | List pending answers |
| PATCH | `/api/attempts/{id}/review/` | Teacher | Mark an answer correct or incorrect |
| GET | `/api/reports/activity/?student=1&skill=two_digit_addition` | Teacher | Report one student/skill pair |
| GET | `/api/health/` | Public | Check app and database connectivity |

Import receives the upstream contract as a JSON **array**. For example:

```json
[
  {
    "id": "qgen_100",
    "skill": "two_digit_addition",
    "grade": 3,
    "prompt_en": "What is 24 + 18?",
    "response_type": "integer",
    "requested_difficulty": 2,
    "assessed_difficulty": 2,
    "source_question_ids": ["wk_012"],
    "generation_config": {"prompt_version": "v3"},
    "validation_status": "accepted",
    "validation_reasons": ["schema_ok"]
  }
]
```

The response contains `created` IDs and `errors` per invalid item. Valid `accepted`, `rejected`, and `flagged` items are stored. The backend independently checks the schema, known skill, skill grade, repeated IDs, and normalized duplicate prompts.

An answer request looks like:

```json
{"question_item":"qgen_100","submitted_answer":"42","time_spent_seconds":20}
```

The response has `reviewed_correct: null` and `reviewed_by: null`. A teacher reviews it with `{"correct":true}` or `{"correct":false}`. Already-reviewed attempts return HTTP 400.

An activity response looks like:

```json
{"student":1,"skill":"two_digit_addition","attempts":10,"pending":2,"correct_percentage":75.0}
```

`correct_percentage` is `null` when there are no reviewed attempts. Only reviewed attempts count in its denominator.

## Structure and decisions

- `accounts` owns student profiles, JWT authentication, and Django group setup.
- `question_bank` owns skills, the upstream question contract, import validation, and practice selection.
- `practice` owns attempts, manual review, activity reporting, and the health check.
- Views handle HTTP and serializers handle request shape. Class based services handle registration, import, selection, submission, review, and reporting.
- A question's grade must match its skill's grade. Student grades are limited to 1–12.
- Duplicate prompts are compared after lowercasing and collapsing whitespace. A SHA-256 digest of the normalized prompt is uniquely indexed; this is exact normalized matching, not semantic matching.
- Practice selection takes the first accepted question for the requested skill and student grade after excluding questions from the last five attempts. When none exists, it returns HTTP 404.
- Activity reports are teacher only. A second review is rejected. PostgreSQL indexes support the selection, recent-attempt, and pending-review queries.

## Limits

This version has no pagination, semantic duplicate detection, automatic grading, password recovery, adaptive learning, or question generator. Migration files are deliberately left for manual creation. The REST API is documented here; a separate OpenAPI or Swagger page is not included.
