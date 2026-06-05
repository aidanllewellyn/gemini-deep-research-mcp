#!/usr/bin/env bash
set -euo pipefail

url=""
dry_run=0
prefix="${INSTALL_PREFIX:-$HOME/.local/bin}"

while [ $# -gt 0 ]; do
  case "$1" in
    --url)
      url="${2:-}"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --prefix)
      prefix="${2:-}"
      shift 2
      ;;
    -h|--help)
      echo "usage: scripts/install-client.sh --url https://research.example.com/mcp [--dry-run] [--prefix DIR]"
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$url" ]; then
  echo "--url is required" >&2
  exit 2
fi

src_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="$prefix/gemini-deep-research-mcp-stdio"

if [ "$dry_run" -eq 0 ]; then
  mkdir -p "$prefix"
  install -m 0755 "$src_dir/gemini-deep-research-mcp-stdio" "$target"
  action="Installed"
else
  action="Would install"
fi

cat <<EOF
$action wrapper: $target

Add these variables to your local secret environment:
  export GEMINI_DEEP_RESEARCH_MCP_URL="$url"
  export GEMINI_DEEP_RESEARCH_MCP_AUTHORIZATION="Bearer <token>"

Codex/Claude command:
  /bin/bash -lc 'set -a; [ -f ~/.secrets.env ] && . ~/.secrets.env; set +a; exec $target'
EOF
