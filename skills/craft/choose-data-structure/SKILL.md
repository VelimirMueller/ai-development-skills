---
name: choose-data-structure
description: Use when a collection's access pattern is wrong — linear scan, missing index, re-sort, set-versus-list — and you must pick the structure with the right complexity.
---

# Choose Data Structure

Picks the collection whose access pattern matches how the code actually uses it (CLRS). Pairs with
[analyze-complexity](../analyze-complexity/SKILL.md) — this is the structure half of the same decision.

## The table

| Access pattern | Structure | Cost |
|---|---|---|
| Indexed access by position | Array / slice / vector | `O(1)` |
| Keyed lookup, no order needed | Hash table / map / dict | `O(1)` average |
| Ordered or range queries, min/max | Balanced BST / sorted tree | `O(log n)` |
| Peek min or max, push and pop | Heap / priority queue | `O(1)` peek, `O(log n)` push/pop |
| Insert/delete at a known position | Linked list | `O(1)` after the node, `O(n)` to find it |
| Membership with ordering | Sorted array + binary search | `O(log n)` search, `O(n)` insert |
| Set of unique keys | Set | `O(1)` membership |

## 1. Audit (change nothing)

```bash
cat .claude/stack-profile.md 2>/dev/null | head -20
grep -rn "\.find(\|\.includes(\|\.indexOf(\|\.sort(\|\.filter(" --include="*.ts" --include="*.rs" --include="*.go" --include="*.py" . 2>/dev/null | head -30
```

Name the actual access: is the code searching for one element repeatedly (→ map/set, not array), does it
need the smallest repeatedly (→ heap), does it re-sort the same list (→ keep it sorted), does it test
membership on a list (→ set)? Each mismatch is a change, not a rewrite.

## 2. Match structure to use

- Repeated `find`/`includes` on an array → build a map or set once, look up in `O(1)`.
- Repeated min/max over an unsorted list → a heap.
- "Does this value exist?" on a list → a set.
- Ordered iteration over a changing sorted list → a balanced tree or a sorted structure that stays sorted.
- A fixed-size lookup table keyed by a small enum → a plain array indexed by the enum.

## 3. State the trade-off

A hash map buys `O(1)` lookup and gives up order; a tree buys order and gives up the constant factor; an
array buys cache locality and gives up keyed lookup. Name which property the code needs and which it
gives up, and keep the simpler structure when both work.

## Verify

The repeated linear scan is gone (one `O(1)` lookup replaces it), the re-sort is gone (the structure stays
sorted), and the chosen structure's complexity matches the named access pattern. State the before/after in
the note.

## When to deviate

- Bounded collections (a handful of items): the constant factor of a map may cost more than a linear scan.
- The structure is the framework's own (a query cache, a store) — use it, do not hand-build a replacement.
