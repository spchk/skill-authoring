#!/usr/bin/env python3
"""
sync_skills.py — перенос навыка из библиотеки Hermes в репозиторий агентства.

Куда: рабочие репозитории команды живут в организации на GitHub. Репозиторий навыков —
<org>/ai-skills — рабочая копия берётся из переменной AI_SKILLS_REPO (по умолчанию ~/projects/ai-skills).
Личный профиль <владелец> для агентских задач не используется.

Команды:
    python3 sync_skills.py status                     сравнить библиотеку Hermes и репозиторий
    python3 sync_skills.py check                      проверить репозиторий его же валидатором
    python3 sync_skills.py push <имя> [--category к]  перенести навык в репо (новая ветка, без сети)

Что делает push:
  1. копирует содержимое навыка (SKILL.md, references/, scripts/, assets/, templates/);
  2. ищет запрещённое: серверные пути, похожие на секреты строки, кириллические имена файлов;
  3. останавливается на находке (exit 2) — сначала чинишь источник или явно повторяешь --allow-paths;
  4. добавляет во фронтматтер category, если его нет;
  5. запускает tools/validate_skill.py из репозитория;
  6. печатает готовые команды: ветка → коммит → push → PR в main.

Коммит и push sync_skills.py НЕ делает: изменения в общий репозиторий уходят только через PR,
и решение о них — за человеком.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Пути не хардкодим: у коллеги своя библиотека навыков и своя рабочая копия репозитория.
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")).expanduser()
HERMES_SKILLS = HERMES_HOME / "skills"
# ищем серверные абсолютные пути: у коллег их нет и быть не должно
SERVER_PATH_RE = re.compile(r"/opt/" + "data/")
HERE = Path(__file__).resolve().parent


def default_repo() -> Path:
    """Рабочая копия репозитория навыков: AI_SKILLS_REPO → ~/projects/ai-skills → рядом с HERMES_HOME."""
    env = os.environ.get("AI_SKILLS_REPO")
    if env:
        return Path(env).expanduser()
    candidates = (Path.home() / "projects" / "ai-skills",
                  HERMES_HOME / "projects" / "spichki" / "ai-skills-repo",
                  HERMES_HOME.parent / "projects" / "spichki" / "ai-skills-repo")
    for cand in candidates:
        if (cand / "skills").is_dir():
            return cand
    return candidates[0]


DEFAULT_REPO = default_repo()
CONTENT = ("SKILL.md", "references", "scripts", "assets", "templates")
SKIP = {"__pycache__", ".git", ".hub", "dist", "node_modules", ".pytest_cache"}

SECRET_PATTERNS = (
    ("OpenAI/Anthropic-ключ", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}")),
    ("Яндекс OAuth", re.compile(r"\by0_[A-Za-z0-9_\-]{20,}")),
    ("Yandex Cloud SA", re.compile(r"\bAQVN[A-Za-z0-9_\-]{15,}")),
    ("Replicate", re.compile(r"\br8_[A-Za-z0-9]{30,}")),
    ("GitHub-токен", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("Google API-ключ", re.compile(r"\bAIza[A-Za-z0-9_\-]{30,}")),
    ("Приватный ключ", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
TEXT_SUFFIXES = {".md", ".py", ".json", ".sh", ".yml", ".yaml", ".txt", ".toml", ""}


def files_of(root: Path) -> list[Path]:
    return [f for f in sorted(root.rglob("*"))
            if f.is_file() and not any(p in SKIP for p in f.parts)]


def find_local(name: str, category: str | None = None) -> Path:
    """Найти навык в библиотеке Hermes: <HERMES_HOME>/skills/<категория>/<имя>/."""
    if category:
        cand = HERMES_SKILLS / category / name
        if (cand / "SKILL.md").exists():
            return cand
    hits = [p.parent for p in HERMES_SKILLS.glob(f"*/{name}/SKILL.md")]
    hits += [p.parent for p in HERMES_SKILLS.glob(f"*/*/{name}/SKILL.md")]
    if not hits:
        sys.exit(f"Навык {name} не найден в {HERMES_SKILLS}")
    if len(hits) > 1:
        sys.exit("Найдено несколько навыков с таким именем: " + ", ".join(str(h) for h in hits))
    return hits[0]


def scan(path: Path, allow_paths: bool) -> list[str]:
    problems: list[str] = []
    for f in files_of(path):
        rel = f.relative_to(path)
        if any(ord(ch) > 127 for ch in f.name):
            problems.append(f"кириллическое имя файла: {rel} — переименуй латиницей")
        if f.suffix.lower() not in TEXT_SUFFIXES:
            continue
        content = f.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS:
            m = pattern.search(content)
            if m:
                problems.append(f"похоже на {label} в {rel}: '{m.group(0)[:12]}…'")
        if SERVER_PATH_RE.search(content) and not allow_paths:
            for i, line in enumerate(content.splitlines(), 1):
                if SERVER_PATH_RE.search(line):
                    problems.append(f"серверный путь в {rel}:{i} — у коллег его нет")
                    break
    return problems


def copy_skill(src: Path, dst: Path) -> list[str]:
    if dst.exists():
        shutil.rmtree(dst)
    copied: list[str] = []
    for entry in CONTENT:
        p = src / entry
        if p.is_file():
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / entry)
            copied.append(entry)
        elif p.is_dir():
            for f in files_of(p):
                rel = f.relative_to(src)
                (dst / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst / rel)
                copied.append(str(rel))
    return copied


def repo_skills(repo: Path) -> dict[str, Path]:
    return {p.name: p for p in sorted((repo / "skills").iterdir()) if (p / "SKILL.md").exists()}


def cmd_status(repo: Path) -> int:
    if not (repo / "skills").is_dir():
        sys.exit(f"{repo} не похож на рабочую копию репозитория агентства")
    print(f"Репозиторий: {repo}")
    subprocess.run(["git", "-C", str(repo), "fetch", "--quiet", "origin"], check=False)
    branch = subprocess.run(["git", "-C", str(repo), "branch", "--show-current"],
                            capture_output=True, text=True).stdout.strip()
    print(f"Ветка: {branch}\n")
    for name, skill_path in repo_skills(repo).items():
        try:
            local = find_local(name)
        except SystemExit:
            print(f"  {name:32} только в репозитории")
            continue
        diff = subprocess.run(["diff", "-rq", str(local), str(skill_path),
                               "-x", "__pycache__", "-x", ".git"],
                              capture_output=True, text=True)
        same = diff.returncode == 0
        print(f"  {name:32} {'совпадает' if same else 'расходится с библиотекой'}")
        if not same:
            for line in diff.stdout.splitlines()[:6]:
                print("        " + line.replace(str(local), "библиотека").replace(str(skill_path), "репо"))
    print()
    return 0


def cmd_check(repo: Path) -> int:
    validator = repo / "tools" / "validate_skill.py"
    if not validator.exists():
        sys.exit(f"нет {validator} — валидатор лежит в репозитории (появляется после мержа CI-ветки)")
    return subprocess.run([sys.executable, str(validator)], cwd=repo).returncode


def validate_pushed(repo: Path, skill_dir: Path) -> int:
    """Проверка после push: валидатором репозитория, а если его ещё нет — нашим упаковщиком."""
    validator = repo / "tools" / "validate_skill.py"
    if validator.exists():
        return cmd_check(repo)
    packager = HERE / "package_skill.py"
    if not packager.exists():
        print("Проверка пропущена: в рабочей копии нет валидатора (обнови main)", file=sys.stderr)
        return 0
    print("В рабочей копии пока нет tools/validate_skill.py — проверяю упаковщиком навыка", file=sys.stderr)
    return subprocess.run([sys.executable, str(packager), "--skill-path", str(skill_dir), "--check"]).returncode


def cmd_push(args) -> int:
    repo = Path(args.repo_dir).expanduser().resolve()
    if not (repo / "skills").is_dir():
        sys.exit(f"{repo} не похож на рабочую копию репозитория агентства (--repo-dir)")
    src = find_local(args.name, args.category)
    category = args.category or src.parent.name

    print(f"Источник: {src}  (категория {category})")
    problems = scan(src, args.allow_paths)
    if problems:
        print("\nВыгрузка остановлена — сначала почини:", file=sys.stderr)
        for p in problems:
            print(f"  • {p}", file=sys.stderr)
        return 2

    dst = repo / "skills" / args.name
    copied = copy_skill(src, dst)
    print(f"Скопировано в {dst}: {len(copied)} файлов")

    skill_md = dst / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    head = text.split("---", 2)[1]
    if "\ncategory:" not in head:
        body = text.split("---", 2)[2]
        skill_md.write_text(f"---\n{head.rstrip()}\ncategory: {category}\n---{body}", encoding="utf-8")
        print(f"Во фронтматтер добавлено поле category: {category}")

    rc = validate_pushed(repo, dst)
    if rc != 0:
        print("Валидатор репозитория нашёл ошибки — правим до PR", file=sys.stderr)
        return rc

    print("\nДальше — ветка, коммит и PR (решение за человеком):")
    print(f"  cd {repo} && git pull && git switch -c add-{args.name} main")
    print(f"  git add skills/{args.name} && git commit -m 'Навык {args.name}: <что делает>'")
    print(f"  git push -u origin add-{args.name}")
    print(f"  gh pr create --repo <org>/ai-skills --base main --head add-{args.name} "
          f"--title 'Навык {args.name}' --body '<что и зачем>'")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Перенос навыков Hermes в репозиторий агентства")
    ap.add_argument("--repo-dir", default=str(DEFAULT_REPO), help="рабочая копия <org>/ai-skills")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="сравнить библиотеку и репозиторий")
    p_status.set_defaults(func=lambda a: cmd_status(Path(a.repo_dir).expanduser().resolve()))

    p_check = sub.add_parser("check", help="валидатор репозитория по всем навыкам")
    p_check.set_defaults(func=lambda a: cmd_check(Path(a.repo_dir).expanduser().resolve()))

    p_push = sub.add_parser("push", help="перенести один навык в рабочую копию репозитория")
    p_push.add_argument("name")
    p_push.add_argument("--category", help="категория источника в библиотеке Hermes")
    p_push.add_argument("--allow-paths", action="store_true",
                        help="не останавливаться на серверных путях (для внутренних справочников)"),
    p_push.set_defaults(func=cmd_push)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
