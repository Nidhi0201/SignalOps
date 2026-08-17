"""Pure unit tests for the flap-damping decision core (no I/O)."""
from datetime import datetime, timedelta

import pytest

from app.alert_engine import decide

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 15, 12, 0, 0)


def _decide(**over):
    base = dict(
        breaching=True,
        has_open_incident=False,
        breach_streak=0,
        clear_streak=0,
        cooldown_until=None,
        for_consecutive=1,
        resolve_after_clear=2,
        cooldown_minutes=5,
        now=NOW,
    )
    base.update(over)
    return decide(**base)


def test_opens_immediately_when_for_consecutive_is_1():
    d = _decide(breaching=True, for_consecutive=1)
    assert d.action == "open"
    assert d.breach_streak == 1


def test_sustained_breach_waits_for_consecutive():
    # first breach: not enough yet
    d1 = _decide(breaching=True, for_consecutive=2, breach_streak=0)
    assert d1.action == "noop"
    assert d1.breach_streak == 1
    # second breach: opens
    d2 = _decide(breaching=True, for_consecutive=2, breach_streak=1)
    assert d2.action == "open"


def test_breach_while_open_updates_not_reopens():
    d = _decide(breaching=True, has_open_incident=True)
    assert d.action == "update"


def test_clear_below_threshold_does_not_resolve():
    d = _decide(breaching=False, has_open_incident=True, resolve_after_clear=2, clear_streak=0)
    assert d.action == "noop"
    assert d.clear_streak == 1


def test_resolves_after_enough_clears():
    d = _decide(breaching=False, has_open_incident=True, resolve_after_clear=2, clear_streak=1)
    assert d.action == "resolve"
    assert d.cooldown_until == NOW + timedelta(minutes=5)


def test_cooldown_blocks_reopen():
    d = _decide(
        breaching=True,
        has_open_incident=False,
        for_consecutive=1,
        cooldown_until=NOW + timedelta(minutes=3),  # still cooling down
    )
    assert d.action == "noop"


def test_cooldown_expired_allows_open():
    d = _decide(
        breaching=True,
        has_open_incident=False,
        for_consecutive=1,
        cooldown_until=NOW - timedelta(minutes=1),  # expired
    )
    assert d.action == "open"


def test_breach_resets_clear_streak_and_vice_versa():
    assert _decide(breaching=True, clear_streak=5).clear_streak == 0
    assert _decide(breaching=False, breach_streak=5).breach_streak == 0


def test_no_incident_and_not_breaching_is_noop():
    d = _decide(breaching=False, has_open_incident=False)
    assert d.action == "noop"
