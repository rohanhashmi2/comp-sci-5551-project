# InspectIQ — Design Notes (Proposal for Team Review)

> **Status:** Starting proposal, drafted during environment setup. This
> document has not been reviewed by the team. It is intentionally opinionated
> so there is something concrete to push back on, but nothing here is
> decided. In particular, the domain model must ultimately follow from the
> user stories the team writes, not the other way round — read the shape
> below as a strawman to critique, delete, or replace once the product
> backlog exists.
>
> Every "proposed" and "suggested" below is exactly that. Where a
> tradeoff was faced, the reasoning is preserved so a reviewer can
> disagree with the *reasons* and not only the outcome.

---

## 1. Open questions and stated assumptions

These are what the team needs to decide first. Every model, view, and test
below rests on the answers. If any of these change, expect ripple effects.

### Stated assumptions (proposed defaults — please confirm or reject)

1. **One ticket per inspection** — after an inspection, the store owner
   receives a single ticket covering *all* issues found on that inspection,
   not one ticket per checklist item. The alternative (one ticket per
   violation) is closer to how some real inspection agencies work and would
   change `Ticket.inspection` from a `OneToOneField` to a `ForeignKey`. Ask
   the team which matches the source requirement they will be graded
   against.
2. **One deadline per ticket** — the inspector sets a single remediation
   deadline that covers every failed item on that inspection, not one
   deadline per item. If per-item deadlines are needed, `deadline` moves
   from `Ticket` back onto `InspectionResult` and the ticket's overdue flag
   becomes an aggregate.
3. **Re-inspection creates a new row** — a follow-up inspection is
   represented as a new `Inspection` linked to the parent via
   `previous_inspection`, rather than cycling the same row's status. This
   preserves history but doubles the number of rows in the audit trail.
4. **Evidence is append-only** — once a store owner uploads evidence for a
   failed item, that row is never edited or deleted. Re-submissions add new
   rows. Simpler to audit; slightly more storage.
5. **No walk-in inspections** — every inspection is scheduled before it
   begins. If the team wants to support unscheduled inspections, the
   scheduling view becomes optional and `SCHEDULED` becomes a state
   inspections can skip.
6. **Self-registration with role selection** — both inspectors and store
   owners register themselves and pick their own role. This is insecure in
   any real deployment (nothing stops a store owner picking `INSPECTOR`);
   acceptable only because this is a course project. If the team wants a
   more realistic model, one option is: inspectors are created by an admin,
   store owners self-register.
7. **One owner per store; one owner may have several stores** — the
   `Store.owner` field is a single `ForeignKey`. Joint-ownership would
   require a `ManyToManyField` or a separate membership table.
8. **Any inspector can conduct any inspection; one person conducts an
   inspection start-to-finish.** No handoff mid-inspection and no
   inspector-to-inspection assignment. (Original wording — "the inspector
   who schedules an inspection is the one who conducts it" — implied an
   assignment feature not present in the model. Revised during Story 6
   planning to resolve the assumption 8 / assumption 14 contradiction.)
9. **Overdue tickets get a dashboard flag only** — no automated escalation,
   no email, no state change when a deadline passes.
10. **No email notifications in MVP scope** — everything is in-app.
11. **Photos are required on every failed checklist item** — no
    exceptions for "documentary" failures like missing certificates.
12. **Inspector sets each deadline freely** — no severity-to-deadline
    policy. Consequently the model has no `severity` field on failed items.
13. **Tests run against local Postgres; the app runs against Supabase.**
    See §12. This divergence is a known risk to re-check before each demo.
14. **Inspectors have unscoped store visibility; stores are not "assigned"
    to inspectors.** Any inspector can see any store, any inspection, and
    any ticket. The `Store` model has no inspector FK; owner-side scoping
    (owners see only their own stores) is enforced by
    `Store.objects.visible_to(user)`. See the note below on AC rewording —
    Dev 2 and Dev 3 should check their own criteria for the same drafting
    error.

#### Note: AC rewording in US-4 (US-4 AC 4.1 and AC 4.2)

Story 4's original acceptance criteria were phrased in terms of stores
being "assigned to" an inspector:

> AC 4.1 (original): Given an inspector is logged in and two stores are
> assigned to them…
>
> AC 4.2 (original): Given an inspector is logged in and a store is
> assigned to a different inspector…

That wording implies a feature — inspector-to-store assignment — that the
project brief does not request and that the design (§3 `Store` model,
assumption 14 above) does not include. The brief itself is explicit that
inspectors can view inspection history of **any** store. Story 3
accordingly chose option (a) in its plan: no inspector FK on `Store`.

Story 4 therefore reworded AC 4.1 and AC 4.2 to match the actual design:

> **AC 4.1 (rewritten): Inspector sees all stores.** Given an inspector
> is logged in and two stores exist. When the inspector opens the store
> list. Then both stores are listed with their name and address.
>
> **AC 4.2 (rewritten): Store list spans all owners.** Given an
> inspector is logged in and one store exists owned by one store owner,
> and another store exists owned by a different store owner. When the
> inspector opens the store list. Then both stores are listed.

AC 4.2's new wording is the symmetric partner of AC 4.4: AC 4.4 proves
owner-side scoping is active; AC 4.2 proves inspector-side scoping is
*not* active.

**Flag for Dev 2 and Dev 3:** your own stories' acceptance criteria may
carry the same drafting error — phrases like "the inspections assigned
to me" or "the tickets assigned to me." If so, reword to match the
unscoped-inspector-visibility design rather than adding an assignment
feature. Raise it before implementation starts, not after.

#### Note: AC rewording in US-6 (US-6 AC 6.5)

Story 6's original AC 6.5 carried the same drafting error that Story 4
corrected:

> AC 6.5 (original): Given an inspection is scheduled for a store
> assigned to a different inspector… When an inspector who is not
> assigned requests that inspection form… Then the system denies access
> and no results are recorded.

Under the revised assumption 8 (any inspector can conduct any
inspection) and assumption 14 (no inspector-side scoping on stores),
there is no "assigned to a different inspector" and no "inspector who
is not assigned." As written, the criterion could not be satisfied
without reintroducing an assignment feature that nothing else in the
project needs.

