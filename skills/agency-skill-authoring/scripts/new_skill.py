#!/usr/bin/env python3
"""
new_skill.py — каркас нового навыка агентства.

Режимы (--mode), по числу контуров из SKILL.md:
  personal — личный навык Hermes: SKILL.md + references/ + scripts/ + CHANGELOG.
  internal — навык команды: папка skills/<name>/ ВНУТРИ уже существующего репозитория агентства
             (<org>/ai-skills, рабочая копия — переменная AI_SKILLS_REPO или ~/projects/ai-skills).
             Новый репозиторий не создаётся: он там уже есть. Дальше — ветка, валидатор, PR в main.
  external — навык для рынка (публичный репо, наш паттерн gdebenz-skill): добавлены
             README.en.md, LICENSE (MIT), release-workflow, docs/releases/.

Раскладка (--layout):
  skills — скилл в skills/<name>/ (так читает Hermes tap; по умолчанию для репо-режимов)
  root   — SKILL.md в корне папки (так упакованы навыки ai-hub-open)

Использование:
    python3 new_skill.py my-process --install-hermes knowledge
    python3 new_skill.py audit-cabinet --mode internal --category knowledge
    python3 new_skill.py ad-audit --mode external --repo-name ad-audit-skill --dir ~/projects \
        --description "Use when аудит рекламного кабинета клиента."
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_DESC_HERMES = 60
MAX_DESC_PACKAGE = 200

# каталог навыков агента и рабочая копия репозитория — из окружения, без хардкода путей
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")).expanduser()
HERMES_SKILLS = HERMES_HOME / "skills"
DEFAULT_REPO = os.environ.get("AI_SKILLS_REPO") or "~/projects/ai-skills"

SKILL_MD = """---
name: __NAME__
description: "__DESC__"
__FM_EXTRA__---

# __TITLE__

## When to Use

__TRIGGERS__
Не для этого навыка: __какие задачи он не берёт__.

**Что делает:** __TODO__ — одно-два предложения, глаголами.
**Чего не делает:** __TODO__ — явный список (не публикует, не тратит бюджет, не удаляет во внешней системе).

## Что нужно от среды

**Обязательный минимум — две способности:**

- **Чтение и запись файлов** в рабочей папке — на этом держится вся воронка: каждый шаг порождает артефакт,
  следующий шаг его читает.
- **Диалог с подтверждением** — задать вопрос и дождаться ответа. На этом стоят гейты перед побочными
  эффектами: заливка/отправка — только после явного «ОК».

Остального достаточно, чтобы дойти до конца. Если способности нет — идём по ветке «если нет» и **печатаем
пометку о пропуске** в артефакт шага (что пропущено и что потеряно), а не упрощаем молчком.

| Способность | Где нужна | Если нет |
|---|---|---|
| **Вызов MCP-инструментов** | шаг 2 | __фолбек__; **Теряется:** __что__ |
| **Запуск кода** | шаги 1, 4 | отдай команду текстом, работай с присланным выводом |
| **Чтение веб-страниц** | шаг 0 | попроси 5 фактов у человека словами |

## Главный принцип

Пошагово, гейт после каждого шага, все артефакты — в рабочей папке `__SLUG__-work/<проект>/`.
Не додумывать на месте цифры: не хватает входа — вернись на шаг-источник.

## Шаг 1. __название шага__

- **Вход:** __какие файлы читает__
- **Что делаем:** __операции списком, без воды__
- **Артефакт:** `01___имя__.md` — __какие поля внутри__
- **Гейт:** покажи __что__ и спроси «__какой вопрос__»

## Шаг 2. __название шага__ (пропускается, если нет __способности__)

- **Вход:** `01___имя__.md`
- **Что делаем:** __...__
- **Артефакт:** `02___имя__.json`

## Стиль работы

- Один вопрос за раз; не задавать три уточнения пачкой.
- Длинные выкладки — в файл, в чат — сводка 5–10 строк.
- Не защищать красивую цифру: расхождение с источником — в отчёт.
- Сомневаешься — скажи «не знаю» и укажи, чем добрать.

## Возобновление

Скажи «продолжаем» — найди рабочую папку, прочитай `_state.json` → `current_step`, начни с него.
Уже принятые решения не переспрашивать.

## При сбое шага

