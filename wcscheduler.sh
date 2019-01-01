#!/bin/sh
# Run in terminal window (instead of under systemd) and output
# timestamps on log messages.
PROG=$(basename $0)
PROG=${PROG%.sh}
exec ./$PROG "$@" 2>&1 | ts
