# providers Specification

## Purpose
Provider connections, personal API keys, the model registry and pricing used to authorize, list and price extractions.

## Requirements

### Requirement: Supported provider connections

The system SHALL support `openai`, `gemini` and `ollama` connections. OpenAI SHALL accept `api_key` and an optional `base_url`; Gemini SHALL accept `api_key` and an optional `model`; Ollama SHALL accept `host`, `model` and `vision_model`. Creating or updating a connection with an unsupported provider MUST return `422`.

#### Scenario: Create an OpenAI key
- **WHEN** an admin submits an OpenAI connection with a valid key
- **THEN** the connection is stored and listed without exposing the key

#### Scenario: Unsupported provider
- **WHEN** a connection names a provider outside the supported set
- **THEN** the response is `422` and no connection is stored

### Requirement: Implicit Ollama connection

The system SHALL always expose an implicit Ollama connection named `ollama`, enabled and configured from `OLLAMA_HOST`, `OLLAMA_MODEL` and `OLLAMA_VISION_MODEL`. It MUST NOT be modified or deleted; such attempts MUST return `422`.

#### Scenario: Implicit connection listed
- **WHEN** a user lists connections or personal keys
- **THEN** the implicit `ollama` connection is present

#### Scenario: Modify implicit connection
- **WHEN** an admin or user tries to update or delete `ollama`
- **THEN** the response is `422` and the connection is unchanged

### Requirement: Connection scope and resolution

A connection SHALL be global when it has no owner and personal when it belongs to a user. Model resolution MUST prefer a personal connection with the same name over a global one, even when the personal one is disabled. Model listing SHALL merge a personal connection only when no global connection has the same name.

#### Scenario: Personal shadows global
- **WHEN** a user has a personal connection with the same name as a global connection
- **THEN** that user's requests use the personal connection

#### Scenario: Foreign personal connection
- **WHEN** a user references another user's personal connection
- **THEN** the request is rejected with `403`

### Requirement: Admin global connections

Admin-only routes SHALL list, read, upsert, delete and test global connections. Unauthenticated requests MUST return `401` and non-admins MUST return `403`. Upsert MUST reject a missing or unsupported provider and a failed connectivity test with `422`. The test route MAY run without an existing connection and SHALL return success with models or a failure with an error.

#### Scenario: Non-admin access
- **WHEN** a non-admin calls a global connection route
- **THEN** the response is `403`

#### Scenario: Failed test on save
- **WHEN** an admin saves a connection whose provider test fails
- **THEN** the response is `422` with the failure reason and the connection is not saved

#### Scenario: Test a candidate connection
- **WHEN** an admin tests a candidate connection
- **THEN** the response is `200` with either `{ok: true, models}` or `{ok: false, error}`

### Requirement: Personal API keys

An authenticated user SHALL be able to list, create, update and delete their own personal provider keys. The list SHALL include the implicit Ollama connection and the caller's keys only. Creating a key MUST validate the provider and test connectivity; updating MUST NOT test connectivity. The name `ollama` MUST be rejected with `422`, and a foreign key MUST be invisible.

#### Scenario: Create a personal key
- **WHEN** a user creates a valid personal key
- **THEN** the key is stored for that user and appears in their list

#### Scenario: Foreign key
- **WHEN** a user tries to update or delete another user's key
- **THEN** the response is `404`

#### Scenario: Reserved name
- **WHEN** a user tries to create a personal key named `ollama`
- **THEN** the response is `422`

### Requirement: Secret protection

Provider secrets MUST be encrypted at rest using `APP_SECRET_KEY`, or an ephemeral key only when `SKIP_ENCRYPTION` is set. List and write responses MUST mask `api_key`, replacing short values entirely and keeping only the last four characters of longer values. The admin single-connection detail is the documented exception that returns decrypted values for editing.

#### Scenario: Masked list
- **WHEN** a user or admin lists connections
- **THEN** no raw `api_key` appears in the response

#### Scenario: Missing encryption key
- **WHEN** encryption is required and `APP_SECRET_KEY` is absent
- **THEN** storing secrets fails instead of writing plaintext

### Requirement: Model listing

`GET /models` SHALL return entries with an id of `provider/connection/model`, the provider, connection and model names, display name, description, capabilities, context window, input and output prices and a default flag. It MUST hide disabled connections, disabled registry rows, deny grants, embeddings-only models and admin-only models from non-admins without an allow grant. Admins SHALL see admin-only models; an allow grant SHALL override the admin-only restriction.

#### Scenario: Disabled model hidden
- **WHEN** a registry row or connection is disabled
- **THEN** its models do not appear in the list

#### Scenario: Admin-only model
- **WHEN** a non-admin lists models without an allow grant
- **THEN** admin-only models are absent, while an admin sees them

#### Scenario: Embeddings model
- **WHEN** a model declares only the embeddings capability
- **THEN** it is absent from the extraction model list

### Requirement: Model authorization denials

Before creating a job or batch, the system SHALL authorize the selected model and MUST return `403` for a plan limited to Ollama when a non-Ollama model is selected, a missing or disabled connection, a disabled registry row, a deny grant, or an admin-only model used without an allow grant.

#### Scenario: Admin-only model blocked
- **WHEN** a non-admin submits an admin-only model without an allow grant
- **THEN** the response is `403` and no job is created

#### Scenario: Denied model
- **WHEN** the selected model has a deny grant
- **THEN** the response is `403`

### Requirement: Model resolution and grants

Admins SHALL bypass the admin-only restriction, and an allow grant SHALL bypass it for users. A missing registry row SHALL be allowed. An empty model id SHALL resolve to the default registry row or the configured Ollama model.

#### Scenario: Allow grant
- **WHEN** a user with an allow grant submits an admin-only model
- **THEN** authorization succeeds

#### Scenario: Empty model id
- **WHEN** a request omits the model id
- **THEN** the default registry model or the configured Ollama model is used

### Requirement: Registry synchronization

Model listing and the admin refresh SHALL synchronize models from the configured providers, upserting by connection and model name, updating the last-seen time and filling capabilities only when they are unset, without deleting stale rows. A provider failure MUST yield an empty list for that provider rather than failing the request.

#### Scenario: Refresh
- **WHEN** an admin refreshes models
- **THEN** new provider models are added and existing rows are updated

#### Scenario: Provider unreachable
- **WHEN** a provider's model endpoint fails
- **THEN** the sync continues with the remaining providers

### Requirement: Pricing

The system SHALL price usage from a static per-million-token table, overridden by enabled registry prices, using an exact model match, then the provider default, then a prefix match. Unknown models MUST cost zero. Cost SHALL equal tokens multiplied by the price and divided by one million, with API estimates and usage rounded to six decimals.

#### Scenario: Exact match
- **WHEN** a known model has a configured price
- **THEN** its cost uses that price per million tokens

#### Scenario: Unknown model
- **WHEN** no price matches the model or provider
- **THEN** the cost is zero

#### Scenario: Prefix match
- **WHEN** a model name starts with a priced prefix
- **THEN** the prefix price is used
