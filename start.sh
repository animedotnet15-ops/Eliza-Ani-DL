#!/usr/bin/env bash
set -e

pip install -r requirements.txt --no-cache-dir --quiet
mkdir -p sessions downloads

python3 bot.py
