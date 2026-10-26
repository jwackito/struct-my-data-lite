#!/usr/bin/env bash
# Install this repository's git hooks and point git at them.
#
# `git config core.hooksPath .githooks` is enough when the checkout lives on a
# normal filesystem. On a `noexec` mount git silently ignores the hooks, so this
# script copies them to an executable location instead.
#
# Usage: bash scripts/install_hooks.sh
set -eu

cd "$(dirname "$0")/.."

dest="${XDG_DATA_HOME:-$HOME/.local/share}/smd-git-hooks"
mkdir -p "$dest"
cp .githooks/* "$dest"/
chmod +x "$dest"/*

git config core.hooksPath "$dest"
echo "Git hooks installed in $dest (core.hooksPath updated)."
