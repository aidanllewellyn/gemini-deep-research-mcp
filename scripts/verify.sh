#!/usr/bin/env bash
set -euo pipefail

uv run ruff check .
uv run ruff format --check .
uv run python -m unittest discover -s tests

if [ -n "${GEMINI_DEEP_RESEARCH_MCP_URL:-}" ] && [ -n "${GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION:-}" ]; then
  headers_file="$(mktemp "${TMPDIR:-/tmp}/gemini-mcp-headers.XXXXXX")"
  body_file="$(mktemp "${TMPDIR:-/tmp}/gemini-mcp-body.XXXXXX")"
  trap 'rm -f "$headers_file" "$body_file"' EXIT

  curl -sS -D "$headers_file" -o "$body_file" \
    -H "Authorization: $GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"0"}}}' \
    "$GEMINI_DEEP_RESEARCH_MCP_URL" >/dev/null
  grep -qi '^mcp-session-id:' "$headers_file"
fi

echo "verification passed"
