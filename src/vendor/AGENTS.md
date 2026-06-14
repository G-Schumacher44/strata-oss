# Vendor — Frozen Dependencies

**Full governance:** `GOVERNANCE.md`

---

## What is here

Reserved space for future frozen dependencies. Phase 1 does not vendor `lkml`.
`lkml` is prior art to mine from a temporary clone only; it is not copied here and is
not a runtime dependency.

## Hard constraints

- **Do not add `lkml` here.** Phase 1 uses an in-house parser. If `lkml` is inspected,
  clone it only to a temporary path outside this repo, copy no source files, and delete
  the clone before implementation continues.
- **Do not modify vendored source** for feature reasons or to work around bugs in
  your own code.
- **Cherry-pick only.** If a future frozen dependency fix is needed, cherry-pick the
  specific commit. Reference the upstream PR/commit SHA in the commit message.
- **Never add new packages here.** Adding a vendored dependency requires a Conductor
  slice spec and explicit operator approval — it is an architecture decision, not a
  convenience.
- **Document pins.** Any future vendored package must include a `VENDOR_PIN.md` with
  the upstream repo URL, pinned commit SHA, pin date, and reason for any local patches.

## How to mine lkml as prior art

The goal is to read implementation ideas only. No source files enter Strata.

```bash
# 1. Clone to a temp path OUTSIDE the strata repo, only if parser reference is needed
git clone https://github.com/joshtemple/lkml /tmp/lkml-vendor-tmp

# 2. Record the commit SHA you inspected in the handoff notes if it informed the work
cd /tmp/lkml-vendor-tmp && git rev-parse HEAD

# 3. Delete the clone — it must not remain
rm -rf /tmp/lkml-vendor-tmp
```

**What NOT to do:**
- Do not `git clone` inside the strata repo directory
- Do not `git submodule add`
- Do not leave a `.git/` directory inside `src/vendor/lkml/`
- Do not `pip install lkml` and copy from site-packages
- Do not copy `lkml` source into `src/vendor/`

## VENDOR_PIN.md template

```markdown
# <package> Vendor Pin

Upstream: <repo URL>
Pinned commit: <SHA from step 2>
Pin date: <YYYY-MM-DD>
License: <license>

## Local patches
None.

## Notes
<any compatibility issues encountered, upstream issue links>
```

## Current contents

| Package | Upstream | Pin |
|---|---|---|
| none | n/a | n/a |

## If you need to add or patch a vendored dependency

1. Write or update a Conductor slice spec first
2. Make the minimal change in the vendored source
3. Add a regression test in `tests/` that would fail without the patch
4. Commit with message: `fix(vendor): <description> [upstream: <issue-or-pr-url>]`
