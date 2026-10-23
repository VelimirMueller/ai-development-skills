---
name: apply-design-patterns
description: Use when a design smells — a switch over type, inheritance chosen for configuration, scattered coupling — or a review asks whether a GoF pattern fits. Maps the smell to a pattern, picks the simplest fit, and adapts it to the language's idiom.
---

# Apply Design Patterns

Turns a design smell into the smallest GoF pattern that removes it, adapted to the stack's idiom.
Catalogue, what-varies table and the when-to-use guard: [patterns-catalogue.md](../_shared/patterns-catalogue.md).
Principles behind the choice: [engineering-principles.md](../../core/_shared/engineering-principles.md).

## 1. Audit (change nothing)

```bash
cat .claude/stack-profile.md 2>/dev/null | head -40
grep -rn "switch\|if.*type\|instanceof\|typeof" --include="*.ts" --include="*.rs" --include="*.go" --include="*.py" . 2>/dev/null | head -30
```

Name the smell precisely: a conditional over a type discriminator (→ Strategy/State), a class hierarchy
that exists only to vary configuration (→ composition or Bridge), a change that ripples across many files
(→ Facade/Mediator), a new-object family (→ Abstract Factory), a one-to-many notification (→ Observer).
Every smell maps to a *what varies* in [patterns-catalogue.md](../_shared/patterns-catalogue.md).

## 2. Decide

| Signal | Move |
|---|---|
| The variation is a future maybe, one caller today | Stop: no pattern. A plain function or union. |
| A switch over a closed set of kinds | Discriminated union + one function per kind (Strategy/State in idiom). |
| Two axes vary independently | Bridge, only if both axes are real. |
| A third-party or legacy interface must fit | Adapter as one wrapper function. |
| An object has many optional parts | Builder as a fluent/options object. |
| Undo or audit history is required | Command (+ Memento snapshots for undo). |

## 3. Apply the idiom

Translate the classic class diagram into the stack's idiom — the GoF book predates first-class
functions, generators, structural typing and discriminated unions:

- **Strategy** = a function type or `Record<Kind, (x) => y>`, never an interface + class tree.
- **Observer** = state + effects + TanStack Query, or `useSyncExternalStore`; never a subject/observer class.
- **Iterator** = a generator or `[Symbol.iterator]`; never a hand-rolled cursor class.
- **Singleton** = a module-level `const`; a lazy class factory only when init cost is real.
- **Adapter/Facade/Proxy** = a structural interface plus one wrapper function, not a hierarchy.
- **Decorator** = a function/HOC for runtime wrapping; `@` decorators for metadata only.
- **Command** = closures/thunks or `{type, payload}` actions; add `{execute, undo}` only for real undo.

## 4. Name the trade-off

State what the pattern buys and what it costs (one extra indirection, one new file, a perf hop) before
applying. If the cost exceeds the flexibility gained, leave the simpler version and record the decision.

## Verify

The smell is gone: the conditional over the discriminator is a lookup, the change that used to touch N
files touches one, and the new indirection is justified by a second caller or a measured need. A second
pass finds no leftover `instanceof`/`typeof` switch that the pattern was meant to replace.

## When to deviate

- Throwaway or prototype code: skip the pattern entirely.
- A pattern already exists in the codebase: reuse it, do not add a second spelling of the same idea.
- The framework owns the mechanism (routing, state, DI): use the framework's form, not a hand-built one.
