# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

## What this is

**Goodbye Fitness** — a single Flask process that serves three self-contained HTML
pages plus a JSON API, backed by flat JSON files on disk. There is **no build step,
no framework, no database, and no package manifest**. Every page is one hand-written
HTML file with inline `<style>` and inline `<script>`.

Two products live side by side in the same server:

1. **The consumer app** (`landing.html` + `index.html`) — public marketing page,
   Firebase email/password auth, activity logging, dog-walk program, GPS walk
   tracking, and optional fitness benchmarks (Garage Test, Cooper Test, cycling).
2. **Andrew's private MTB coaching dashboard** (`andrew.html` + `coach/`) — a
   calendar dashboard driven by a deterministic, rule-based coaching engine that
   recommends one workout per day from readiness data and training history.

The coaching engine is the substantive part of the codebase. Treat it as the
system of record for anything training-related.

## Layout

```
server.py                       Flask app: routes, Twilio SMS, Strava OAuth, scheduler
start-server.sh                 Andrew's local macOS launcher (see Gotchas — path is stale)
landing.html                    Public marketing page, served at /
index.html                      Consumer app (auth, logging, benchmarks), served at /app
andrew.html                     Private MTB coaching calendar, served at /andrew
user_data.json                  Consumer-app profile + Strava tokens (TRACKED IN GIT — see Gotchas)
g-icon.{png,svg}, canva-*.png   Brand assets

coach/
  engine.py                     recommend_workout() — the decision ladder + workout templates
  profile.py                    Athlete profile + get_unknowns()   -> athlete_profile.json
  readiness.py                  Manual morning check-in + scoring  -> checkins.json
  health.py                     Athlytic health-score entry        -> health_scores.json
  history.py                    Training-history providers (mock / Strava / Apple Health stub)
  trails.py                     Local MTB trail database + ranking -> trails.json
  schema.py                     Imperative validator for a calendar workout
  calendar-workout.schema.json  JSON Schema mirror of the same contract

tests/test_coach.py             All 49 tests, in one file
```

Runtime JSON data files (`checkins.json`, `health_scores.json`, `athlete_profile.json`,
`trails.json`, `uploads/`) are written to the **repo root** and are gitignored. Each
`coach/` module falls back to a hardcoded default when its file is absent, so a fresh
checkout works with no seeding.

## Running and testing

```bash
python3 server.py                 # http://localhost:8090  (honors $PORT)
python3 tests/test_coach.py       # runs all 49 tests, prints PASS lines
pytest tests/test_coach.py        # also works — plain asserts, no fixtures
```

Dependencies are **not declared anywhere** — no `requirements.txt`, no `pyproject.toml`.
The server needs `flask`, `requests`, `apscheduler`, and (lazily, only when SMS is
configured) `twilio`. Install them by hand if the environment lacks them. If you add a
dependency, say so explicitly in your summary; there is no manifest to update.

Environment variables, all optional (features degrade gracefully when unset):

