# HERMUS — Hardening List (deferred robustness work)

Items intentionally deferred from feature phases. Each is non-blocking for the
current build but should be addressed before heavy production load. Newest first.

---

## H-1 · Advisory lock on schedule claim (multi-process safety)
**Found:** Doc 29 §5.1b executor phase (scheduler_exec.py).
**Risk:** the executor's background tick selects due schedules and runs them. If
two backend processes run at once (e.g. a kill/restart overlap, or horizontal
scaling), both ticks can see the same row as due in the same window and
**double-fire** it (two reminders, two sends). Observed transiently during a
restart overlap in testing.
**Fix:** claim each due row atomically before running — `SELECT … FOR UPDATE
SKIP LOCKED` on the due set, or a Postgres advisory lock keyed by schedule id,
so only one worker runs a given schedule per tick. Single-process local desktop
is unaffected; this matters only when >1 backend can run concurrently.

## H-2 · Normalize `reminder.create` date input to tz-aware
**Found:** Doc 29 §5.1b (surfaced when a scheduled `reminder.create` got a naive `due_at`).
**Risk:** `reminder.create` compares `due < ctx.now`; a **naive** `due_at`
(ISO string with no timezone offset) raises "can't compare offset-naive and
offset-aware datetimes" → the tool hard-fails. The live `/assistant` path always
emits tz-aware ISO so it never triggers there, but a user/integration (or a
feature schedule) passing a naive datetime fails every run.
**Fix:** in `_parse_dt` (tier1_tools), attach UTC when the parsed datetime is
naive (`dt.replace(tzinfo=timezone.utc)`), so the tool is robust to either form.
Consider doing the same anywhere user-supplied datetimes are compared to `now()`.
