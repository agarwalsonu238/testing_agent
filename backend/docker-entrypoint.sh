#!/bin/sh
# Deployed mode: a container has no local checkout of the app under test, so when
# APP_REPO_GIT_URL is set, clone it (or fetch+reset if already cloned from a previous start)
# before handing off to the real command. Read-only: Save as test still needs a writable local
# repo, so that flow isn't available against a container-cloned checkout.
set -eu

if [ -n "${APP_REPO_GIT_URL:-}" ]; then
  repo_path="${APP_REPO_PATH:-/app-repo}"
  ref="${APP_REPO_GIT_REF:-main}"
  url="$APP_REPO_GIT_URL"
  if [ -n "${APP_REPO_GIT_TOKEN:-}" ]; then
    # https:// URLs only; an SSH-style URL (git@github.com:...) needs a deploy key mounted
    # instead, which this script doesn't set up.
    url=$(echo "$url" | sed -E "s#https://#https://x-access-token:${APP_REPO_GIT_TOKEN}@#")
  fi
  if [ -d "$repo_path/.git" ]; then
    echo "Refreshing $repo_path from $ref..."
    git -C "$repo_path" fetch origin "$ref" --quiet
    git -C "$repo_path" checkout "$ref" --quiet
    git -C "$repo_path" reset --hard "origin/$ref" --quiet
  else
    echo "Cloning $ref into $repo_path..."
    git clone --branch "$ref" --single-branch "$url" "$repo_path" --quiet
  fi
  export APP_REPO_PATH="$repo_path"
fi

exec "$@"
