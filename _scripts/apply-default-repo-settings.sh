#!/usr/bin/env bash
#
# Apply Default Repository Settings
# ==================================
# This script ensures all repositories in the organization have the
# standard default settings applied.
#
# Usage:
#   ./apply-default-repo-settings.sh [--dry-run] [--verbose]
#
# Options:
#   --dry-run    Show what would be changed without making changes
#   --verbose    Show detailed output for each operation
#
# Settings Applied:
#   1. Auto-delete branches after PR merge
#   2. Branch protection on public repos (required reviews, admin bypass)
#   3. Team access (collab team with maintain permission)
#
# Author: rediacc organization
# Last Updated: 2025-10-06

set -euo pipefail

#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------

ORG="rediacc"
TEAM_SLUG="collab"

# Exclude list: repos that should NOT have default settings applied
# Add repos here if they need special configuration
EXCLUDE_LIST=(
  "cryptolens-cpp"    # Archived
  "qedis"             # Archived
  "serenity"          # Archived
  "spa"               # Archived
  "tests"             # Archived
  # Add more repos to exclude as needed
)

# Branch protection settings for public repos
BRANCH_PROTECTION_CONFIG='{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}'

#------------------------------------------------------------------------------
# Parse Arguments
#------------------------------------------------------------------------------

DRY_RUN=false
VERBOSE=false

for arg in "$@"; do
  case $arg in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

if [ "$DRY_RUN" = true ]; then
  echo "🔍 DRY RUN MODE - No changes will be made"
  echo ""
fi

#------------------------------------------------------------------------------
# Helper Functions
#------------------------------------------------------------------------------

log_verbose() {
  if [ "$VERBOSE" = true ]; then
    echo "  $1"
  fi
}

is_excluded() {
  local repo=$1
  for excluded in "${EXCLUDE_LIST[@]}"; do
    if [ "$repo" = "$excluded" ]; then
      return 0
    fi
  done
  return 1
}

#------------------------------------------------------------------------------
# Get All Repositories
#------------------------------------------------------------------------------

echo "========================================================================"
echo "Rediacc Organization - Apply Default Repository Settings"
echo "========================================================================"
echo ""
echo "📋 Fetching repository list..."

REPOS=$(gh api orgs/$ORG/repos --paginate --jq '.[] | select(.archived == false) | .name' | sort)
REPO_COUNT=$(echo "$REPOS" | wc -l)

echo "Found $REPO_COUNT active repositories"
echo ""

#------------------------------------------------------------------------------
# Statistics Counters
#------------------------------------------------------------------------------

SETTING_1_ALREADY=0
SETTING_1_APPLIED=0
SETTING_1_FAILED=0

SETTING_2_ALREADY=0
SETTING_2_APPLIED=0
SETTING_2_SKIPPED=0
SETTING_2_FAILED=0

SETTING_3_ALREADY=0
SETTING_3_APPLIED=0
SETTING_3_FAILED=0

EXCLUDED_COUNT=0

#------------------------------------------------------------------------------
# Setting 1: Auto-Delete Branches After Merge
#------------------------------------------------------------------------------

echo "========================================================================"
echo "Setting 1: Auto-Delete Branches After Merge"
echo "========================================================================"
echo ""

for repo in $REPOS; do
  # Check if excluded
  if is_excluded "$repo"; then
    log_verbose "⊘ $repo (excluded)"
    ((EXCLUDED_COUNT++))
    continue
  fi

  # Check current setting
  current=$(gh api repos/$ORG/$repo --jq '.delete_branch_on_merge')

  if [ "$current" = "true" ]; then
    log_verbose "✓ $repo (already enabled)"
    ((SETTING_1_ALREADY++))
  else
    if [ "$DRY_RUN" = true ]; then
      echo "Would enable: $repo"
    else
      if gh api -X PATCH repos/$ORG/$repo -f delete_branch_on_merge=true &>/dev/null; then
        echo "✓ Enabled: $repo"
        ((SETTING_1_APPLIED++))
      else
        echo "✗ Failed: $repo"
        ((SETTING_1_FAILED++))
      fi
    fi
  fi
done

echo ""
echo "Summary:"
echo "  Already enabled:  $SETTING_1_ALREADY"
echo "  Newly enabled:    $SETTING_1_APPLIED"
echo "  Failed:           $SETTING_1_FAILED"
echo ""

#------------------------------------------------------------------------------
# Setting 2: Branch Protection on Public Repos
#------------------------------------------------------------------------------

echo "========================================================================"
echo "Setting 2: Branch Protection on Public Repos"
echo "========================================================================"
echo ""

