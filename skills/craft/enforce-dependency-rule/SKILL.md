---
name: enforce-dependency-rule
description: Use when laying out a service's layers or untangling cross-layer imports — dependencies point inward, hexagonal boundaries, and component cohesion and coupling hold.
---

# Enforce Dependency Rule

Lays out the concentric layers of a service (Clean Architecture) and keeps source dependencies pointing
inward, so the high-level policy never depends on a detail. Class-level rules are in
[apply-solid](../apply-solid/SKILL.md); the canonical service layout is
[service-layout.md](../../backend/_shared/service-layout.md).

## The rule

**Source dependencies point only inward, toward higher-level policy.** An inner layer never names an
outer-layer entity or data format. Four layers, inward to outward:

1. **Entities** — enterprise-wide business rules and data (plain, dependency-free).
2. **Use cases** — application-specific rules; orchestrate entities, contain the story of one feature.
3. **Interface adapters** — presenters, controllers, gateways, SQL mappers; translate between the
   use case's plain data and the framework's format.
4. **Frameworks & drivers** — the web server, database, UI toolkit; glue only. `main` (the composition
   root) is the one place that knows the framework and DI container.

Data crossing a boundary is plain, dependency-free and in the *inner* circle's format — never an entity
or a DB row leaking inward, and never an inner-layer type leaking outward.

## Component cohesion

- **REP** — the granule of reuse is the granule of release: classes reused together are released together.
- **CCP** — classes that change for the same reason belong together (one reason to change).
- **CRP** — classes reused together stay together; do not force a client to depend on what it never uses.
  These three are a tension triangle: pick two for the current phase and say which.

## Component coupling

- **ADP** — no dependency cycles. A cycle makes a change ripple in both directions; break it with a seam.
- **SDP** — depend in the direction of stability. Stability rises as more things depend on a component
  (and falls as it depends on more).
- **SAP** — a stable component should be abstract so it can still be extended. Dependencies run toward
  abstraction.

## 1. Audit (change nothing)

```bash
cat .claude/stack-profile.md 2>/dev/null | head -20
grep -rn "import.*from\|require(" --include="*.ts" --include="*.rs" --include="*.go" --include="*.py" . 2>/dev/null | head -40
```

Map the imports and find the violations: a use case importing a web framework, an entity importing a DB
row type, a cycle between two components, a stable component that is concrete. List them before touching.

## 2. Apply

- Move the offending import so it points inward; if an inner layer needs an outer service, define an
  interface (port) in the inner layer and implement it (adapter) in the outer.
- Break a cycle at the seam that belongs to the higher-level policy.
- Confine the framework to adapters and `main`; keep SQL/MVC/HTTP out of entities and use cases.

## Verify

A dependency graph (or a grep of imports) shows every edge pointing inward; a cycle detector reports none;
the entity/use-case files import no framework or DB type. State the layer map in the note.

## When to deviate

- A single small service where four layers are ceremony — collapse to two (domain + adapters) and say so.
- The repo's own CLAUDE.md or stack-profile dictates a different layering — local convention wins.
