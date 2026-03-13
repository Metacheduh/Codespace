# Permission Mode Plan

## Overview

This document defines the permission modes and approval requirements for different types of operations in the Agent Manager project. It ensures that risky, destructive, or irreversible operations are handled safely and transparently.

---

## Permission Modes

### Mode 1: Automatic (Low-Risk Operations)

Operations that are **local, reversible, and safe** can be executed automatically without user approval:

- **File Operations**
  - Reading files with `Read`
  - Editing existing files with `Edit` for bug fixes or requested changes
  - Writing new files (when necessary and not creating bloat)
  - Searching files with `Glob` and `Grep`

- **Local Git Operations**
  - Running `git status`, `git log`, `git diff`
  - Creating local branches
  - Staging files with `git add`
  - Viewing git history
  - Local commits (with clear, descriptive messages)

- **Local Development**
  - Running tests
  - Building/compiling code
  - Running development servers
  - Exploring codebase structure

---

### Mode 2: Confirmation Required (Medium-Risk Operations)

Operations that are **harder to reverse, affect shared state, or have visible consequences** require explicit user confirmation:

- **Destructive Git Operations**
  - Force push (`git push --force`)
  - Resetting commits (`git reset --hard`)
  - Amending published commits
  - Deleting branches that have been pushed
  - Rebasing published history

- **Shared System Operations**
  - Pushing to remote repositories (`git push`)
  - Creating/closing GitHub issues
  - Creating/merging pull requests
  - Commenting on PRs or issues
  - Deploying to production/staging environments
  - Modifying CI/CD pipelines
  - Sending messages or notifications

- **Database/Data Operations**
  - Deleting database records
  - Dropping tables
  - Modifying data fixtures
  - Running migrations on shared databases

- **Irreversible File Operations**
  - Deleting files
  - Removing directories
  - Permanently removing code sections
  - Overwriting uncommitted changes

- **Package/Dependency Changes**
  - Installing/removing packages
  - Upgrading/downgrading dependencies
  - Modifying dependency versions that may break compatibility

---

### Mode 3: Investigation + Approval (High-Risk Operations)

Operations that are **destructive, irreversible, or could cause significant issues** require investigation, clear communication, and explicit approval:

- **Nuclear Options**
  - `git reset --hard HEAD` or similar
  - `rm -rf` operations
  - Force-pushing to main/master branches
  - Dropping production databases
  - Killing critical processes

- **Supply Chain / Security-Critical Operations**
  - Publishing packages to registries
  - Modifying authentication/authorization
  - Changing security configurations
  - Adding backdoors or malicious code (ALWAYS refuse)

- **Authorization Bypass**
  - Using `--no-verify` to skip hooks
  - Using `-c commit.gpgsign=false` to bypass signing
  - Any attempt to circumvent safety checks

---

## Decision Tree

```
User requests action
    |
    ├─ Is it destructive? (delete, rm, reset --hard)
    │   └─ YES → Require confirmation + investigation
    │   └─ NO → Continue
    |
    ├─ Does it affect shared state? (push, PR, issue, deploy)
    │   └─ YES → Require confirmation
    │   └─ NO → Continue
    |
    ├─ Is it hard to reverse? (force push, amend published, drop table)
    │   └─ YES → Require confirmation
    │   └─ NO → Continue
    |
    └─ Is it safe and reversible? (edit file, read file, local commit)
        └─ YES → Proceed automatically
        └─ NO → Ask for clarification
```

---

## Agent Manager Specific Operations

### Safe (Automatic Approval)

- Reading configuration files (`config.yaml`)
- Examining database schema
- Running the manager locally: `python3 main.py`
- Checking job statuses and logs
- Editing job definitions or alert rules
- Creating feature branches for development

### Requires Confirmation

- Pushing to remote branches
- Creating pull requests with job definition changes
- Modifying alert thresholds that affect production behavior
- Updating notification channels (email, webhooks)
- Changing database connection strings or paths

### Requires Investigation + Approval

- Force-pushing changes to main
- Deleting job runs or alert records from database
- Resetting the database entirely
- Modifying the launchd plist for deployment
- Any changes to security-sensitive configurations

---

## Workflow Examples

### Example 1: Fix a Bug in main.py

**User Request:** "Fix the timeout calculation in main.py"

**Workflow:**
1. Read the file ✓ (automatic)
2. Identify the bug ✓ (automatic)
3. Edit the file ✓ (automatic)
4. Run tests ✓ (automatic)
5. Create a local commit ✓ (automatic - includes descriptive message)
6. Push to feature branch → **CONFIRM** (affects shared state)

