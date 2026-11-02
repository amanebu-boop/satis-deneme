# Hostinger migration architecture

Status date: 2026-11-02
Repository: https://github.com/amanebu-boop/satis-deneme
Working branch: `infra/github-hostinger-pipeline`

## Goal

Use GitHub-hosted automation as the control plane so the owner's personal computer does not need to remain online. Hostinger VPS remains the intended application host. Render remains untouched until an explicit production cutover approval.

## Target topology

- GitHub repository: source of truth; all application changes land on a reviewed development branch/PR.
- GitHub Actions hosted runners: temporary CI/build workers; no permanent self-hosted runner on the VPS.
- Hostinger VPS: Traefik edge proxy, application container, PostgreSQL 17, persistent uploaded-document volume.
- PostgreSQL: private Docker network only; no public database port.
- Uploaded documents and generated outputs: persistent host volume with independent backup/restore procedure.
- Secrets: GitHub Actions encrypted secrets for deployment-only SSH material; runtime application secrets remain on the VPS in root-owned files or Docker secrets, never committed to Git.

## Current verified state

- A separate branch `infra/github-hostinger-pipeline` exists.
- A GitHub Actions test workflow exists at `.github/workflows/hostinger-migration-checks.yml`; it provisions a temporary PostgreSQL 17 service, runs the SQLite suite plus a PostgreSQL integration test, and builds the application image without publishing it.
- A non-root application `Dockerfile` and `.dockerignore` exist; the image is built only in CI and has not been deployed.
- The workflow runs on pushes to this migration branch / feature branches, pull requests, and manual dispatch.
- CI installs Python 3.11, LibreOffice Calc and fonts used by document integration tests, then runs `python -m pytest -q`.
- VPS preparation already reported by the owner: Docker/Compose, Traefik, private `satis-internal` network, PostgreSQL 17 container with persistent data, UFW and SSH hardening. This document does not independently assert current live health.

## Blocking application compatibility issue

The application has an opt-in PostgreSQL backend and database-aware health check, but is not yet ready for production deployment.

- `app/db.py` retains SQLite for local/test use and now has an opt-in PostgreSQL backend through `SALES_DATABASE_URL` using psycopg 3.
- Schema setup and migrations use SQLite-specific `PRAGMA table_info`, `executescript`, and SQLite DDL.
- Existing qmark SQL is adapted for PostgreSQL by a compatibility wrapper; PostgreSQL schema introspection, case-insensitive search, and stable row ordering are covered by a dedicated integration test.
- `pyproject.toml` now declares `psycopg[binary]`.
- `app/main.py` health endpoint reports the configured backend dynamically; the application stage remains `prototype`.
- README explicitly describes the application as a prototype and warns against real customer data / commercial offers.
- The app has local authentication/prototype limitations; PostgreSQL alone does not make the app production-safe.

PostgreSQL connection support and a CI smoke test now exist, but this is not yet a production migration. Do not copy SQLite data into the Hostinger database or expose the VPS publicly until migration/rollback tooling, auth, backup/restore, and acceptance tests are complete.

## Required implementation sequence

1. Baseline: earlier GitHub Actions run `41459517303` passed both Python/PostgreSQL tests and the non-root Docker build. The latest pre-fix run `41462992982` exposed a migration-tool bug: batch inserts called `executemany` on a psycopg connection instead of a cursor. Fixed on this branch in commit `12575f7`. The follow-up CI run is `41465393641` and was pending at the time of this update.
2. Database layer: opt-in PostgreSQL backend, psycopg 3, schema introspection, case-insensitive search, health readiness (HTTP 503 on DB failure), atomic quote-number allocation and 12-way concurrency test are implemented. Full CRUD and PostgreSQL error-mapping coverage remain open.
3. Data migration: dry-run-by-default SQLite-to-PostgreSQL importer is implemented. It preserves IDs/values, checks required tables and exact column order, refuses non-empty targets, orders product options after parents, imports transactionally and verifies row counts. An end-to-end PostgreSQL 17 test covers company/contact/product-option/meeting/follow-up/quotation records. Follow-up CI result pending. Never run against production data without explicit approval and a tested backup.
4. File storage: configurable persistent document root, upload/download/generated XLSX/PDF and backup/restore behavior remain to be implemented and tested.
5. Runtime: non-root Dockerfile and healthcheck exist; CI image build passed in run `41462992982`. Runtime Compose, resource limits, persistent upload mount, staging image publication/deployment and smoke tests remain open. Keep PostgreSQL private.
6. Security: replace prototype access assumptions with production authentication/session controls, CSRF protections, authorization and audit logging. Secrets must not be present in source, image layers, logs, or workflow output.
7. CI: run unit, integration, migration, document, and container-build checks on GitHub-hosted runners.
8. Staging deployment: add a dedicated, least-privilege deploy account and a fixed server-side deployment command. Store only the deployment private key and connection metadata in GitHub encrypted secrets. Pin the server host key; do not use blind `ssh-keyscan` trust at deploy time.
9. Staging verification: deploy only to an isolated staging hostname/database; run smoke tests and backup/restore checks.
10. Production cutover: requires separate explicit approval. Keep Render available for rollback until Hostinger production is verified.

## Deployment security model

- Use GitHub-hosted runners, not a persistent runner on the VPS.
- The deployment SSH account must not be root and must not have unrestricted sudo.
- Prefer a forced command or a root-owned wrapper script that accepts only a validated release identifier and performs a fixed deployment sequence.
- Do not give the workflow a general-purpose shell on the VPS.
- Use a protected GitHub Environment for any deployment that can affect a live service.
- Limit workflow token permissions to read-only unless a specific job requires more.
- Never put Hostinger panel/API credentials, database passwords, application secrets, or private SSH keys in repository files.
- Do not automatically deploy from `main` until staging checks and the production approval gate are in place.

## Owner interaction policy

Minimize owner work. The assistant should implement repository changes and inspect CI results directly when connector permissions allow. Ask the owner only for actions that cannot be performed through available integrations, such as creating the first VPS-side deploy identity or authorizing a credential. Never request a private key or password in chat. Explain each unavoidable one-time action and batch it.

## Current boundary

This branch is preparation only. It does not deploy, restart, migrate data, modify Render, or change DNS.
