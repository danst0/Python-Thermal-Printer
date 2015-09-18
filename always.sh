#!/bin/bash
cd /home/danst/thpr/
until /home/danst/thpr/thpr.py; do
    echo "'thpr.py' exited with exit code $?. Restarting..." >&2
    sleep 1
done
