"""Outbound request throttling: the token-bucket RateLimiter."""

import pytest

from fluvilog.wgmn import RateLimiter


class FakeClock:
    """Deterministic monotonic clock; sleep() advances it and records the wait."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_burst_up_to_capacity_does_not_block() -> None:
    clock = FakeClock()
    rl = RateLimiter(1.0, 3, monotonic=clock.monotonic, sleep=clock.sleep)
    for _ in range(3):
        rl.acquire()
    assert clock.sleeps == []


def test_acquire_on_empty_bucket_waits_for_one_token() -> None:
    clock = FakeClock()
    rl = RateLimiter(2.0, 1, monotonic=clock.monotonic, sleep=clock.sleep)
    rl.acquire()  # drains the only token, no wait
    rl.acquire()  # empty → wait one token at 2/s = 0.5s
    assert clock.sleeps == [pytest.approx(0.5)]


def test_sustained_rate_is_capped() -> None:
    clock = FakeClock()
    rl = RateLimiter(4.0, 2, monotonic=clock.monotonic, sleep=clock.sleep)
    for _ in range(10):
        rl.acquire()
    # 2 pass on the initial burst; the other 8 are throttled to 4/s.
    assert sum(clock.sleeps) == pytest.approx(8 / 4.0)


def test_idle_refills_up_to_capacity() -> None:
    clock = FakeClock()
    rl = RateLimiter(1.0, 3, monotonic=clock.monotonic, sleep=clock.sleep)
    for _ in range(3):
        rl.acquire()  # drain
    clock.now += 100.0  # long idle refills, but only up to capacity
    for _ in range(3):
        rl.acquire()  # full burst again, no waiting
    rl.acquire()  # 4th must wait, proving the refill was capped at 3
    assert clock.sleeps == [pytest.approx(1.0)]
