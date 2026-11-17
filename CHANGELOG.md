# Changelog

## 0.4.0 — Alpha

- Add recursive discovery across explicit roots, nested skills, plugin caches and
  symlink aliases, with cycle protection and reported resource limits.
- Keep filesystem discovery separate from trusted host observations and usage.
- Add categorized, source-located evidence findings and explicit inspection coverage.
- Add a seeded synthetic benchmark with fixed review budgets, hidden ground truth,
  paired scoring, and unobserved token/cost fields.
- Preserve the original shallow scan, audit, draft and inventory commands.

## 0.3.0 — Alpha

- Reframe the prototype as local Agent Skill management.
- Add the unified `skill-diet` CLI and installable Python package.
- Discover skills in an explicit directory without automatic registration.
- Show whether registered skill entries still exist on disk.
- Preserve the standalone audit and usage script interfaces.
- Fix complete observation windows being misclassified at an exact lookback boundary.
- Return a validation error for non-string event timestamps.
- Write unified CLI output as UTF-8 even when the host's pipe encoding is ASCII.
- Add CLI integration tests and a Windows/macOS/Linux CI configuration.

## 0.2 — supplied prototype

- Add SQLite inventory, explicit usage imports, coverage-aware inactivity
  candidates, and keep markers.

## 0.1 — supplied prototype

- Add static audits and review drafts, synthetic examples, and a documented
  PPT Master static case study.
