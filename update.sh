#!/bin/bash -eu
echo "Deploying $SSH_ORIGINAL_COMMAND"
git fetch --all
git checkout $SSH_ORIGINAL_COMMAND
git reset --hard origin/$SSH_ORIGINAL_COMMAND
. venv/bin/activate
pip install -r requirements.txt
pylint *.py
docker compose build $SSH_ORIGINAL_COMMAND
docker compose up -d $SSH_ORIGINAL_COMMAND
