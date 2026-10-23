---
name: apply-design-principles
description: Use when writing or reviewing class or module design — encapsulate what varies, program to an interface, favor composition over inheritance, keep class and type distinct, and obey the Law of Demeter and the Hollywood Principle.
---

# Apply Design Principles

The durable object-oriented rules behind every pattern, as a review checklist. They are the "why" the
patterns exist. Catalogue of the patterns themselves: [patterns-catalogue.md](../_shared/patterns-catalogue.md).

## The principles

1. **Encapsulate what varies.** Identify the part that changes and isolate it behind a boundary; change
   to that part no longer ripples. Ask of every new module: what here will change, and is it fenced off.
2. **Program to an interface, not a concrete class.** Depend on the behaviour you need, not the specific
   type that happens to provide it. A function that takes a shape instead of a class stays usable with
   any compatible shape.
3. **Favor composition over inheritance.** Composition is black-box reuse (runtime, keeps encapsulation);
   inheritance is white-box reuse (compile-time, breaks encapsulation). Prefer "has-a" over "is-a";
   reach for inheritance only for a genuine subtype relationship.
4. **Class ≠ type.** A class is one implementation; a type is the interface it satisfies. Two classes can
   share a type without sharing code. Under structural typing any object with the compatible shape
   satisfies the interface — no subclass required.
5. **Principle of Least Knowledge (Law of Demeter).** Talk only to immediate friends. A method should
   call methods on its own object, its arguments, and objects it creates — never the friends of a friend
   (`a.b.c.d()`). This keeps coupling shallow and change local.
6. **Hollywood Principle (Inversion of Control).** "Don't call us, we'll call you." High-level policy
   calls the low-level detail, not the reverse. Let the framework/host drive; supply the hook.
7. **Open/Closed.** Open for extension, closed for modification: add new behaviour by adding code, not by
   editing existing code, so the stable part stops accumulating churn.
8. **Dependency Inversion.** Depend on abstractions, not concretions; high-level policy never depends on
   low-level details, both depend on abstractions. Details (DB, web, framework) point inward toward policy.

## 1. Audit (change nothing)

```bash
cat .claude/stack-profile.md 2>/dev/null | head -20
grep -rn "extends\|class.*extends\|a\.b\.c\." --include="*.ts" --include="*.rs" --include="*.go" --include="*.py" . 2>/dev/null | head -30
```

Find the violation first: an inheritance chain that exists for reuse, a chain of method calls through
three collaborators, a module that imports a concrete vendor type everywhere, a policy that imports a
framework.

## 2. Apply the smallest fix

- A type that changes together → one module that owns it (encapsulate what varies).
- A parameter typed to a concrete class → type it to the interface/shape it uses.
- A subclass used only for reuse → a composed field or a function.
- A `a.b.c()` chain → a method on the friend that owns the traversal.

## 3. State the exception

Every principle has a "when to break" line. Record why the violation is the honest choice (performance,
the framework's own convention, a throwaway) instead of silently leaving it.

## Verify

The change that used to touch many files now touches one; a second subclass was added without editing
the base; the import of a vendor SDK is confined to one seam. State the trade-off in the review note.

## When to deviate

- A tiny, stable, single-author codebase where a principle's ceremony outweighs its benefit.
- The language or framework idiom contradicts the classic form (structural typing, DI containers,
  composition-over-inheritance in Rust) — follow the idiom, keep the intent.
