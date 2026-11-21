# Development

This page is the local development and verification entry point. Detailed client guides remain in their client directories. The standard server and acceptance suites must run against disposable local PostgreSQL; never point test commands at production or beta databases.

## Regression commands

- Build: `make -j4`
- Python client: `pytest -q client/python_client/tests`
- Python V2 acceptance contracts: `pytest -q tests.v2`
- Godot 4.5.x offline client suite: `GODOT_BIN=$(command -v gdot) python3 tests.v2/suite_client_regressions.py`
- Disposable PostgreSQL server regression: use `tests.v2/run_regression_instance.py` with a dedicated QA PostgreSQL role, unique loopback ports, and an explicit QA cluster identity check.
- TLS acceptance: run `suite_tls_smoke.json` explicitly so the runner configures its disposable TLS listener.

The live acceptance matrix, exact test references, and latest known counts are maintained in [`V3_PARITY.md`](V3_PARITY.md).


---

# First-time local setup

# Local development setup

This guide points to the current build and client instructions; it is not a
production deployment runbook.

## Before starting

- Use an isolated development database and test accounts.
- Keep secrets out of source files, command history and reports.
- The supported full-game database runtime is PostgreSQL.
- Do not connect acceptance tests to beta, production or an unverified host DB.

## Build and run

Use the repository Makefile and `compose.beta.yaml` as the current source for
build targets, container services, ports and environment settings. Do not
copy old commands from historical setup reports: server startup and database
configuration have changed over the life of the project.

For player workflows and client options, see
[`../client/python_client/README.md`](../client/python_client/README.md) and
the Godot project README. For repeatable integration acceptance, see
[`testing/V3_INTEGRATION_QA.md`](testing/V3_INTEGRATION_QA.md).

### Windows without WSL or Docker

The Windows build uses the 64-bit Cygwin runtime for the server's POSIX
process and socket APIs. GitHub Actions builds it (`.github/workflows/windows-server.yml`)
and uploads `twclone-windows-x64.zip`. To build by hand, use a Cygwin terminal
and install `gcc-core`, `make`, `autoconf`, `automake`, `libpq-devel`,
`libssl-devel`, `libreadline-devel`, `libjansson-devel` and `libargon2_1`.
Check out the source with LF line endings
(`git -c core.autocrlf=false clone <repository-url>`).

```sh
autoreconf -fi
./configure --enable-postgres
make clean
make -j2 SANITIZE_FLAGS=
```

`bin/bigbang.exe` initializes the PostgreSQL database and `bin/server.exe`
hosts the game. PostgreSQL can run as a Windows service or on another host.
To launch from PowerShell, put the Cygwin `bin` directory on the process's
`PATH` so Windows can find the runtime DLLs. The ZIP also carries the BBS
door from `tools/bbs-door` (see `DOOR-README.md` in the ZIP).

## Deployment boundary

Local setup does not authorize external exposure. The release-candidate audit
currently blocks external beta deployment. Follow
[`V3_DEPLOYMENT_HARDENING_PLAN.md`](V3_DEPLOYMENT_HARDENING_PLAN.md) with the
environment owner before changing credentials, firewall rules, services,
accounts or deployment state.


---

# Python client development handover

# Python client developer guide

The menu-driven terminal client is a normal V3 player client and a useful
reference for protocol workflows. The published command contracts are in
[`PROTOCOL.v3`](PROTOCOL.v3/00_index.md); do not treat old change logs or this
guide as a second protocol specification.

## Source map

- `client.py`: entry point, request/workflow dispatch and terminal menus
- `menus.json`: player-facing command and context menu definitions
- `protocol.py`: framing, correlation, event handling and diagnostic
  sanitization
- `workflows/`: separated gameplay workflows where present
- `tests/`: client unit and workflow regressions

Use `rg` against the current tree before relying on a path or symbol; the
client has been reorganized over time.

## Run and test

Follow [`../client/python_client/README.md`](../client/python_client/README.md)
for installation, connection and test commands. For server-backed work, use
the isolated setup in [`testing/V3_INTEGRATION_QA.md`](testing/V3_INTEGRATION_QA.md).

## Client rules

- Treat server responses as authoritative. Do not fabricate success or infer
  entity identity from unrelated response fields.
- Refresh state from the server after state-changing operations and preserve
  server refusals and error codes in the UI.
- Keep gameplay operations reachable through ordinary menus; debug/RPC tools
  are not substitutes for player workflows.
- Sanitize diagnostic exchanges before buffering or display. Never capture
  credentials, private messages or unapproved personal data.
- Preserve request correlation and idempotency keys across uncertain retries
  when the operation contract requires it.
- Client tests should assert protocol behavior and fail-closed handling, not
  brittle terminal wording unless that wording is part of the user contract.

Current suite counts and live-client evidence are summarized in
[`V3_PARITY.md`](V3_PARITY.md) and
the linked acceptance reports. Re-run the relevant suite after changing code;
historical counts in old reports are not a current baseline.
