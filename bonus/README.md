# Social media bonus tracker

A private page at **`/bonus`** on goodbyefitness.com: the same two-part
spreadsheet — monthly tracker plus payout summary — but shared, so both
logins see the same numbers.

## Getting it running

On the server (the machine that runs `server.py`):

```
git pull                                  # or check out the branch
pip install -r requirements.txt
python tools/bonus_setup.py init          # create the two logins
# restart the server — e.g. ./start-server.sh
```

Then open `/bonus` and sign in. Website visitor counting works immediately;
the three social connections need credentials (below) and can be added later,
one at a time, without touching anything else.

`python tools/bonus_setup.py check` prints what's set up and what isn't —
dependencies, logins, cookie mode, each connection, and the rates in force.
Run it any time something looks wrong.

## What it does

| | |
|---|---|
| Tracker | One row per account/metric: previous month, current month, gain, bonus |
| Summary | Gain and bonus split by group, total owed, paid / unpaid |
| History | Every saved month with its total, newest first |
| YouTube | Subscribers and hours watched pulled straight from the channel |
| Instagram | Follower count, snapshotted nightly |
| Facebook | Follower count, snapshotted nightly |
| Google | Positive reviews (four stars and up), counted from the review dates |
| Website | Visitors to goodbyefitness.com, counted by the site itself |
| Nightly | Everything re-syncs on its own at 03:15, unattended |

Rates as configured: YouTube subscribers $0.50, Instagram $0.25, Facebook
$0.25, Google positive reviews $1.50, YouTube hours watched $0.50 per hour.
Bonus is paid on the **gain over the previous month** and is floored at $0
when a metric declines. Previous-month figures carry forward automatically,
so each number is typed once.

Any row can instead be set to pay on **the month's own total** — pick it under
"Paid on" in the rates panel. The difference matters most for hours watched:
on *gain*, 2,150 hours last month and 2,480 this month pays $165; on *total*,
it pays $1,240.

## Connecting Instagram and Facebook

The two are tracked as separate accounts throughout — separate rows, separate
sync buttons, separate bonus figures, and either can be synced without the
other. The one thing they share is the sign-in: Meta only grants Instagram
access through the linked Facebook Page, so connecting is a single
authorisation covering both.

One Meta app covers both. The Facebook Page's follower count comes from the
Page itself; Instagram's comes through the Instagram Business account linked
to that Page.

Meta reports only what the counts are **right now** — there's no dependable
historical follower series — so the server snapshots both counts every night
and a month closes on its last snapshot. Follower history therefore starts the
day you connect, not before. Until a month has a snapshot, the sync says so and
leaves the row empty rather than guessing.

Requirements:

- The Instagram account must be a **Professional** (Business or Creator)
  account, linked to the Facebook Page.
- You must be an admin of the Page.

