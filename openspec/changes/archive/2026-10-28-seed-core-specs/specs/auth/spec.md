# Spec Delta

## Purpose

Authentication, sessions, API tokens and account access for the lite edition, including registration policy, token lifecycle and the identity every other capability uses for ownership.

## ADDED Requirements

### Requirement: Email registration

The system SHALL create a user with role `user` when public registration is enabled, normalising the email to trimmed lowercase and defaulting the display name to the email local-part. It MUST reject malformed emails, passwords shorter than eight characters and duplicate emails with `422`.

#### Scenario: Successful registration
- **WHEN** a visitor posts a valid email and an eight-character password while registration is enabled
- **THEN** the response is `200` with a JWT and user record, and a `token` cookie is set

#### Scenario: Duplicate email
- **WHEN** a visitor registers an email that already exists
- **THEN** the response is `422` with `Email already registered` and no user is created

#### Scenario: Registration disabled
- **WHEN** public registration is disabled
- **THEN** registration returns `403` and the registration page is unavailable

### Requirement: Login and session cookie

The system SHALL authenticate an active user by email and password, returning a JWT and setting an `httponly` `token` cookie whose lifetime matches the JWT expiry, 24 hours by default. Invalid credentials MUST return `401`; disabled accounts MUST return `403`.

#### Scenario: Valid login
- **WHEN** an active user posts the correct email and password
- **THEN** the response is `200` with a JWT and user record, and the `token` cookie is set

#### Scenario: Invalid credentials
- **WHEN** the password is wrong or the email is unknown
- **THEN** the response is `401` with `Invalid email or password`

#### Scenario: Disabled account
- **WHEN** a disabled user presents valid credentials
- **THEN** the response is `403` with `Account is disabled`

### Requirement: Session validation

The system SHALL accept a JWT from the `Authorization: Bearer` header or the `token` cookie, reject missing, invalid or expired tokens with `401`, and reject tokens for disabled users. `JWT_SECRET` MUST be configured when `ENV` is not `dev`; the application MUST fail at startup without it outside development.

#### Scenario: Authenticated request
- **WHEN** a request carries a valid JWT in the header or cookie
- **THEN** the request is attributed to that user and role

#### Scenario: Missing or invalid token
- **WHEN** a protected request has no token, an expired token or a malformed token
- **THEN** the response is `401` and no protected data is returned

#### Scenario: Missing secret outside development
- **WHEN** the application starts with `ENV` set to a non-development value and no `JWT_SECRET`
- **THEN** startup fails instead of generating a secret

### Requirement: Logout

The system SHALL clear the authentication cookie on logout and return `200` even when no valid session is present.

#### Scenario: Logout
- **WHEN** a client posts to `/auth/logout`
- **THEN** the `token` cookie is cleared and the response is `200`

### Requirement: API token lifecycle

The system SHALL let a user create a named API token, return the raw value exactly once with the `smd_` prefix, list only metadata afterwards, and revoke a token so that it can no longer authenticate. Tokens MUST be stored as a hash, belong to their creator, and MAY have an expiry.

#### Scenario: Create and list
- **WHEN** a user creates a named token
- **THEN** the response contains the raw `smd_` token once, and later list responses contain only its id, name, prefix, state, expiry and timestamps

#### Scenario: Revoked token
- **WHEN** a user revokes a token and then uses it
- **THEN** the token is rejected with `401`

#### Scenario: Foreign token
- **WHEN** a user tries to revoke another user's token
- **THEN** the response is `404` and the token remains active

### Requirement: Account status and roles

The system SHALL treat users as either `user` or `admin`. Disabled users MUST NOT authenticate with a password, JWT or API token. Admin-only routes MUST reject non-admins with `403`; ownership checks MUST allow admins to access foreign documents and jobs where the route permits it.

#### Scenario: Disabled user with a token
- **WHEN** a disabled user presents a previously valid JWT or API token
- **THEN** the request is rejected and no data is returned

#### Scenario: Non-admin on an admin route
- **WHEN** a `user` calls an admin-only route
- **THEN** the response is `403`

### Requirement: Auth rate limiting

The system SHALL apply an in-memory per-IP token bucket to login and registration, defaulting to ten requests per minute, and MUST return `429` with a `Retry-After` header when the limit is exceeded.

#### Scenario: Limit exceeded
- **WHEN** a client exceeds the configured auth rate limit
- **THEN** the response is `429` with `Retry-After` and no authentication attempt is processed

### Requirement: Password storage

The system SHALL store passwords only as bcrypt hashes and MUST never return a password hash in an API response.

#### Scenario: User response
- **WHEN** a user is created or fetched
- **THEN** the response contains no password or password hash
