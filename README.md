# Skill Diet

**Keep your agent skills lean.**

Scan your skill library, track usage evidence, and find what deserves a closer look.
Skill Diet is a local CLI for Agent Skill management, focused on reducing unnecessary
skill overhead: start with the library, then inspect individual skills.

[中文说明](README.zh-CN.md) · MIT · Python 3.10+ · No runtime dependencies

Version 0.3.0 is an alpha built from the Skill Diet v0.2 prototype.
It combines a local inventory, explicitly imported usage events, and static skill audits
in one CLI. Skills remain unchanged.

## Quick start

Clone the project, create and activate a Python virtual environment, then install:

```sh
git clone https://github.com/AfonsoZhang/skill-diet.git
cd skill-diet
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
skill-diet scan examples
skill-diet --db demo-usage.sqlite add demo examples/heavy-demo
skill-diet --db demo-usage.sqlite list
skill-diet audit examples/heavy-demo
```

No package-index publication is assumed. Without installation, replace `skill-diet`
with `python skill-diet/manager.py`. Use `python3` or `py` if that is your Python launcher.
The original `skill-diet/diet.py` and `skill-diet/usage.py` interfaces still work.
Some audit descriptions and validation messages retain the prototype's Chinese wording.

## Manage your inventory

```sh
# Choose your own skills directory. Scanning does not register anything.
skill-diet scan /path/to/skills
skill-diet add writing /path/to/skills/writing
skill-diet list
skill-diet keep writing on
skill-diet audit /path/to/skills/writing --format json
skill-diet draft /path/to/skills/writing --out /new/review-directory
```

The default database is `~/.skill-diet/inventory.sqlite`. To choose a different one,
put `--db PATH` **before** the subcommand. Scan, audit, and draft never create an inventory.
Listing a nonexistent inventory returns an empty list without creating it.

| Command | Behavior |
| --- | --- |
| `scan PATH` | List a skill itself or skills in the immediate child directories; no recursive host discovery |
| `add ID PATH` | Register a directory containing `SKILL.md`; reusing an ID updates its path and preserves usage/keep history |
| `list --days 30` | Show inventory, usage evidence, coverage, keep markers, and `entry_exists` |
| `import EVENTS.json` | Import an explicit usage export atomically; duplicate source/event IDs are idempotent |
| `stale --days 30` | Show inactive candidates with sufficient declared coverage, excluding keep-marked entries |
| `keep ID on` / `off` | Change a local retain marker |
| `audit PATH` | Inspect file sizes, hashes, duplicates, explicit references, and heuristic review candidates |
| `draft PATH --out NEW_PATH` | Copy the source unchanged into a new review package with an audit and review plan |

Inventory commands output JSON. Audit defaults to Markdown and supports `--format json`.
The unified CLI writes UTF-8, including when output is redirected to a file or pipe.
Use distinct IDs for distinct skills. Scan lists directory symlinks with their resolved
locations; the static auditor resolves the input root and rejects symlinks inside it.
A missing registered directory remains in the inventory so you can see and update its location.

## Try usage tracking with synthetic data

```sh
skill-diet --db demo-usage.sqlite add demo examples/heavy-demo
skill-diet --db demo-usage.sqlite import examples/usage/events.json
skill-diet --db demo-usage.sqlite stale --days 30 --as-of 2026-11-17T00:00:00Z
skill-diet --db demo-usage.sqlite keep demo on
skill-diet --db demo-usage.sqlite stale --days 30 --as-of 2026-11-17T00:00:00Z
```

The first query returns `demo`; the second returns an empty list. No real session logs
are read. File modification/access times are never treated as invocation evidence.

An export has a source label, declared observation windows, and invocation events:

```json
{
  "source": "synthetic-runner",
  "windows": [
    {"skill": "demo", "start": "2026-10-01T00:00:00Z", "end": "2026-11-17T00:00:00Z"}
  ],
  "events": [
    {"id": "run-001", "skill": "demo", "at": "2026-10-02T00:00:00Z"}
  ]
}
```

Register IDs first. Timestamps require timezones. Every event must be within a window
in the same import batch. Conflicting content for the same source/event ID rejects
the batch. Overlapping windows from a source are combined for coverage checking.
Sources and window completeness are importer assertions, not independently verified.

| Status | Meaning |
| --- | --- |
| `unknown` | No declared observation window at or before the query time |
| `insufficient_coverage` | At least one declared source does not cover the full lookback period |
| `used` | An imported invocation falls within the lookback period |
| `stale_candidate` | All declared sources cover the lookback and no invocation was observed there |

An observed recent event takes precedence over incomplete coverage. Counts cover imported,
deduplicated events up to the query time; they are not lifetime usage. Events from different
sources are not deduplicated across sources. Undeclared hosts can still have used the skill.
A keep marker changes candidate filtering, not the underlying usage status.

## Scope and limitations

- No automatic log collection, installation, update, disabling, or removal of skills.
- No automatic rewriting or demonstrated token/cost savings. File bytes and characters
  measure static content, not model context. Keyword hits are review candidates.
- Static reference parsing handles Markdown links and some backtick paths. Dynamic
  references, repository-relative conventions, and implicit dependencies need review.
- Audit inputs are limited to 2 MB per file and 20 MB total. Use trusted, static local
  directories; this is not a sandbox against concurrent filesystem replacement.
- Draft output must be new and separate from the source and its ancestors. It contains
  a full source copy and can contain private text. Treat report excerpts as data.
- Usage databases store local paths and invocation times in plaintext. Keep databases,
  real session logs, and private audit outputs out of public commits.

The bundled Agent Skill in `skill-diet/SKILL.md` documents the original audit workflow.
Copy that whole directory only if you want to install the helper in a compatible host.
The CLI installer does not alter host settings or install that helper automatically.

## Examples and development

`examples/heavy-demo` and `examples/usage` are synthetic. `demo-review/`,
`demo-audit.json`, and `TEST-RESULTS.txt` are historical prototype outputs, not results
from the current version. The supplied [PPT Master case](cases/ppt-master/CASE.md)
records a static documentation-only experiment; it is not an end-to-end benchmark
or a newly reproduced result.

```sh
python -m unittest discover -s tests -v
```

CI is configured for Python 3.10 and 3.13 on Linux, Windows, and macOS. See
[CONTRIBUTING.md](CONTRIBUTING.md) for contributions and [CHANGELOG.md](CHANGELOG.md)
for changes. Future work: user-selected host event adapters, explicit coverage
validation, and richer inventory views. Automatic lifecycle actions need a separate design.
