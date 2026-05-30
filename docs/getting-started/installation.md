# Installation

## For Primary Agents (Recommended Path)

The preferred way to install for normal use is from PyPI:

```bash
pip install code-delegation-harness
```

After installation:

```bash
gcdh --version
gcdh --help
```

### Specific Version (from GitHub)

If you need a particular released version before it reaches PyPI:

```bash
pip install git+https://github.com/joshuafielden43/code-delegation-harness.git@v0.2.1
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