| Variable | Purpose |
| --- | --- |
| `PORT` | Listen port (default `8090`; Render sets this) |
| `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REDIRECT_URI` | Strava OAuth |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` | Daily SMS nudges |
| `NOTIFY_EMAIL`, `NOTIFY_APP_PASSWORD` | Gmail SMTP signup notifications |

## The test file is script-shaped — read this before adding tests

`tests/test_coach.py` is both a pytest module and a standalone script, and the script
half is easy to break:

- Every test is listed **by name** in the `if __name__ == "__main__":` block at the
  bottom. A new test that isn't added there silently never runs under
  `python3 tests/test_coach.py`.
- The last line prints `=== ALL 49 TESTS PASSED ===`. **Update that count** when you
  add or remove a test.
- Tests share on-disk state. Anything touching `checkins.json` / `health_scores.json`
  must wrap its body in `try/finally` and call `_cleanup_checkins()` /
  `_cleanup_health()`, following the existing tests. Forgetting this leaks state into
  later tests and into the developer's real data files.
- Each test ends with `print("PASS: ...")`. Match that style.
- Frontend tests are **string assertions against the rendered HTML** — they
  `GET /andrew` and assert that identifiers like `attachCardClickHandlers`,
  `showDetailsModal`, `detailEdit`, `renderMonth`, and `data-eidx` appear in the
  source. Renaming a JS function or a DOM id in `andrew.html` will break tests in
  `tests/test_coach.py` even though no Python changed. Grep the test file before
  renaming anything in that page.

## The coaching engine

`coach/engine.py:recommend_workout(target_date, calendar_events)` is deterministic —
no LLM call, no randomness. It gathers inputs, walks a fixed priority ladder, fills a
template, validates against the schema, and returns
`{"recommendation": workout, "source": "coaching_engine"}`.

**Input blending.** Two independent readiness signals:

- `readiness.compute_readiness_score(checkin)` — manual morning check-in.
  Weighted `sleep 25 / energy 25 / soreness 20 / pain 15 / stress 15`, clamped 1–100.
  `pain >= 7` short-circuits to score `1`.
- `health.compute_health_readiness(health, yesterday_exertion)` — Athlytic screenshot
  data. `(recovery + sleep) / 2`, minus `(yesterday_exertion - 6) * 5` when yesterday's
  exertion was `>= 7`.

When both exist they blend **60% health / 40% check-in**; otherwise whichever exists is
used alone. The 75 / 50 / 30 label thresholds are duplicated in both modules — change
them together.

**Decision ladder**, evaluated top-down (first match wins):

1. A `locked` calendar event for that date → returned untouched, `source: "locked_calendar"`.
2. Readiness `< 30` → `rest_day`, confidence `high`.
3. Readiness `< 50` → `recovery_ride` (or `morning_mobility` on Sunday).
4. Yesterday had RPE `>= 7` → a non-hard workout. No back-to-back hard days.
5. Already `>= 2` hard days in the trailing 7 → a non-hard workout.
6. Otherwise → the day-of-week default from `_select_workout_for_day()`
   (Mon easy ride, Tue upper strength, Wed intervals, Thu mobility, Fri lower
   strength, Sat long endurance, Sun rest).

**History source.** `is_strava_connected()` decides. If Strava tokens are present the
engine pulls 42 days of real activities and maps them through `STRAVA_TYPE_MAP`,
estimating RPE from `suffer_score`, then average HR, then duration. Any failure falls
back to `MockHistoryProvider`, which synthesizes six weeks of plausible data. The
chosen source is reported in `dataQuality.inputsUsed` as `strava_training_history` or
`mock_training_history`.

**Trails.** For `mtb_ride` workouts the engine ranks trails from `coach/trails.py`
(five real SE-Michigan trails as defaults) and attaches the top match. Trails with
status `confirmed_closed` are excluded at both the search and ranking layers.

### Safety invariants — do not regress these

These are encoded in the engine and each has a test. If a change makes one of them
fail, the change is wrong, not the test.

- **Never invent athlete data.** Unknown benchmarks stay `null` and are surfaced in
  `dataQuality.unknowns` via `profile.get_unknowns()`. A missing check-in is itself
  listed as an unknown and drops `confidence` to `low`.
- **Never two hard days in a row**, and **never more than two hard days per week**.
- **Never recommend a `confirmed_closed` trail.**
- **Never overwrite a `locked` calendar event.**
- **`pain >= 7` means rest**, regardless of every other input.
- **Never prescribe unsafe mileage catch-up** to hit a weekly target.
- Every returned workout must carry a plain-language `explanation`, a `backup`
  option, and a `dataQuality` block.

### The workout schema is defined twice

`coach/schema.py` (imperative, actually enforced at runtime) and
`coach/calendar-workout.schema.json` (declarative, documentation) describe the same
object. **Keep both in sync** when adding or changing a field. `validate_workout()`
returns a list of error strings — empty means valid — and `recommend_workout()` returns
`{"error": "Schema validation failed", ...}` instead of a recommendation if it fails,
so a schema drift shows up as a broken endpoint, not a warning.

## HTTP API

Consumer app: `/api/notify/signup`, `/api/profile`, `/api/sms/{test,status,generate}`,
`/api/strava/{connect,status,activities,disconnect}`, `/callback/strava`.

Coaching dashboard, all under `/api/coach/`:

```
GET  /profile                 GET  /profile/unknowns      POST /profile
POST /checkin                 GET  /checkin/<date>        GET  /checkins/recent?days=7
POST /health                  GET  /health/<date>         POST /health/upload   (multipart image)
GET  /history?source=&days=   GET  /history/weekly?source=&weeks=
GET  /recommend?date=YYYY-MM-DD
GET  /trails                  GET  /trails/<id>           POST /trails/<id>/status
```

Conventions: JSON in, JSON out. Validation failures raise `ValueError` in the service
layer and are converted to `400` with `{"error": str(e)}` in the route. Missing records
return `404`. Success-only endpoints return `{"ok": true}`. Dates are always
`YYYY-MM-DD` strings.

## Frontend conventions

- **One file per page.** All CSS and JS is inline. No bundler, no npm, no imports.
  Do not introduce a build step or a framework without being asked.
- **Vanilla JS only**, except the Firebase compat SDK loaded from a CDN `<script>` tag
  in `index.html`.
- **Two distinct visual identities**, both driven by CSS custom properties on `:root`:
  `index.html` is a dark app theme (`--bg:#0a0a0a`, `--accent:#3b82f6`);
  `andrew.html` is a high-contrast blue/pink calendar (`--blue-bg:#4F9DFF`,
  `--pink:#FF4FA3`). Use the existing variables rather than hardcoding colors.
