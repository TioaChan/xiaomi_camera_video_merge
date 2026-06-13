#!/bin/sh

set -e

exec python /app/main.py --outdir "$outputdir" "$inputdir" "$@"
