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

# group: "audience" = followers/subscribers, "reviews", "watch", "website"
# basis: "gain" pays on the increase over last month, "total" pays on the
# month's own figure. Everything defaults to "gain"; hours watched is the one
# that might reasonably be paid on the month's total instead.
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
        "key": "website_visitors",
        "label": "Website — Visitors",
        "unit": "per new visitor",
        "group": "website",
        "decimals": 0,
        # No rate agreed yet — the row tracks visitors and pays nothing until
        # someone sets one in the rates panel.
        "defaultRate": 0.00,
    },
    {
        "key": "youtube_hours",
        "label": "YouTube — Hours Watched",
        "unit": "per additional hour",
        "group": "watch",
        "decimals": 1,
        "defaultRate": 0.50,
    },
]

METRICS_BY_KEY = {m["key"]: m for m in METRICS}


BASES = ("gain", "total")


def default_rates():
    return {m["key"]: m["defaultRate"] for m in METRICS}


def default_bases():
    return {m["key"]: "gain" for m in METRICS}


def load_data():
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text())
    else:
        data = {}
    data.setdefault("rates", {})
    data.setdefault("bases", {})
    data.setdefault("months", {})
    for key, rate in default_rates().items():
        data["rates"].setdefault(key, rate)
    for key, basis in default_bases().items():
        data["bases"].setdefault(key, basis)
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


def get_bases():
    return load_data()["bases"]


def set_bases(new_bases):
    """Switch a metric between paying on the gain and paying on the month's total."""
    with _LOCK:
        data = load_data()
        for key, value in (new_bases or {}).items():
            if key not in METRICS_BY_KEY:
                raise ValueError("unknown metric: %s" % key)
            if value not in BASES:
                raise ValueError("basis must be one of: %s" % ", ".join(BASES))
            data["bases"][key] = value
        save_data(data)
        return data["bases"]


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


def save_month(month, values, editor=None, source="manual"):
    """Store the counts for one month. `values` is {metric_key: {prev, curr}}.

    `source` records who filled the row in — "manual" when someone typed it,
    or the name of the integration that synced it.
    """
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
            slot["source"] = source
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
    bases = data["bases"]
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
        basis = bases.get(metric["key"], "gain")
        payable = max(0.0, curr_number) if basis == "total" else max(0.0, gain)
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
            "basis": basis,
            "bonus": round(payable * rate, 2),
            "source": entry.get("source", "manual"),
        })

    def bonus_for(group):
        return round(sum(r["bonus"] for r in rows if r["group"] == group), 2)

    return {
        "month": month,
        "rows": rows,
        "totalBonus": round(sum(r["bonus"] for r in rows), 2),
        "summary": {
            "byMetric": {row["key"]: row["bonus"] for row in rows},
            "audienceGain": round(sum(r["gain"] for r in rows if r["group"] == "audience"), 1),
            "audienceBonus": bonus_for("audience"),
            "watchBonus": bonus_for("watch"),
            "reviewsBonus": bonus_for("reviews"),
            "websiteBonus": bonus_for("website"),
        },
        "paid": bool(record.get("paid")),
        "paidOn": record.get("paidOn"),
        "paidBy": record.get("paidBy"),
        "updatedBy": record.get("updatedBy"),
    }


def record_autosync(at, results):
    """Remember when the unattended sync last ran, and how it went."""
    with _LOCK:
        data = load_data()
        data["autosync"] = {"at": at, "results": results}
        save_data(data)
        return data["autosync"]


def get_autosync():
    return load_data().get("autosync")


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