1. Нет входа — вернись на шаг-источник, не выдумывай данные.
2. Нет способности среды — перейди на ветку «если нет» и пометь пропуск в артефакте.
3. Внешний сервис ответил ошибкой — покажи код и текст, предложи фолбек, не перебирай варианты молча.

## Карта глубины

| Тема | Файл | Когда открывать |
|---|---|---|
| __тема 1__ | `references/example-reference.md` | __когда нужен этот файл__ |
| Вспомогательный скрипт | `scripts/example_script.py` | __когда запускать__ |

Все ссылки выше должны существовать в пакете — упаковщик это проверяет.
"""

REFERENCE_STUB = """# __тема__

Что здесь лежит: __заполни или удали файл__. Здесь живут длинные выкладки, справочники, лимиты площадок,
тексты шаблонов — всё, что не должно раздувать SKILL.md.

Правило: каждую цифру лимита/порога — со ссылкой на источник и датой проверки.
"""

SCRIPT_STUB = '''#!/usr/bin/env python3
"""__what__

Использование:
    python3 example_script.py --input 01_input.md --output 02_output.json
"""

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    raw = Path(args.input).read_text(encoding="utf-8")
    result = {"lines": raw.count("\\n"), "source": args.input}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"готово: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

CHANGELOG = """# История версий

Формат — semver. Ломающие изменения — только мажорной версией.

## 0.1.0 — __TODAY__

### Добавлено

- Первый каркас навыка.
"""

README_INTERNAL = """# __NAME__ — внутренний навык агентства

__Что делает: два-три предложения для коллеги.__

**Владелец:** __имя__  •  **Контур:** внутренний (только команда)  •  **Не публикуется наружу.**

## Что делает

- __шаг/возможность 1__
- __шаг/возможность 2__

## Как поставить себе

```bash
bash scripts/install.sh --agent hermes      # или --agent claude|cline|codex|openclaw
```

Через Hermes tap (обновление по требованию):

```bash
hermes skills tap add <owner>/<repo>
hermes skills install <owner>/<repo>/__NAME__
```

## Как обновлять

Правки — в ветку `dev`, PR — в `dev`. В `main` только через PR. Тег `vX.Y.Z` + запись в `CHANGELOG.md`.

## Что нельзя в этот репозиторий

Клиентские выгрузки, токены, id кабинетов, переписка, скриншоты чужих кабинетов.
Секреты живут в `~/.hermes/credentials/` у каждого; в навыке — только инструкция, где взять ключ.
"""

README_EXTERNAL = """# __NAME__ — навык для ИИ-агентов

__Что делает: два-три предложения для чужого человека. Кому полезно, что на выходе.__

Работает в Hermes Agent, OpenClaw, Claude Code, Cline, Cursor, Codex. Лицензия MIT.

## Возможности

- __возможность 1__
- __возможность 2__

## Быстрый старт

```
__фраза-триггер__
```

__Что вернёт навык: артефакт и короткое описание.__

## Установка

### Hermes Agent

```bash
hermes skills tap add <owner>/__REPO__
hermes skills install <owner>/__REPO__/__NAME__
```

### Claude Code и другие агенты (через skills.sh)

```bash
npx skills add <owner>/__REPO__
```

### Любой агент (универсально)

```bash
git clone https://github.com/<owner>/__REPO__.git
bash __REPO__/scripts/install.sh --agent hermes   # или claude|cline|codex|openclaw, или --dir PATH
```

### Вручную

Скопируй папку `skills/__NAME__/` в каталог скиллов своего агента и перезапусти сессию.

## Требования

- __Python 3.9+ (если есть `scripts/`) / внешний сервис / ключ__
- Ключи хранятся вне репозитория: `~/.hermes/credentials/`, переменные окружения агента

## Что на выходе

- `01___имя__.md` — __что внутри__

## Важно знать

- __Границы: чего навык сознательно не делает.__
- __Известные ограничения и почему.__

## Лицензия

MIT — см. `LICENSE`. Баги и предложения — через issue.

## Ключевые слова / Keywords

__RU: три-пять ключевых фраз; EN: те же смыслы по-английски — по ним находят в поиске.__
"""

README_EN = """# __NAME__ — skill for AI agents

__What it does in one or two sentences for a non-Russian reader.__

Works with Hermes Agent, OpenClaw, Claude Code, Cline, Cursor, Codex. MIT licensed.

## What it does

- __capability 1__
- __capability 2__

## Install

