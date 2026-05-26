#!/bin/sh
# Ensure config.json is a file, not a directory (Docker bind-mount gotcha)
if [ -d /app/config.json ]; then
    rm -rf /app/config.json
fi
if [ ! -f /app/config.json ]; then
    echo '{}' > /app/config.json
fi
exec "$@"
