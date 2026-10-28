# schemas Specification

## Purpose
Saved Pydantic schemas, the visual builder, import and export, and sharing for reusable extraction definitions.

## Requirements

### Requirement: Schema CRUD

The system SHALL let an authenticated user list their own saved schemas newest first, create a schema from a name and code, read one, update its name, code or visibility, and delete it. Creating or updating SHALL return `422` for an empty name or empty code, and an unknown or inaccessible schema SHALL return `404`.

#### Scenario: Create and list
- **WHEN** a user creates a schema and then lists schemas
- **THEN** the new schema appears in their list with its id and name

#### Scenario: Unknown schema
- **WHEN** a user requests a schema they cannot read
- **THEN** the response is `404`

#### Scenario: Unauthenticated
- **WHEN** a request without a valid session calls a schema route
- **THEN** the response is `401`

### Requirement: Schema name uniqueness

Saved schema names SHALL be unique within a user's namespace. Creating or renaming to an existing name MUST return `409`; the same name MAY exist for different users.

#### Scenario: Duplicate name
- **WHEN** a user creates a schema whose name already exists in their namespace
- **THEN** the response is `409` and the existing schema is unchanged

#### Scenario: Same name across users
- **WHEN** two users create schemas with the same name
- **THEN** both succeed and each sees only their own

### Requirement: Schema access control

The owner and admins SHALL be able to read, update and delete a schema. A public schema MAY be read and duplicated by other users, but public visibility MUST NOT grant write access.

#### Scenario: Shared schema is read-only
- **WHEN** a non-owner tries to update or delete another user's public schema
- **THEN** the response is `404` and the schema is unchanged

#### Scenario: Admin manages any schema
- **WHEN** an admin updates or deletes another user's schema
- **THEN** the operation is allowed

### Requirement: Schema length limit

Schema code SHALL be limited to 10,000 characters on create, update and import file size. A longer value MUST return `422` and MUST NOT be saved.

#### Scenario: Code too long
- **WHEN** a user submits schema code above the limit
- **THEN** the response is `422` and no schema is created or updated

### Requirement: Schema validation boundary

Creating or updating a saved schema SHALL enforce only non-empty fields and the length limit. Sandbox validation MUST run when a schema is parsed, imported, used for extraction or used for a batch, and MUST reject unsafe code there with `422`.

#### Scenario: Unsafe code saved but rejected on use
- **WHEN** a user saves code that passes the length check but violates the sandbox
- **THEN** saving succeeds and parsing, importing or extracting with it returns `422`

### Requirement: Public and shared schemas

Schemas SHALL default to private. A user MAY mark their schema public; the shared list SHALL return other users' public schemas with the owner name, ordered by name. Duplicating a shared schema SHALL create a private copy owned by the caller under the same name.

#### Scenario: Shared list
- **WHEN** a user requests shared schemas
- **THEN** they see public schemas owned by others, with owner names and read-only access

#### Scenario: Duplicate a shared schema
- **WHEN** a user duplicates a shared schema
- **THEN** a private copy is created for that user and a name collision returns `409`

### Requirement: Schema import

The system SHALL import a `.py` or `.json` file up to 10,000 bytes over UTF-8. JSON SHALL be detected by a leading `{`; otherwise the file is treated as Python and named from the filename without its extension. Imported code MUST pass the sandbox, an empty file MUST return `422`, and an invalid file or JSON MUST return `422`.

#### Scenario: Import Python
- **WHEN** a user imports a valid Python schema file
- **THEN** a schema is created using the filename as its name

#### Scenario: Import JSON
- **WHEN** a user imports a valid JSON schema file
- **THEN** a schema is created with the same name rules as Python imports

#### Scenario: Oversized or invalid file
- **WHEN** the file exceeds 10,000 bytes, is not UTF-8 or fails the sandbox
- **THEN** the response is `422` and no schema is created

### Requirement: Schema export

The system SHALL export a readable schema as a `text/plain` attachment named `<name>.py`, containing a comment header with the schema name, creation time and format version, followed by the Pydantic code.

#### Scenario: Export
- **WHEN** an owner exports a schema
- **THEN** the response is a `.py` attachment with the header and the schema code

### Requirement: Schema parsing for the builder

The system SHALL parse Pydantic code into a model name and a field tree for the visual builder. It SHALL support `str`, `int`, `float`, `bool`, `date`, `datetime`, `List`, `Optional`, nested models, descriptions and defaults, and SHALL return `422` for empty code, syntax errors or sandbox violations.

#### Scenario: Nested model
- **WHEN** the code defines a model with a nested model field
- **THEN** the parsed field tree contains a child object for the nested model

#### Scenario: Invalid syntax
- **WHEN** the code is not valid Python
- **THEN** the response is `422` with a syntax error

### Requirement: Builder and code generation

The system SHALL generate executable Pydantic code from a builder field tree and parse that code back into an equivalent tree. Generated code MUST be valid Python, MUST import only what it uses, and MUST support empty models.

#### Scenario: Round trip
- **WHEN** a builder tree is converted to code and parsed back
- **THEN** the resulting tree is equivalent to the original

#### Scenario: Empty model
- **WHEN** a model has no fields
- **THEN** the generated class is valid and uses `pass`

### Requirement: Admin schema management

The system SHALL let admins view every saved schema with its owner, visibility and timestamps, and change visibility or delete any schema through the normal update and delete routes.

#### Scenario: Admin publishes a schema
- **WHEN** an admin sets a schema public
- **THEN** it appears in other users' shared list

#### Scenario: Non-admin admin page
- **WHEN** a non-admin requests the schema admin data
- **THEN** the response is `403`
