# Spec Delta

## Purpose

Development and production topology, image build, configuration, migrations, health checks, CI and release for the lite edition.

## ADDED Requirements

### Requirement: Deployment topology

The system SHALL provide a development compose with `app`, `db` and `test-db`, and a production compose with `app`, `db` and `caddy`. Ollama MUST run externally and be reached through `host.docker.internal`; production MUST NOT publish application or database ports, and Caddy SHALL publish port 80 and the configured HTTPS port.

#### Scenario: Development services
- **WHEN** the development stack starts
- **THEN** the app is reachable on port 8080 and both databases are available to tests

#### Scenario: Production exposure
- **WHEN** the production stack starts
- **THEN** only Caddy publishes host ports and the app and database stay internal

### Requirement: Production image

The production image SHALL build from a digest-pinned Python 3.12 slim image, install hash-pinned requirements and `antiword`, run as UID 10001, bake the application, scripts and Alembic files, and create a writable `/app/storage`.

#### Scenario: Non-root runtime
- **WHEN** the production container starts
- **THEN** the process runs as UID 10001 and can write to `/app/storage`

#### Scenario: Reproducible dependencies
- **WHEN** the image is built
- **THEN** dependencies are installed from hash-pinned requirement files

### Requirement: Production hardening

The production stack SHALL enable init, a 30-second stop grace period, restart unless stopped, memory and CPU limits for every service, json-file log rotation, and a readiness healthcheck against `/health/ready` for the application.

#### Scenario: App readiness
- **WHEN** the application fails its readiness check
- **THEN** the container is reported unhealthy and restart policy applies

#### Scenario: Log rotation
- **WHEN** a service writes more logs than the configured limit
- **THEN** old log files are rotated out

### Requirement: Configuration and secrets

Configuration SHALL come from `etc/.env`, which MUST be gitignored. `JWT_SECRET` MUST be set when `ENV` is not `dev`; `APP_SECRET_KEY` MUST be a Fernet key for provider-secret encryption; `POSTGRES_PASSWORD` SHALL secure the database. Uploaded documents SHALL persist in a named volume.

#### Scenario: Missing JWT secret
- **WHEN** production starts without `JWT_SECRET`
- **THEN** startup fails instead of using a random secret

#### Scenario: Secret storage
- **WHEN** an operator follows the setup
- **THEN** secrets live in `etc/.env` and are not committed

### Requirement: Migrations

Production migrations SHALL run through `python -m scripts.migrate`, which takes advisory lock `727234001`, runs `alembic upgrade head` as a subprocess and always attempts to release the lock. Bare Alembic MUST NOT be the documented production path.

#### Scenario: Locked migration
- **WHEN** two deploys migrate at the same time
- **THEN** the advisory lock serialises them

#### Scenario: Failure
- **WHEN** the upgrade fails
- **THEN** the runner returns the failure code and releases the lock

### Requirement: Health and readiness

`GET /health` SHALL return `200` with an ok status without querying the database. `GET /health/ready` SHALL execute a database check, returning `200` when it succeeds and `503` when it fails.

#### Scenario: Liveness
- **WHEN** the database is unreachable but the process is alive
- **THEN** `/health` still returns `200`

#### Scenario: Readiness
- **WHEN** the database check fails
- **THEN** `/health/ready` returns `503`

### Requirement: Startup

Startup SHALL initialise the JWT secret, then wait up to 30 attempts of one second for the database unless `SKIP_DB_WAIT` is set, and SHALL fail if the database never becomes available. `GET /api/version` SHALL return the first version heading in `CHANGELOG.md`, or `dev` when absent.

#### Scenario: Database available late
- **WHEN** the database becomes available within the wait window
- **THEN** startup continues

#### Scenario: Database never available
- **WHEN** the wait window expires
- **THEN** startup fails with an error

### Requirement: CI checks

CI SHALL run the pytest suite on pull requests and pushes to `main` against PostgreSQL 16 and Python 3.12, plus a shell syntax check. Pull requests MUST pass the branch and commit guards and the OpenSpec validation job, and a push to `main` without an associated pull request MUST be flagged.

#### Scenario: Pull request
- **WHEN** a pull request is opened
- **THEN** tests, guards and OpenSpec validation run

#### Scenario: Direct push
- **WHEN** a commit reaches `main` without a pull request
- **THEN** the main guard reports a failure

### Requirement: Release

A tag matching `v*-lite` SHALL build and push the production image to `ghcr.io/jwackito/struct-my-data` with the tag name and a `sha-<commit>` tag. Production compose SHALL accept a pinned image reference, a repository and tag, or a default image.

#### Scenario: Release tag
- **WHEN** a `vX.Y.Z-lite` tag is pushed
- **THEN** CI publishes the image under that tag and the commit tag

#### Scenario: Pinned deploy
- **WHEN** an operator sets an image reference
- **THEN** production compose uses that image instead of the default

### Requirement: Configuration defaults

The system SHALL default to a 10 MiB upload limit, 50 files per batch, two concurrent jobs, four queued jobs, a 24-hour JWT, auth/extract/batch rate limits of 10/30/5 per minute, `ENV=dev` and usage enforcement off.

#### Scenario: Fresh development install
- **WHEN** no optional environment variables are set
- **THEN** the documented defaults apply
