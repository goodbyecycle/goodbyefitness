# Social media bonus tracker

A private page at **`/bonus`** on goodbyefitness.com: the same two-part
spreadsheet — monthly tracker plus payout summary — but shared, so both
logins see the same numbers.

## What it does

| | |
|---|---|
| Tracker | One row per account/metric: previous month, current month, gain, bonus |
| Summary | Gain and bonus split by group, total owed, paid / unpaid |
| History | Every saved month with its total, newest first |
| Export | `Download CSV` gives the whole month in one file |

Rates as configured: YouTube subscribers $0.50, Instagram $0.25, Facebook
$0.25, Google positive reviews $1.50, YouTube hours watched $1.00 per hour.
Bonus is paid on the **gain over the previous month** and is floored at $0
when a metric declines. Previous-month figures carry forward automatically,
so each number is typed once.

## Setting up the two logins

Passwords are typed at a prompt and stored only as hashes, in
`bonus_users.json` (gitignored, mode 600):

```
python tools/bonus_user.py add andy --role admin --name "Andy"
python tools/bonus_user.py add jess --name "Jess"
python tools/bonus_user.py list
python tools/bonus_user.py password andy     # change a password
python tools/bonus_user.py remove jess
```

`admin` can change the bonus rates and mark a month paid. `member` can enter
and save the monthly numbers and see everything.

## Running it

Nothing new to install — it rides on the existing Flask server.

```
python server.py            # https, cookies marked Secure
BONUS_DEV=1 python server.py   # http on localhost during development
```

Optional environment variables:

- `BONUS_SECRET_KEY` — session signing key. Without it, one is generated and
  saved to `bonus_secret.key` (mode 600) so logins survive a restart.
- `BONUS_DEV=1` — drops the `Secure` flag on the session cookie. Development
  only; over plain http on a public host the session cookie is exposed.

## Files

| Path | |
|---|---|
| `bonus.html` | The page (login + tracker), served at `/bonus` |
| `bonus/store.py` | Rates, months, and all bonus arithmetic |
| `bonus/auth.py` | Password hashing, lockout after 5 failed attempts, session key |
| `bonus_data.json` | The saved months and rates (gitignored — this is the real data) |
| `tools/bonus_user.py` | Create and manage the logins |
| `tools/build_bonus_tracker.py` | Builds the standalone .xlsx version |
| `tests/test_bonus.py` | Store, auth, and API tests |

## Security notes

- Every `/api/bonus/*` route requires a login; writes also require the CSRF
  token handed out by `/api/bonus/me`.
- Session cookies are HttpOnly, SameSite=Lax, and Secure unless `BONUS_DEV=1`.
- Five wrong passwords lock that username for 15 minutes.
- Rate changes and marking a month paid are admin-only.
- Serve the site over https — the login is only as private as the connection.
