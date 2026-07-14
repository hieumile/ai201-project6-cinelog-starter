# PR Response Doc — CineLog Watchlist Feature

## AI Usage
I used an AI assistant for orientation and hygiene, not for the design decisions:
- **Codebase orientation:** summarized `models.py`, `services/collection_service.py`,
  and `tests/test_collection.py` to learn the `verb_to_noun` naming, the
  query-existing-first deduplication pattern in `add_to_collection()`, and the
  pytest fixture structure (`app` / `sample_user` / `sample_film`) before writing
  any watchlist code.
- **Stress-testing Comments 4 and 5:** after drafting both design responses myself,
  I asked the AI "what counterargument would a careful reviewer raise, and what
  tradeoff am I not acknowledging?" For Comment 4 it pushed on watchlists revealing
  *intent* being more sensitive than a watched-history, which I already partly had —
  I expanded the "Tradeoff acknowledged" paragraph to tie the default explicitly to
  a per-entry opt-out. For Comment 5 it argued recency-first helps right after a
  batch-add; I folded that into the "Engagement" paragraph as the case for an
  explicit `?sort=` parameter rather than changing my default. The positions and
  reasoning are my own; the AI only surfaced gaps to check.
- **Hygiene:** verified the final `git log --oneline` against the Conventional
  Commits spec.

## Comment 1 — Rename
**What I did:** Renamed `save_to_watchlist()` to `add_to_watchlist()` in `services/watchlist_service.py` to match the project's `verb_to_noun` convention (`add_to_collection`, `remove_from_collection`). Searched the whole tree for `save_to_watchlist` and found exactly one other reference, the import and call in `routes/watchlist/watchlist.py`, and updated both. Also updated the function's docstring ("Save a film..." → "Add a film...") so it doesn't contradict its own name.
**How I verified:** Ran `grep -rn "save_to_watchlist" --include="*.py" .` before and after the change — zero remaining references after the rename. Confirmed `routes/watchlist/watchlist.py` still imports and calls the renamed function correctly, and re-ran the watchlist tests to confirm the endpoint still works end to end.

## Comment 2 — Deduplication
**What I did:** Followed `add_to_collection()`'s exact pattern in `services/collection_service.py`: added an `AlreadyInWatchlistError` exception (mirroring `AlreadyInCollectionError`), and in `add_to_watchlist()` query for an existing `WatchlistEntry` with the same `user_id`/`film_id` before creating a new one, raising `AlreadyInWatchlistError` if found. Also updated the `/watchlist/<user_id>/add` route to catch `FilmNotFoundError` (404) and `AlreadyInWatchlistError` (409) — the original route had no error handling at all, so both cases would have surfaced as unhandled 500s. This matches how `routes/collection.py` handles the same two errors for the collection endpoint.
**How I verified:** Added `test_add_to_watchlist_duplicate_raises` in `tests/test_watchlist.py`, modeled on `test_add_to_collection_duplicate_raises`: adds a film, adds it again, asserts `AlreadyInWatchlistError` is raised, and confirms exactly one row exists in the table afterward. Ran `pytest tests/ -v` — passes. Also exercised the route directly with the Flask test client: a second POST to `/watchlist/<user_id>/add` for the same film returns `409`, and a POST with a nonexistent `film_id` returns `404`.

## Comment 3 — Missing test
**What I did:** Created `tests/test_watchlist.py`, using `tests/test_collection.py`'s `app` / `sample_user` / `sample_film` fixtures as the template. Added `test_add_to_watchlist_nonexistent_film_raises`, the direct equivalent of `test_add_to_collection_nonexistent_film_raises` — calls `add_to_watchlist()` with a `film_id` that doesn't exist and asserts `FilmNotFoundError` is raised. I used the same UUID sentinel the collection test uses (`"00000000-0000-0000-0000-000000000000"`) so it stays valid against the post-refactor UUID `film_id`. Per `CONTRIBUTING.md`'s testing guidance ("include a test for the happy path, duplicate/conflict handling, and a nonexistent ID"), I also added `test_add_to_watchlist_creates_entry` and `test_add_to_watchlist_duplicate_raises` so `add_to_watchlist()` has the same coverage as `add_to_collection()`, plus `test_get_watchlist_returns_alphabetical` (documents the Comment 5 sort decision) and two tests for `remove_from_watchlist()` (see Stretch Features).
**How I verified:** Ran `pytest tests/ -v` — all 10 tests pass (4 collection + 6 watchlist). I also drove the HTTP layer through the Flask test client end to end with real UUID film IDs: `POST /add` → 201, duplicate → 409, nonexistent film → 404, `GET /watchlist/<user_id>` → 200 with the entry, `DELETE /remove` → 200, remove again → 404.