At [developers.facebook.com](https://developers.facebook.com/):

1. Create an app (type: Business).
2. Add the **Facebook Login** product, with redirect URI
   `https://goodbyefitness.com/callback/meta`.
3. Keep the app in Development mode — as its admin you can use
   `pages_read_engagement` and `instagram_basic` without Meta's App Review.
4. Set the credentials on the server and restart:

```
export META_APP_ID=...
export META_APP_SECRET=...
export META_REDIRECT_URI=https://goodbyefitness.com/callback/meta   # optional
export META_API_VERSION=v21.0                                      # optional
```

Then sign in as admin and hit **Connect**. If the account manages more than one
Page, the one with an Instagram account attached is chosen and the others are
listed on the page.

**The sign-in expires after about 60 days.** The page warns when there are ten
days or fewer left — hit Reconnect. If it lapses, the sync fails loudly and the
rows can still be typed in.

## Connecting Google reviews

Reviews carry the date they were written, so this connection can work out any
month **exactly** — including months from before it was ever connected. Every
review is fetched, grouped by the month it was left, and a "positive" review is
one of **four or five stars**.

The row is kept as a running total: the previous-month figure is the count of
positive reviews up to the end of that month, so the gain is precisely the
positive reviews received during the month.

**Google gates this API.** Reading reviews needs the Google Business Profile
APIs, which Google grants per project on request — approval takes days to
weeks, so start it early. Until it is granted the calls come back 403 and the
page says exactly that rather than showing zeros.

1. Request access: fill in the Business Profile APIs form linked from
   [the prerequisites page](https://developers.google.com/my-business/content/prereqs),
   using the same Google Cloud project as YouTube.
2. Once granted, enable in that project: **My Business Account Management API**,
   **My Business Business Information API**, and **Google My Business API**
   (the last one serves reviews).
3. Add `https://goodbyefitness.com/callback/google-reviews` as a redirect URI on
   the OAuth client.
4. Set the credentials — or skip this if you're reusing the YouTube ones, which
   the code falls back to automatically:

```
export GOOGLE_BUSINESS_CLIENT_ID=...
export GOOGLE_BUSINESS_CLIENT_SECRET=...
export GOOGLE_BUSINESS_REDIRECT_URI=https://goodbyefitness.com/callback/google-reviews   # optional
```

Then sign in as admin and hit **Connect**. The first listing on the account is
used; any others are listed on the page.

## Website visitors

The site counts its own traffic — no Google Analytics, no third-party script,
no tracking cookie. Every public page request is counted; the tracker's own
pages, the API, static assets, and anything that looks like a bot are not.

Unique visitors are counted per day: the visitor's IP and user agent are
hashed with a salt that is regenerated each day and thrown away when the day
rolls over, so nothing on disk can be tied back to a person. Raw addresses are
never written down.

The **Website — Visitors** row starts at a rate of **$0.00**, so it tracks
without paying anything. Set a rate in the rates panel when you agree one.

## Nightly sync

At 03:15 every night the server syncs the current month from YouTube, from
Instagram and Facebook, from Google reviews, and from the site's own visitor
counts. For the first five days of a month it refreshes
the previous month too, because YouTube's analytics lag a day or two and a
month isn't final on the 1st. Failures are logged and swallowed — a broken
sync never takes the page down, and everything can still be entered by hand.

- `BONUS_AUTOSYNC=0` turns the nightly sync off.
- `BONUS_AUTOSYNC_HOUR=3` moves it (server local time, minute is fixed at 15).

The page shows when it last ran, under Connected accounts.

## Connecting YouTube

Once connected, `Sync this month` fills in the two YouTube rows from the
channel's own analytics. Subscribers come from `subscribersGained` minus
`subscribersLost` — the exact net figure, since Google rounds the public
subscriber *count* to three significant figures. Hours watched come from
`estimatedMinutesWatched`. Rows filled by a sync are tagged **auto**; a sync
never overwrites a row someone typed by hand unless it is forced.

In [Google Cloud Console](https://console.cloud.google.com/):

1. Create a project.
2. Enable **YouTube Analytics API** and **YouTube Data API v3**.
3. Configure the OAuth consent screen (External, and add the channel's Google
   account as a test user unless the app is published).
4. Create an **OAuth client ID** of type *Web application* with the redirect
   URI `https://goodbyefitness.com/callback/youtube`.
5. Set the two values on the server and restart:

```
export YOUTUBE_CLIENT_ID=...apps.googleusercontent.com
export YOUTUBE_CLIENT_SECRET=...
export YOUTUBE_REDIRECT_URI=https://goodbyefitness.com/callback/youtube   # optional, this is the default
```

Then sign in on the page as admin and hit **Connect YouTube**. Only an admin
can connect or disconnect; either login can run a sync.

The very first sync has nothing to anchor the running subscriber total on, so
it works back from YouTube's rounded public count and says so — set the
starting figure by hand if you know it exactly. Every month after that moves
by exact deltas.

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
- `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REDIRECT_URI` — see
  **Connecting YouTube** above. Without them the page shows setup instructions
  instead of a Connect button.

## Files

| Path | |
|---|---|
| `bonus.html` | The page (login + tracker), served at `/bonus` |
| `bonus/store.py` | Rates, months, and all bonus arithmetic |
| `bonus/auth.py` | Password hashing, lockout after 5 failed attempts, session key |
| `bonus/youtube.py` | Google OAuth, the Analytics query, and the month sync |
| `bonus/meta.py` | Meta OAuth, nightly follower snapshots, and the month sync |
| `bonus_meta.json` | Meta tokens and daily follower counts (gitignored, mode 600) |
| `bonus/google_reviews.py` | Google OAuth, review fetching, and the month sync |
| `bonus_google.json` | Google tokens and per-month review counts (gitignored, mode 600) |
| `bonus/traffic.py` | Website visitor counting and its month sync |
| `bonus_traffic.json` | Daily views and visitors (gitignored) |
| `bonus_youtube.json` | OAuth tokens (gitignored, mode 600) |
| `bonus_data.json` | The saved months and rates (gitignored — this is the real data) |
| `tools/bonus_user.py` | Create and manage the logins |
| `tools/build_bonus_tracker.py` | Builds the standalone .xlsx version |
| `tests/test_bonus.py` | Store, auth, and API tests |
| `tests/test_bonus_youtube.py` | Sync mapping, overwrite rules, OAuth routes |
| `tests/test_bonus_traffic.py` | Visitor counting, bot filtering, nightly sync |
| `tests/test_bonus_meta.py` | Page selection, snapshots, month close, OAuth routes |
| `tests/test_bonus_google.py` | Review grouping, running totals, paging, OAuth routes |

## Security notes

- Every `/api/bonus/*` route requires a login; writes also require the CSRF
  token handed out by `/api/bonus/me`.
- Session cookies are HttpOnly, SameSite=Lax, and Secure unless `BONUS_DEV=1`.
- Five wrong passwords lock that username for 15 minutes.
- Rate changes and marking a month paid are admin-only.
- Serve the site over https — the login is only as private as the connection.
- YouTube is authorised read-only (`yt-analytics.readonly`, `youtube.readonly`)
  and the OAuth callback checks a `state` value tied to the session.
- Visitor counting stores no raw IP addresses and sets no cookies.
- Meta is authorised read-only (`pages_read_engagement`, `instagram_basic`) and
  its callback checks a `state` value tied to the session.
- Google reviews use `business.manage` — the only scope Google offers for
  reading reviews. Nothing in the tracker writes to the listing.
