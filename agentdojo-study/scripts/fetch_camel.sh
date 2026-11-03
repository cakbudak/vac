#!/usr/bin/env bash
# Fetch the unmodified upstream CaMeL research code at the pinned commit.
# The repository is NOT vendored in the submission archive (license: Apache-2.0,
# google-research/camel-prompt-injection); this script reproduces the exact tree.
set -euo pipefail
cd "$(dirname "$0")/.."
COMMIT="f083b6b"
if [ ! -d external/camel-prompt-injection/.git ]; then
  mkdir -p external
  git clone --quiet https://github.com/google-research/camel-prompt-injection external/camel-prompt-injection
fi
git -C external/camel-prompt-injection checkout --quiet "$COMMIT"
echo "CaMeL at commit $(git -C external/camel-prompt-injection rev-parse --short HEAD)"
