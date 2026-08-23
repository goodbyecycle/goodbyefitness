"""Andrew's own data must not be readable without the admin login.

These routes were public for the life of the site; this pins them shut.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from server import app  # noqa: E402

PRIVATE = ["/andrew", "/andrew.html", "/api/profile",
           "/api/coach/profile", "/api/coach/history", "/api/strava/status"]
PUBLIC = ["/", "/landing.html", "/app", "/nicki", "/bonus"]


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def admin(client):
    with client.session_transaction() as sess:
        sess["bonus_user"] = {"username": "a", "displayName": "A", "role": "admin"}
    return client


@pytest.fixture
def member(client):
    with client.session_transaction() as sess:
        sess["bonus_user"] = {"username": "n", "displayName": "N", "role": "member"}
    return client


@pytest.mark.parametrize("path", PRIVATE)
def test_private_routes_reject_a_stranger(client, path):
    res = client.get(path)
    assert res.status_code in (301, 302, 401), \
        "%s answered %s to an anonymous request" % (path, res.status_code)
    if res.status_code in (301, 302):
        assert "/nicki" in res.headers.get("Location", "")


@pytest.mark.parametrize("path", PRIVATE)
def test_private_routes_reject_nicki(member, path):
    """Her member login reaches the bonus tracker and nothing else."""
    res = member.get(path)
    assert res.status_code in (301, 302, 401)


@pytest.mark.parametrize("path", PRIVATE)
def test_admin_still_gets_through(admin, path):
    assert admin.get(path).status_code not in (301, 302, 401, 403)


@pytest.mark.parametrize("path", PUBLIC)
def test_public_pages_stay_public(client, path):
    assert client.get(path).status_code == 200


def test_oauth_callbacks_stay_reachable(client):
    """Providers redirect here unauthenticated; a login wall would break them."""
    assert client.get("/callback/strava").status_code != 401
