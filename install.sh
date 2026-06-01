#!/usr/bin/env bash
# Agentis 설치 — install.py wrapper.
# 직접 인자 주려면: ./install.sh --target /path/to/work
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -eq 0 ]; then
  printf '\nAgentis 설치\n'
  printf '설치할 작업 폴더의 절대 경로를 입력하세요.\n'
  printf '예: /Users/me/work/project-a\n\n'
  printf '> '
  IFS= read -r TARGET_DIR
  if [ -z "${TARGET_DIR}" ]; then
    printf '대상 경로가 비어 있어 설치를 취소합니다.\n' >&2
    exit 2
  fi
  exec python3 "${SCRIPT_DIR}/install.py" --target "${TARGET_DIR}"
fi

exec python3 "${SCRIPT_DIR}/install.py" "$@"
