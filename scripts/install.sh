#!/usr/bin/env bash
# Установка навыков этого репозитория в каталог скиллов ИИ-агента.
#
# Usage:
#   bash scripts/install.sh                     # определить агента автоматически
#   bash scripts/install.sh --agent hermes      # hermes|openclaw|claude|cline|codex|cursor
#   bash scripts/install.sh --dir ~/my/skills   # в свой каталог
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT=""
DIR=""

usage() { echo "Usage: $0 [--agent hermes|openclaw|claude|cline|codex|cursor] [--dir PATH]"; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) AGENT="${2:-}"; shift 2 ;;
    --dir)   DIR="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Неизвестный аргумент: $1"; usage ;;
  esac
done

if [[ -z "$DIR" ]]; then
  if [[ -z "$AGENT" ]]; then
    if command -v hermes &>/dev/null || [[ -d "$HOME/.hermes" ]]; then AGENT=hermes
    elif [[ -d "$HOME/.openclaw" ]]; then AGENT=openclaw
    elif [[ -d "$HOME/.claude" ]]; then AGENT=claude
    elif [[ -d "$HOME/.cline" ]]; then AGENT=cline
    elif [[ -d "$HOME/.codex" ]]; then AGENT=codex
    else AGENT=manual; fi
  fi
  case "$AGENT" in
    hermes)   DIR="$HOME/.hermes/skills" ;;
    openclaw) DIR="$HOME/.openclaw/skills" ;;
    claude)   DIR="$HOME/.claude/skills" ;;
    cline)    DIR="$HOME/.cline/skills" ;;
    codex)    DIR="$HOME/.codex/skills" ;;
    cursor)   DIR="$HOME/.cursor/skills" ;;
    manual)   echo "Не определил агента — укажи каталог: --dir PATH"; exit 1 ;;
    *)        echo "Неизвестный агент: $AGENT"; usage ;;
  esac
fi

shopt -s nullglob
count=0

install_one() {  # $1 — папка навыка
  local src="$1" name dest
  name="$(basename "$src")"
  [[ -f "$src/SKILL.md" ]] || return 0
  dest="$DIR/$name"
  mkdir -p "$DIR"
  rm -rf "$dest"
  cp -R "$src" "$dest"
  find "$dest" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  echo "✓ $name → $dest"
  count=$((count + 1))
}

if [[ -f "$REPO_DIR/SKILL.md" ]]; then
  install_one "$REPO_DIR"
else
  for src in "$REPO_DIR"/skills/*/; do
    name="$(basename "$src")"
    [[ "$name" == _* || "$name" == .* ]] && continue
    install_one "$src"
  done
fi

if [[ $count -eq 0 ]]; then
  echo "Не нашёл навыков с SKILL.md (ожидаю skills/<имя>/SKILL.md или SKILL.md в корне)" >&2
  exit 1
fi

echo
echo "Поставлено навыков: $count → $DIR"
echo "Перезапусти агентную среду/сессию, чтобы навыки подхватились."
