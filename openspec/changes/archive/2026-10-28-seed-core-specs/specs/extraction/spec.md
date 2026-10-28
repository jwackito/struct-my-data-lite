# Spec Delta

## Purpose

Parsing and LLM extraction for a single document, from job creation through pending, running, completed or failed, including schema sandboxing and model authorization.

## ADDED Requirements

### Requirement: Extraction job creation

The system SHALL create a pending extraction job from a document id and a Pydantic schema of at most 10,000 characters, returning `200` with the job id and status. It MUST return `404` for a missing document, `403` for a foreign document, `422` for an invalid or unsafe schema, and `403` for an unauthorized model.

#### Scenario: Valid request
- **WHEN** a user posts a readable document and a valid schema
- **THEN** the response is `200` with a pending job id

#### Scenario: Foreign document
- **WHEN** a user posts another user's document
- **THEN** the response is `403` with `Access denied` and no job is created

#### Scenario: Unsafe schema
- **WHEN** the schema attempts an import, builtin or dunder escape
- **THEN** the response is `422` and no job is created

### Requirement: Schema sandbox

The system SHALL validate the submitted schema through an AST allowlist before creating a job. It MUST allow only `pydantic`, `typing`, `datetime`, `enum`, `uuid` and `decimal` imports and `Field(...)` calls, and MUST reject builtins, dunder traversal, relative or wildcard imports and any other call with `422`.

#### Scenario: Disallowed import
- **WHEN** the schema imports a module outside the allowlist
- **THEN** the response is `422` with an invalid Pydantic schema error

#### Scenario: Runtime schema failure
- **WHEN** a schema passes validation but fails while building the model during extraction
- **THEN** the job fails and records the error instead of failing the HTTP request

### Requirement: Model authorization

The system SHALL authorize the selected model before creating a job. Disabled registry entries, an explicit deny grant, an admin-only model for a non-admin, a missing or disabled connection, a foreign personal connection and a plan provider-scope violation MUST return `403`.

#### Scenario: Admin-only model
- **WHEN** a non-admin selects a model marked admin-only
- **THEN** the response is `403` and no job is created

#### Scenario: Denied model
- **WHEN** the selected model has a deny grant
- **THEN** the response is `403` regardless of role

### Requirement: Job lifecycle

The system SHALL move a job only through `pending`, `running`, `completed` and `failed`. A completed job MUST store structured output data; a failed job MUST store an error message and an error detail truncated to 8 KB. A terminal job MUST have a completion timestamp.

#### Scenario: Successful extraction
- **WHEN** parsing and the model call succeed
- **THEN** the job becomes `completed`, stores the structured output and sets `completed_at`

#### Scenario: Failed extraction
- **WHEN** parsing or the model call raises an error
- **THEN** the job becomes `failed`, stores the error message and detail, and sets `completed_at`

### Requirement: Job result contract

The system SHALL return a job's id, document id, status, output data, error message, token counts, timings, connection name, provider type, model name and timestamps from `GET /jobs/{id}`. The owner and admins MAY read a job; other users MUST receive `404`.

#### Scenario: Owner reads a job
- **WHEN** the owner requests their job
- **THEN** the response contains the full result contract

#### Scenario: Foreign job
- **WHEN** a non-owner requests another user's job
- **THEN** the response is `404` and the job is not disclosed

### Requirement: Parsing by document type

The system SHALL parse PDF, DOCX, DOC, TXT, CSV and image documents. It MUST extract PDF text per page, read DOCX as OOXML, read legacy DOC through antiword or python-docx, pass TXT through unchanged, read CSV rows with padded columns and pass images as base64 data. An unsupported type MUST fail the job.

#### Scenario: Text PDF
- **WHEN** a PDF contains extractable text
- **THEN** the text is extracted and sent to the model as text

#### Scenario: CSV
- **WHEN** a CSV has rows of different widths
- **THEN** short rows are padded and joined so the model receives an even table

#### Scenario: Unsupported type
- **WHEN** no parser matches the document
- **THEN** the job fails with an unsupported content type error

### Requirement: Vision extraction

The system SHALL send images as image content alongside the extraction prompt. A PDF with no extractable text MUST be rendered to page images and processed as a vision request, using the connection's configured vision model when one is set.

#### Scenario: Scanned PDF
- **WHEN** every page of a PDF lacks extractable text
- **THEN** the pages are rendered to images and the extraction uses the vision path

#### Scenario: Image upload
- **WHEN** the document is an image
- **THEN** the raw image is sent as base64 with the prompt

### Requirement: Job retry

The system SHALL allow retry only for pending or failed jobs. A retry MUST reset the job to pending and clear its error, completion time, token counts and parsing and model timings while preserving upload timing. A completed job MUST be rejected.

#### Scenario: Retry a failed job
- **WHEN** the owner retries a failed job
- **THEN** the job returns to pending and the previous error and timings are cleared

#### Scenario: Retry a completed job
- **WHEN** the owner retries a completed job
- **THEN** the request is rejected and the job is unchanged

### Requirement: Queue overflow

The system SHALL run at most the configured number of jobs concurrently and allow a bounded waiting queue, two running and four waiting by default. When no slot is available, job creation MUST return `503` and MUST NOT leave committed job rows behind.

#### Scenario: Queue full
- **WHEN** the queue has no free slot
- **THEN** the response is `503` with `Server is busy, try again shortly` and no orphan job remains

### Requirement: Usage recording

The system SHALL store input and output token counts when the provider reports usage, and leave them null when it does not. Cost MUST be computed when usage is read rather than stored on the job.

#### Scenario: Provider reports usage
- **WHEN** the model response includes usage
- **THEN** the job stores both token counts and usage views can price them

#### Scenario: No usage reported
- **WHEN** the provider returns no usage
- **THEN** the job's token fields remain null and cost reads as zero
