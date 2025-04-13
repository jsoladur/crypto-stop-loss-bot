#!/bin/bash

set -e

# activate our virtual environment here
source /app/.venv/bin/activate

# You can put other setup logic here

# Evaluating passed command:
exec "$@"