# Rediacc Organization Scripts

This directory contains maintenance scripts for managing the Rediacc GitHub organization.

## Scripts

### `apply-default-repo-settings.sh`

Ensures all repositories have the organization's default settings applied.

#### What It Does

1. **Auto-Delete Branches After Merge**
   - Enables `delete_branch_on_merge` on all repositories
   - Branches are automatically deleted when PRs are merged
   - Keeps repositories clean without manual cleanup

2. **Branch Protection on Public Repos**
   - Applies protection to default branch (main/master)
   - Requires 1 approval for pull requests
   - Dismisses stale reviews automatically
   - Admin bypass enabled (`enforce_admins: false`)
   - Prevents force pushes and branch deletions

3. **Team Access**
   - Grants "collab" team maintain access to all repos
   - Ensures consistent permissions across organization
   - Simplifies user management

#### Usage

```bash
# Apply settings to all repositories
./apply-default-repo-settings.sh

# Dry run - see what would change without making changes
./apply-default-repo-settings.sh --dry-run

# Verbose output - see details for each repo
./apply-default-repo-settings.sh --verbose

# Combine options
./apply-default-repo-settings.sh --dry-run --verbose
```

#### Exclude List

Certain repositories are excluded from default settings:

- **Archived repos**: cryptolens-cpp, qedis, serenity, spa, tests
- **Special cases**: Add to `EXCLUDE_LIST` in the script

To exclude additional repositories, edit the script and add to the `EXCLUDE_LIST` array:

```bash
EXCLUDE_LIST=(
  "cryptolens-cpp"    # Archived
  "qedis"             # Archived
  "special-repo"      # Your reason here
)
```

#### When to Run

Run this script:

- **After creating new repositories** - Ensure they have default settings
- **Periodically** (monthly/quarterly) - Verify all repos maintain standards
- **After team changes** - Ensure team access is up to date
- **When onboarding new developers** - Verify permissions are correct

#### Requirements

- GitHub CLI (`gh`) installed and authenticated
- Organization owner permissions (for team and org-level changes)
- Admin permissions on repositories (for branch protection)

#### Exit Codes

- `0` - Success (all settings applied or already configured)
- `1` - Failure (one or more operations failed)

#### Examples

**First time setup:**
```bash
# Check what would be changed
./apply-default-repo-settings.sh --dry-run --verbose

# Apply changes
./apply-default-repo-settings.sh
```

**Regular maintenance:**
```bash
# Quick check - run monthly
./apply-default-repo-settings.sh
```

**After creating new repo:**
```bash
# Apply settings to all repos (including new one)
./apply-default-repo-settings.sh --verbose
```

## Organization Default Settings Reference

### Repository Settings

| Setting | Value | Applies To | Reason |
|---------|-------|------------|--------|
| Auto-delete branches | Enabled | All active repos | Keeps repos clean |
| Branch protection | Enabled | Public repos only | Code quality, reviews |
| Required reviews | 1 approval | Public repos | Quality control |
| Admin bypass | Enabled | Public repos | Emergency access |
| Team access (collab) | Maintain | All active repos | Consistent permissions |

### Team Structure

**Team: collab**
- **Members**: All 6 organization members
- **Permission**: Maintain on all repositories
- **Purpose**: Centralized access management

**Organization Owner**: mfbayraktar
- Can bypass all restrictions
- Manages org-level settings
- Emergency access

### Branch Protection Details (Public Repos)

```json
{
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "require_last_push_approval": false
  },
  "enforce_admins": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

### Private Repos

⚠️ **Note**: GitHub Free does not support enforced branch protection on private repos.

**Team Policy**: All changes should go through PRs (not enforced)
- See `PRIVATE_REPO_POLICY.md` for guidelines
- Relies on team discipline
- Consider upgrading to GitHub Team ($24/month) for enforcement

## Troubleshooting

### "Not Found" errors
- Ensure you're authenticated: `gh auth status`
- Check you have org owner permissions
- Verify repository names are correct

### "Forbidden" errors
- Some settings require org owner role
- Check your permissions: `gh api orgs/rediacc/members/YOUR_USERNAME`

### Script hangs or is slow
- Normal for many repositories (API rate limits)
- Use `--verbose` to see progress
- GitHub API is rate-limited (5000 requests/hour for authenticated users)

### Changes not applying
- Check exclude list - repo might be excluded
- Verify repo is not archived
- Check error messages in output

## Contributing

When modifying these scripts:

1. Test with `--dry-run` first
2. Document changes in this README
3. Update the script's header comments
4. Commit changes with clear message
5. Notify team of any setting changes

## Support

- **Script issues**: Open issue in this repo
- **GitHub API docs**: https://docs.github.com/rest
- **Organization settings**: https://github.com/orgs/rediacc/settings

---

**Last Updated**: 2025-10-06
**Maintained By**: Organization owners
