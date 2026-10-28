# Spec Delta

## Purpose

Batch creation, progress, retry, cancellation and combined results for groups of documents extracted with one schema and model.

## ADDED Requirements

### Requirement: Batch creation

The system SHALL create a batch from a non-empty list of document ids with one pending job per document, a shared schema and an optional model, returning the batch id, job ids and name. It MUST reject more than `MAX_BATCH_SIZE`, 50 by default, or a lower plan cap with `422`, and MUST reject missing or foreign documents with `404` or `403`.

#### Scenario: Create a batch
- **WHEN** a user submits two readable documents and a valid schema
- **THEN** the response is `200` with a batch id, two job ids and a generated name

#### Scenario: Over the limit
- **WHEN** a user submits 51 documents with the default limit
- **THEN** the response is `422` with `Batch exceeds max size of 50` and no batch is created

#### Scenario: Foreign document
- **WHEN** a batch includes another user's document
- **THEN** the response is `403` and no batch is created

### Requirement: Batch ownership

The system SHALL restrict every batch endpoint to the batch owner. A non-owner MUST receive `404`, and admins MUST NOT bypass batch ownership.

#### Scenario: Foreign batch
- **WHEN** a user requests another user's batch progress
- **THEN** the response is `404`

#### Scenario: Admin on a foreign batch
- **WHEN** an admin requests another user's batch
- **THEN** the response is `404`

### Requirement: Batch listing and progress

The system SHALL list a user's batches newest first with offset and limit, 20 per page by default, and return per-batch counts for total, pending, running, completed and failed jobs. Batch progress SHALL list each job with its id, filename, status, error message and model name.

#### Scenario: List batches
- **WHEN** a user requests their batch list
- **THEN** the response contains their batches with pagination totals and job counters

#### Scenario: Batch progress
- **WHEN** the owner requests a batch
- **THEN** the response lists each job with its current status and counters

### Requirement: Retry failed jobs

The system SHALL retry only failed jobs in a batch, resetting them to pending and clearing their error, completion time, tokens and timings, clearing the batch completion time, and enqueuing them again. It MUST return the number of retried jobs and leave other jobs unchanged.

#### Scenario: Retry failed
- **WHEN** the owner retries a batch with failed jobs
- **THEN** those jobs return to pending and the response reports how many were retried

#### Scenario: No failed jobs
- **WHEN** the owner retries a batch with no failed jobs
- **THEN** the response reports zero retried jobs and no job changes state

### Requirement: Cancel batch

The system SHALL cancel pending and running jobs in a batch, marking them failed with `Cancelled by user` and a completion time, and return the number cancelled.

#### Scenario: Cancel
- **WHEN** the owner cancels a batch with pending and running jobs
- **THEN** those jobs become failed with `Cancelled by user` and the response reports the count

### Requirement: Combined results

The system SHALL return a JSON download named `batch-<id>.json` containing the batch id, name and one result per job with job id, filename, status, output data, error message and model name.

#### Scenario: Download results
- **WHEN** the owner downloads a batch's results
- **THEN** the response is a JSON attachment with one entry per job

### Requirement: Cost estimate

The system SHALL estimate a batch before creation from a non-empty list of file sizes, rejecting a list above the batch limit with `422`. It SHALL estimate input tokens as total bytes divided by four, output tokens as one quarter of the input estimate, and return document count, estimated tokens, estimated cost rounded to six decimals and the selected model.

#### Scenario: Estimate
- **WHEN** a user submits valid file sizes
- **THEN** the response contains the document count, token estimate, cost estimate and model

#### Scenario: Missing sizes
- **WHEN** the request omits file sizes
- **THEN** the response is `422`

### Requirement: Multipart UI batch

The system SHALL create a batch from the upload form even when it contains a single file, skip files above the upload limit, reuse the same user's duplicate documents, and redirect to the batch page with `HX-Redirect`.

#### Scenario: Single file
- **WHEN** a user submits one file from the upload form
- **THEN** a batch of one is created and the response redirects to its batch page

#### Scenario: Oversized file in a batch
- **WHEN** one file in a multipart batch exceeds 10 MiB
- **THEN** that file is skipped and the remaining files form the batch

### Requirement: Batch quotas

When usage enforcement or a plan sets limits, the system SHALL reject batch creation that would exceed the user's active or daily job cap with `429`, and MUST reject a batch above a plan's vision batch cap with `422`.

#### Scenario: Active job cap
- **WHEN** a user with an active-job cap submits a batch that would exceed it
- **THEN** the response is `429` and no jobs are created
