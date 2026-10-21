# Agent Team

Bloom Beauty Bar is built by three agent roles. Each has a clear job, and no
task is done until a role other than the one that built it has checked it.

## Roles

### Product Manager (PM)
Turns [product-spec.md](../product-spec.md) into tasks.
- Breaks features into small, independently shippable tasks.
- Writes testable acceptance criteria for each task, traced to the spec.
- Sets priority and order (e.g. data model and seeding before booking UI).
- Guards scope: rejects work that falls under the spec's non-goals.
- Answers questions about intent; updates the spec if a gap is found.

### Engineer
Implements tasks.
- Builds exactly what the task and its acceptance criteria describe.
- Follows the stack and conventions in [AGENTS.md](../AGENTS.md).
- Writes unit tests alongside the code and makes sure existing tests pass.
- Hands off with a short note: what changed, how to run it, anything QA
  should know.

### QA
Verifies tasks independently.
- Reads the acceptance criteria, not the Engineer's note, as the definition
  of done.
- Writes and runs integration tests (and extra unit tests where needed) that
  prove each criterion.
- Checks the failure cases too, e.g. a booking missing a required field is
  rejected with a clear message.
- Passes the task, or returns it to the Engineer with the failing criterion
  and steps to reproduce.

## Workflow

```
PM defines task  ->  Engineer implements  ->  QA verifies  ->  Done
                          ^                       |
                          +------ fails ----------+
```

1. **Define.** The PM writes the task: a title, the spec feature it serves,
   and acceptance criteria.
2. **Implement.** The Engineer builds it with unit tests and hands it off.
3. **Verify.** QA tests every acceptance criterion independently.
   - All pass: the task is done and can be merged.
   - Any fail: back to the Engineer with details. Repeat steps 2–3.
4. **Clarify.** If the Engineer or QA finds the criteria unclear or in
   conflict with the spec, it goes back to the PM rather than being guessed.

## Task template

```markdown
### <Task title>
Spec feature: <e.g. 2. Book an appointment>

Acceptance criteria:
- [ ] <observable, testable behaviour>
- [ ] <failure case>

Engineer notes: <what changed, how to run>
QA result: <pass / fail + details>
```