```bash
hermes skills tap add <owner>/__REPO__ && hermes skills install <owner>/__REPO__/__NAME__
npx skills add <owner>/__REPO__
```

Manual: copy `skills/__NAME__/` into your agent's skills directory and restart the session.

## Requirements

- __Python 3.9+ / external service / API key kept outside the repo__

## License

MIT — see `LICENSE`.

## Keywords

__EN keywords; add RU ones too — the skill is built for Russian-speaking marketers.__
"""

GITIGNORE = """__pycache__/
*.py[cod]
.venv/
venv/
dist/
.env
.env.*
!.env.example
credentials.json
*.pem
*.key
.DS_Store
.pytest_cache/
__pycache__/
"""

SKILLS_SH_JSON = """{
  "$schema": "https://skills.sh/schemas/skills.sh.schema.json",
  "notGrouped": "bottom",
  "groupings": [
    {
      "title": "__REPO__",
      "description": "__GROUP_DESC__",
      "skills": ["__NAME__"]
    }
  ]
}
"""

INSTALL_SH = r'''#!/usr/bin/env bash
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
'''

CI_YML = """name: CI

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Зависимости
        run: pip install pyyaml
      - name: Найти навыки
        id: find
        run: |
          if [ -f SKILL.md ]; then
            echo "paths=." >> $GITHUB_OUTPUT
          else
            echo "paths=$(ls -d skills/*/ 2>/dev/null | tr '\\n' ' ')" >> $GITHUB_OUTPUT
          fi
      - name: Валидация пакетов
        run: |
          for p in ${{ steps.find.outputs.paths }}; do
            echo "::group::пакет $p"
            python tools/package_skill.py --skill-path "$p" --target claude --check
            echo "::endgroup::"
          done
      - name: Синтаксис скриптов
        run: |
          for d in ${{ steps.find.outputs.paths }}; do
            [ -d "$d/scripts" ] && python -m compileall -q "$d/scripts" || true
          done
      - name: В индексе нет байт-кода и сборок
        run: |
          if git ls-files | grep -E '(__pycache__|\\.pyc$|^dist/)'; then
            echo "В репозитории байт-код или сборка — убери из индекса"; exit 1
          fi
      - name: Секреты (gitleaks)
        run: |
          if [ -f .gitleaks.toml ] || [ -d .git ]; then
            docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect --source=/repo --no-git=false --exit-code 1 --verbose || true
          fi
"""

RELEASE_YML = """name: Release

on:
  push:
    tags: ["v*"]

permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Зависимости
        run: pip install pyyaml
      - name: Собрать пакеты
        run: |
          mkdir -p dist
          if [ -f SKILL.md ]; then
            python tools/package_skill.py --skill-path . --target claude --output dist --strict-public
          else
            for p in skills/*/; do
              python tools/package_skill.py --skill-path "$p" --target claude --output dist --strict-public
            done
          fi
      - name: Релизные заметки для пользователей
        run: |
          f="docs/releases/${{ github.ref_name }}.md"
          if [ ! -f "$f" ]; then
            echo "Нет $f — напиши релизные заметки перед тегом (шаблон: docs/releases/_template.md)" >&2
            exit 1
          fi
      - name: Приложить пакеты к релизу
        uses: softprops/action-gh-release@v2
        with:
          files: dist/*.zip
          body_path: docs/releases/${{ github.ref_name }}.md
          generate_release_notes: false
"""

RELEASE_NOTE_TEMPLATE = """# __TAG__ — YYYY-MM-DD

## Что изменилось

- __одно-два изменения для пользователя, без внутренних терминов__

## Как обновить

```bash
hermes skills tap update __OWNER__/__REPO__   # или заново скачать архив релиза
```
"""

LICENSE_PROPRIETARY = """Все права защищены. Внутренний ресурс агентства.

Материалы этого репозитория (методология, тексты, скрипты) — внутренний ресурс;
распространение вне команды без разрешения владельца не допускается.

© __YEAR__ __HOLDER__
"""


MODES = ("personal", "internal", "external")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_skill_md(name: str, description: str, title: str, mode: str,
                   category: str = "knowledge") -> str:
    fm_extra = ""
    if mode == "personal":
        fm_extra = ("version: 0.1.0\ncreated_by: agent\n"
                    "metadata:\n  hermes:\n    tags: []\n    related_skills: []\n")
    elif mode == "internal":
        # фронтматтер репозитория агентства: только name, description, category
        fm_extra = f"category: {category}\n"
    triggers = ("- «__триггер 1__», «__триггер 2__» — фразы, по которым навык должен включаться.\n"
                "- Триггеры из описания стоит продублировать здесь человеческим языком: описание читает индекс,\n"
                "  а маршрутизацию внутри навыка держит этот раздел.\n")
    return (SKILL_MD
            .replace("__FM_EXTRA__", fm_extra)
            .replace("__NAME__", name)
            .replace("__DESC__", description.replace('"', "'"))
            .replace("__TITLE__", title)
            .replace("__TRIGGERS__", triggers)
            .replace("__SLUG__", name))


def main() -> int:
    ap = argparse.ArgumentParser(description="Каркас нового навыка агентства")
    ap.add_argument("name", help="имя навыка: строчные латинские, дефисы (my-skill)")
    ap.add_argument("--mode", choices=list(MODES), default="personal")
    ap.add_argument("--layout", choices=["skills", "root"], default=None)
    ap.add_argument("--dir", default=None, help="где создать папку (для режима external — родитель репо)")
    ap.add_argument("--repo-name", default=None, help="имя репозитория (режим external)")
    ap.add_argument("--category", default="knowledge", help="поле category во фронтматтере (режим internal)")
    ap.add_argument("--repo-dir", default=DEFAULT_REPO,
                    help="рабочая копия общего репозитория навыков (режим internal)")
    ap.add_argument("--install-hermes", default=None, metavar="CATEGORY",
                    help="положить сразу в каталог навыков агента (<HERMES_HOME>/skills/<CATEGORY>/) (режим personal)")
    ap.add_argument("--description", default="Use when замени это на свой триггер.",
                    help="текст description")
    ap.add_argument("--title", default=None, help="заголовок H1 (по умолчанию имя)")
    ap.add_argument("--owner", default=os.environ.get("GITHUB_OWNER", ""), help="GitHub-владелец для ссылок и лицензии")
    ap.add_argument("--holder", default="Антон Белицкий", help="правообладатель в LICENSE")
    ap.add_argument("--force", action="store_true", help="писать в непустую папку")
    args = ap.parse_args()

    name = args.name.strip()
    if not name or not all(c.islower() or c.isdigit() or c == "-" for c in name):
        print("Имя навыка: только строчные латинские буквы, цифры и дефисы.", file=sys.stderr)
        return 2

    mode = "personal" if args.install_hermes else args.mode
    layout = args.layout or ("skills" if mode in ("internal", "external") else "root")
    repo_name = args.repo_name or f"{name}-skill"
    year = dt.date.today().year

    desc = args.description
    limit = MAX_DESC_HERMES if mode == "personal" else MAX_DESC_PACKAGE
    if len(desc) > limit:
        print(f"description {len(desc)} знаков — лимит {limit} для режима {mode}. "
              f"Сократи до триггера (первых 57 знаков достаточно), остальное — в тело навыка.", file=sys.stderr)
        return 2
    if not desc[:9].lower().startswith("use when"):
        print("Совет: начинай description с 'Use when …' — индекс показывает первые 57 знаков.")

    if mode == "personal":
        root = (HERMES_SKILLS / args.install_hermes / name) if args.install_hermes \
            else Path(args.dir or ".").expanduser().resolve() / name
        skill_dir = root
        repo_root = None
    elif mode == "internal":
        # навык кладётся в УЖЕ существующий репозиторий агентства; новый репозиторий не создаём
        repo_root = Path(args.repo_dir).expanduser().resolve()
        if not (repo_root / "skills").is_dir():
            print(f"{repo_root} не похож на рабочую копию <org>/ai-skills "
                  f"(нет папки skills/). Склонируй репозиторий или укажи --repo-dir.", file=sys.stderr)
            return 2
        skill_dir = repo_root / "skills" / name
    else:
        base = Path(args.dir or ".").expanduser().resolve()
        repo_root = base / repo_name
        skill_dir = repo_root / "skills" / name if layout == "skills" else repo_root

    # для режима internal репозиторий заведомо непуст — проверяем только папку самого навыка
    check_dir = skill_dir if mode == "internal" else (repo_root or skill_dir)
    if check_dir.exists() and any(check_dir.iterdir()) and not args.force:
        print(f"{check_dir} уже существует и не пуста (--force, чтобы писать поверх)", file=sys.stderr)
        return 2

    # --- навык ---
    write(skill_dir / "SKILL.md", build_skill_md(name, desc, args.title or name, mode, args.category))
    write(skill_dir / "references" / "example-reference.md",
          REFERENCE_STUB.replace("__тема__", "Тема справочника"))
    write(skill_dir / "scripts" / "example_script.py",
          SCRIPT_STUB.replace("__what__", "Вспомогательный скрипт навыка."))
    (skill_dir / "scripts" / "example_script.py").chmod(0o755)
    if mode == "personal":
        # в личном навыке история версий лежит рядом со SKILL.md
        write(skill_dir / "CHANGELOG.md", CHANGELOG.replace("__TODAY__", dt.date.today().isoformat()))

    # --- репозиторий (только внешний контур: сам репозиторий агентства уже существует) ---
    if mode == "external":
        write(repo_root / ".gitignore", GITIGNORE)
        # история версий — одна на репозиторий (версии = теги репо), а не на каждый навык
        write(repo_root / "CHANGELOG.md", CHANGELOG.replace("__TODAY__", dt.date.today().isoformat()))
        write(repo_root / "skills.sh.json", SKILLS_SH_JSON
              .replace("__REPO__", repo_name)
              .replace("__NAME__", name)
              .replace("__GROUP_DESC__", desc[:120]))
        write(repo_root / "scripts" / "install.sh", INSTALL_SH)
        (repo_root / "scripts" / "install.sh").chmod(0o755)
        write(repo_root / ".github" / "workflows" / "ci.yml", CI_YML)
        write(repo_root / "docs" / "releases" / "_template.md", RELEASE_NOTE_TEMPLATE
              .replace("__TAG__", "vX.Y.Z").replace("__OWNER__", args.owner).replace("__REPO__", repo_name))
        src_packager = HERE / "package_skill.py"
        if src_packager.exists():
            write(repo_root / "tools" / "package_skill.py", src_packager.read_text(encoding="utf-8"))
        prefix = "" if layout == "root" else "skills/" + name + "/"
        if mode == "external":
            write(repo_root / "README.md", README_EXTERNAL.replace("__NAME__", name).replace("__REPO__", repo_name))
            write(repo_root / "README.en.md", README_EN.replace("__NAME__", name).replace("__REPO__", repo_name))
            write(repo_root / ".github" / "workflows" / "release.yml", RELEASE_YML)
            mit = HERE.parent / "assets" / "mit.txt"
            license_text = mit.read_text(encoding="utf-8") if mit.exists() else "MIT License\n"
            write(repo_root / "LICENSE", license_text.replace("__YEAR__", str(year)).replace("__HOLDER__", args.holder))
        if prefix and layout == "skills":
            print(f"  (навык лежит в {prefix}SKILL.md — так читает Hermes tap)")

    print(f"✓ Каркас создан: {check_dir}  (режим: {mode}, раскладка: {layout})")
    for path in sorted(check_dir.rglob("*")):
        if path.is_file():
            print(f"   {path.relative_to(check_dir)}")
    print()
    if mode == "personal":
        print("Дальше: заполни SKILL.md по скелету (references/skill-md-skeleton.md в навыке")
        print("agency-skill-authoring), затем: python scripts/package_skill.py --check")
    elif mode == "internal":
        print("Дальше (навык лежит в рабочей копии репозитория агентства, изменения — через PR в main):")
        print(f"  cd {repo_root} && git pull && git switch -c add-{name} main")
        print(f"  заполни skills/{name}/SKILL.md и справочники")
        print(f"  python3 tools/validate_skill.py skills/{name}")
        print(f"  git add skills/{name} && git commit -m 'Навык {name}: <что делает>'")
        print(f"  git push -u origin add-{name}")
        print(f"  gh pr create --repo <org>/ai-skills --base main --head add-{name} "
              f"--title 'Навык {name}' --body '<что и зачем>'")
    else:
        print("Дальше:")
        print(f"  cd {check_dir} && git init -b main && git add -A && git commit -s -m 'chore: каркас навыка'")
        print("  gh repo create <owner>/" + repo_name + " --public --source=. --push --description '<RU+EN одной строкой>'")
        print("  python tools/package_skill.py --skill-path " + (f"skills/{name}" if layout == "skills" else ".")
              + " --target claude --public-check --strict-public --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
