#!/usr/bin/env bash
# One virtual environment for the whole study: AgentDojo 0.1.35, CaMeL (editable,
# pinned commit), numpy, scikit-learn, pytest.  Python 3.11+ required.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
"$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
bash scripts/fetch_camel.sh
.venv/bin/python -m pip install --quiet -e external/camel-prompt-injection
.venv/bin/python - <<'PY'
import importlib.metadata as m
from agentdojo.task_suite import get_suites; get_suites("v1.2.2")
import camel.models  # noqa: F401
print("environment ready: agentdojo", m.version("agentdojo"), "| numpy", m.version("numpy"),
      "| scikit-learn", m.version("scikit-learn"))
PY
