# Security Policy

## Maintainer

- **Security maintainer:** João Antonio Mesquita Felipe
- **GitHub:** [@mesquitafelipe571-ai](https://github.com/mesquitafelipe571-ai)
- **Runtime environment:** Google Cloud Platform, region `southamerica-east1`
  (see [docs/INSTALACAO_GOOGLE_VM.md](docs/INSTALACAO_GOOGLE_VM.md))

## Scope

In scope: the code and configuration maintained in this repository —
`scripts/`, `tests/`, `.github/workflows/`, `.devcontainer/`, `.codex/`,
`.claude/`, `config/`, `compose.paperclip.json` and `package.json`.

Out of scope here: the vendored skills under `.agents/skills/` and the Git
submodules (`orca`, `paperclip`, `awesome-linux-dev`, `claude-melhores-skills`,
`awesome-claude-code-mods`). Report issues in those to their upstream projects;
the files under `.agents/<source>/SOURCE.md` link to each one. If an upstream
issue affects how this repository uses that code, a report here is welcome too.

## Supported versions

Only the current `main` branch receives security fixes.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub private vulnerability reporting:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Describe the issue, the affected file or command, steps to reproduce, and the
   impact you expect.

## What to expect

| Step | Target |
| --- | --- |
| Acknowledge the report | within 7 days |
| Initial assessment (valid or not, severity) | within 14 days |
| Fix or mitigation for confirmed issues | within 90 days of the report |

Disclosure is coordinated: once a fix is merged, a GitHub Security Advisory is
published for confirmed vulnerabilities, crediting the reporter unless they ask
otherwise. If a fix needs more than 90 days, the maintainer will agree on a new
date with the reporter before any public disclosure.

## How this repository is checked

- `scripts/check-repo.py` and the test suite run on every pull request
  (`.github/workflows/`).
- Dependabot watches GitHub Actions, the dev container image and features, and
  the pinned Git submodules (`.github/dependabot.yml`).
- Changes to `main` go through pull requests.
