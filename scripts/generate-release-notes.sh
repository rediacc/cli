#!/bin/bash
# Generate release notes from git commits between tags
# Usage: ./generate-release-notes.sh [current_tag] [previous_tag]
# Example: ./generate-release-notes.sh v0.1.41 v0.1.40

set -e

CURRENT_TAG="${1:-}"
PREVIOUS_TAG="${2:-}"

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# If no tags provided, try to auto-detect
if [ -z "$CURRENT_TAG" ]; then
    # Get current tag (if on a tag)
    CURRENT_TAG=$(git describe --exact-match --tags HEAD 2>/dev/null || echo "")

    if [ -z "$CURRENT_TAG" ]; then
        echo "Error: Not on a tag and no tag specified" >&2
        echo "Usage: $0 [current_tag] [previous_tag]" >&2
        exit 1
    fi
fi

if [ -z "$PREVIOUS_TAG" ]; then
    # Get previous tag
    PREVIOUS_TAG=$(git tag -l 'v[0-9]*.[0-9]*.[0-9]*' | sort -V | tail -2 | head -1)

    if [ -z "$PREVIOUS_TAG" ]; then
        echo "Warning: No previous tag found, using all commits" >&2
        PREVIOUS_TAG=""
    fi
fi

# Generate release notes
echo "# Release $CURRENT_TAG"
echo ""
echo "## What's Changed"
echo ""

# Get commits between tags
if [ -n "$PREVIOUS_TAG" ]; then
    COMMIT_RANGE="$PREVIOUS_TAG..$CURRENT_TAG"
    echo "_Changes since $PREVIOUS_TAG_"
else
    COMMIT_RANGE="$CURRENT_TAG"
    echo "_Initial release_"
fi

echo ""

# Parse commits and group by type
declare -A COMMITS_BY_TYPE

# Conventional commit types
TYPES=("feat" "fix" "refactor" "perf" "test" "docs" "build" "ci" "chore" "style")

# Read commits
while IFS= read -r line; do
    HASH=$(echo "$line" | awk '{print $1}')
    MESSAGE=$(echo "$line" | cut -d' ' -f2-)

    # Detect commit type
    TYPE="other"
    for commit_type in "${TYPES[@]}"; do
        if [[ "$MESSAGE" =~ ^${commit_type}(\(.*\))?:\ .* ]]; then
            TYPE="$commit_type"
            # Remove type prefix from message
            MESSAGE=$(echo "$MESSAGE" | sed "s/^${commit_type}[^:]*: //")
            break
        fi
    done

    # Store commit
    if [ -z "${COMMITS_BY_TYPE[$TYPE]}" ]; then
        COMMITS_BY_TYPE[$TYPE]="$HASH|$MESSAGE"
    else
        COMMITS_BY_TYPE[$TYPE]="${COMMITS_BY_TYPE[$TYPE]}"$'\n'"$HASH|$MESSAGE"
    fi
done < <(git log --oneline --no-merges "$COMMIT_RANGE" 2>/dev/null)

# Output grouped commits
print_commits() {
    local type="$1"
    local title="$2"

    if [ -n "${COMMITS_BY_TYPE[$type]}" ]; then
        echo "### $title"
        echo ""
        while IFS='|' read -r hash message; do
            echo "- $message ($hash)"
        done <<< "${COMMITS_BY_TYPE[$type]}"
        echo ""
    fi
}

# Print sections in order of importance
print_commits "feat" "✨ New Features"
print_commits "fix" "🐛 Bug Fixes"
print_commits "perf" "⚡ Performance Improvements"
print_commits "refactor" "♻️ Code Refactoring"
print_commits "build" "📦 Build System"
print_commits "ci" "👷 CI/CD"
print_commits "docs" "📚 Documentation"
print_commits "test" "🧪 Tests"
print_commits "style" "💄 Style Changes"
print_commits "chore" "🔧 Chores"
print_commits "other" "🔹 Other Changes"

# Installation instructions
echo "## Installation"
echo ""
echo "\`\`\`bash"
echo "# Install from PyPI"
echo "pip install rediacc==${CURRENT_TAG#v}"
echo ""
echo "# Or upgrade existing installation"
echo "pip install --upgrade rediacc"
echo "\`\`\`"
echo ""

# Full changelog link (if on GitHub)
REMOTE_URL=$(git config --get remote.origin.url 2>/dev/null || echo "")
if [[ "$REMOTE_URL" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
    REPO_PATH="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
    REPO_PATH="${REPO_PATH%.git}"

    if [ -n "$PREVIOUS_TAG" ]; then
        echo "**Full Changelog**: https://github.com/$REPO_PATH/compare/$PREVIOUS_TAG...$CURRENT_TAG"
    else
        echo "**Full Changelog**: https://github.com/$REPO_PATH/commits/$CURRENT_TAG"
    fi
fi
