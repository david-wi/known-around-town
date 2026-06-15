# Multi-Agent Workspace — File Edit Contention

This repo is worked on by multiple concurrent Claude agents (e.g., Posey's
subagents running fixes in parallel). Any file edit made through the Edit
tool can be silently reverted when another agent does a `git checkout` or
`git reset --hard` while your change is unstaged.

## Safe pattern for making changes in this repo

Apply all file changes in a single Python script and commit immediately
in the same Bash call:

```python
# 1. Apply all edits with string replacement in Python
# 2. Run tests
# 3. git add <specific files> && git commit immediately
```

Never leave changes unstaged in a shared checkout. Always:
- Branch from a freshly-fetched origin/main
- Apply changes atomically
- Commit before doing anything else (tests, other reads, etc.)
- Stage only your specific files by name (never `git add -A`)