## Comment 4 — Default visibility
**My position:** Keep `public=True` as the default for new `WatchlistEntry` rows, but pair it with an explicit, easy way to opt out per-entry (see the follow-up note below).
**Reasoning:** CineLog bills itself as a "community film tracking app," and a watchlist is exactly the kind of data that makes a community feature useful: it's the signal other users would want to see to recommend films, find people with similar taste, or notice a friend is about to watch something they loved. If watchlists default to private, the feature launches essentially invisible — nobody builds a habit around a social feature that starts out looking empty to everyone else, and the "community" pitch doesn't get any evidence to prove itself. This also matches the norm in the closest real-world comparable products (Letterboxd's watchlist, Goodreads' "want to read" shelf): both default to visible-on-profile, specifically because want-to-consume lists double as the platform's discovery mechanism, not just personal bookkeeping.
**Tradeoff acknowledged:** A watchlist arguably reveals more about a user than their collection does — a `CollectionEntry` records something they already watched and (optionally) rated, i.e. a completed, evaluated fact, but a `WatchlistEntry` reveals *intent* — what someone is curious about before they've committed to it, which can be more personal (a niche interest, something tied to a sensitive topic, or just an unpolished/embarrassing pick) than their finished, curated history. Defaulting that to public risks surprising users who don't realize their curiosity is visible. I'm not dismissing this: it's the reason I think this default only holds up if paired with a visible, low-friction way to mark individual entries private. `WatchlistEntry.public` already exists as a column, but `add_to_watchlist()` and the `/watchlist/<user_id>/add` endpoint don't currently expose it as a caller-settable parameter — they always take the column default. I'd want to follow up by threading an optional `public` argument through `add_to_watchlist(user_id, film_id, public=True)` and the request body, so a user (or a future UI) can opt out per-entry instead of the default being silently unconfigurable.

## Comment 5 — Sort order
**My position:** Keep `get_watchlist()` sorted alphabetically by title (the current behavior), rather than switching to date-added, at least as the unconditional default.
**Reasoning:** A watchlist and a collection log are different mental models, even though they're both "date-added" data under the hood. `get_collection()` sorting newest-first makes sense because it's a diary — a record of what you did recently, where recency is the whole point. A watchlist is a queue of things you intend to do, and the way people actually use a "want to watch" list is to scan it and pick something, or to check whether a title is already on it before re-adding it or recommending it to a friend. Alphabetical order is what makes that scanning/lookup fast, especially once a list grows past a dozen or so entries — which is exactly when insertion order stops being useful and turns into scrolling.
**Engagement with reviewer's point:** @dev-lead's reasoning was "most users want to see what they added recently," and that's true for some sessions (e.g., someone who just spent ten minutes adding films from a "best of the decade" list probably does want those at the top for a bit). But I'd push back on treating that as the steady-state case: recency-first ordering means the films someone has wanted to watch the longest — arguably the ones most worth surfacing, since they've survived the longest without being watched or removed — get pushed to the bottom and quietly forgotten, which undermines the point of keeping a watchlist at all. Rather than picking one default that's wrong for the other use case, I'd propose adding an explicit `?sort=date_added|title` query parameter to `GET /watchlist/<user_id>` in a follow-up, defaulting to `title` (current behavior) so lookup stays fast, while giving people who just did a batch-add a one-click way to see their newest additions first. I haven't implemented the query parameter itself in this PR — flagging it here as the compromise I'd want to make instead of an either/or default, and I'm glad to build it if you'd rather have it in this PR than as a follow-up.

## Comment 6 — Rebase
**What conflicted:** Ran `git fetch origin` then `git rebase origin/main`. The dangerous part was a *silent* conflict git never flagged. Main's `refactor: migrate film IDs from integer to UUID` commit changed `Film.id`/`CollectionEntry.film_id` to UUIDs **and deleted the `WatchlistEntry` model entirely**, since main has no knowledge of the watchlist feature (the PR was still open). My feature commit added a `watchlist_entries` relationship line to `Film` on *different lines* from main's edits, so git's line-based 3-way merge applied that line cleanly with no `<<<<<<<` markers — and the rebase reported "Successfully rebased." But the result was broken: `Film.watchlist_entries` pointed at a `WatchlistEntry` class that main had removed, so `from models import Film, WatchlistEntry` in `services/watchlist_service.py` raised `ImportError` and the app wouldn't even start. This is the trap of a clean-looking rebase — no markers doesn't mean no conflict.
**How I resolved it:** I restored the `WatchlistEntry` model in `models.py`, but with `film_id` as `db.Column(db.String(36), db.ForeignKey("film.id"))` (UUID) instead of `db.Integer`, matching how main's refactor changed `CollectionEntry.film_id`. I deliberately wrote the service, routes, and tests to be ID-type-agnostic (they never hard-code an integer `film_id`, and the nonexistent-film test already used the UUID sentinel), so once the model was UUID-correct nothing else needed to change. This is the `fix: restore WatchlistEntry model with UUID film_id after main rebase` commit. (No `.gitignore` conflict occurred — main's `.gitignore` was already in place on the commit I rebased onto, and I did not add a second one on the branch.)
**How I verified no conflict remains:** `git log --merges --oneline origin/main..HEAD` returns nothing and `git merge-base --is-ancestor origin/main HEAD` succeeds — fully linear history, no merge commits. `python -c "import app; app.create_app()"` now imports cleanly. I re-ran `pytest tests/ -v` (all 10 pass) and drove the endpoints through the Flask test client with real UUID film IDs (add 201 / duplicate 409 / nonexistent 404 / get 200 / remove 200 / remove-again 404) to confirm the feature actually works post-rebase, not just that it imports.

