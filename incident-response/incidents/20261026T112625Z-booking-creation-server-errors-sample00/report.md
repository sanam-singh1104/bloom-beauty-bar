## Summary
`POST /api/bookings` returned HTTP 500 three times in the 10:33–11:26 UTC window. Two failures were at 10:48:23 and 10:48:28, which fired the alert. A third came at 11:17:04. All three raised `sqlalchemy.exc.OperationalError` from inside the `create_booking` span after about 5.0–5.3 s. In the same window, 6 requests returned 201 and 2 returned 422 (invalid contact, which is normal validation). The failures look intermittent, not a full outage. The ~5 s duration points to a database lock or connection timeout, not a code bug.

## Evidence
- Status counts: 201 ×6, 422 ×2, 500 ×3.
- Error logs: `Unhandled error: OperationalError` at 10:48:23, 10:48:28 and 11:17:04. Each matches a failed trace.
- All three failed traces have the same shape. The root `POST /api/bookings` span is 5021–5277 ms with `error.type=OperationalError`. The child `create_booking` span (`backend/app/main.py:80`) is 5018–5218 ms and carries the same error. So the time was spent inside the handler, in the DB calls, not in request parsing.
- All three failures were for `booking.service_id=1`. Service 1 is the only service in the failing traces, but I can't tell whether that is a pattern or just the most popular service.
- The 422s took 11–89 ms and are unrelated. Their `customer_contact` validation (`Booking rejected: invalid (customer_contact)`) is working as designed.
- The consistent ~5 s is the signature of a DB-level timeout. SQLite's default busy timeout is 5 s (`database is locked`). Postgres connect or statement timeouts would not normally land on 5.0 s so consistently.
- The code that can raise `OperationalError` in this path (`backend/app/sql_store.py`):
  - `:105-108` `get_service`, called from `main.py:82`. It is a read that opens a connection.
  - `:110-115` `create_booking`: `Session.begin()` at `:111`, `flush()` at `:114` (the INSERT), and the implicit commit when the `with` block exits at `:115`.
  - `:82` `create_engine(...)` uses default pooling and sets no `timeout`, `pool_pre_ping` or `pool_recycle`. A stale or dropped connection on Postgres would also surface as `OperationalError`.
- Pool exhaustion is unlikely. It would raise `sqlalchemy.exc.TimeoutError` after 30 s, not `OperationalError` after 5 s.
- The telemetry does not record the exception message, so the exact cause (locked, connection refused, SSL closed, and so on) is unconfirmed.

## Likely cause
1. **SQLite write lock contention (`database is locked`).** This is the most likely cause if the failing instance uses SQLite, as in compose with the `bloom-data` volume.
   - The 5 s duration matches the default busy timeout.
   - Writes from the FastAPI threadpool (`sql_store.py:78-79`, `check_same_thread=False`) serialize on one file. A concurrent write, such as another booking, a cancel (`:123-127`), or startup seeding (`:94`), can hold the lock.
   - Failures are sporadic and bursty: two within 5 s, then one 30 minutes later.
2. **Postgres connectivity problem on Render.** Examples are a free-tier DB pausing or restarting, idle connections dropped by the server, or a network blip. Stale pooled connections would raise `OperationalError`, and `create_engine` has no `pool_pre_ping` (`sql_store.py:82`). This is less likely given the exact 5 s timing, but it can't be excluded without the message or deployment target.
3. **Lower likelihood:** a read-only or full volume, or a permissions problem on the SQLite file or directory. That would normally fail every write, and 6 bookings succeeded, so it is unlikely.

## Impact
- At least 3 customers who tried to book in the window got a 500 after waiting about 5 s. Their bookings were not saved, assuming the transaction rolled back.
- Roughly 3 of 9 booking attempts that passed validation failed. About 6 succeeded, so booking is degraded, not down.
- Customers must retry. The 11:17 failure shows the issue is still recurring, not just a one-time burst.
- No data corruption is indicated, because failed transactions roll back. Staff list and cancel views were not covered by this alert, so their status is unknown.

## Mitigation and fix
**Immediate:**
- Ask customers or staff to retry the booking. Check whether the failures have stopped.
- If the target is Postgres, check the Render DB status and restart the web service to reset the pool.
- If the target is SQLite under compose, check for long-running writers and restart the backend.

**Recommended code and config fixes:**
- Add `pool_pre_ping=True` and a sensible `pool_recycle` to `create_engine` (`sql_store.py:82`). This fixes stale Postgres connections.
- For SQLite, raise the busy timeout via `connect_args["timeout"]` and enable WAL mode (`PRAGMA journal_mode=WAL`). This reduces lock contention.
- Catch `OperationalError` in `SqlStore.create_booking` and return a clean 503 with a retry hint instead of a bare 500. Optionally retry once, since the insert is idempotent-safe before commit.
- Put `get_service` and the insert in one session, or at least record which one failed. Separate child spans in `main.py:82` and `main.py:86` would show which DB step times out.
- Add a log field or span attribute with the DB dialect and the SQLAlchemy `OperationalError` class of the original error (not its message), which is allowed under the no-customer-data rule.

## Next steps
1. Confirm the environment and DB behind the failing instance (`DATABASE_URL` backend: sqlite or postgresql).
2. Check the app container or Render logs for the `OperationalError` traceback around 10:48:23, 10:48:28 and 11:17:04 UTC. It will show the message, such as `database is locked`, `server closed the connection unexpectedly`, or `could not connect`. Do not paste customer data from request logs.
3. Run this in Grafana or Prometheus: `sum by (http_response_status_code) (increase(http_server_request_duration_seconds_count{http_route="/api/bookings"}[5m]))`. Also check whether `GET /api/bookings` and `GET /api/services` show errors or slowness at the same times.
4. In Tempo, search `{ name="create_booking" && status=error }` and compare timestamps against concurrent requests. Look for overlapping booking or cancel writes around 10:48 and 11:17.
5. If it's Postgres, check the Render DB dashboard for restarts, connection limits, or maintenance windows at those times.
6. After deploying the fix, watch the alert and trace queries for a recurrence. Also run `py scripts/run_checks.py` and add an integration test for the 503 path before handing off to QA.