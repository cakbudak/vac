#!/usr/bin/env bash
# Rebuild the harness's environments from scratch.  Network access to npm, PyPI and GitHub needed.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${VAC_SUBMISSION_DIR:?set VAC_SUBMISSION_DIR to the agentdojo-study directory of this package}"

uv venv -q .venv
uv pip install -q --python .venv/bin/python "mcp==2.3.0" "agentdojo==0.1.35" "scikit-learn>=1.4,<2" numpy pyyaml

mkdir -p servers && cd servers
[ -f package.json ] || npm init -y >/dev/null
npm install --silent @modelcontextprotocol/server-filesystem@2.1.0

uv venv -q pyenv
uv pip install -q --python pyenv/bin/python mcp-server-git==2026.10.28
uv venv -q pyenv-sqlite                       # the archived sqlite server and MSB's FastMCP tools need mcp<2
uv pip install -q --python pyenv-sqlite/bin/python "mcp-server-sqlite==2025.4.25" "mcp<2" pandas

[ -d msb/.git ] || git clone --quiet --depth 1 https://github.com/dongsenzhang/MSB msb
echo "environment ready"
