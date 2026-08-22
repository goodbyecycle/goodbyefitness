"""Social media bonus tracker data store.

One JSON file holds the bonus rates and a record per month. Everything the
page shows is derived from those two things — bonus is always recomputed
from the stored counts, never stored as a number that could drift.
"""

import json
import re
from pathlib import Path
from threading import Lock

DATA_DIR = Path(__file__).parent.parent
DATA_FILE = DATA_DIR / "bonus_data.json"

_LOCK = Lock()

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# group: "audience" = followers/subscribers, "reviews", "watch"
METRICS = [
    {
        "key": "youtube_subs",
        "label": "YouTube — Subscribers",
        "unit": "per new subscriber",
        "group": "audience",
        "decimals": 0,
        "defaultRate": 0.50,
    },
    {
        "key": "instagram_followers",
        "label": "Instagram — Followers",
        "unit": "per new follower",
        "group": "audience",
        "decimals": 0,
        "defaultRate": 0.25,
    },
    {
        "key": "facebook_followers",
        "label": "Facebook — Followers",
        "unit": "per new follower",
        "group": "audience",
        "decimals": 0,
        "defaultRate": 0.25,
    },
    {
        "key": "google_reviews",
        "label": "Google — Positive Reviews",
        "unit": "per new positive review",
        "group": "reviews",
        "decimals": 0,
        "defaultRate": 1.50,
    },
    {
        "key": "youtube_hours",
        "label": "YouTube — Hours Watched",
        "unit": "per additional hour",
        "group": "watch",
        "decimals": 1,
        "defaultRate": 1.00,
    },
]

METRICS_BY_KEY = {m["key"]: m for m in METRICS}


def default_rates():
    return {m["key"]: m["defaultRate"] for m in METRICS}


def load_data():
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text())
    else:
        data = {}
    data.setdefault("rates", {})
    data.setdefault("months", {})
    for key, rate in default_rates().items():
        data["rates"].setdefault(key, rate)
    return data


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2, sort_keys=True))


def valid_month(month):
    return bool(MONTH_RE.match(month or ""))