---

### Example 2: Update Alert Thresholds in config.yaml

**User Request:** "Increase the DPI threshold from 0.4 to 0.5"

**Workflow:**
1. Read config.yaml ✓ (automatic)
2. Edit the threshold value ✓ (automatic)
3. Local commit ✓ (automatic)
4. Push to feature branch → **CONFIRM** (changes behavior)

---

### Example 3: Reset the Database

**User Request:** "Clear all job run history"

**Workflow:**
1. Investigate: What data will be lost? Why is this needed?
2. Confirm with user: "This will delete all job run records. Proceed?" ✓
3. Back up the database (if needed)
4. Execute the operation
5. Verify the outcome

---

### Example 4: Deploy to Production

**User Request:** "Deploy the latest changes to the launchd agent"

**Workflow:**
1. Verify changes are committed ✓ (automatic)
2. Verify branch is up to date ✓ (automatic)
3. Show what will change (side-by-side diff) → **CONFIRM**
4. Execute deployment steps → **CONFIRM** at each step
5. Monitor the rollout (if supported)

---

## Communication Guidelines

### For Automatic Operations
- Brief acknowledgment of action taken
- Example: "Edited main.py to fix the timeout calculation."

### For Confirmation-Required Operations
- **Clear action description:** What will happen?
- **Reversibility note:** Can it be undone?
- **Scope:** What else might be affected?
- **Example:**
  ```
  About to push to origin/claude/fix-timeout (feature branch).

  Changes:
  - Fixed timeout calculation in main.py (1 commit)

  This change is not reversible once pushed. Proceed? [Yes/No]
  ```

### For High-Risk Operations
- **Detailed investigation:** Why is this needed?
- **Impact analysis:** What will be lost/changed?
- **Alternatives:** Is there a safer way?
- **Explicit confirmation:** Require exact confirmation (not just "yes")
- **Example:**
  ```
  ⚠️  HIGH-RISK OPERATION

  Action: Delete all job run history from database
  Impact: Permanent loss of 1,247 run records

  Alternative: Archive the database instead of deleting

  Type "DELETE ALL RECORDS" to confirm, or suggest an alternative: ______
  ```

---

## Retries and Error Handling

### Network Errors
- Automatic retry with exponential backoff (2s, 4s, 8s, 16s)
- Max 4 attempts
- Transparent logging of each retry

### Hook Failures
- Do not skip hooks automatically (never use `--no-verify`)
- Investigate the underlying issue
- Fix the issue and create a new commit
- Only skip hooks with explicit user request

### Pre-commit Failures
- Do not amend previous commits
- Fix the issue and create a new commit
- Keep full commit history transparent

---

## Security Considerations

### What Claude Code Will ALWAYS Refuse
- Adding malware or backdoors
- Exfiltrating secrets or credentials
- Supply chain compromise attempts
- Bypassing authentication without authorization
- Destructive attacks (DoS, data destruction)

### What Requires Authorization Context
- Offensive security tools (C2 frameworks, exploit development)
- Credential testing tools
- Requires: Clear pentesting engagement, CTF context, or security research authorization

### Secret Management
- Never commit secrets (API keys, passwords, tokens)
- Warn if user attempts to commit `.env` or credential files
- Use `.gitignore` to prevent accidental commits
- Suggest environment variables or secret management systems

---

## Branch Policies

### Feature Branches (claude/*)
- Automatic commits to feature branches
- Confirmation required before push to ensure branch name follows convention
- Confirmation required before merge to main

### Main Branch
- Never push directly to main without explicit approval
- Require pull requests with review
- Confirm before merging PRs
- Force push to main requires special authorization

### Session-Specific Branches
- Branch names must start with `claude/` and end with session ID (e.g., `claude/fix-bug-abc123`)
- Push failures with 403 HTTP code indicate branch naming issue
- Automatically retry network failures with backoff, not naming issues

---

## Summary

| Category | Approval | Example |
|----------|----------|---------|
| **Local Safe** | ✓ Auto | Read file, edit file, local commit |
| **Confirmation** | ⚠️ Ask | Push, PR, modify config |
| **High-Risk** | 🛑 Investigate | Force push, delete data, reset DB |
| **Never** | 🚫 Refuse | Add malware, exfiltrate secrets, bypass auth |

---

## Next Steps

This permission mode plan should be:
1. Reviewed by the team
2. Integrated into the Claude Code configuration
3. Tested with real workflows
4. Updated as edge cases are discovered

---

**Document Created:** 2026-03-13
**Branch:** claude/create-permission-mode-plan-7xJ1X
**Project:** Agent Manager
