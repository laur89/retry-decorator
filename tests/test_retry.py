import statistics
import time
from collections.abc import Callable
from unittest.mock import AsyncMock, Mock

import pytest

from retry_deco import retry

BACKOFF = 0.002  # Base backoff parameter for tests.


def get_exponential_backoff_time(total_attempts: int, backoff: int | float) -> int | float:
    return sum([backoff * 2**a for a in range(total_attempts - 1)])


def create_named_mock(mock_type: type[Mock] | type[AsyncMock]) -> Callable:
    mock = mock_type(side_effect=RuntimeError())
    mock.__name__ = "failed"
    return mock


@pytest.fixture()
def failed():
    return create_named_mock(Mock)


@pytest.fixture()
async def async_failed():
    return create_named_mock(AsyncMock)


def test_retry__expected_exceptions(failed):
    decorator = retry((ValueError, RuntimeError))
    decorated = decorator(failed)
    with pytest.raises(RuntimeError):
        decorated()
    assert failed.call_count > 1


def test_retry__expected_exceptions__no_retry(failed):
    """check not retry if raised exception is not expected."""
    decorator = retry(ValueError)
    decorated = decorator(failed)
    with pytest.raises(RuntimeError):
        decorated()
    assert failed.call_count == 1


def test_retry__attempts(failed):
    attempts = 3
    decorator = retry(RuntimeError, retries=attempts - 1)
    decorated = decorator(failed)
    with pytest.raises(RuntimeError):
        decorated()
    assert failed.call_count == attempts


def test_retry__backoff(failed):
    backoff = BACKOFF
    decorator = retry(RuntimeError, backoff=backoff)
    decorated = decorator(failed)
    time_start = time.time()
    with pytest.raises(RuntimeError):
        decorated()
    estimated_time = time.time() - time_start
    assert backoff < estimated_time < backoff * 2


@pytest.mark.asyncio()
async def test_retry__backoff__async(async_failed):
    backoff = BACKOFF
    decorator = retry(RuntimeError, backoff=backoff)
    decorated = decorator(async_failed)
    time_start = time.time()
    with pytest.raises(RuntimeError):
        await decorated()
    estimated_time = time.time() - time_start
    assert backoff < estimated_time < backoff * 2


def test_retry__exponential_backoff(failed):
    attempts = 3
    backoff = BACKOFF
    decorator = retry(RuntimeError, retries=attempts - 1, backoff=backoff, exponential_backoff=True)
    decorated = decorator(failed)
    time_start = time.time()
    with pytest.raises(RuntimeError):
        decorated()
    estimated_time = time.time() - time_start
    expected_time = get_exponential_backoff_time(attempts, backoff)
    assert expected_time < estimated_time < expected_time + backoff


def test_retry__do_not_raise_when_attempts_exceeded(failed):
    on_exception = Mock()
    decorator = retry(RuntimeError, on_exhaustion=True, on_exception=on_exception)
    decorated = decorator(failed)
    decorated()
    assert failed.call_count == 2
    assert on_exception.call_count == 1


def test_retry__jitter(failed):
    attempts = 2
    backoff = BACKOFF
    decorator = retry(RuntimeError, retries=attempts - 1, backoff=backoff, jitter=backoff)
    decorated = decorator(failed)
    estimated = []
    for _ in range(10):
        time_start = time.time()
        with pytest.raises(RuntimeError):
            decorated()
        estimated.append(time.time() - time_start)
    assert statistics.stdev(estimated) > backoff * 0.1


def test_retry__maximum_backoff(failed):
    attempts = 4
    backoff = BACKOFF
    decorator = retry(
        RuntimeError,
        retries=attempts - 1,
        backoff=backoff,
        exponential_backoff=True,
        maximum_backoff=backoff * 2,
    )
    decorated = decorator(failed)
    time_start = time.time()
    with pytest.raises(RuntimeError):
        decorated()
    estimated_time = time.time() - time_start
    expected_time = get_exponential_backoff_time(attempts, backoff)
    assert backoff * attempts < estimated_time < expected_time


def test_retry__on_exception(failed):
    on_exception = Mock()
    decorator = retry(RuntimeError, retries=4, on_exception=on_exception)
    decorated = decorator(failed)
    with pytest.raises(RuntimeError):
        decorated()
    assert on_exception.call_count == 4


def test_0_retries__ok(failed):
    decorator = retry(RuntimeError, retries=0)
    decorated = decorator(failed)
    with pytest.raises(RuntimeError):
        decorated()
    assert failed.call_count == 1


@pytest.mark.asyncio()
async def test_retry__on_exception__async(async_failed):
    on_exception = AsyncMock()
    decorator = retry(RuntimeError, retries=3, on_exception=on_exception)
    decorated = decorator(async_failed)
    with pytest.raises(RuntimeError):
        await decorated()
    assert on_exception.call_count == 3


@retry(Exception, retries=3)
def sync_retry_via_decorator(e_to_raise):
    raise e_to_raise()


@retry(Exception, retries=3)
async def async_retry_via_decorator(e_to_raise):
    raise e_to_raise()


def test_sync_decorator():
    with pytest.raises(ValueError):
        sync_retry_via_decorator(ValueError)


@pytest.mark.asyncio()
async def test_async_decorator():
    with pytest.raises(ValueError):
        await async_retry_via_decorator(ValueError)