def shift_month(month, delta):
    """'2026-08' shifted by -1 is '2026-07'."""
    year, mon = int(month[:4]), int(month[5:])
    index = year * 12 + (mon - 1) + delta
    return "%04d-%02d" % (index // 12, index % 12 + 1)


def _coerce_count(value, decimals):
    if value in (None, ""):
        return None
    number = float(value)
    if number < 0:
        raise ValueError("counts cannot be negative")
    return round(number, decimals) if decimals else int(round(number))


def get_rates():
    return load_data()["rates"]


def set_rates(new_rates):
    """Set bonus rates. Unknown keys are rejected; missing keys keep their value."""
    with _LOCK:
        data = load_data()
        for key, value in (new_rates or {}).items():
            if key not in METRICS_BY_KEY:
                raise ValueError("unknown metric: %s" % key)
            rate = float(value)
            if rate < 0:
                raise ValueError("rates cannot be negative")
            data["rates"][key] = round(rate, 4)
        save_data(data)
        return data["rates"]


def save_month(month, values, editor=None):
    """Store the counts for one month. `values` is {metric_key: {prev, curr}}."""
    if not valid_month(month):
        raise ValueError("month must look like 2026-08")
    with _LOCK:
        data = load_data()
        record = data["months"].get(month, {})
        stored = record.get("values", {})
        for key, entry in (values or {}).items():
            metric = METRICS_BY_KEY.get(key)
            if metric is None:
                raise ValueError("unknown metric: %s" % key)
            slot = dict(stored.get(key, {}))
            for field in ("prev", "curr"):
                if field in (entry or {}):
                    slot[field] = _coerce_count(entry[field], metric["decimals"])
            stored[key] = slot
        record["values"] = stored
        if editor:
            record["updatedBy"] = editor
        data["months"][month] = record
        save_data(data)
    return compute_month(month)


def set_paid(month, paid, paid_on=None, editor=None):
    if not valid_month(month):
        raise ValueError("month must look like 2026-08")
    with _LOCK:
        data = load_data()
        record = data["months"].setdefault(month, {})
        record["paid"] = bool(paid)
        record["paidOn"] = paid_on if paid else None
        if editor:
            record["paidBy"] = editor if paid else None
        data["months"][month] = record
        save_data(data)
    return compute_month(month)


def compute_month(month, data=None):
    """Build the full month view: one row per metric plus the payout summary.

    A month with no `prev` entered carries forward the previous month's
    `curr`, so counts only ever have to be typed once.
    """
    if not valid_month(month):
        raise ValueError("month must look like 2026-08")
    data = data or load_data()
    rates = data["rates"]
    record = data["months"].get(month, {})
    values = record.get("values", {})
    carried = data["months"].get(shift_month(month, -1), {}).get("values", {})

    rows = []
    for metric in METRICS:
        entry = values.get(metric["key"], {})
        prev = entry.get("prev")
        carried_prev = False
        if prev is None:
            prev = carried.get(metric["key"], {}).get("curr")
            carried_prev = prev is not None
        curr = entry.get("curr")
        prev_number = prev or 0
        curr_number = curr or 0
        gain = round(curr_number - prev_number, 1)
        rate = rates.get(metric["key"], metric["defaultRate"])
        rows.append({
            "key": metric["key"],
            "label": metric["label"],
            "unit": metric["unit"],
            "group": metric["group"],
            "decimals": metric["decimals"],
            "prev": prev,
            "curr": curr,
            "carriedPrev": carried_prev,
            "gain": gain,
            "rate": rate,
            "bonus": round(max(0.0, gain) * rate, 2),
        })

    def bonus_for(group):
        return round(sum(r["bonus"] for r in rows if r["group"] == group), 2)

    return {
        "month": month,
        "rows": rows,
        "totalBonus": round(sum(r["bonus"] for r in rows), 2),
        "summary": {
            "audienceGain": round(sum(r["gain"] for r in rows if r["group"] == "audience"), 1),
            "audienceBonus": bonus_for("audience"),
            "watchBonus": bonus_for("watch"),
            "reviewsBonus": bonus_for("reviews"),
        },
        "paid": bool(record.get("paid")),
        "paidOn": record.get("paidOn"),
        "paidBy": record.get("paidBy"),
        "updatedBy": record.get("updatedBy"),
    }


def list_months():
    """Every month that has data, newest first, with its total."""
    data = load_data()
    out = []
    for month in sorted(data["months"], reverse=True):
        if not valid_month(month):
            continue
        view = compute_month(month, data)
        out.append({
            "month": month,
            "totalBonus": view["totalBonus"],
            "paid": view["paid"],
            "paidOn": view["paidOn"],
        })
    return out


def month_csv(month):
    """The two-tab spreadsheet, flattened into one CSV."""
    view = compute_month(month)
    lines = ["Goodbye Fitness — Social Media Bonus,%s" % month, ""]
    lines.append("Account / Metric,Previous Month,Current Month,Gain,Rate,Bonus")
    for row in view["rows"]:
        lines.append("%s,%s,%s,%s,%.2f,%.2f" % (
            row["label"].replace(",", " "),
            "" if row["prev"] is None else row["prev"],
            "" if row["curr"] is None else row["curr"],
            row["gain"], row["rate"], row["bonus"],
        ))
    summary = view["summary"]
    lines += [
        "",
        "Bonus payout summary",
        "Total gain across follower/subscriber rows,%s" % summary["audienceGain"],
        "Bonus from followers & subscribers,%.2f" % summary["audienceBonus"],
        "Bonus from YouTube hours watched,%.2f" % summary["watchBonus"],
        "Bonus from Google positive reviews,%.2f" % summary["reviewsBonus"],
        "Total bonus owed this period,%.2f" % view["totalBonus"],
        "Paid,%s" % ("yes on %s" % view["paidOn"] if view["paid"] else "no"),
    ]
    return "\n".join(lines) + "\n"
