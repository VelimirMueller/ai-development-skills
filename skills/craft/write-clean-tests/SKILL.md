---
name: write-clean-tests
description: Use when writing or reviewing tests — F.I.R.S.T. properties, one concept per test, state coverage not line coverage, and a regression test for every bug fix.
---

# Write Clean Tests

Tests are first-class code: they must be as readable as production and must fail for the right reason.
Production testing boundary is set by [engineering-principles.md](../../core/_shared/engineering-principles.md).

## F.I.R.S.T.

- **Fast** — a slow suite stops being run. Keep unit tests in memory; push the slow ones out of the unit layer.
- **Independent** — one test must not depend on another's order or state; run them in any order.
- **Repeatable** — same result in any environment; no flakiness from time, network or shared state.
- **Self-validating** — a boolean pass/fail, never a human reading the output.
- **Timely** — written just before or with the production code, not weeks later.

## 1. Audit (change nothing)

```bash
cat .claude/stack-profile.md 2>/dev/null | head -20
find . \( -name "*_test.*" -o -name "*_spec.*" -o -name "*.test.*" -o -name "*.spec.*" -o -name "*Test.*" -o -name "*Tests.*" -o -name "test_*.*" -o -path "*__tests__*" \) 2>/dev/null | head -20
```

Read the tests for three failures: tests that mirror the implementation (they break on every refactor and
catch nothing), tests with several unrelated asserts (one failure hides another), and tests that assert
internals instead of behaviour.

## 2. One concept per test

- One assert per behaviour, one concept per test. A test named "it works" asserts nothing; name it
  "returns zero when the list is empty".
- Test the public behaviour, not the private shape. A test coupled to internals fails when the code
  improves.
- Use the arrange/act/assert shape; keep the arrange minimal so the reader sees the one thing under test.

## 3. State coverage over line coverage

- Cover the *states and transitions that pay* (the boundary conditions, the error paths, the money path),
  not a percentage. A line covered is not a bug caught.
- Saboteur-test the tests: break the production code and confirm a test fails — a test that cannot fail
  tests nothing.

## 4. A regression test for every fix

- A bug is a missing test. Write the test that fails on the old code, then the fix — the test is the proof
  the bug cannot return.
- Use real data (and a synthetic edge case) over an exhaustive mock of reality.

## Verify

`pnpm test` (or the profile's runner) is green, each test states one behaviour, and breaking the code
under test fails exactly one test with a message that names the cause. State the new coverage in the note.

## When to deviate

- A prototype with a one-week life: a couple of smoke tests, not a full suite.
- A bug cheap to fix and loud (an internal dashboard): a thin regression test is enough.
