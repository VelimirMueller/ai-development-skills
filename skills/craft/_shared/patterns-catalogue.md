# Patterns Catalogue

The GoF catalogue (Gamma, Helm, Johnson, Vlissides, 1994) as a decision aid, not a taxonomy to memorise.
Two axes: **purpose** (creational / structural / behavioral) × **scope** (class = fixed at compile time
via inheritance; object = changeable at run time via composition). Most patterns are object-scope.

## The guard

Apply a pattern only when the flexibility it buys is actually needed. Every pattern adds an indirection;
indirection costs code, a perf hit and a new place to look. Read a pattern's **Consequences** section as
the evaluation gate, not the afterword. The honest answer to "which pattern fits?" is often "none yet —
wait until the second caller."

## The what-varies table

Pick a pattern by naming what changes:

| What varies | Pattern |
|---|---|
| The algorithm | Strategy |
| The states | State |
| The implementation | Bridge |
| The interface | Adapter |
| The product families | Abstract Factory |
| The dependent-object count | Observer |
| The object being created | Factory Method |
| The traversal | Iterator |
| The steps of an algorithm | Template Method |

## Creational (5)

- **Abstract Factory** — provide an interface for creating families of related objects without naming
  concrete classes. Use when a system must stay independent of how its products are created and families
  must be used together. Cost: adding a new product type changes the factory interface.
- **Builder** — separate the construction of a complex object from its representation, so one process
  builds many representations. Use when the object has many optional parts or a construction order matters.
  Cost: more classes; a fluent or options object is the idiomatic TS/Rust form.
- **Factory Method** — define an interface for creating an object but let subclasses decide the class.
  Use when a class cannot know in advance the class of objects it must create. Cost: subclasses multiply;
  in functional languages this collapses to a function that returns a value.
- **Prototype** — create new objects by copying a prototype. Use when the cost of construction is high or
  types are dynamic. Cost: deep-copy semantics must be defined; in most languages a constructor or
  `structuredClone` is enough.
- **Singleton** — ensure one instance and provide a global point of access. Use only when exactly one
  instance must exist (a real resource, lazy init with cost). Cost: hidden global state, hard to test;
  an ES-module `const` is the honest form in TS/JS.

## Structural (7)

- **Adapter** — convert one interface into another a client expects. Use to reconcile incompatible
  interfaces. Cost: one more layer of indirection; under structural typing it is one wrapper function.
- **Bridge** — decouple an abstraction from its implementation so both vary independently. Use when both
  axes of change are real. Cost: more indirection; only worth it with two genuinely independent axes.
- **Composite** — compose objects into tree structures and treat leaf and node uniformly. Use for
  part-whole hierarchies. Cost: the uniform interface can force a lowest-common-denominator design.
- **Decorator** — attach responsibilities to an object dynamically without subclassing. Use to add
  behaviour to individual objects, not a class. Cost: many small objects; a function wrapper/HOC is the
  idiomatic form.
- **Facade** — a unified, higher-level interface to a subsystem. Use to hide a complex subsystem. Cost:
  the facade can become a god object; keep it thin and honest.
- **Flyweight** — share fine-grained objects to support large numbers efficiently. Use when objects are
  numerous and mostly shared state. Cost: separates intrinsic from extrinsic state.
- **Proxy** — a placeholder that controls access to another object. Use for lazy load, access control,
  logging or a remote handle. Cost: one more hop on every call.

## Behavioral (11)

- **Chain of Responsibility** — pass a request along a chain of handlers. Use when more than one handler
  may handle a request and the handler is not known ahead. Cost: a request can fall through unhandled.
  Built into DOM bubbling, `try/catch` + rethrow, and Express/Hono middleware.
- **Command** — encapsulate a request as an object. Use for undo, queues, or parameterising requests.
  Cost: class proliferation; closures/thunks (`() => void`) or action objects `{type, payload}` give it
  for free.
- **Interpreter** — define a grammar and an interpreter for sentences in it. Use for small languages.
  Cost: poor for large grammars — prefer a real parser.
- **Iterator** — access elements sequentially without exposing the representation. Use to traverse a
  collection. Cost: hand-rolled cursor classes; a generator or `[Symbol.iterator]` is the idiomatic form.
- **Mediator** — an object that encapsulates how a set of objects interact. Use to untangle a many-to-many
  web. Cost: the mediator can become a monolith; in UI it is lifted state or a context.
- **Memento** — capture and externalise an object's state so it can be restored later. Use for undo.
  Cost: memory; snapshot (Immer/`structuredClone`) beats reverse-operations for real undo.
- **Observer** — a one-to-many dependency so dependents are notified automatically. Use when a change to
  one object changes others without tight coupling. Cost: notification storms; in UI it is state + effects
  or `useSyncExternalStore`.
- **State** — let an object alter its behaviour when its internal state changes. Use when behaviour
  depends on state and has many conditionals. Cost: many classes; a discriminated union + reducer is the
  idiomatic form.
- **Strategy** — a family of interchangeable algorithms behind one interface. Use when an algorithm has
  several variants. Cost: indirection; a function type or `Record<Kind, fn>` is the idiomatic form.
- **Template Method** — define the skeleton of an algorithm, deferring steps to subclasses. Use when an
  algorithm has invariant and variant parts. Cost: inheritance couples subclasses to the skeleton; an
  async template function with hook callbacks is the modern form.
- **Visitor** — an operation to be performed on elements of an object structure, new operations without
  changing the classes. Use when distinct operations over a stable structure accumulate. Cost: adding a
  new element type breaks every visitor.

## Fixed record per pattern

When the catalogue is cited, use this shape so every entry answers the same questions: **Intent**
(one line), **Applicability** (when it earns its place), **Consequences** (the cost), and **Known uses**
(one idiomatic example from the stack at hand).