Story 6 therefore reworded AC 6.5 to test the real adjacent invariant —
owner-side denial of the conducting flow, mirroring AC 5.4's shape:

> **AC 6.5 (rewritten): A store owner cannot open the inspection
> form.** Given a store owner is logged in. When the store owner
> requests the inspection form for any inspection. Then the system
> denies access and no results are recorded.

The replacement proves that owners cannot conduct inspections even
against stores they own, which the project brief explicitly requires.

### Genuinely open questions

- **What are the actual user stories?** Everything below is speculative
  until they exist. The strawman assumes the standard inspector/owner
  workflow described in the project brief. If the team's stories carve up
  the domain differently, most of §3–§6 needs to be revisited.
- **Does the grading rubric require a specific mapping between acceptance
  criteria and test names?** §7 uses `test_ac<NN>_<MM>_*` (story.criterion);
  the team should confirm this matches the rubric.
- **How does an inspection get created that has NA rows?** Is the inspector
  expected to explicitly mark items `NOT_APPLICABLE`, or do items default
  to that until the inspector touches them? Different UX; same schema.
- **Who seeds `ChecklistItem` rows in production?** Fixture on deploy?
  Admin panel? Left as an implementation detail for a later sprint.
- **What Postgres major version does each teammate's Supabase project
  run?** May vary across projects created at different times. See §12.
*(Resolved: the assumption 8 / 14 contradiction was closed in Story 6
planning by revising assumption 8 to drop the assignment implication.
No `conducted_by` field was added, because no acceptance criterion in
the backlog reads it. See the AC 6.5 rewording note below.)*

---

## 2. Proposed repository layout

```
comp-sci-5551-project/
├── manage.py
├── pyproject.toml              # Black, Ruff, pytest-django config
├── requirements/
│   ├── base.txt                # runtime pins
│   └── dev.txt                 # -r base.txt + test/lint pins
├── .env.example
├── .gitignore
├── README.md
├── conftest.py                 # root pytest fixtures + test-DB swap
├── config/                     # project package (settings, urls, wsgi, asgi)
├── apps/
│   ├── accounts/               # custom User + role (built in skeleton)
│   ├── common/                 # mixins, decorators, base template (proposed)
│   ├── stores/                 # Store, owner linkage, history (proposed)
│   ├── inspections/            # ChecklistItem + Inspection + services (proposed)
│   └── tickets/                # Ticket + Evidence (proposed)
├── templates/base.html + <per-app>/
├── static/, media/
└── docs/
    ├── design-notes.md         # this file
    ├── acceptance_criteria.md  # to be written
    └── erd.md                  # to be drawn
```

Only `accounts` and `common` exist in the skeleton commit; the other three
apps are proposed. Rationale for splitting them:

- **`accounts`** owns the custom `User` model. Must be a separate app
  declared before `INSTALLED_APPS` grows, because Django's custom user model
  has to be set on day one or migrations become painful. Isolates auth
  churn from feature work.
- **`stores`** proposed as its own small app so one developer can own store
  CRUD end-to-end (model + views + tests) without touching inspection
  logic. Low merge-conflict surface. **Tradeoff:** if the team prefers
  fewer moving parts, fold into `inspections`.
- **`inspections`** proposed to hold `ChecklistItem`, `Inspection`, and
  `InspectionResult`. `ChecklistItem` lives inside this app rather than a
  separate `checklists` app because a table with no views of its own is a
  module, not an app.
- **`tickets`** proposed as separate from `inspections` because remediation
  is a distinct workflow (owner uploads evidence, inspector reviews) that
  runs on a different timeline from conducting the inspection itself.
  Splitting keeps the two developers' PRs from colliding on the same files.
  **Tradeoff:** if the two apps end up importing each other constantly,
  merging is acceptable.
- **`common`** for shared mixins and the base template. Prevents circular
  imports between feature apps.

---

## 3. Proposed domain model

Field types are Django ORM names. Every field has a one-line rationale.

### `accounts.User` (extends `AbstractUser`) — built in skeleton
- `role: CharField(choices=[INSPECTOR, OWNER])` — the enum column
  representing role. Proposed as a single field rather than Django Groups
  because the team is small and beginner-level; Groups is more flexible
  but harder to test and debug.
- inherited `username`, `email`, `password`, etc.
- **Constraint (proposed):** DB-level `CheckConstraint` that
  `role IN ('INSPECTOR','OWNER')`. Django's `choices=` doesn't add this at
  the DB layer on its own.

### `stores.Store` — proposed
- `name: CharField(max_length=200)` — human-readable identifier for
  reports.
- `address: TextField()` — required on printed inspection reports.
- `owner: ForeignKey(User, on_delete=PROTECT, limit_choices_to={'role':
  OWNER})` — proposed link between owner and store; `PROTECT` prevents
  accidental cascade-deletion of stores when a user row is removed.
- `created_at: DateTimeField(auto_now_add=True)` — audit.

**Note on `limit_choices_to`:** this filters the admin dropdown and
`ModelForm` choices only. It is *not* a DB or API constraint. Real
validation is proposed to live in `Store.clean()`, which raises
`ValidationError` when `self.owner.role != OWNER`, covered by a test
`test_store_rejects_non_owner_user`. A DB-level guarantee here would need a
trigger — rejected as overkill for a course project.

### `inspections.ChecklistItem` — proposed
- `code: CharField(max_length=16, unique=True)` — stable identifier so
  wording changes don't break historical reports.
- `title: CharField(max_length=200)` — short label on the form.
- `description: TextField()` — full standard text.
- `is_active: BooleanField(default=True)` — soft-retire items without
  breaking historical FKs.
- `ordering: PositiveSmallIntegerField(default=0)` — deterministic display
  order.
- **Proposed as data-driven** (rows in a table seeded from a JSON fixture),
  not hardcoded, so catalog changes don't require a deploy and one
  developer can seed while another builds the form in parallel. **Tradeoff:**
  a Python constant is simpler and requires no fixture management, at the
  cost of tying every catalog edit to a code commit.

