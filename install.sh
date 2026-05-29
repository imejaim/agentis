#!/usr/bin/env bash
# Agentis 설치 — install.py wrapper.
# 직접 인자 주려면: ./install.sh --target /path/to/work
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/install.py" "$@"
