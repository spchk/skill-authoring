#!/usr/bin/env python3
"""
package_skill.py — валидация и сборка пакета навыка (для навыков агентства).

Правила — в references/packaging-and-validation.md. Кратко: один SKILL.md в корне,
валидный фронтматтер, описание-триггер, живые ссылки на references/scripts,
никакого байт-кода и сборок в пакете, стоп на секретах.

Использование:
    python3 package_skill.py --check
    python3 package_skill.py --output dist
    python3 package_skill.py --target claude --check
    python3 package_skill.py --target hermes --public-check --check

Коды возврата: 0 — чисто (возможны предупреждения), 1 — есть ошибки, 2 — нет SKILL.md.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED = ("anthropic", "claude")
DESC_XML = re.compile(r"<[^>]+>")

EXCLUDE_DIRS = {
    "__pycache__", ".git", ".github", ".venv", "venv", "dist", "tools", "tests",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode", ".cursor",
    "node_modules", "marketing-campaigns",
}
EXCLUDE_FILES = {
    ".gitignore", ".DS_Store", "package.sh", "package.bat", "pytest.ini",
    "requirements-dev.txt", "uv.lock", "poetry.lock",
}
EXCLUDE_GLOBS = ("*.pyc", "*.pyo", "*.bak", "*.swp", "*~", "*-campaign-*", "*.zip")

SECRET_FILES = {
    ".env", ".env.local", ".env.production", ".env.development", ".envrc", ".netrc",
    "credentials.json", "secrets.json", "service-account.json", "id_rsa", "id_ed25519",
}
SECRET_GLOBS = ("*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "id_rsa*", "id_ed25519*")
SECRET_TEMPLATES_OK = {".env.example", ".env.sample", ".env.template", "credentials.example.json"}

SECRET_PATTERNS = (
    ("OpenAI-ключ", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("Anthropic-ключ", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("Яндекс OAuth", re.compile(r"\by0_[A-Za-z0-9_\-]{20,}")),
    ("Yandex Cloud SA", re.compile(r"\bAQVN[A-Za-z0-9_\-]{15,}")),
    ("Replicate", re.compile(r"\br8_[A-Za-z0-9]{30,}")),
    ("GitHub-токен", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("Google API-ключ", re.compile(r"\bAIza[A-Za-z0-9_\-]{30,}")),
    ("Приватный ключ", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)

PUBLIC_PATTERNS = (
    ("внутренний путь сервера", re.compile(r"/opt/" + "data/")),
    ("id нашего рекламного кабинета", re.compile(r"\bspchk-\d{6}-[a-z0-9]+\b")),
    ("внутренний хост хостинга", re.compile(r"\b[A-Za-z0-9\-]+\.beget\.tech\b")),
)

TEXT_SUFFIXES = {".md", ".py", ".json", ".sh", ".yml", ".yaml", ".txt", ".toml", ".cfg", ".ini", ""}
SELF_NAME = "package_skill.py"

ALLOWED_FRONTMATTER = {
    "claude": {"name", "description"},
    "hermes": {"name", "description", "version", "title", "author", "license", "created_by",
               "metadata", "platforms", "tags", "allowed-tools"},
}

MAX_NAME = 64
MAX_DESC = {"claude": 200, "hermes": 1024}
WARN_DESC = 200
MAX_BODY_LINES_CLAUDE = 500
WARN_BODY_LINES = 500
MAX_BODY_CHARS_HERMES = 100_000


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def print(self) -> None:
        for m in self.errors:
            print(f"  ✗ {m}")
        for m in self.warnings:
            print(f"  ! {m}")


# ---------- фронтматтер ----------

def split_frontmatter(text: str):
    if not text.startswith("---"):
        return None, text, "нет YAML-фронтматтера (файл должен начинаться с ---)"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text, "фронтматтер не закрыт строкой ---"
    return parts[1], parts[2], None


def parse_frontmatter(raw: str, report: Report):
    try:
        import yaml  # type: ignore
    except ImportError:
        report.warn("нет PyYAML — фронтматтер разобран упрощённо (pip install pyyaml для полной проверки)")
        data = {}
        for line in raw.splitlines():
            m = re.match(r"^(name|description|version|author|license|created_by|platforms|tags):\s*(.+)$", line)
            if m:
                val = m.group(2).strip().strip('"').strip("'")
                data[m.group(1)] = val
        if re.search(r'^\w+:.*:\s', raw, re.M):
            report.warn("в фронтматтере есть 'имя: значение' с двоеточием внутри — закавычь значение")
        return data
    try:
        data = yaml.safe_load(raw)
    except Exception as exc:  # noqa: BLE001
        report.err(f"фронтматтер не парсится как YAML: {str(exc).splitlines()[0]}")
        return None
    if not isinstance(data, dict):
        report.err("фронтматтер — не словарь ключ-значение")
        return None
    return data


# ---------- обход файлов ----------

def is_excluded(rel: Path) -> bool:
    if any(p in EXCLUDE_DIRS for p in rel.parts[:-1]):
        return True
    name = rel.name
    if name in EXCLUDE_FILES:
        return True
    return any(rel.match(g) for g in EXCLUDE_GLOBS)


def collect(skill_dir: Path) -> tuple[list[Path], list[Path]]:
    kept, skipped = [], []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(skill_dir)
        if is_excluded(rel):
            skipped.append(rel)
        else:
            kept.append(rel)
    return kept, skipped


# ---------- проверки ----------

def check_package(skill_dir: Path, target: str, public_check: bool, strict_public: bool) -> Report:
    report = Report()
    skill_files = sorted(skill_dir.rglob("SKILL.md"))
    if not skill_files:
        report.err("в пакете нет SKILL.md")
        return report
    if len(skill_files) > 1:
        report.err("SKILL.md больше одного: " + ", ".join(str(p.relative_to(skill_dir)) for p in skill_files))
    main = skill_dir / "SKILL.md"
    if not main.exists():
        report.err("SKILL.md лежит не в корне пакета — загрузчик его не увидит")
        main = skill_files[0]

    text = main.read_text(encoding="utf-8")
    raw, body, err = split_frontmatter(text)
    if err:
        report.err(err)
        data = {}
    else:
        data = parse_frontmatter(raw, report) or {}

    allowed = ALLOWED_FRONTMATTER[target]
    for key in sorted(data):
        if key not in allowed:
            msg = f"поле фронтматтера '{key}' не поддерживается целью {target}"
            report.err(msg) if target == "claude" else report.warn(msg + " — лишнее поле может сломать чужой загрузчик")

    name = str(data.get("name", ""))
    if not name:
        report.err("во фронтматтере нет name")
    else:
        if len(name) > MAX_NAME:
            report.err(f"name длиннее {MAX_NAME} знаков ({len(name)})")
        if not NAME_RE.match(name):
            report.err(f"name '{name}': допустимы только строчные [a-z0-9-]")
        if any(w in name for w in RESERVED):
            report.err(f"name '{name}': зарезервированное слово ({', '.join(RESERVED)})")
        if name != skill_dir.name:
            report.warn(f"name '{name}' не совпадает с именем папки '{skill_dir.name}' — пакет ставится по имени папки")

    desc = str(data.get("description", ""))
    if not desc:
        report.err("во фронтматтере нет description — навык не будет находиться по триггерам")
    else:
        if len(desc) > MAX_DESC[target]:
            report.err(f"description {len(desc)} знаков — лимит {MAX_DESC[target]} для цели {target}")
        elif len(desc) > WARN_DESC:
            report.warn(f"description {len(desc)} знаков — лучше ≤{WARN_DESC}, иначе у части загрузчиков обрежется")
        if DESC_XML.search(desc):
            report.err("в description есть XML-теги — они ломают схему")
        head = desc[:57]
        if not re.match(r"(?i)^(use when|use for|когда|для задач)", head):
            report.warn(f"description начинается не с триггера: '{head}' — первые 57 знаков решают, найдётся ли навык")

    lines = body.count("\n")
    if target == "claude" and lines > MAX_BODY_LINES_CLAUDE:
        report.err(f"тело SKILL.md {lines} строк — лимит {MAX_BODY_LINES_CLAUDE} для переносимого навыка (вынеси в references/)")
    elif lines > WARN_BODY_LINES:
        report.warn(f"тело SKILL.md {lines} строк — разнеси детали по references/")
    if len(body) > MAX_BODY_CHARS_HERMES:
        report.err(f"тело SKILL.md {len(body)} знаков — Hermes обрежет на {MAX_BODY_CHARS_HERMES}")

    kept, skipped = collect(skill_dir)
    kept_set = {str(p) for p in kept}

    # ссылки именно на файлы пакета: «scripts/x.py», но не «чужой-репо/scripts/x.py»
    link_re = re.compile(r"(?<![\w./-])((?:references|scripts|assets|templates)/[\w\-./]+\.\w+)")
    for link in sorted(set(link_re.findall(text))):
        if link not in kept_set:
            report.err(f"SKILL.md ссылается на '{link}', а в пакете его нет")

    junk = [str(p) for p in kept if p.suffix in {".pyc", ".pyo"} or ".egg-info" in str(p)]
    if junk:
        report.err("в пакете байт-код/сборка: " + ", ".join(junk[:5]))
    cache = sorted(str(p.relative_to(skill_dir)) for p in skill_dir.rglob("*")
                   if p.is_dir() and p.name in {"__pycache__", ".pytest_cache", "dist", ".mypy_cache"})
    if cache:
        report.warn("в папке навыка кэш/сборка (" + ", ".join(cache[:4]) +
                    ") — в пакет не попадёт, но и коммитить это не надо")

    check_secrets(skill_dir, kept, report)
    if public_check:
        check_public(skill_dir, kept, report, strict_public)
    return report


def check_secrets(skill_dir: Path, kept: list[Path], report: Report) -> None:
    for rel in kept:
        name = rel.name
        if name in SECRET_TEMPLATES_OK:
            continue
        if name in SECRET_FILES or any(rel.match(g) for g in SECRET_GLOBS):
            report.err(f"файл с секретами в пакете: {rel} — убери из папки навыка, ключи хранятся вне репозитория")
            continue
        if rel.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = (skill_dir / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in SECRET_PATTERNS:
            m = pattern.search(content)
            if m:
                report.err(f" похоже на {label} в {rel}: '{m.group(0)[:12]}…' — сборка остановлена, отзови ключ и убери его")


def check_public(skill_dir: Path, kept: list[Path], report: Report, strict: bool) -> None:
    findings = 0
    for rel in kept:
        if rel.name == SELF_NAME or rel.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = (skill_dir / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in PUBLIC_PATTERNS:
            m = pattern.search(content)
            if m:
                findings += 1
                msg = f"публичный чек: {label} в {rel}: '{m.group(0)[:40]}'"
                report.err(msg) if strict else report.warn(msg)
    if findings == 0:
        print("  ✓ публичный чек: наш внутренний контекст не найден")


# ---------- сборка ----------

def build(skill_dir: Path, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{name}.zip"
    kept, _ = collect(skill_dir)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in kept:
            zf.write(skill_dir / rel, f"{name}/{rel.as_posix()}")
    return archive


def main() -> int:
    ap = argparse.ArgumentParser(description="Валидация и сборка пакета навыка")
    ap.add_argument("--skill-path", default=".", help="папка навыка (по умолчанию текущая)")
    ap.add_argument("--output", default="dist", help="куда собирать архив (по умолчанию dist/)")
    ap.add_argument("--target", choices=["hermes", "claude"], default="hermes", help="цель переносимости")
    ap.add_argument("--name", default=None, help="имя пакета (по умолчанию имя папки)")
    ap.add_argument("--check", action="store_true", help="только валидация, без сборки")
    ap.add_argument("--public-check", action="store_true", help="искать внутренний контекст агентства")
    ap.add_argument("--strict-public", action="store_true", help="находки публичного чека считаются ошибками")
    args = ap.parse_args()

    skill_dir = Path(args.skill_path).expanduser().resolve()
    if not skill_dir.is_dir():
        print(f"нет папки {skill_dir}", file=sys.stderr)
        return 2
    if not (skill_dir / "SKILL.md").exists():
        print(f"в {skill_dir} нет SKILL.md — это не папка навыка", file=sys.stderr)
        return 2

    name = args.name or skill_dir.name
    print(f"Пакет: {name}  (цель: {args.target}, папка: {skill_dir})")
    report = check_package(skill_dir, args.target, args.public_check, args.strict_public)
    report.print()

    if report.errors:
        print(f"\n❌ Ошибок: {len(report.errors)}, предупреждений: {len(report.warnings)} — пакет не собран")
        return 1

    kept, skipped = collect(skill_dir)
    print(f"\n✓ Проверки пройдены (предупреждений: {len(report.warnings)})")
    print(f"  файлов в пакете: {len(kept)}" + (f", исключено: {len(skipped)}" if skipped else ""))
    if args.check:
        return 0

    archive = build(skill_dir, Path(args.output).expanduser().resolve(), name)
    size = archive.stat().st_size
    print(f"✓ Собрано: {archive}  ({size // 1024} КБ)")
    print(f"  форма: {name}/SKILL.md внутри архива — так ждут загрузчики")
    return 0


if __name__ == "__main__":
    sys.exit(main())