### `inspections.Inspection` — proposed
- `store: ForeignKey(Store, on_delete=PROTECT)`.
- `inspector: ForeignKey(User, on_delete=PROTECT, limit_choices_to={'role':
  INSPECTOR})` — cosmetic per the `Store` note above; real check in
  `clean()`.
- `scheduled_for: DateTimeField()`.
- `started_at: DateTimeField(null=True, blank=True)` — set when inspector
  opens the form.
- `completed_at: DateTimeField(null=True, blank=True)` — set on submission.
- `status: CharField(choices=[SCHEDULED, IN_PROGRESS, COMPLETED,
  RE_INSPECTION_SCHEDULED])`.
- `notes: TextField(blank=True)` — inspector's summary.
- `previous_inspection: ForeignKey('self', null=True, blank=True,
  on_delete=SET_NULL, related_name='follow_ups')` — links a re-inspection
  to its parent, per assumption 3.
- **Constraint (proposed):** DB-level `CheckConstraint` on `status` values.

### `inspections.InspectionResult` — proposed, records every checklist item
The paper form being replaced is a **completed checklist**, not a list of
failures. Today's proposed model must therefore distinguish "passed clean"
from "never filled in". Two ways to model this were considered:

- **(a) Single `InspectionResult` model, `outcome=FAIL` carries comment and
  photo.** One table. Comment and photo are nullable and only populated
  when the outcome is FAIL. Consistency enforced by `Model.clean()`.
- **(b) `InspectionResult` records outcome; a separate `Violation` model
  hangs off any result with `outcome=FAIL`.** Two tables joined 1:1 on FAIL
  rows. Schema-level guarantee that failure details exist iff outcome is
  FAIL.

**Recommendation:** (a). Reasons:
1. There is no attribute of a violation that a `PASS`/`N/A` row doesn't
   store as null anyway.
2. Every access pattern ("list failures with photos") in (b) would need to
   join two tables that always co-vary — extra query overhead, more places
   to forget the join.
3. The consistency risk in (a) — a FAIL row without a photo — is caught by
   a single `clean()` check plus a test. Easier to reason about than the
   cross-table invariant in (b).
4. Fewer models means less merge-conflict surface for a three-dev team.

**Proposed fields (option a):**
- `inspection: ForeignKey(Inspection, on_delete=CASCADE,
  related_name='results')`.
- `checklist_item: ForeignKey(ChecklistItem, on_delete=PROTECT)` — PROTECT
  so retired catalog items don't orphan history.
- `outcome: CharField(choices=[PASS, FAIL, NOT_APPLICABLE])`.
- `comment: TextField(blank=True)` — required in `clean()` when
  `outcome=FAIL`.
- `photo: ImageField(upload_to='results/%Y/%m/', blank=True, null=True)` —
  required in `clean()` when `outcome=FAIL` (per assumption 11).
- `created_at: DateTimeField(auto_now_add=True)`.
- **Constraints (proposed):**
  - `UniqueConstraint(fields=['inspection', 'checklist_item'],
    name='one_result_per_item_per_inspection')` — one row per item per
    inspection.
  - `CheckConstraint` that `outcome IN ('PASS','FAIL','NOT_APPLICABLE')`.
  - `CheckConstraint` that `outcome != 'FAIL' OR comment != ''` — DB
    guarantee that a failing result carries a comment. Photo presence is
    left to `clean()` because `ImageField` stores a path string and
    empty-string checks are brittle at the DB layer.

### `tickets.Ticket` — proposed, one per Inspection
- `inspection: OneToOneField(Inspection, on_delete=CASCADE,
  related_name='ticket')`.
- `deadline: DateField()` — per assumption 2, one deadline covers the whole
  inspection. If the team decides on per-item deadlines, this moves back
  onto `InspectionResult`.
- `issued_at: DateTimeField(auto_now_add=True)`.
- **No stored `status` field.** Proposed as derived — see §4.

Proposed to be created by an explicit service function
(`complete_inspection` in §5), not a `post_save` signal.

### `tickets.Evidence` — proposed, attached per failed `InspectionResult`
- `result: ForeignKey(InspectionResult, on_delete=CASCADE,
  related_name='evidence')`.
- `submitted_by: ForeignKey(User, on_delete=PROTECT)` — audit.
- `photo: ImageField(upload_to='evidence/%Y/%m/')` — primary artifact.
- `note: TextField(blank=True)`.
- `submitted_at: DateTimeField(auto_now_add=True)`.
- `review_status: CharField(choices=[PENDING, ACCEPTED, REJECTED],
  default=PENDING)` — the only stored review state; ticket status derives
  from these (§4).
- `reviewer_comment: TextField(blank=True)`.
- `reviewed_at: DateTimeField(null=True, blank=True)`.

**Why per-result, not per-ticket:** the owner fixes and photographs one
issue at a time; the inspector reviews evidence item-by-item. Attaching to
the ticket would either force one giant upload covering every issue
(unrealistic) or need an extra `result` FK on `Evidence` anyway. Per-result
is the natural grain.

**Append-only** per assumption 4: no update view; existing rows are never
edited.

---

## 4. Proposed state machine

### Inspection — the sole owner of "a re-inspection has been scheduled"

| From | Event | To |
|---|---|---|
| `SCHEDULED` | inspector opens the form | `IN_PROGRESS` |
| `IN_PROGRESS` | `complete_inspection` service runs | `COMPLETED` |
| `COMPLETED` | inspector creates a follow-up Inspection | `RE_INSPECTION_SCHEDULED` |

No walk-ins (assumption 5). Re-inspection is a new row (assumption 3).
Enforcement proposed via `apps/inspections/transitions.py::apply(instance,
event)` raising `InvalidTransition` on illegal moves.

### Ticket — status derived, not stored

`Ticket.status` proposed as a Python `@property`:
- `CLOSED` when every `InspectionResult` on the parent inspection with
  `outcome=FAIL` has at least one `Evidence` row with
  `review_status=ACCEPTED`.
- `OPEN` otherwise.