for repo in $REPOS; do
  # Check if excluded
  if is_excluded "$repo"; then
    log_verbose "⊘ $repo (excluded)"
    continue
  fi

  # Check if public
  visibility=$(gh api repos/$ORG/$repo --jq '.visibility')
  if [ "$visibility" != "public" ]; then
    log_verbose "⊘ $repo (private, skipped)"
    ((SETTING_2_SKIPPED++))
    continue
  fi

  # Get default branch
  default_branch=$(gh api repos/$ORG/$repo --jq '.default_branch')

  # Check if already protected
  if gh api repos/$ORG/$repo/branches/$default_branch/protection &>/dev/null; then
    # Check if enforce_admins is false
    enforce_admins=$(gh api repos/$ORG/$repo/branches/$default_branch/protection --jq '.enforce_admins.enabled // false')
    if [ "$enforce_admins" = "false" ]; then
      log_verbose "✓ $repo ($default_branch already protected)"
      ((SETTING_2_ALREADY++))
    else
      # Need to update to set enforce_admins: false
      if [ "$DRY_RUN" = true ]; then
        echo "Would update: $repo ($default_branch)"
      else
        if echo "$BRANCH_PROTECTION_CONFIG" | gh api -X PUT repos/$ORG/$repo/branches/$default_branch/protection --input - &>/dev/null; then
          echo "✓ Updated: $repo ($default_branch)"
          ((SETTING_2_APPLIED++))
        else
          echo "✗ Failed: $repo ($default_branch)"
          ((SETTING_2_FAILED++))
        fi
      fi
    fi
  else
    # Apply protection
    if [ "$DRY_RUN" = true ]; then
      echo "Would protect: $repo ($default_branch)"
    else
      if echo "$BRANCH_PROTECTION_CONFIG" | gh api -X PUT repos/$ORG/$repo/branches/$default_branch/protection --input - &>/dev/null; then
        echo "✓ Protected: $repo ($default_branch)"
        ((SETTING_2_APPLIED++))
      else
        echo "✗ Failed: $repo ($default_branch)"
        ((SETTING_2_FAILED++))
      fi
    fi
  fi
done

echo ""
echo "Summary:"
echo "  Already protected: $SETTING_2_ALREADY"
echo "  Newly protected:   $SETTING_2_APPLIED"
echo "  Skipped (private): $SETTING_2_SKIPPED"
echo "  Failed:            $SETTING_2_FAILED"
echo ""

#------------------------------------------------------------------------------
# Setting 3: Team Access (collab team with maintain permission)
#------------------------------------------------------------------------------

echo "========================================================================"
echo "Setting 3: Team Access ($TEAM_SLUG team)"
echo "========================================================================"
echo ""

# Get current repos with team access
TEAM_REPOS=$(gh api orgs/$ORG/teams/$TEAM_SLUG/repos --paginate --jq '.[].name' | sort)

for repo in $REPOS; do
  # Check if excluded
  if is_excluded "$repo"; then
    log_verbose "⊘ $repo (excluded)"
    continue
  fi

  # Check if team already has access
  if echo "$TEAM_REPOS" | grep -q "^${repo}$"; then
    log_verbose "✓ $repo (team already has access)"
    ((SETTING_3_ALREADY++))
  else
    # Grant team access
    if [ "$DRY_RUN" = true ]; then
      echo "Would grant access: $repo"
    else
      if gh api -X PUT orgs/$ORG/teams/$TEAM_SLUG/repos/$ORG/$repo -f permission=maintain &>/dev/null; then
        echo "✓ Granted access: $repo"
        ((SETTING_3_APPLIED++))
      else
        echo "✗ Failed: $repo"
        ((SETTING_3_FAILED++))
      fi
    fi
  fi
done

echo ""
echo "Summary:"
echo "  Already has access: $SETTING_3_ALREADY"
echo "  Newly granted:      $SETTING_3_APPLIED"
echo "  Failed:             $SETTING_3_FAILED"
echo ""

#------------------------------------------------------------------------------
# Final Summary
#------------------------------------------------------------------------------

echo "========================================================================"
echo "FINAL SUMMARY"
echo "========================================================================"
echo ""
echo "Total repositories processed: $REPO_COUNT"
echo "Excluded repositories:        $EXCLUDED_COUNT"
echo ""
echo "Setting 1 (Auto-delete branches):"
echo "  Already configured: $SETTING_1_ALREADY"
echo "  Newly applied:      $SETTING_1_APPLIED"
echo "  Failed:             $SETTING_1_FAILED"
echo ""
echo "Setting 2 (Branch protection on public repos):"
echo "  Already configured: $SETTING_2_ALREADY"
echo "  Newly applied:      $SETTING_2_APPLIED"
echo "  Skipped (private):  $SETTING_2_SKIPPED"
echo "  Failed:             $SETTING_2_FAILED"
echo ""
echo "Setting 3 (Team access):"
echo "  Already configured: $SETTING_3_ALREADY"
echo "  Newly applied:      $SETTING_3_APPLIED"
echo "  Failed:             $SETTING_3_FAILED"
echo ""

TOTAL_FAILURES=$((SETTING_1_FAILED + SETTING_2_FAILED + SETTING_3_FAILED))
TOTAL_CHANGES=$((SETTING_1_APPLIED + SETTING_2_APPLIED + SETTING_3_APPLIED))

if [ "$DRY_RUN" = true ]; then
  echo "🔍 DRY RUN complete - no changes were made"
elif [ $TOTAL_FAILURES -gt 0 ]; then
  echo "⚠️  Completed with $TOTAL_FAILURES failure(s)"
  exit 1
elif [ $TOTAL_CHANGES -eq 0 ]; then
  echo "✅ All repositories already have default settings"
else
  echo "✅ Successfully applied $TOTAL_CHANGES change(s)"
fi

echo "========================================================================"
