# Architecture Specification

## Decoupling Paradigm

The system is intentionally split into three layers with strict boundaries. Each layer should remain independently testable, replaceable, and auditable.

### 1. API Clients (`etsy_api_client.py`)
Responsibilities:
- Perform only network I/O and HTTP request orchestration.
- Read credentials from environment variables.
- Implement defensive retry behavior for HTTP 429 responses using exponential backoff.
- Return structured dictionaries for both success and failure paths.

Constraints:
- No business logic.
- No PDF generation.
- No database writes.
- No CLI behavior.

### 2. Analytical Executors (`api_factory_v2.py`, `ebay_api_executor.py`)
Responsibilities:
- Serve as the execution core for marketplace opportunity generation.
- Accept CLI parameters.
- Initialize and use SQLite with explicit timeouts.
- Calculate metrics safely, including empty-response protection.
- Generate PDF artifacts for operator review.
- Return strict SGR JSON to stdout.

Constraints:
- May orchestrate API client calls.
- Must avoid raw exception leakage in user-facing JSON output.
- Must validate payload construction before emitting final SGR output.

### 3. Publishers (`etsy_publisher.py`)
Responsibilities:
- Read local JSON payload files.
- Extract publish-ready fields.
- Delegate API submission to API clients.
- Emit strict machine-readable JSON in stdout.

Constraints:
- No analytics logic.
- No PDF rendering.
- No SQLite analytics pipeline.

## Data Flow
1. Executor reads CLI parameters.
2. Executor queries marketplace client.
3. Executor computes metrics and stores run metadata in SQLite.
4. Executor generates a PDF artifact in `ready_to_publish/`.
5. Executor emits an SGR JSON envelope with publish-ready API payloads.
6. Publisher consumes saved JSON later and submits drafts through the client layer.

## Reliability Rules
- All fatal external API errors degrade gracefully into structured error dictionaries.
- Empty or malformed API responses must not trigger division-by-zero or uncaught exceptions.
- Output to stdout must remain valid JSON for all expected runtime paths.
