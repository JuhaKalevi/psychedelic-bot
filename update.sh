#!/bin/bash -eu
git fetch --all
git checkout $SSH_ORIGINAL_COMMAND
git pull
docker compose build
docker compose up -d $SSH_ORIGINAL_COMMAND
