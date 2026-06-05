# Install

## Local Development

```bash
uv sync
cp .env.example .env
```

Set:

```text
GEMINI_API_KEY=
MCP_TRANSPORT=stdio
```

Run:

```bash
uv run python server.py
```

## Hosted Server

Recommended production shape:

```text
Cloudflare Tunnel hostname -> http://127.0.0.1:8000
```

Configure:

```text
GEMINI_API_KEY=
MCP_TRANSPORT=http
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_AUTH_TOKEN=<generated token>
```

Generate a strong bearer token with a password manager or:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Install the service:

```bash
sudo cp deploy/mcp-gemini-deep-research.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-gemini-deep-research
```

The service template assumes `/opt/gemini-deep-research-mcp`. Edit `WorkingDirectory`, `EnvironmentFile`, and `ExecStart` if you install elsewhere.

## Cloudflare Tunnel

Copy [deploy/cloudflared.config.example.yml](deploy/cloudflared.config.example.yml), replace placeholders, and point the hostname at the local service:

```yaml
tunnel: REPLACE_WITH_TUNNEL_ID
credentials-file: /etc/cloudflared/REPLACE_WITH_TUNNEL_ID.json
ingress:
  - hostname: research.example.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Then install:

```bash
sudo cp deploy/cloudflared-named.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared-named
```

## Local MCP Client

Install the stdio HTTPS proxy:

```bash
scripts/install-client.sh --url https://research.example.com/mcp
```

Store local client auth in your secret environment:

```bash
export GEMINI_DEEP_RESEARCH_MCP_URL="https://research.example.com/mcp"
export GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION="Bearer <token>"
```

Codex TOML example:

```toml
[mcp_servers.gemini-deep-research]
command = "/bin/bash"
args = ["-lc", "set -a; [ -f ~/.secrets.env ] && . ~/.secrets.env; set +a; exec ~/.local/bin/gemini-deep-research-mcp-stdio"]
```

Claude Desktop JSON example:

```json
{
  "mcpServers": {
    "gemini-deep-research": {
      "command": "/bin/bash",
      "args": [
        "-lc",
        "set -a; [ -f ~/.secrets.env ] && . ~/.secrets.env; set +a; exec ~/.local/bin/gemini-deep-research-mcp-stdio"
      ]
    }
  }
}
```

## Verify Hosted Endpoint

Unauthenticated requests should fail:

```bash
curl -i https://research.example.com/mcp
```

Authenticated initialize should return HTTP 200 and an `mcp-session-id` header:

```bash
MCP_AUTHORIZATION='Bearer <token>'
curl -i \
  -H "Authorization: ${MCP_AUTHORIZATION}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  https://research.example.com/mcp
```
