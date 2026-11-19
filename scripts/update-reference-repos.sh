#!/usr/bin/env bash
# Keep the read-only reference clones in sync while features are being merged.
# Safe to run repeatedly: clones what is missing, fast-forwards what exists.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/reference"
mkdir -p "$DEST"

repos=(
  "https://github.com/mstanton/m365_sheppard.git|m365_sheppard"
  "https://github.com/sameerk27/vigil365.git|vigil365"
  "https://github.com/microsoft/zerotrustassessment.git|zerotrustassessment"
)

for entry in "${repos[@]}"; do
  url="${entry%%|*}"
  name="${entry##*|}"
  target="$DEST/$name"
  if [ -d "$target/.git" ]; then
    echo "Updating $name"
    git -C "$target" fetch --depth 1 origin
    git -C "$target" reset --hard origin/HEAD
  else
    echo "Cloning $name"
    git clone --depth 1 "$url" "$target"
  fi
done

echo "Reference repositories ready in $DEST"
