# School Management ERP — Odoo 19 Community

A modular school management system for Odoo 19 Community: schools and branches,
academics, admissions, students, teachers, timetables, attendance, exams, fees,
library, transport, communication and two web portals (parents and students).

Documentation screenshots: [docs/screenshots/demo](docs/screenshots/demo/README.md).

## Modules

| Module | Responsibility |
| --- | --- |
| `school_core` | Schools, branches, user school/branch scoping, shared mixins |
| `school_academic` | Academic years, curricula, stages, grades, subjects, sections |
| `school_security` | School groups and record rules (school isolation) |
| `school_student` | Student files, guardians and guardian links |
| `school_admission` | Admission applications with workflow states |
| `school_teacher` | Teacher profiles, contracts, subject assignment |
| `school_timetable` | Periods, timetables and schedule lines |
| `school_attendance` | Attendance sessions and lines |
| `school_exam` | Exams, exam schedules and results |
| `school_fees` | Fee types, structures, plans (assignments) and payments |
| `school_accounting` | Bridge school fees to Odoo invoices and payments |
| `school_library` | Books, members and loans |
| `school_transport` | Vehicles, routes, stops and subscriptions |
| `school_communication` | Announcements and school messages |
| `school_parent_portal` | Parent portal: `/my/children`, child dashboard, notifications |
| `school_student_portal` | Student portal: `/my/student` |

## Stack

- Odoo 19 Community, PostgreSQL 16, nginx, Docker Compose.
- Project addons are mounted at `/mnt/extra-addons`; optional third-party
  accounting addons live in `custom-addons/` (not versioned in this repository).

## Quick start

```bash
cp .env.example .env            # set POSTGRES_PASSWORD (file is git-ignored)
docker compose up -d --build
# first run: install the school modules with demo data
docker compose stop odoo
docker compose run --rm odoo -d school_erp \
  -i school_core,school_academic,school_security,school_student,school_admission,\
school_teacher,school_timetable,school_attendance,school_exam,school_fees,\
school_accounting,school_library,school_transport,school_communication,\
school_parent_portal,school_student_portal \
  --with-demo --stop-after-init
docker compose start odoo
```

Open http://localhost:8069 (database `school_erp`).

Database credentials and database name are read from `.env` (seeded from
`.env.example`); the odoo and db containers share the same values, and the
`.env` file is excluded from version control.

## Demo users

Demo data is loaded with `--with-demo`. All demo users use the password `demo`.

| Login | Role |
| --- | --- |
| `admin` | Administrator |
| `demo.manager` | School manager |
| `demo.staff` | School staff (read-only) |
| `demo.teacher` | Teacher |
| `demo.accountant` | Accountant |
| `demo.parent` | Parent portal |
| `demo.student` | Student portal |

Demo dataset: one school with two branches, two academic years, four sections,
seven students with guardians and enrollments, eight admission applications,
four teachers, timetables, attendance sessions, exams and results, fees and
payments, library, transport and communication records.

## Tests

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm odoo -d school_erp \
  --test-tags /school_core --stop-after-init
```

Replace `/school_core` with any module to run its tests. The helper
`tools/validate_addons.py` checks manifests, XML ids and file references
before a real run.

## Code generation

School codes are generated automatically from the school name when the field
is left empty (multi-word names use the word initials, single words use the
first four letters), uniqueness is enforced per company with a numeric suffix
and manual codes are preserved.

## Repository layout

```
addons/            project modules (16)
custom-addons/     optional third-party accounting addons (ignored by git)
docker/            Odoo config, nginx config, entrypoint scripts
docs/screenshots/  module and portal screenshots (demo data)
tools/             addon validation helper
.vscode/tasks.json ready-made compose tasks
```
