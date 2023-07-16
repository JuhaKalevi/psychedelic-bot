#!/bin/bash -eu
docker compose logs -t -n 100 -f "$SSH_ORIGINAL_COMMAND"
