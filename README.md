# Gemini Deep Research MCP

[![CI](https://github.com/aidanllewellyn/gemini-deep-research-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/aidanllewellyn/gemini-deep-research-mcp/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-%3E%3D3.11-3776ab)
![FastMCP](https://img.shields.io/badge/FastMCP-Streamable_HTTP-2f6fed)
![Auth](https://img.shields.io/badge/hosted_auth-Bearer_required-success)
![License](https://img.shields.io/badge/license-MIT-green)

Cost-aware MCP server that exposes Google Gemini Deep Research as safe async tools for Claude, Codex, and other MCP clients.

The server turns Deep Research into an operational workflow: callers must explicitly choose a cost tier, reports are tracked as durable jobs, completed work can be searched/exported, and local agents can reach the service through a stable HTTPS endpoint without Tailscale, SSH port-forwards, browser login loops, or private-key runtime dependencies.

```text
MCP client
  -> local stdio HTTPS proxy
  -> stable HTTPS endpoint
  -> Cloudflare Tunnel or reverse proxy
  -> 127.0.0.1 Gemini Deep Research MCP service
```

## What This Demonstrates

- Hosted MCP over Streamable HTTP with bearer-auth public ingress.
- Local stdio compatibility through a lightweight HTTPS proxy.
- Explicit user confirmation before any paid Deep Research run.
- Tier-aware cost controls for `standard` and `max`.
- Cost-aware prompt contracts for screening, deep dives, outreach packs, competitive maps, and diligence.
- Durable SQLite job history plus FTS5 search over completed reports.
- Markdown, HTML, PDF, and DOCX export helpers.
- Lazy Gemini client initialization: imports and tests stay side-effect light, production startup still validates `GEMINI_API_KEY`.
- Zero-cost `ping` and metadata tools that do not call Gemini.

## Design Notes

The non-obvious decisions, and why they were made:

- **Cost is a first-class API contract.** Deep Research costs real money per run, so `research_start` *refuses to execute* until the caller passes an explicit `tier` and `user_confirmed=True`. The unconfirmed call returns the tier menu instead of running — the model can't quietly spend the user's budget.
- **Prompt-enforced "high-alpha" wrapper.** A hardened wrapper imposes a research mode, word/source/search budgets, and a decision-object schema so reports come back as decision matrices rather than generic essays. It's idempotent (a marker prevents double-wrapping) and opt-out via `cost_guardrail`.
- **Durable jobs, not fire-and-forget.** Every run is recorded in SQLite (WAL mode) with FTS5 over completed reports, so history, search, cost roll-ups, and follow-up chaining survive process restarts. The Gemini SDK doesn't have to expose a list endpoint for any of this to work.
- **Prompt-injection guardrail on researcher input.** The user's topic is fenced in `<research_topic>` tags under a system directive that treats fenced text as data, not instructions — defense in depth for a tool that feeds arbitrary text to a web-browsing agent.
- **Lazy client init.** The Gemini client is constructed on first use, not at import, so the module imports cleanly in tests and CI with no API key, while production startup still fails fast if `GEMINI_API_KEY` is missing.
- **Best-effort cost estimation.** Background Deep Research jobs often return only `total_tokens`; the estimator computes a precise per-rate cost when the input/output split is present and falls back to a documented blended rate otherwise — always labelling which mode it used.

## One-Command Verification

```bash
git clone https://github.com/aidanllewellyn/gemini-deep-research-mcp.git
cd gemini-deep-research-mcp
uv sync
scripts/verify.sh
```

`scripts/verify.sh` runs the unit test suite and, when remote MCP env vars are present, can also verify the hosted endpoint handshake.

## Quick Start

```bash
uv sync
cp .env.example .env
uv run python server.py
```

For local development:

```text
GEMINI_API_KEY=
MCP_TRANSPORT=stdio
```

For hosted use:

```text
GEMINI_API_KEY=
MCP_TRANSPORT=http
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_AUTH_TOKEN=<generated token>
MCP_DB_PATH=./data/jobs.db
```

Hosted `/mcp` requests must include:

```text
Authorization: Bearer <token>
```

## Client Install

Install the local stdio proxy:

```bash
scripts/install-client.sh --url https://research.example.com/mcp
```

Store local client auth in a secret environment or password manager:

```bash
export GEMINI_DEEP_RESEARCH_MCP_URL="https://research.example.com/mcp"
export GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION="Bearer <token>"
export GEMINI_DEEP_RESEARCH_MCP_TIMEOUT_SECONDS=300
```

Configure an MCP client to run:

```bash
/bin/bash -lc 'set -a; [ -f ~/.secrets.env ] && . ~/.secrets.env; set +a; exec ~/.local/bin/gemini-deep-research-mcp-stdio'
```

See [INSTALL.md](INSTALL.md) for full server, Cloudflare, systemd, Codex, Claude Code, and Claude Desktop setup.

## MCP Tools

| Tool | Purpose | Cost posture |
| --- | --- | --- |
| `research_start` | Start an async Deep Research job after explicit tier confirmation. | Paid call |
| `research_check` | Poll a job and persist completed report/usage metadata. | Metadata/read call |
| `research_cancel` | Cancel a running job when the SDK supports cancellation. | Control call |
| `research_list` | Show recent in-memory jobs. | Zero Gemini cost |
| `research_history` | Query persisted SQLite job history. | Zero Gemini cost |
| `research_search` | Full-text search completed reports. | Zero Gemini cost |
| `research_export` | Export reports as markdown, HTML, PDF, or DOCX. | Zero Gemini cost |
| `research_stats` | Aggregate usage/cost metadata. | Zero Gemini cost |
| `research_chain` | Walk previous-interaction chains for follow-up research. | Zero Gemini cost |
| `ping` | Return liveness, tier map, and counters. | Zero Gemini cost |

## Tier And Cost Controls

`research_start` refuses to run until the caller has explicitly chosen a tier:

| Tier | Typical cost | Typical time | Use for |
| --- | --- | --- | --- |
| `standard` | about 0.30-1.00 USD | 2-4 min | briefs, monitoring, first-pass screening |
| `max` | about 2.50-9.00 USD | 10-30 min | due diligence, finalist validation, high-stakes decisions |

The prompt wrapper can also apply budget profiles:

| Profile | Behavior |
| --- | --- |
| `lean` | Smaller word/source/search caps for cheap screening. |
| `balanced` | Default mode-specific caps. |
| `thorough` | Higher caps for diligence without forcing Max. |
| `exhaustive` | Requires explicit `max` confirmation before running. |

## Example Tool Calls

Start a screening report:

```json
{
  "tool": "research_start",
  "arguments": {
    "prompt": "Compare three vendor options for an MCP web search stack.",
    "tier": "standard",
    "user_confirmed": true,
    "research_mode": "screening",
    "budget_profile": "balanced",
    "word_cap": 1800,
    "source_budget": {
      "max_sources": 12,
      "max_searches": 8
    },
    "decision_schema_required": true
  }
}
```

Poll the report:

```json
{
  "tool": "research_check",
  "arguments": {
    "interaction_id": "interaction_id_from_research_start"
  }
}
```

Search completed reports:

```json
{
  "tool": "research_search",
  "arguments": {
    "query": "vendor pricing",
    "limit": 5
  }
}
```

## Security Model

- No API keys, OAuth tokens, bearer tokens, `.env` files, local DBs, logs, caches, or tunnel credentials are committed.
- `.env.example` contains variable names only.
- Hosted HTTP mode requires `MCP_AUTH_TOKEN` and FastMCP bearer auth.
- The service should bind to `127.0.0.1`; Cloudflare Tunnel or a reverse proxy handles public HTTPS.
- The stdio proxy reads `GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION` from local secret storage and never embeds token values in MCP config files.
- The stdio proxy requires HTTPS for remote endpoints and only allows plain HTTP for localhost development.
- SQLite report history is private user data and is excluded from the repository.

See [SECURITY.md](SECURITY.md).

## Testing And Audit

```bash
uv run ruff check .            # lint
uv run ruff format --check .   # format check
uv run python -m unittest discover -s tests
scripts/verify.sh             # all of the above, plus an optional live endpoint handshake
```

Useful public-release checks:

```bash
gitleaks protect --staged --redact --no-banner --source .
git ls-files
```

## Deployment Shape

The deployment examples in [deploy/](deploy/) assume:

- Python service installed on a Linux host.
- `MCP_HOST=127.0.0.1` so the service is not directly exposed.
- Cloudflare Tunnel or Caddy terminates public HTTPS.
- Server credentials are stored in environment files, `systemd-creds`, or another secret manager.
- Local MCP clients use the stdio proxy and only store auth in local secret storage.

## Repository Layout

```text
server.py          FastMCP server: 11 tools, tier/cost controls, prompt wrapper, cost estimator
storage.py         SQLite persistence: jobs table + FTS5 search + chain traversal (WAL mode)
export.py          Markdown → HTML / PDF / DOCX rendering
canonical_style.css  Shared stylesheet for HTML/PDF export
tests/             unittest suite: prompt wrapper, tier gating, cost math, text extraction
scripts/
  install-client.sh             Install the local stdio proxy for an MCP client
  gemini-deep-research-mcp-stdio  The stdio↔HTTPS proxy itself
  verify.sh                     ruff lint → format check → tests (+ optional live handshake)
deploy/            Caddy, systemd unit, and Cloudflare Tunnel examples
.github/workflows/ CI: ruff lint, format check, tests on Python 3.11 / 3.12 / 3.13
```

## License

MIT. See [LICENSE](LICENSE).
