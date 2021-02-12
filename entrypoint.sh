#!/usr/bin/env bash

# it needs to be explicity ONE worker
gunicorn --worker-class gevent --workers 1 --bind ${CT_HOSTNAME}:${CT_PORT} "mct:gunicorn()" --max-requests 10000 --timeout 30 --keep-alive 5 --log-level info --log-file -