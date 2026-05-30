# Installation

## Recommended Installation

The recommended way to install the Code Delegation Harness is from PyPI (once published) or from a tagged GitHub release:

```bash
pip install code-delegation-harness
```

After installation, the `gcdh` command will be available:

```bash
gcdh --version
gcdh --help
```

## For Bleeding Edge / Development Use

If you need the absolute latest code (for example, to test a new feature or contribute), you can install directly from the repository:

```bash
pip install git+https://github.com/joshuafielden43/code-delegation-harness.git
```

> **Note**: Git-based installs pull the full repository history and are not ideal for production agent environments or version-pinned setups. Use this method only when you specifically need the latest development version.

## Development Installation

If you want to work on the harness itself:

```bash
git clone https://github.com/joshuafielden43/code-delegation-harness.git
cd code-delegation-harness
pip install -e .
```

This installs the package in editable mode so changes to the source are reflected immediately.

## Verifying the Installation

After installing, run:

```bash
gcdh --version
gcdh --help
```

You should see the command available and ready to use.
