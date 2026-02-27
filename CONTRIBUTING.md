 # Contributing to ethercat-tool

Thank you for your interest in improving `ethercat-tool`! This project aims to make EtherCAT network troubleshooting easier and more repeatable; contributions of all sizes are welcome.

Before contributing, please also read the `CODE_OF_CONDUCT.md`.

## Ways to contribute

- **Bug reports:** Problems running the tool, inaccurate reports, crashes, or confusing behaviour.
- **Feature requests:** Ideas that make EtherCAT troubleshooting easier (new report sections, extra checks, CLI flags, etc.).
- **Documentation:** Clarifying the README, adding examples, or improving error/help messages.
- **Code changes:** Bug fixes, refactors, tests, or new features.

If you are not sure whether something is in scope, feel free to open an issue first and ask.

## Development setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/dbrowngm/ethercat-tool.git
   cd ethercat-tool
   ```

2. **Create and activate a virtual environment (recommended)**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies (including dev tools)**

   ```bash
   pip install -e .[dev]
   ```

   This installs the package itself plus `pytest`, `ruff`, and `mypy`.

## Running tests and checks

Run the test suite:

```bash
pytest
```

Run the linter (Ruff):

```bash
ruff check .
```

Run type checking (mypy):

```bash
mypy .
```

Please make sure tests pass and there are no new linter/type errors before opening a pull request.

## Coding guidelines

- **Python version:** Target Python 3.10+ (see `pyproject.toml`).
- **Type hints:** New or modified functions should use type hints where practical. The project is configured with `disallow_untyped_defs = true`.
- **Style:** Ruff is configured with a 100-character line length and a small, focused rule set; run it locally and let it guide formatting.
- **Structure:** Keep CLI-related logic in `ethercat_tool/cli.py` and core logic in the existing modules (`scanner.py`, `diagnostics.py`, `report.py`, etc.). Prefer small, testable functions.
- **Tests:** Add or update tests under `tests/` when changing behaviour or adding new functionality.

## Working with EtherCAT-specific data

When sharing logs or configuration files, keep in mind:

- **Sensitive information:** Remove or anonymise MAC addresses, serial numbers, or proprietary device names if they are sensitive in your environment.
- **Example reports:** See `EXAMPLE-REPORT.md` for the style and level of detail the tool aims to produce. If you change report structure, please refresh or add an example.
- **TwinCAT configurations:** If your change relates to `--validate-config`, including a minimal example XML (with any sensitive names redacted) in the tests can be very helpful.

## Opening a pull request

1. **Create a feature branch** from `main`:

   ```bash
   git checkout -b my-feature
   ```

2. **Make your changes**, keeping commits reasonably focused and well described.

3. **Run tests, lint, and type checks** locally.

4. **Open a pull request** on GitHub:
   - Describe **what** you changed and **why**.
   - Mention any limitations, follow-ups, or potentially breaking changes.
   - If your change affects CLI flags or report output, mention that explicitly.

5. Be prepared to discuss feedback in the PR. Reviews are a normal part of the process and help keep the tool reliable.

## Reporting security issues

If you believe you have found a security-related issue, please **do not** open a public GitHub issue. Instead, contact the maintainer directly via the email listed on their GitHub profile or the project’s PyPI page so we can coordinate a fix and disclosure.

