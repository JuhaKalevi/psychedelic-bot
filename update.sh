#!/bin/bash -eu
echo "Deploying $SSH_ORIGINAL_COMMAND"
git fetch --all
git checkout $SSH_ORIGINAL_COMMAND
git pull
. venv/bin/activate
pylint *.py
docker compose build $SSH_ORIGINAL_COMMAND
docker compose up -d $SSH_ORIGINAL_COMMAND
