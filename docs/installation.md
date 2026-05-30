# Installation

## For Primary Agents (Recommended Path)

For normal day-to-day use as a primary agent, install a specific released version:

```bash
pip install git+https://github.com/joshuafielden43/code-delegation-harness.git@v0.2.1
```

This gives you a clean, versioned install without pulling the full repository history.

After installation:

```bash
gcdh --version
gcdh --help
```

Once the package is published on PyPI, the command will simplify to:

```bash
pip install code-delegation-harness
```

## For Bleeding Edge / Development Use

Only use the following if you need the absolute latest code from the repository (e.g. to test an unreleased change or to contribute):

```bash
pip install git+https://github.com/joshuafielden43/code-delegation-harness.git
```

**Note:** Git-based installs are slower, pull unnecessary history, and do not work well with version pinning or constrained environments. Treat this as a temporary/development option only.

## Development Installation (Modifying the Harness)

If you are actively developing or modifying the harness:

```bash
git clone https://github.com/joshuafielden43/code-delegation-harness.git
cd code-delegation-harness
pip install -e .
```

This installs the package in editable mode.

## Verifying the Installation

```bash
gcdh --version
gcdh --help
```
