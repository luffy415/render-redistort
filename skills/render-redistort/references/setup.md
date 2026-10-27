# Installation / isolated runtime

The distribution repository contains this skill at `skills/render-redistort`. A recipient can ask Codex in one chat message to install that path from the repository and prepare/check the runtime. Use the built-in skill-installer helper when available; otherwise use the repository's audited `install.py`. A link does not itself run code or bypass local permissions.

Installation steps for the agent:

1. Inspect the repository installation instructions and scripts. Install only this skill folder into `$CODEX_HOME/skills` or `~/.codex/skills`; never bundle the user's production footage, environment, credentials or unrelated files.
2. Find a usable Python3.11–3.13 (3.13 tested). Prefer an existing local interpreter or the Codex bundled Python discovered through workspace dependencies. If none exists, arrange installation from Python's official distribution within the user's authorized setup scope; don't silently replace system Python. Wheels must be available for the recipient platform.
3. Run `python <installed-skill>/scripts/setup_runtime.py`. It creates `<skill>/.runtime`, installs the pinned requirements, executes synthetic tests, and writes `runtime.local.json` with the resolved Python path. No global pip changes, GPU tools or account/API keys are needed.
4. On later use run `python <skill>/scripts/setup_runtime.py --check-only` or use the recorded runtime Python after checking it exists. An existing non-venv directory is not overwritten. An optional `--runtime` path can place the isolated environment elsewhere.
5. Report registration, dependency/test status and the next-turn invocation `$render-redistort`. Do not call installation ready when only SKILL.md was copied.

Dependencies are fetched from PyPI: NumPy2.4.2, SciPy1.17.1, OpenImageIO3.1.18.1. Their own licenses remain in the installed packages; no dependency binaries are bundled in the skill archive. Runtime files, caches and local absolute paths are excluded from public releases.

If an installation is interrupted, inspect the registered skill and dedicated environment. If the source matches, resume runtime preparation; do not blindly delete/reinstall existing user changes. The repository installer compares distributed code before resuming an existing install.
