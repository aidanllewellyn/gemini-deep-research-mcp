# Gemini Deep Research MCP

MCP server exposing Google Gemini Deep Research as async tools for Claude, Codex, and other MCP clients.

The project supports two deployment modes:

- local stdio for development
- hosted Streamable HTTP behind bearer auth for production

The recommended hosted client shape is:

```text
MCP client -> local stdio proxy -> HTTPS endpoint -> Cloudflare Tunnel -> 127.0.0.1 Gemini MCP service
```

No Tailscale session, local SSH port-forward, or local private SSH key is required for MCP startup.

## Tools

| Tool | Purpose |
| --- | --- |
| `research_start` | Start an async Gemini Deep Research job after explicit tier confirmation. |
| `research_check` | Poll a job and return the report when complete. |
| `research_cancel` | Cancel a running job. |
| `research_list` | Show recent in-memory jobs. |
| `research_history` | Query persisted SQLite job history. |
| `research_search` | Full-text search completed reports. |
| `research_export` | Export reports as markdown, HTML, PDF, or DOCX. |
| `research_stats` | Aggregate job counters. |
| `ping` | Low-cost liveness check. |

## Tier Routing

`research_start` refuses to run unless the caller has explicitly confirmed a tier:

| Tier | Typical cost | Typical time | Use for |
| --- | --- | --- | --- |
| `standard` | about 0.30-1.00 USD | 2-4 min | briefs, monitoring, iterative research |
| `max` | about 2.50-9.00 USD | 10-30 min | due diligence and high-stakes deep dives |

## Quick Start

```bash
uv sync
cp .env.example .env
uv run python server.py
```

For local development, keep `MCP_TRANSPORT=stdio`.

For hosted use, set `MCP_TRANSPORT=http`, bind to `127.0.0.1`, and put Cloudflare Tunnel or a reverse proxy in front of the service. Set `MCP_AUTH_TOKEN` so HTTP clients must send `Authorization: Bearer <token>`.

## Client Install

Install the stdio HTTPS proxy:

```bash
scripts/install-client.sh --url https://research.example.com/mcp
```

Set local client secrets:

```bash
export GEMINI_DEEP_RESEARCH_MCP_URL="https://research.example.com/mcp"
export GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION="Bearer <token>"
```

Then configure an MCP client to run:

```bash
/bin/bash -lc 'set -a; [ -f ~/.secrets.env ] && . ~/.secrets.env; set +a; exec ~/.local/bin/gemini-deep-research-mcp-stdio'
```

See [INSTALL.md](INSTALL.md) for full server, Cloudflare, and client setup.

## Security

- `GEMINI_API_KEY` and `MCP_AUTH_TOKEN` are environment or secret-manager values.
- The hosted HTTP endpoint enforces bearer auth through FastMCP.
- The local stdio proxy reads auth from environment variables and does not store token values in MCP config.
- Local SQLite history, logs, caches, `.env`, and tunnel credentials are ignored and must not be committed.

See [SECURITY.md](SECURITY.md).

## Verification

```bash
scripts/verify.sh
```

## License

MIT. See [LICENSE](LICENSE).