Consequences:
- No stored `Ticket.status` column — it cannot drift out of sync with
  evidence.
- `RE_INSPECTION_SCHEDULED` lives only on `Inspection.status`. The ticket
  doesn't need to duplicate it because a re-inspection *is* a new
  `Inspection`.
- `APPROVED` and `CLOSED` collapse into `CLOSED`.

**Tradeoff:** computing on every read is an extra query. At course-project
scale, invisible. If it ever mattered, cache with a stored field kept in
sync via a service call — deferred.

**Dashboard overdue flag:** proposed as
`Ticket.is_overdue = deadline < today() and status == OPEN`.
Presentational only, no state transition (assumption 9).

---

## 5. Proposed service layer

Ticket creation is proposed *not* to be a `post_save` signal. Instead, an
explicit service function.

**`apps/inspections/services.py::complete_inspection(inspection,
deadline=None) -> Ticket | None`**

Proposed behaviour:
1. Assert `inspection.status == IN_PROGRESS`; raise `InvalidTransition`
   otherwise.
2. Assert every active `ChecklistItem` has a matching `InspectionResult`;
   raise `IncompleteInspection` otherwise. This is the check that
   distinguishes "passed clean" from "never filled in".
3. If any result has `outcome=FAIL` and no `deadline` was supplied, raise
   `DeadlineRequired`.
4. Inside `transaction.atomic()`:
   - Set `completed_at = timezone.now()`, `status = COMPLETED`, save the
     inspection.
   - If any FAIL results exist, create the `Ticket` with the given
     `deadline`.
   - Return the `Ticket` (or `None` if all-pass).

**Where it is called:** exactly one place — the inspection submit view. The
view is the HTTP adapter; it converts the POST into service arguments and
translates service exceptions into form errors.

**How it is unit-tested independently of HTTP:** proposed tests in
`apps/inspections/tests/test_services.py` import and call
`complete_inspection` directly with model instances built via factories.
Cases:
- Creates a ticket when any result fails.
- Creates no ticket when all results pass.
- Rejects when not every checklist item has a result.
- Rejects a missing deadline when failures exist.
- Rejects a wrong starting status.
- Rolls the inspection back to `IN_PROGRESS` if ticket creation raises
  (verified by mocking `Ticket.save` to raise inside the atomic block).

**Why not a signal:** signals hide the "when does a Ticket appear?"
question, run in implicit order, and are painful to test in isolation. An
explicit service is one call site and one test file, and it makes the
transaction boundary visible.

---

## 6. Proposed access control

The rule "an owner sees only their store; an inspector sees any store"
needs a single choke point that a newly added view cannot skip.

**Proposed approach:** queryset-scoping methods on managers, plus a view
mixin that requires them.

- Manager methods `Store.objects.visible_to(user)`,
  `Inspection.objects.visible_to(user)`,
  `InspectionResult.objects.visible_to(user)`,
  `Ticket.objects.visible_to(user)`, `Evidence.objects.visible_to(user)`.
  Inspector sees all rows; owner sees rows whose store's owner is
  themself.
- `apps.common.mixins.RoleScopedQuerysetMixin` — view mixin whose
  `get_queryset` calls `self.model.objects.visible_to(self.request.user)`.
  Every list/detail/update view inherits it.
- `InspectorRequiredMixin`, `OwnerRequiredMixin` for role-gated write
  actions.
- Cross-owner access returns **404**, not 403, to avoid leaking whether a
  row ID exists.

**Where the check lives:** at the ORM boundary (`visible_to`), not the
template and not the URL. The mixin makes it declarative; explicit tests
below make it enforceable.

**A URLconf-walking meta-test** that inspects every registered view and
asserts it either uses the mixin or is on an allow-list has been
considered. Proposed to defer this to Sprint 3 (see §9). Until then, the
guardrail is **explicit negative tests** in
`apps/common/tests/test_access_boundary.py`:
- `test_owner_cannot_view_other_stores_store_detail_returns_404`
- `test_owner_cannot_view_other_stores_inspection_detail_returns_404`
- `test_owner_cannot_view_other_stores_inspection_result_returns_404`
- `test_owner_cannot_view_other_stores_ticket_detail_returns_404`
- `test_owner_cannot_upload_evidence_to_other_stores_result_returns_404`
- `test_owner_cannot_view_other_stores_history_returns_404`
- `test_owner_role_cannot_hit_inspector_only_write_endpoints_returns_403`

**Tradeoff:** `django-guardian` provides per-object permissions and is the
more general answer. Rejected as overkill for two fixed roles; a role
column and `visible_to` are dumber and easier to reason about.

---

## 7. Proposed test layout

- Tests colocated with the code they exercise:
  `apps/<app>/tests/test_<layer>.py` — `test_models.py`,
  `test_services.py`, `test_views.py`, `test_workflow.py`, `test_access.py`.
- **Naming for AC-mapped tests:** `test_ac<NN>_<MM>_<slug>`, where `NN`
  is the user-story number and `MM` is the acceptance-criterion number
  within that story (both zero-padded to two digits). Example:
  `test_ac01_03_password_mismatch_rejected` maps to AC 1.3 of US-1.
  Confirm this matches the grading rubric.
- **Docstring convention:** the Given/When/Then from
  `docs/acceptance_criteria.md` is copied verbatim into the test's
  docstring. This is how a grader traces test → criterion.
- **Traceability check:** proposed `scripts/check_ac_coverage.py` (~30
  lines) parses the AC document for `AC N.M` headings and greps the test
  suite for a matching `test_acNN_MM_` function. Missing means an AC has
  no test. Run manually until CI is added.
- **Fixtures:** proposed to use `factory-boy` (`UserFactory`,
  `StoreFactory`, etc.). Cuts fixture boilerplate. Alternative is plain
  pytest fixtures; workable at this size but repetitive.
- **Database:** tests run against a **local Postgres**, not Supabase (§12).

### Sprint report — implementation-table conventions

When filling the Sprint 1 report's implementation tables, follow these
rules so the three developers' entries read the same way:

