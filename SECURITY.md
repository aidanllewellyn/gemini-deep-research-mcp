# Security

## Secret Handling

Do not commit:

- `.env` files
- Gemini API keys
- MCP bearer tokens
- Cloudflare tunnel credential JSON files
- systemd encrypted credential blobs
- SQLite job history
- logs, caches, virtual environments, or generated output

Use `.env.example` for variable names only.

## Hosted MCP Auth

In HTTP mode, set `MCP_AUTH_TOKEN`. FastMCP rejects unauthenticated `/mcp` requests and requires:

```text
Authorization: Bearer <token>
```

Keep the Python service bound to `127.0.0.1` and publish through Cloudflare Tunnel or a reverse proxy.

## Local MCP Clients

Use the stdio proxy in `scripts/gemini-deep-research-mcp-stdio`. Store `GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION` in a local secret environment or password manager. Do not put token values in MCP config files.

## Data Retention

Completed reports are persisted in SQLite when `MCP_DB_PATH` is set or when the default `data/jobs.db` path is used. Treat that database as private user data and keep it out of public repos.

