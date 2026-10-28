# admin Specification

## Purpose
Administrative visibility and control over users, usage, failures, jobs, schemas and models in the lite edition.

## Requirements

### Requirement: Admin authorization

Every `/admin` page and data route SHALL require an admin. Missing or invalid credentials MUST return `401`; an authenticated non-admin MUST return `403`. The navigation SHALL show admin links only to admins.

#### Scenario: No session
- **WHEN** an unauthenticated request calls an admin route
- **THEN** the response is `401`

#### Scenario: Regular user
- **WHEN** a non-admin calls an admin route
- **THEN** the response is `403` with `Admin access required`

#### Scenario: Navigation
- **WHEN** a regular user loads the application
- **THEN** admin links are absent from the navigation

### Requirement: User listing and creation

`GET /admin/users/data` SHALL list users newest first with offset, limit, 20 by default, a case-insensitive search over email and display name, and a job count per user. `POST /admin/users` SHALL create a user with a valid email, a password of at least eight characters and a role of `user` or `admin`, defaulting to `user`.

#### Scenario: Search users
- **WHEN** an admin searches by part of an email or display name
- **THEN** only matching users are returned with their job counts

#### Scenario: Create a user
- **WHEN** an admin submits a unique email and a valid password
- **THEN** the user is created with the requested or default role

#### Scenario: Duplicate email
- **WHEN** an admin creates a user with an existing email
- **THEN** the response is `422`

### Requirement: User status, role and deletion

Admins SHALL be able to toggle a user's active status, set their role, and delete them. Deletion SHALL soft-disable the user. A missing user MUST return `404`, and an admin attempting to change their own status, role or account MUST return `422`.

#### Scenario: Disable a user
- **WHEN** an admin toggles a user inactive
- **THEN** the user can no longer authenticate

#### Scenario: Self action
- **WHEN** an admin tries to change their own status or role
- **THEN** the response is `422`

#### Scenario: Delete
- **WHEN** an admin deletes a user
- **THEN** the user is marked inactive and their data is retained

### Requirement: System usage

`GET /admin/usage/data` SHALL summarize completed jobs with non-null token counts, optionally filtered by date range and user, and SHALL return total users, jobs, input and output tokens and cost, plus per-user rows sorted by job count. Costs MUST be rounded to six decimals. `group=day` SHALL add a daily breakdown.

#### Scenario: Usage summary
- **WHEN** an admin requests system usage
- **THEN** totals and per-user rows are returned with costs rounded to six decimals

#### Scenario: Date filter
- **WHEN** an admin supplies a from or to date
- **THEN** only jobs inside the inclusive range are counted

### Requirement: Failure observability

`GET /admin/failures/data` SHALL list failed jobs newest first with pagination and optional filters for user, model, connection, content type and a since/until time range. It SHALL return the job id, creation time, user email, filename, content type, model, connection, provider and error message.

#### Scenario: Filter failures
- **WHEN** an admin filters by model and content type
- **THEN** only matching failed jobs are returned

#### Scenario: Only failures
- **WHEN** an admin opens the failures view
- **THEN** completed and pending jobs are absent

### Requirement: Job inspection and download

`GET /admin/jobs/{id}` SHALL show a job's owner, document, model, connection, provider, timestamps, schema, error and output. `GET /admin/jobs/{id}/document` SHALL return the original document with its content type and an attachment filename. A missing job, document or file MUST return `404`.

#### Scenario: Inspect a job
- **WHEN** an admin opens a job detail page
- **THEN** the page shows the job, owner and result or error

#### Scenario: Download the document
- **WHEN** an admin downloads the job's document
- **THEN** the response is the original bytes with its content type

### Requirement: Model administration

`GET /admin/models/data` SHALL list registry models with connection, provider, search and hidden filters, showing implicit Ollama rows as `ollama` and hiding disabled models unless requested. `POST /admin/models/refresh` SHALL sync providers and refresh pricing. `PATCH /admin/models/{id}` SHALL accept only display, description, capabilities, context window, prices, enabled, admin-only, default and sort fields; an unknown field MUST return `422` and a missing model `404`.

#### Scenario: Hidden models
- **WHEN** an admin lists models without including hidden ones
- **THEN** disabled registry rows are absent

#### Scenario: Set a default
- **WHEN** an admin marks a model as default
- **THEN** other models for the same connection lose the default flag

#### Scenario: Unknown patch field
- **WHEN** an admin patches a field outside the allowed set
- **THEN** the response is `422`

### Requirement: Per-user model grants

Admins SHALL be able to read and replace a user's model grants with `allow`, `deny` or `default`. `default` SHALL remove the grant. An invalid access value MUST return `422`, and a missing user or model MUST return `404`.

#### Scenario: Deny a model
- **WHEN** an admin sets a user's grant for a model to `deny`
- **THEN** that model disappears from the user's list and is rejected at job creation

#### Scenario: Reset a grant
- **WHEN** an admin sets a grant to `default`
- **THEN** the explicit grant is removed

### Requirement: Admin override

Admins SHALL be able to use foreign documents for extraction, read, retry and download foreign jobs, access their WebSocket and bypass admin-only model restrictions. Personal job and usage listings SHALL still show only the caller's records.

#### Scenario: Foreign document
- **WHEN** an admin extracts from another user's document
- **THEN** the extraction is allowed

#### Scenario: Personal listing
- **WHEN** an admin opens their own job history
- **THEN** it contains only their jobs

#### Scenario: Admin-only model
- **WHEN** an admin selects an admin-only model
- **THEN** authorization succeeds
