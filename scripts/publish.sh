#!/bin/bash
set -e

echo "Building clean distributions..."
python -m pip install --upgrade build twine
python -m build --wheel --sdist

echo ""
echo "Distributions built in dist/:"
ls -la dist/

echo ""
echo "Ready to upload to PyPI."
echo "Run: twine upload dist/*"
echo ""
echo "Make sure you have a PyPI API token configured (either via ~/.pypirc or TWINE_USERNAME/TWINE_PASSWORD)."
