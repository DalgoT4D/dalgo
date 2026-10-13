# prefect_airbyte

## Origin

This package was originally maintained as a standalone repo at
`github.com/Ishankoradia/prefect-airbyte` and installed as a git dependency in
`prefect-proxy/pyproject.toml` via a `[tool.uv.sources]` entry.

It was vendored into the monorepo in October 2025 to:
- eliminate the external git dependency from the Docker build
- keep the package in sync with the proxy without separate releases
- allow the Prefect worker sparse-checkout (`directories=["prefect-proxy"]`) to
  include the package automatically, since workers clone the monorepo to load
  flow code

The git dependency and `[tool.uv.sources]` block have been removed from
`pyproject.toml`. The package is now a plain local directory — no installation
step needed; Python finds it because the proxy runs from `prefect-proxy/` which
is on `sys.path`.

## API compatibility

The package was migrated from the Airbyte internal v1 API to the public API:

| Operation | Old endpoint | New endpoint |
|-----------|-------------|--------------|
| Trigger sync | `POST /api/v1/connections/sync/` | `POST /api/public/v1/jobs` |
| Poll job status | `POST /api/v1/jobs/get/` | `GET /api/public/v1/jobs/{id}` |
| Cancel job | `POST /api/v1/jobs/cancel/` | unchanged |

`AirbyteSyncResult.created_at` and `updated_at` are now `Optional[datetime] = None`
because the public API job response does not return timestamps.

## Module layout

| File | Purpose |
|------|---------|
| `client.py` | `AirbyteClient` — raw httpx calls to Airbyte API |
| `connections.py` | `AirbyteConnection`, `AirbyteSync`, `AirbyteSyncResult` blocks |
| `flows.py` | Prefect flows: `run_connection_sync`, `cancel_job`, `reset_connection`, etc. |
| `server.py` | `AirbyteServer` block |
| `exceptions.py` | All custom exception types |
| `configuration.py` | Deprecated `export_configuration` task |
| `utils.py` | Internal helpers |

## Retry behaviour

`client.get_job_info` retries on `httpx.HTTPStatusError` and
`AirbyteServerNotHealthyException` (transient/server errors) with exponential
backoff up to 8 attempts. It does **not** retry `JobNotFoundException` (404) —
that surfaces immediately with `reraise=True`.

## Test suite

Tests live in `tests/prefect_airbyte/`. They are slow (~30 s) because several
flow tests spin up a real Prefect ephemeral API server via `prefect_test_harness`.

CI only runs this suite when files under `prefect_airbyte/` or
`tests/prefect_airbyte/` change (see `.github/workflows/prefect-proxy.yml`).

### Key fixture decisions

- `respx_mock` is overridden in `conftest.py` to pass through `127.0.0.1`
  traffic so the Prefect local API server isn't intercepted, and
  `assert_all_called=False` so routes registered but not hit (e.g. the
  passthrough route in non-flow tests) don't cause teardown errors.
- All fixtures mock the **public** Airbyte API endpoints, not the old internal
  v1 ones.
- `cancel_job` flow tests expect `AirbyteSyncResult.job_status == "cancelled"`;
  the flow catches `AirbyteSyncJobFailed` from `wait_for_completion` since a
  successfully-cancelled job is reported as "cancelled" (not a failure).
