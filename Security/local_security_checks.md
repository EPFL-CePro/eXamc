# Local Security Checks Before Pull Requests

This project runs `django/security/security_check.sh` in GitHub Actions. The same check can be run locally before opening or updating a pull request, so dependency audit failures are caught earlier.

Paths below are relative to the repository root:

```
.
├─ .githooks/            # Versioned Git hooks (pre-commit, pre-push)
├─ .github/
│  └─ dependabot.yml
└─ django/
   ├─ app/               # Django application (pyproject.toml, uv.lock)
   └─ security/
      ├─ check_forbidden_calls.py
      ├─ check_require_post.py
      └─ security_check.sh
```

## 1. Install Local Security Tooling

Install `bandit` and `pip-audit` once, either globally as isolated tools:

```bash
uv tool install bandit
uv tool install pip-audit
```

or with pip into your current Python environment:

```bash
python3 -m pip install bandit pip-audit
```

## 2. Run the Same Check as CI

```bash
cd django
bash security/security_check.sh
```

This runs:

- Mutation endpoint guard checks;
- Forbidden high-risk call scanning;
- `bandit` on `django/app/`, blocking only high-severity/high-confidence findings;
- `pip-audit` against the application dependencies (`app/pyproject.toml` / `app/uv.lock`).

## 3. Enable Versioned Git Hooks

The repository contains hooks in `.githooks/` at the repository root.

Enable them once per local clone, from the repository root:

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push
```

After this:

- `pre-commit` blocks accidental commits of `.env` files and database dumps.
- `pre-push` runs `django/security/security_check.sh` before code reaches GitHub.

If a hook fails because `bandit` or `pip-audit` is missing, install the tooling from step 1.

## 4. Dependency Updates

GitHub Dependabot is configured in `.github/dependabot.yml` to check the Python dependencies in `django/app` weekly.

When Dependabot opens a dependency update PR:

1. Review the changelog or release notes for risky breaking changes.
2. Run the local security check.
3. Run the relevant application tests or smoke checks (see *TEST / PROD overview* in the main `README.md` for the test command).
4. Merge if CI is green.

## 5. Handling Audit Failures

When `pip-audit` reports a vulnerable direct dependency:

1. Prefer upgrading to a fixed version when one exists (`uv add "package>=fixed.version"` or `uv lock --upgrade-package package`, run in `django/app`).
2. If no fixed version exists and the package is lightly used, replace or remove the dependency.
3. Use `--ignore-vuln` only as a temporary exception, with a documented reason and follow-up date.

For direct dependencies used in production paths, do not leave permanent audit ignores without a reviewed risk acceptance.