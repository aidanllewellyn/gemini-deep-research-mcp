#!/usr/bin/env bash
set -euo pipefail

uv run python -m unittest discover -s tests

if [ -n "${GEMINI_DEEP_RESEARCH_MCP_URL:-}" ] && [ -n "${GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION:-}" ]; then
  curl -sS -D /tmp/gemini-mcp-headers.$$ -o /tmp/gemini-mcp-body.$$ \
    -H "Authorization: $GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"0"}}}' \
    "$GEMINI_DEEP_RESEARCH_MCP_URL" >/dev/null
  grep -qi '^mcp-session-id:' /tmp/gemini-mcp-headers.$$
  rm -f /tmp/gemini-mcp-headers.$$ /tmp/gemini-mcp-body.$$
fi

echo "verification passed"

