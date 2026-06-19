# Local Security Checks Before Pull Requests

This project runs `scripts/security_check.sh` in GitHub Actions. The same check can be run locally before opening or updating a pull request, so dependency audit failures are caught earlier.

## 1. Install Local Security Tooling

From the Django project directory:

```bash
cd examc
python3 -m pip install bandit pip-audit
```

If you use the project virtual environment:

```bash
cd examc
../venv/bin/python -m pip install bandit pip-audit
```

## 2. Run the Same Check as CI

```bash
cd examc
bash scripts/security_check.sh
```

This runs:

- mutation endpoint guard checks;
- forbidden high-risk call scanning;
- Bandit, blocking only high-severity/high-confidence findings;
- `pip-audit` against `requirements.txt`.

## 3. Enable Versioned Git Hooks

The repository contains hooks in `.githooks`.

Enable them once per local clone:

```bash
cd examc
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push
```

After this:

- `pre-commit` blocks accidental commits of `.env` files and database dumps.
- `pre-push` runs `scripts/security_check.sh` before code reaches GitHub.

If a hook fails because `bandit` or `pip-audit` is missing, install the tooling from step 1.

## 4. Dependency Updates

GitHub Dependabot is configured in `.github/dependabot.yml` to check Python dependencies weekly.

When Dependabot opens a dependency update PR:

1. Review the changelog or release notes for risky breaking changes.
2. Run the local security check.
3. Run the relevant application tests or smoke checks.
4. Merge if CI is green.

## 5. Handling Audit Failures

When `pip-audit` reports a vulnerable direct dependency:

1. Prefer upgrading to a fixed version when one exists.
2. If no fixed version exists and the package is lightly used, replace or remove the dependency.
3. Use `--ignore-vuln` only as a temporary exception, with a documented reason and follow-up date.

For direct dependencies used in production paths, do not leave permanent audit ignores without a reviewed risk acceptance.
