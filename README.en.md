# skill-authoring — build, package and ship agent skills

A skill for people who turn a working process into an AI-agent skill: from the text of `SKILL.md`
to a public repository with versions, releases and CI. Distilled from the practice of the «Спички»
agency — internal skills for the team's agents and public skills for the market.

Works with Hermes Agent, OpenClaw, Claude Code, Cline, Cursor, Codex. MIT license.

## What you get

- **Three storage tiers** — the agent's personal skills folder, the team's private repository, the
  public market repository: what is mandatory in each tier and why "personal first, decide later" is
  the wrong default.
- **A `SKILL.md` skeleton** — section order with wording: when it triggers, boundaries, what the
  skill needs from the environment with an "if missing" fallback, artifacts between steps, gates on
  side effects.
- **Versions, updates and requirement checks** — `version` in the skill front matter, `CHANGELOG.md`,
  releases tagged `<skill-name>-v<version>`, a script that compares the installed version with the
  repository, and a preflight check of environment and models **before** the run (keys, a live model
  probe, balance, cost estimate).
- **Packaging and validation** — a packager that stops on secrets instead of silently dropping them,
  plus a pre-publication checklist (internal paths, client names, account ids).
- **Going public** — license obligations, public repository layout, `main`/`dev` branches, PR rules,
  user-facing release notes, CI and tag-driven releases.

## Quick start

Ask your agent:

```
build a skill for the team: turn client call transcripts into decisions
package our process as a skill — what goes into the repo and what does not
check whether this skill is safe to publish publicly
```

You get a skill folder following the canon, a secrets and internal-context report, ready-to-run
branch/commit/PR commands, and for the public tier — a README in two languages, LICENSE, CI and a
release workflow.

## Scripts

| script | purpose |
|---|---|
| `scripts/new_skill.py` | scaffold a skill for one of three tiers (`personal` / `internal` / `external`) |
| `scripts/package_skill.py` | packaging and validation: secrets, portability, `--public-check` before publishing |
| `scripts/sync_skills.py` | move a skill from the personal library into the team repository, then validate |

## Installation

### Hermes Agent (tap)

```bash
hermes skills tap add spchk/skill-authoring
hermes skills install agency-skill-authoring
```

### Manual copy

```bash
git clone https://github.com/spchk/skill-authoring.git
cd skill-authoring
bash scripts/install.sh --agent hermes      # or --dir ~/my/skills
```

The script copies `skills/*` into the agent's skills folder
(`--agent hermes|openclaw|claude|cline|codex|cursor`). Restart the agent session afterwards.

### Other agents

A skill is just a `SKILL.md` plus reference files and Python scripts: drop
`skills/agency-skill-authoring/` into any agent that reads this format.

## Versions and releases

The skill version lives in the front matter of `skills/agency-skill-authoring/SKILL.md`, its history
in the `CHANGELOG.md` next to it. Releases are tagged `<skill-name>-v<version>`:

```bash
gh release list
gh release view agency-skill-authoring-v1.1.0
```

Current version: **1.1.0**.

## License

MIT — see [LICENSE](LICENSE). Use it, change it, embed it in your own process.