- **State lives in `localStorage`.** Keys are prefixed `ft_` in the consumer app
  (`ft_profile`, `ft_history`, `ft_training`, `ft_journal`, `ft_dog_profile`,
  `ft_dog_assessment`, `ft_dog_reminders`, `ft_spots`); the dashboard uses the single
  key `andrew_workouts`. The server is not the source of truth for consumer data.
- `andrew.html` **gates recommendations**: `Get Today's Recommendation` refuses to run
  until a morning check-in or a health score exists for the day, showing the
  `#checkinGate` message instead. Preserve that gate.
- Strava-sourced activities are **read-only** in the details modal — no Edit or Delete
  buttons. Locally created workouts get both.
- Escape closes modals; card clicks call `stopPropagation()` so they don't trigger the
  calendar cell's own navigation. All four view renderers (`renderMonth`, `renderWeek`,
  `renderThreeDay`, `renderDay`) must call `attachCardClickHandlers()` after rendering.
- User-supplied strings go through the `esc()` helper before interpolation into
  `innerHTML`.

## Code conventions

- Python: 4-space indent, double-quoted strings, module docstrings, section dividers
  written as `# ─── Section ───`. Services are plain functions over module-level file
  paths; there are no classes outside the `TrainingHistoryProvider` hierarchy.
- Private helpers are `_`-prefixed. Tests import several of them directly
  (`_count_recent_hard_days`, `_was_yesterday_hard`), so renaming them breaks tests.
- Imperial units throughout: miles, feet, mph. Strava's metric payloads are converted
  at the boundary in `server.py` and `coach/history.py` — keep conversions there.
- Prose in explanations and labels uses em dashes and is written to be read by the
  athlete, not by a developer.

## Gotchas

- **`user_data.json` is committed and contains live Strava OAuth tokens.** It is listed
  in `.gitignore`, but it was added to the index before that rule existed, so git still
  tracks it and every write to it shows up as a working-tree change. Do not commit
  further token updates. If you touch this file, flag it — the tokens in HEAD should be
  revoked and rotated, and the file removed from tracking with
  `git rm --cached user_data.json`.
- The Firebase web config in `index.html` is inline and public. That is normal for
  Firebase web apps (access is controlled by Firebase security rules, not by hiding the
  key), but do not add any server-side secret to a HTML file.
- `start-server.sh` hardcodes `/Users/andrewriley/.fitness-server` and `zsh` +
  Homebrew Python. It only works on Andrew's Mac and does not reflect the deployed
  setup. Run `python3 server.py` directly instead.
- `coach/history.py` uses `date.strftime("%s")` to build the Strava `after` timestamp.
  That is a platform-specific libc extension — it works on Linux and macOS, and would
  need replacing with `int(time.mktime(...))` if Windows ever matters.
- The APScheduler daily-SMS job only starts under `if __name__ == "__main__"`, so SMS
  scheduling does not run under a WSGI server. Test imports of `server` are safe
  because of this.
- There is no CI. Run the test suite locally before committing.

## Git workflow

Work on the branch you were assigned, commit with a clear message, and push with
`git push -u origin <branch>`. Do not push to `main`. Do not open a pull request unless
explicitly asked. Commit messages in this repo are short imperative summaries
("Add Athlytic health score entry with readiness integration").
