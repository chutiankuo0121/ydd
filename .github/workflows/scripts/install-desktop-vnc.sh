#!/usr/bin/env bash
set -e
export DEBIAN_FRONTEND=noninteractive
# Skipped: Linux desktop/VNC setup not required for Windows-only builds.
echo "[skip] install-desktop-vnc.sh: Windows-only build; skipping Linux desktop/VNC installation."
exit 0
