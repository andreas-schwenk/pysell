#!/bin/bash

# DEPENDENCIES
#   pip install hatchling twine

# update pySELL itself
python3 build-pysell.py

# update the python package
rm dist/*.whl
rm dist/*.tar.gz
python3 -m build
echo "upload to pypi.org via: twine upload dist/*"