- **"Class Name(s) of the Test Code" column:** put the **test file name**
  (e.g. `apps/accounts/tests/test_registration.py`). Our tests are
  module-level pytest functions, not `unittest.TestCase` classes — there
  is no class name to list. Put the test function name in the adjacent
  column.
- **"Notes" column — inherited behaviour:** where an acceptance criterion
  is satisfied by a Django class or method we did not override, say so
  and name the inherited method. Example: AC 1.3 is satisfied by
  `UserCreationForm.clean_password2` which we inherit without override;
  the Notes column should state that explicitly.
- **Status values:** exactly one of `completed` / `inProgress` / `toDo`.
  Case-sensitive. No other values and no synonyms.
- **Supporting tests that do not map to an acceptance criterion** (for
  example `test_ac02_03_04_response_equivalence`, or
  `test_direct_post_with_inspector_owner_rejected`) go into the report's
  **"other tests" table**, never duplicated against an AC. An AC's row
  references only the test that is 1:1 with that criterion.

---

## 8. Proposed work distribution — three roughly equal tracks

Every developer must produce 400+ lines of their own production and test
code. The proposal below aims to keep the three tracks comparable so no
developer is bottlenecked by another.

**Track A — Accounts UX + Stores + History (~one dev's ~400 LOC)**
- Registration form with role selection, login, logout, password change.
- Base template scaffolding, role-aware nav.
- `Store` model, admin, CRUD views for inspectors, owner-scoped views for
  owners.
- Store history view (owner sees their own store; inspector sees any
  store).
- Access tests for stores and history.

**Track B — Inspections engine (~one dev's ~400 LOC)**
- `ChecklistItem` model + seed fixture + admin.
- `Inspection`, `InspectionResult`, `transitions.py`,
  `services.py::complete_inspection`.
- Inspector dashboard, scheduling view, conducting form.
- Re-inspection flow.
- Model, service, view, and workflow tests including the atomic-rollback
  test.

**Track C — Common + Tickets + Evidence (~one dev's ~400 LOC)**
- `apps.common.mixins` and role decorators.
- factory-boy factories shared across all three tracks.
- The full negative-access test suite in §6.
- `Ticket` model, derived `status` property, `is_overdue` flag.
- Owner ticket list, per-result evidence upload.
- Inspector evidence review with accept/reject and comment.

**Coordination note:** Track C's mixins and factories are used by A and B,
so C's early commits must land before A and B can write access tests. This
is reflected in the build order below.

---

## 9. Proposed build order and sprint mapping

Ten commits, smallest first, each proposed to leave the repo green
(`pytest --reuse-db` and `python manage.py check` both pass).

### Sprint 1 — weeks 1–8: primitive functions of must-have features
Proposed commits 1–8. **Commit 8 is proposed as the week-8 cut line.**

1. **Skeleton** — the commit associated with this document.
2. **Accounts foundation** — custom `User` with `role`, `AUTH_USER_MODEL`,
   self-registration form, login/logout. Blocks everything downstream.

*Fork point — Tracks A, B, C in parallel after commit 2:*

3. **`common` infrastructure** (Track C) — mixins, decorators, base
   template, factory-boy factories, factory-validity meta-test. Small
   commit but blocks the access tests in later commits; **land this
   early**.
4. **`stores`** (Track A) — model, `visible_to`, admin, CRUD, templates,
   negative-access tests. Depends on commit 3.
5. **`ChecklistItem` + fixture** (Track B) — model, `checklist_items.json`,
   `loaddata` in the setup steps, fixture-load tests. Depends on commit 1
   only.

*Second fork point — commits 6 and 7 depend on 4 and 5; commit 8 depends
on 6/7.*

6. **Inspection scheduling** (Track B) — `Inspection` model,
   `transitions.py`, scheduling view, inspector dashboard.
7. **Conducting inspections** (Track B) — `InspectionResult`, conducting
   form, `services.py::complete_inspection`, submit view. Full service
   test file including the atomic-rollback case.
8. **Tickets + evidence — happy path** (Track C) — `Ticket` wired to
   `complete_inspection`, derived `status`, owner ticket list, per-result
   evidence upload, inspector evidence review.

**Proposed week-8 demo:** a registered inspector and a registered owner
both log in against a live Supabase-hosted database. The inspector creates
a store, assigns it to the owner, schedules an inspection, conducts it —
recording PASS/FAIL/NA outcomes across every checklist item with a photo
attached to each FAIL. On submit, a ticket appears in the owner's queue
with a deadline. The owner uploads evidence against a specific failed
item. The inspector accepts it; the ticket's derived status flips to
CLOSED. Every acceptance criterion driving that flow has a
`test_ac<NN>_<MM>_*` test.

### Sprint 2 — weeks 9–12: all basic features

9. **Store history** (Track A) — history view for owner (own store) and
   inspector (any store), rendering the inspection chain including any
   follow-ups.
10. **Re-inspection flow** (Track B) — inspector action on a completed
    inspection with an outstanding ticket that creates a new `Inspection`
    with `previous_inspection` set.

Also in Sprint 2: Bootstrap styling pass across all templates, form UX
polish, the "overdue" dashboard flag on the ticket list, error-page
templates, deployment README notes (not deployment itself).

### Sprint 3 — weeks 13–16: testing, refactoring, extras

- Coverage push toward whatever threshold the report requires.
- The deferred URLconf-walking meta-test from §6.
- Refactor duplicated view code into `common` mixins.
- `scripts/check_ac_coverage.py` traceability checker from §7.
- Any nice-to-have features scoped in: PDF export of an inspection report,
  admin dashboard, CI pipeline.

### Coordination

- Commits 3, 4, 5 touch disjoint file sets — three PRs can be open at once
  without conflict.
- The template `base.html` (commit 3) is the one file everyone edits
  later; agree the block structure in commit 3 so subsequent PRs *add*
  blocks rather than *rewrite* the file.
- Each developer runs their own Supabase project. Rule of thumb: never
  push a migration you haven't successfully applied to your own project's
  database first.

---

## 10. Dependency pins

Runtime (`requirements/base.txt`), resolved against PyPI on 2026-09-22:

```
Django==5.2.17
psycopg[binary]==3.3.6
Pillow==12.3.0
django-environ==0.14.0
django-bootstrap5==26.3
whitenoise==6.12.0
```

Dev/test (`requirements/dev.txt`, first line `-r base.txt`):

```
pytest==9.1.1
pytest-django==4.14.0
pytest-cov==7.1.0
factory-boy==3.3.3
black==26.5.1
ruff==0.16.8
```

`pre-commit` was in an earlier draft; not included in this proposal. Add it back if the team wants automatic formatting/lint hooks on commit.

Source-of-truth split: `requirements/*.txt` for *what* to install;
`pyproject.toml` for *how* Black, Ruff, and pytest behave.

---

## 11. `apps/` nesting configuration

Four pieces must line up on the first commit:

- **`__init__.py` files** must exist in `apps/`, `apps/accounts/`,
  `apps/common/`, and every future app package.
- **`INSTALLED_APPS`** uses the dotted `AppConfig` path
  (`apps.accounts.apps.AccountsConfig`), not the bare name.
- **Each `apps.py`** sets both `name` (dotted import path) *and* `label`
  (short unique identifier used in migration filenames and FK strings).
  Django will derive `label` from the last segment of `name` if omitted,
  which happens to work here — but explicit is one line and removes a
  rename-time bug.
- **`AUTH_USER_MODEL = "accounts.User"`** uses the app **label**, not the
  dotted path. A common footgun.

`startapp` creates apps at the project root, not inside `apps/`. Either
pass an explicit destination (`python manage.py startapp <name>
apps/<name>` after making the target directory) or write the small
skeleton by hand.

---

## 12. Database — local Postgres for tests, Supabase for `runserver`

Every developer's `.env` holds two connection strings:

- `DATABASE_URL` — their own Supabase session-pooler URI. Used by
  `runserver`, `migrate`, and everything the app does at runtime.
- `TEST_DATABASE_URL` — a local Postgres URI. Used only by `pytest`.

`conftest.py` at the project root swaps `os.environ["DATABASE_URL"]` to
the test URL before Django's settings are imported. `settings.py` reads
`DATABASE_URL` unconditionally; there is no branching in settings.

### Why this split

The Supabase `postgres` role on a free-tier project is not a superuser and,
based on community reports as of 2026, does not have `CREATEDB`. That
means `pytest-django`, which creates a fresh `test_*` database before each
test run, fails immediately against Supabase. The workarounds are:

- Grant CREATEDB — impossible on Supabase free.
- Pre-create a `test_*` database via the Supabase SQL editor — not
  reliable across free-tier projects; some reject `CREATE DATABASE`
  entirely.
- **Run tests against local Postgres** — the option this proposal
  implements in the skeleton. Same engine, no quota consumption per
  test run, no cross-project schema drift. Open to reversal if the team
  finds a workable Supabase-only path.
- Run tests against a second Supabase project — burns a project per
  developer for the test database and still hits the same CREATEDB
  wall.

### Known risk: local vs. Supabase drift

The two databases are the same major version if the team keeps them in
sync — but that discipline is manual, not enforced. Bugs that only appear
against Supabase (extension differences, RLS being off, connection-pool
quirks, subtle version differences) can pass tests locally.

**Proposed mitigation:** before each demo and before each sprint sign-off,
run through the golden-path acceptance criteria manually against the live
Supabase database. Do not treat green `pytest` output as sufficient
evidence that the demo will work.

### Version matching

Supabase currently provisions Postgres 15 or 17 depending on when a project
was created. Each developer should check their project's version and
install the matching major locally.

Check the Supabase project's version, either from the dashboard's Database
Settings page or by running in the SQL editor:

```sql
SHOW server_version;
```

Then install a matching major locally. Instructions in the README (§ Setup
steps).

### Connection settings

- **Pooler mode:** session pooler (port 5432). Transaction pooler (port
  6543) breaks Django's implicit prepared statements and long-lived
  connections.
- **SSL:** Supabase URL should end with `?sslmode=require`. Local Postgres
  URL leaves `sslmode` off (defaults to `prefer`).
- **`CONN_MAX_AGE`:** 60 seconds. Safe under the session pooler.
- **`CONN_HEALTH_CHECKS`:** True. Handles Supabase's pause-on-inactivity
  behaviour without surfacing as a 500.

---

## 13. `.gitignore` minimum

```
.env
.env.*
!.env.example
.venv/
venv/
media/
staticfiles/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.coverage
htmlcov/
*.log
.DS_Store
.idea/
.vscode/
```

`!.env.example` re-includes the template after the `.env*` wildcard hides
real env files. `staticfiles/` is Django's `collectstatic` target. All
other entries are the standard Python/pytest hygiene set.

---

## 14. UI conventions

Hand-off for Stories 7–13. Rules below are what the stylesheet already
assumes; do not re-decide them on a per-page basis. Stylesheet lives at
`apps/common/static/css/inspectiq.css`; load it with
`{% static 'css/inspectiq.css' %}` in `base.html` (already wired).

### 14.1 Palette — six tokens

| Token            | Hex      | Use for                                                        |
|------------------|----------|----------------------------------------------------------------|
| `--iq-paper`     | `#F7F5EF`| Page background. Warm off-white. Never pure white.             |
| `--iq-ink`       | `#17171C`| Primary text, strong buttons, active N/A outcome.              |
| `--iq-rule`      | `#2B2B30`| Strong borders — card edges, button borders, section rules.    |
| `--iq-rule-faint`| `#D6D1C4`| Hairlines — table-row dividers, in-card separators.            |
| `--iq-stamp`     | `#A3202C`| **Consequences only.** FAIL outcome; ticket deadline; overdue state; validation-error borders. |
| `--iq-mark`      | `#2E5339`| **Recorded passes only.** PASS outcome.                        |

**Restrictions, hard rules:**

- **`--iq-stamp` is reserved for consequences.** Failures, open-ticket indicators, deadlines passed or near, validation errors (on the row with the problem). It must **never** appear on a secondary button, a success message, an "Add" button, or a nav link, no matter how much a page needs a highlight. Dilution kills the signal across the whole product. If a button needs weight, use `.btn-primary` (ink-filled); if a section needs separation, use a rule, not colour.
- **`--iq-mark` is reserved for recorded passes.** It is the opposite of `--iq-stamp`. Do not use it for success toasts, "Save" buttons, confirmed-anything else. A pass is quiet.
- **Everything else is ink on paper.** Buttons, nav, body prose, status labels, timestamps. If you're reaching for a third accent colour, you're reaching for the wrong tool — rework the hierarchy with weight, border, or typography instead.

### 14.2 Typography — three faces, one family (IBM Plex)

Loaded from Google Fonts in `base.html`. Do not add a fourth typeface.

| Face                | CSS                                       | Use for                                                                |
|---------------------|-------------------------------------------|------------------------------------------------------------------------|
| **IBM Plex Serif**  | `font-family: 'IBM Plex Serif', Georgia, serif;` | Page titles (`<h1>`), section titles (`<h2>`), store names in queue/standing rows, **the deadline date on a ticket** — and nothing else. |
| **IBM Plex Sans**   | `font-family: 'IBM Plex Sans', system-ui, sans-serif;` | Body prose, buttons, form fields, dashboard content, nav items. The default — don't declare it unless overriding. |
| **IBM Plex Mono**   | `font-family: 'IBM Plex Mono', monospace;` | Checklist item codes (`FS-01`), status labels (`SCHEDULED`, `OPEN`), timestamps, ticket IDs, letterhead field labels. Always uppercase with `letter-spacing: 0.08em–0.1em`. |

**Rule:** serif is the strongest typographic signal in the product. Reserve it for things that carry weight. If you find yourself using serif inside a table cell, you've over-promoted it.

### 14.3 Layout rules — easy to break by accident

- **Flush-left for everything.** No centered content, no centered page titles. Public documents are flush-left; centering is a wedding-invitation signal.
- **`border-radius: 0`.** The stylesheet forces this. Do not re-enable rounded corners with `.rounded-*` Bootstrap utility classes.
- **No shadows anywhere.** Do not add `box-shadow`, do not use Bootstrap's `shadow-*` utilities.
- **Rules, not cards.** Sections are separated by horizontal rules (`<hr class="iq-section-rule">`, `.iq-section-title` with its own bottom border, or `border-bottom` on list items). Not floating `<div class="card">` elements.
- **Spacing scale:** 4 / 8 / 16 / 24 / 32 / 48 px. Nothing in between. Prefer margin and padding over Bootstrap's spacer utilities when they fit cleanly in the scale.
- **Container:** every page's content lives inside `main.iq-container` (already in `base.html`). Max-width 960px, flush-left on wider screens.

### 14.4 Component classes — reuse before invent

One-line reference. If none of these fits what you're building, add a new one in `inspectiq.css` **and** add a row here.

| Class                | For                                                                                       |
|----------------------|-------------------------------------------------------------------------------------------|
| `.iq-strip`          | The ink header strip at the top of every page. Lives in `base.html`'s `{% block navbar %}`. |
| `.iq-container`      | The main content column. Max 960px, flush-left. Wrap page content inside `main.iq-container`. |
| `.iq-letterhead`     | The `<dl>`-based FROM/TO/DATE/SUBJECT block at the top of the owner dashboard and (in Story 11) the ticket detail page. |
| `.iq-standing`       | The `<ul>` of per-store status lines on the owner dashboard. Each `<li>` carries a store on the left, a mono status on the right. Status gets `.iq-standing__state--open` (stamp colour) when something is unresolved. |
| `.iq-queue`          | The `<ul>` of inspection rows on the inspector dashboard, with four slots per row (when / store+address / status / action). In Story 10 the ticket list reuses this layout. |
| `.iq-empty`          | Empty-state block (bordered top-and-bottom, serif headline, muted sub). See §14.5 voice rules. |
| `.iq-error-banner`   | Stamp-bordered banner at the top of a form that failed validation. Contains an `<h2>` and a list of anchor links to the specific rows that need attention. |
| `.iq-row-card`       | A single row on the conduct form. Modifiers: `.iq-row-card--error` (thick stamp left border + row-top strip), `.iq-row-card--recorded` (title muted, standard details collapsed). |
| `.iq-outcome-btn`    | The three outcome buttons inside `.iq-outcome`. Variants `--pass` / `--fail` / `--na` style the checked state. |
| `.iq-deadline`       | Bordered block titled "DEADLINE" with a serif date inside. **The only place in the product a date renders in serif.** See §14.5 for use. |
| `.iq-chip`           | Inline mono-uppercase status label. Modifier `.iq-chip--stamp` for stamp colour. See §14.5 for rules. |
| `.iq-section-title`  | A section heading styled as uppercase mono with a 2px rule beneath it. For subsidiary sections on a page. |
| `.iq-form-column`    | Form-only pages (login, register, add store, schedule inspection). 480px max-width, flush-left. |

Utilities also in the sheet: `.iq-section-rule` (horizontal rule), `.iq-sr-only` (visually hidden but screen-reader readable), `.iq-mono` (mono+uppercase inline).

### 14.5 What your stories will need

**Stories 7 and 8 — comment and photo on `.iq-row-card`**

Both extensions live **inside** each row's `.iq-row-card`, **below** the `.iq-outcome` div, **outside** the `<details>` standard disclosure. Shape:

```html
<article class="iq-row-card ...">
    …code / title / <details>Standard / .iq-outcome…
    <div class="iq-row-detail">              {# new wrapper, add to stylesheet #}
        <label for="…-comment">Comment</label>
        <textarea ... class="iq-input"></textarea>   {# existing form field styles cover this #}
        <label for="…-photo">Photo</label>
        <input type="file" ... class="iq-file" />
    </div>
</article>
```

- The comment field and photo input show up **only when the row's outcome is FAIL**. For Story 7 you can gate this at template level (`{% if form.outcome.value == "FAIL" %}`) — no JavaScript required.
- Required-on-FAIL errors use the same `.iq-row-card--error` / `.iq-row-error-strip` machinery that already exists for AC 6.3. Add the error code to the form's `clean()` so a specific error label can be shown.
- Add a `.iq-row-detail` class to the stylesheet when you ship this, matching the row's internal spacing (16px padding, 1px `--iq-rule-faint` top border).
- Form `<form method="post" enctype="multipart/form-data" ...>` on the conduct template once a file input exists (Story 8). Don't add `enctype` until it does.

**Story 11 — ticket detail with `.iq-deadline`**

Markup pattern:

```html
<div class="iq-deadline">
    <span class="iq-deadline__label">Deadline</span>
    <p class="iq-deadline__date">{{ ticket.deadline|date:"l, j F Y" }}</p>
    <span class="iq-deadline__sub">{{ ticket.deadline|days_remaining }}</span>
</div>
```

- The `days_remaining` filter **does not exist yet.** It's your filter to write (in `apps/common/templatetags/`). Return `"15 DAYS REMAINING"` for a future date, `"OVERDUE — 3 DAYS PAST"` for a past date, `"DUE TODAY"` for today. Uppercase, no period. The stylesheet already colours the sub-line stamp-red; your filter returns the text.
- Date format is long form (`"l, j F Y"` → "Tuesday, 20 October 2026"). Short-form ISO dates belong on bookkeeping rows, not here. The point of this block is to look like a date on a letter.
- Only one `.iq-deadline` per page. The deadline is the single most consequential date in the product — do not render two side-by-side.

**Stories 10–13 — status chips with `.iq-chip`**

Use for inline status labels in list rows and tables (ticket list, evidence review queue):

```html
<span class="iq-chip">Pending</span>
<span class="iq-chip iq-chip--stamp">Rejected</span>
```

**Rule:** a status chip must **always** carry a word. Never colour alone. A chip without a word is a bug. Reasons:

- Printed inspection records are often monochrome photocopies — colour disappears.
- Colour-blind inspectors and owners read the word.
- An accessible screen reader reads the text node; a background colour is invisible to it.

If you need to distinguish three or more statuses, use the word plus (optionally) a glyph prefix (`✓ Accepted`, `✕ Rejected`, `— Pending`). Match the pattern established in `.iq-outcome-btn`.

**Every list page needs an empty state**

Use `.iq-empty`. Voice is uniform across the product:

- **Declarative sentences.** Period at the end.
- **No exclamation marks.** Not ever. This is a public-service product.
- **No emoji.** Not ever.
- **No second-person cheer.** Not "You're all caught up!" — write what is true ("No open tickets.") or what to do next ("A store must be on file before an inspection can be scheduled.").
- Pattern: a `.iq-empty__headline` with the statement in serif, then (optional) a `.iq-empty__sub` in muted sans with the follow-up action if there is one.

Three varieties by role:
- **Statement of record** ("No stores on file.", "No open tickets.") — closes with a short clarifying sub-line if useful; no CTA inside the block.
- **Invitation to one action** — one and only one `.btn-primary` *below* the `.iq-empty` block (not inside it). Keeps the empty-state block uniform.
- **Confirmation of good standing** ("Your establishments are in good standing as of 2026-10-05.") — Story 10's owner-dashboard pattern. Fully terminal, no action.

### 14.6 Load-bearing modern-CSS features

Two features of the stylesheet don't degrade gracefully. If a reviewer or demo laptop runs an older browser, these specific effects fall back:

- **`:has()` selector.** Used to style the three `.iq-outcome-btn` variants based on which `<input type="radio">` inside the label is `:checked`. Required: Safari 15.4+ (March 2022), Chrome 105+ (September 2022), Firefox 121+ (December 2023). On an older browser **selected outcome buttons will render identical to unselected buttons** — the native radio dot inside the hidden input will not be visible either (we `opacity: 0` it). The form still submits correctly; it's unusable for conducting but tests still pass. If you need to support older browsers, the fallback is to render a visible native radio inside each button and swap the current selector-based styling for a template-level `{% if radio.data.selected %}` adding a `.is-checked` class to the label.
- **`color-mix()` in `oklab`.** Used for the muted-text tokens `--iq-ink-60` and `--iq-ink-75`. Required: Safari 16.2+, Chrome 111+, Firefox 113+. On an older browser the muted text takes the browser default (usually inherits ink colour), reducing the visual hierarchy but not breaking anything.

Both features are standard baseline as of late 2025, so demo-day Chrome/Safari/Firefox on any laptop updated in the last two years is fine. **Don't debug "my radios all look identical" blind — check the browser version first.**

### 14.7 Supabase: Row Level Security is intentionally off

If you open the Supabase dashboard and see every one of our tables flagged as **"Unrestricted"** with a yellow warning, that is expected, not a defect. Do not enable RLS.

Reasons:
- We use Supabase as **a managed Postgres host only**. The Data API (PostgREST), the auto-generated REST endpoints, the JavaScript / Python / Dart client SDKs, Supabase Auth, Supabase Storage, and Realtime are **all unused**. Nothing talks to Postgres except our Django process, over the session-pooler connection, as the single `postgres.<project-ref>` role.
- Row-level security exists to protect multi-tenant data when the database is directly exposed to clients (which the Data API does). With no direct client access, RLS has no attack surface to protect against.
- **All access control lives in `visible_to()` manager methods and the `InspectorRequiredMixin` / `OwnerRequiredMixin` pair.** `Store.objects.visible_to(user)`, `Inspection.objects.visible_to(user)`, `InspectionResult.objects.visible_to(user)`, and (coming in Stories 10–13) `Ticket.objects.visible_to(user)` + `Evidence.objects.visible_to(user)` are the authoritative scoping. Views call these; Track C's `RoleScopedQuerysetMixin` will enforce the call at the view layer.
- Turning RLS on without migrating this logic into Postgres policies would **break every query** because the Django connection role would start getting filtered-out results it should see.

If a grader or a code-reviewer flags the "Unrestricted" warning: point them at this section.

---

*End of proposal. Please argue with any of it.*