## Stretch Features

**`remove_from_watchlist(user_id, film_id)`** — Added following the
`remove_from_collection()` pattern: a `NotInWatchlistError`, the service function
(look up the entry, delete it, `NotInWatchlistError` if it isn't there), and a
`DELETE /watchlist/<user_id>/remove` route that maps that error to 404. Covered by
`test_remove_from_watchlist_removes_entry` (happy path) and
`test_remove_from_watchlist_not_present_raises` (error path). Chosen because the
watchlist is a queue users curate over time — being able to remove a film once
they've watched it or lost interest is table stakes, and the collection service
already established the exact pattern to mirror.

## Commit History

Final linear history on top of `origin/main` (no merge commits — verified with
`git log --merges --oneline origin/main..HEAD`, which returns nothing):

```
fix: restore WatchlistEntry model with UUID film_id after main rebase
test: add watchlist service tests
feat: add remove_from_watchlist service function and endpoint
fix: add deduplication check to prevent duplicate watchlist entries
fix: rename save_to_watchlist to add_to_watchlist per naming convention
feat: add watchlist model relationship, service, and endpoints
```
<!-- Replace this block with a screenshot of `git log --oneline` before submitting
     (the docs commit that adds this file will appear as the tip / HEAD). -->

## PR Description

### What the watchlist feature does
Adds a per-user watchlist for films a user wants to watch later, mirroring the
existing collection feature. New REST endpoints under `/watchlist`:
- `GET /watchlist/<user_id>` — list the user's watchlist, sorted alphabetically by title
- `POST /watchlist/<user_id>/add` — add a film (`{ "film_id": "<uuid>" }`); 404 if the
  film doesn't exist, 409 if it's already on the list
- `DELETE /watchlist/<user_id>/remove` — remove a film (`{ "film_id": "<uuid>" }`); 404 if
  it isn't on the list

Backed by a `WatchlistEntry` model (UUID `film_id`, a `public` visibility flag, and
`date_added`) and an `add_to_watchlist` / `remove_from_watchlist` / `get_watchlist`
service that follows the project's `verb_to_noun` naming and query-existing-first
deduplication conventions.

### Design decisions
1. **Default visibility (`public=True`)** — New watchlist entries default to public,
   because CineLog is a community app and want-to-watch lists are its discovery signal
   (see Comment 4). The tradeoff — a watchlist reveals *intent*, which is more sensitive
   than watched history — is why the `public` column exists per-entry and why I'd follow
   up by exposing it as a caller-settable parameter.
2. **Sort order (alphabetical by title)** — `get_watchlist()` sorts alphabetically rather
   than newest-first, because a watchlist is a lookup/scan queue, not a diary (see
   Comment 5). I propose an explicit `?sort=date_added|title` parameter as the follow-up
   compromise rather than baking in one default that's wrong for the other use case.

### How to manually test
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# There are no user/film creation endpoints (films are seeded, read-only), so
# create a user and a film once to get real UUIDs to test with:
python - <<'PY'
from app import create_app, db
from models import User, Film
app = create_app()
with app.app_context():
    u = User(username="ada", email="ada@example.com")
    f = Film(title="Heat", year=1995, genre="Crime")
    db.session.add_all([u, f]); db.session.commit()
    print("USER_ID:", u.id)
    print("FILM_ID:", f.id)
PY

python app.py   # runs at http://127.0.0.1:5000 (no frontend; 404 at / is expected)

# In another terminal, using the printed IDs:
curl -X POST http://127.0.0.1:5000/watchlist/<USER_ID>/add \
     -H "Content-Type: application/json" -d '{"film_id": "<FILM_ID>"}'      # 201
curl -X POST http://127.0.0.1:5000/watchlist/<USER_ID>/add \
     -H "Content-Type: application/json" -d '{"film_id": "<FILM_ID>"}'      # 409 (duplicate)
curl http://127.0.0.1:5000/watchlist/<USER_ID>                             # 200, list
curl -X DELETE http://127.0.0.1:5000/watchlist/<USER_ID>/remove \
     -H "Content-Type: application/json" -d '{"film_id": "<FILM_ID>"}'      # 200
```
Or run the automated suite: `pytest tests/ -v` (10 tests pass).
