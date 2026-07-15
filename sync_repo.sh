#!/usr/bin/env bash
set -euo pipefail

# AVE Forensics Laboratory repository sync helper.
#
# Usage:
#   ./sync_repo.sh
#   ./sync_repo.sh "Describe the update"
#
# Optional environment variable:
#   AVE_REMOTE=origin ./sync_repo.sh "Commit message"

REMOTE="${AVE_REMOTE:-origin}"
COMMIT_MESSAGE="${1:-AVE sync: $(date '+%Y-%m-%d %H:%M:%S')}"

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail "git is not installed."
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || fail "Run this script from inside the AVE Git repository."

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

BRANCH="$(git branch --show-current)"
[[ -n "$BRANCH" ]] || fail "Detached HEAD detected. Check out a branch before syncing."

git remote get-url "$REMOTE" >/dev/null 2>&1 \
  || fail "Remote '$REMOTE' is not configured."

printf 'Repository: %s\n' "$REPO_ROOT"
printf 'Branch:     %s\n' "$BRANCH"
printf 'Remote:     %s\n' "$REMOTE"

# Refresh remote state first. Pull only when the upstream branch already exists.
git fetch "$REMOTE"

if git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
  printf 'Rebasing local work onto %s/%s...\n' "$REMOTE" "$BRANCH"
  git pull --rebase --autostash "$REMOTE" "$BRANCH"
else
  printf 'Remote branch %s/%s does not exist yet; it will be created on push.\n' \
    "$REMOTE" "$BRANCH"
fi

git add --all

if git diff --cached --quiet; then
  printf 'No local changes to commit.\n'
else
  git commit -m "$COMMIT_MESSAGE"
fi

printf 'Pushing %s to %s...\n' "$BRANCH" "$REMOTE"
git push --set-upstream "$REMOTE" "$BRANCH"

printf 'AVE repository sync complete.\n'
