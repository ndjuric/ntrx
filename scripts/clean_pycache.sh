#!/bin/bash
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type d -name ".pytest_cache" -exec rm -rf {} +
find . -type d -name ".mypy_cache" -exec rm -rf {} +
find . -type f -name "*.pyc" -exec rm -f {} +
find . -type f -name "*.pyo" -exec rm -f {} +
find . -type d -name "*.egg-info" -exec rm -rf {} +

echo "Clean complete."
