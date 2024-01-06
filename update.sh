#!/bin/bash -eu
. venv/bin/activate
pip install -r requirements.txt --use-deprecated legacy-resolver
pylint --jobs=$(nproc) src/*.py
systemctl --user restart psychedelic-bot@$SSH_ORIGINAL_COMMAND
