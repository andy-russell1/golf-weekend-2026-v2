---

## `AGENTS.md`

```markdown
# AGENTS.md

This file defines how AI coding agents should operate in this repository.

The repository contains a Streamlit-based golf weekend app. The app is designed for a small real-world user group and should remain practical, structured, and credible without becoming overengineered.

## Core Mission

Support a clean, usable golf weekend app that helps users with:

- player management
- course exploration
- rounds / weekend itinerary
- score entry
- leaderboard / standings
- golf weekend experience

This is a focused product, not a generic golf SaaS platform.

Agents must preserve that focus.

## Current Project Stage

The project has already passed initial product and architecture thinking.

The first build phases have covered:

1. product scope
2. frontend architecture
3. data / state / logic model
4. golf scoring logic
5. initial Streamlit UI implementation

Upcoming work is expected to focus on:

6. UX / design improvement
7. QA / testing
8. refactor / code quality
9. deployment / persistence planning
10. v2 roadmap shaping

Agents should assume the repo is now in the **improve and harden** stage, not blank-sheet ideation.

## Mandatory Working Principles

### 1. Do not restart from scratch

Do not replace the app wholesale unless the current implementation is fundamentally broken and the reason is clearly explained.

Prefer targeted improvement over broad rewrites.

### 2. Work from the existing structure

Respect current files, naming, and architecture direction unless there is a clear reason to improve them.

If changing structure, do so deliberately and minimally.

### 3. Keep UI and business logic separate

Golf rules, handicap logic, scoring, standings, and derived calculations must not be embedded directly inside presentational UI code unless trivial.

Prefer dedicated domain modules.

### 4. Prefer small focused units

Prefer:

- small components
- focused state helpers
- isolated domain logic
- readable utilities

Avoid giant page files and overloaded helper modules.

### 5. Preserve product focus

Do not turn the app into a generic golf platform.

Do not introduce broad features unrelated to the golf weekend use case unless explicitly requested.

### 6. Respect v1 vs v2 boundaries

Default behaviour should be:

- strengthen v1 usability and reliability first
- defer speculative flexibility to v2
- avoid premature extensibility that adds complexity without immediate value

### 7. Be explicit about assumptions

If the codebase or requirements force assumptions, document them in comments, notes, or README updates where appropriate.

### 8. Do not invent golf logic

Do not make up rules, handicap treatments, or scoring logic.

Where logic is unclear, preserve existing assumptions or isolate the uncertainty cleanly rather than improvising silently.

### 9. Avoid unnecessary dependencies

Do not add packages casually.

Any new dependency should have a clear reason and a real payoff.

### 10. Leave the repo clearer than you found it

Edits should improve readability, maintainability, or usability.

## Product Constraints

The app should remain:

- practical
- understandable
- mobile-usable
- visually coherent
- trustworthy in scoring behaviour
- appropriate for a small real group on a golf weekend

Agents should optimise for real use during the trip, not for generic demo flash.

## Architecture Expectations

Agents should generally preserve or improve the following separation:

- **pages**: high-level Streamlit view composition
- **components**: reusable presentational or view-level UI units
- **state/support**: session state, app context, and interactive behaviour
- **domain logic**: scoring, handicaps, standings, formats
- **data/services**: loading, persistence, transformation
- **config/models**: constants, configuration, and data-shape definitions

Do not collapse these layers together without strong justification.

## Preferred Change Types at This Stage

Good changes include:

- improving score entry UX
- improving leaderboard clarity
- tightening responsive behaviour
- reducing duplication
- isolating logic from components
- improving naming
- adding validation
- fixing edge cases
- improving state shape
- clarifying domain calculations
- improving documentation
- preparing sensible persistence patterns

## Change Types to Avoid Unless Explicitly Requested

Avoid introducing the following unless specifically asked:

- full auth systems
- complex backend platforms
- advanced role-based admin
- deep analytics engines
- broad CMS-style content management
- highly configurable rules builders
- large design system overhauls
- overabstracted architecture layers
- premature microservice-style separation

## UX Expectations

The app is likely to be used in real conditions during a golf weekend.

Agents should therefore value:

- quick navigation
- fast score entry
- readable standings
- clear round/format context
- touch-friendly interactions
- reasonable mobile behaviour
- minimal confusion under time pressure

A visually impressive but clumsy UI is not a success.

## Scoring Logic Expectations

Scoring-related code must be:

- clear
- testable
- isolated
- consistent across views
- resistant to duplicated calculation logic

If standings, shots received, handicap-derived values, or points are calculated, prefer centralised logic rather than repeating formulas across components.

## State Management Expectations

Agents should keep a clean distinction between:

- persisted data
- derived domain data
- temporary UI state
- form state

Do not mix these casually.

Prefer straightforward patterns that fit the current scale of the app.

## Responsive Design Expectations

Agents should assume mobile usage matters.

At minimum, these flows must remain usable on smaller screens:

- entering scores
- viewing leaderboard
- selecting round/player
- checking schedule / round context
- navigating between core app sections

Desktop-only assumptions should be treated as defects unless explicitly accepted.

## Documentation Rules

When meaningful changes are made, agents should update documentation accordingly.

This may include:

- README updates
- notes about assumptions
- notes about persistence strategy
- notes about data model changes
- notes about architectural boundaries

Do not leave structural changes undocumented.

## File and Code Hygiene

Agents should prefer:

- descriptive names
- small diffs where possible
- predictable file placement
- removal of dead code when safe
- comments only where they add clarity
- direct, readable logic over clever abstraction

Agents should avoid:

- hidden behaviour
- magic constants scattered across files
- duplicate scoring formulas
- broad util dumping grounds
- component files with unrelated responsibilities

## Testing Mindset

Even if formal tests are limited, agents should reason like testers.

Look for:

- invalid score inputs
- incomplete rounds
- ties
- bad handicap assumptions
- broken derived standings
- state desynchronisation
- mobile layout breakage
- misleading or unclear labels

## When Refactoring

Refactor only with purpose.

The preferred order is:

1. preserve behaviour
2. isolate logic
3. reduce duplication
4. improve readability
5. improve extension paths for v2

Do not refactor simply for stylistic purity.

## Persistence and Deployment Mindset

At this stage, the likely goal is a simple, reliable setup for a small group.

Agents should favour:

- minimal fragility
- understandable persistence
- straightforward deployment
- low operational overhead

Do not assume enterprise infrastructure is needed.

## Output Expectations for AI Agents

When asked to work on the repo, agents should usually provide:

- concise assessment of what they are changing
- specific file-level changes
- rationale for structural decisions
- any assumptions made
- any follow-up risks or limitations

## Summary Rule

Make the app:

- easier to use
- easier to trust
- easier to maintain
- easier to extend

Do not make it bigger, cleverer, or more abstract unless that clearly improves the product.
