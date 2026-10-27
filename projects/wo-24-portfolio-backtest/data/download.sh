#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -x ".venv/bin/python" ]]; then
  python3.11 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m wo24.pipeline --download-only "$@"
