#!/usr/bin/env bash
# Prevent direct pushes to main/master branches.
# Used as a pre-push hook via pre-commit.
# pre-commit 4.x sets PRE_COMMIT_REMOTE_BRANCH env var.

if [ -n "$PRE_COMMIT_REMOTE_BRANCH" ]; then
    if echo "$PRE_COMMIT_REMOTE_BRANCH" | grep -qE "^(main|master)$"; then
        echo "" >&2
        echo "REJECTED: Direct push to '$PRE_COMMIT_REMOTE_BRANCH' is not allowed." >&2
        echo "Please create a pull request instead." >&2
        echo "" >&2
        exit 1
    fi
fi

exit 0
