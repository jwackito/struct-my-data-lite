# Spec Delta

## Purpose

Document intake, upload limits, safe storage names, per-user deduplication and ownership rules for every file the system extracts from.

## ADDED Requirements

### Requirement: Authenticated upload

The system SHALL accept a multipart `file` upload only from an authenticated user and return the stored document's id, filename, content type, size, storage path and timestamps.

#### Scenario: Authenticated upload
- **WHEN** an authenticated user uploads a file
- **THEN** the response is `200` with the document metadata and the file is stored for that user

#### Scenario: Anonymous upload
- **WHEN** an unauthenticated request posts a file
- **THEN** the response is `401` and no document is created

### Requirement: Upload size limit

The system SHALL reject files larger than `MAX_UPLOAD_SIZE`, 10 MiB by default, with `413` and MUST NOT store the rejected file.

#### Scenario: Oversized file
- **WHEN** an authenticated user uploads a file larger than the configured limit
- **THEN** the response is `413` with `File exceeds maximum upload size` and no document row is created

### Requirement: Safe storage names

The system SHALL store each accepted upload under the storage directory using a unique generated name, replacing path separators and NUL characters in the client filename, so that uploads cannot overwrite each other or escape the directory.

#### Scenario: Duplicate filenames
- **WHEN** two uploads use the same client filename
- **THEN** both are stored under different generated names and neither file is overwritten

#### Scenario: Unsafe filename
- **WHEN** a client filename contains `/`, `\`, `:` or NUL
- **THEN** those characters are replaced before the name is used on disk

### Requirement: Per-user deduplication

The system SHALL deduplicate identical uploads by content hash within a single user's documents. Re-uploading the same bytes as the same user MUST return the existing document; the same bytes uploaded by another user MUST create a separate document.

#### Scenario: Same user re-uploads
- **WHEN** a user uploads bytes that hash to an existing document they own
- **THEN** the existing document id is returned and no duplicate row or file is created

#### Scenario: Different users
- **WHEN** two users upload identical bytes
- **THEN** each user gets their own document row and access is isolated

### Requirement: Document ownership

The system SHALL associate each document with its uploading user. Non-owners MUST receive `403` when using the document for extraction or batch creation, while admins MAY access foreign documents. A document without an owner MUST NOT be accessible to non-admins.

#### Scenario: Foreign document
- **WHEN** a user references another user's document in extraction or batch creation
- **THEN** the response is `403` with `Access denied`

#### Scenario: Admin access
- **WHEN** an admin references a foreign document
- **THEN** the operation is allowed

### Requirement: Deferred type validation

The system SHALL accept an upload without enforcing a MIME or extension allowlist at upload time. Unsupported types MUST fail later during parsing as a failed extraction job rather than as an upload rejection.

#### Scenario: Unsupported type
- **WHEN** a user uploads a file whose type no parser supports
- **THEN** the upload succeeds and the extraction job fails with an unsupported content type error

### Requirement: Document metadata

The system SHALL preserve the original client filename, the detected content type, the byte size, the storage path and creation and update timestamps for each document, defaulting a missing content type to `application/octet-stream` and a missing filename to `unnamed`.

#### Scenario: Missing metadata
- **WHEN** an upload omits the filename or content type
- **THEN** the stored document uses `unnamed` and `application/octet-stream` respectively
