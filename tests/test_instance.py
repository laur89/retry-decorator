import statistics
import time
from collections.abc import Callable
from unittest.mock import AsyncMock, Mock

import pytest

from retry_deco import Retry, RetryAsync

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
    instance = Retry((ValueError, RuntimeError))
    with pytest.raises(RuntimeError):
        instance(failed)
    assert failed.call_count > 1


def test_retry__expected_exceptions__no_retry(failed):
    """check not retry if raised exception is not expected."""
    instance = Retry(ValueError)
    with pytest.raises(RuntimeError):
        instance(failed)
    assert failed.call_count == 1


def test_retry__attempts(failed):
    attempts = 3
    instance = Retry(RuntimeError, retries=attempts - 1)
    with pytest.raises(RuntimeError):
        instance(failed)
    assert failed.call_count == attempts


def test_retry__backoff(failed):
    backoff = BACKOFF
    instance = Retry(RuntimeError, backoff=backoff)
    time_start = time.time()
    with pytest.raises(RuntimeError):
        instance(failed)
    estimated_time = time.time() - time_start
    assert backoff < estimated_time < backoff * 2


@pytest.mark.asyncio()
async def test_retry__backoff__async(async_failed):
    backoff = BACKOFF
    instance = RetryAsync(RuntimeError, backoff=backoff)
    time_start = time.time()
    with pytest.raises(RuntimeError):
        await instance(async_failed)
    estimated_time = time.time() - time_start
    assert backoff < estimated_time < backoff * 2


def test_retry__exponential_backoff(failed):
    attempts = 3
    backoff = BACKOFF
    instance = Retry(RuntimeError, retries=attempts - 1, backoff=backoff, exponential_backoff=True)
    time_start = time.time()
    with pytest.raises(RuntimeError):
        instance(failed)
    estimated_time = time.time() - time_start
    expected_time = get_exponential_backoff_time(attempts, backoff)
    assert expected_time < estimated_time < expected_time + backoff


def test_retry__do_not_raise_when_attempts_exceeded(failed):
    on_exception = Mock()
    instance = Retry(RuntimeError, raise_on_no_retries=False, on_exception=on_exception)
    instance(failed)
    assert failed.call_count == 2
    assert on_exception.call_count == 2


def test_retry__jitter(failed):
    attempts = 2
    backoff = BACKOFF
    instance = Retry(RuntimeError, retries=attempts - 1, backoff=backoff, jitter=backoff)
    estimated = []
    for _ in range(10):
        time_start = time.time()
        with pytest.raises(RuntimeError):
            instance(failed)
        estimated.append(time.time() - time_start)
    assert statistics.stdev(estimated) > backoff * 0.1


def test_retry__maximum_backoff(failed):
    attempts = 4
    backoff = BACKOFF
    instance = Retry(
        RuntimeError,
        retries=attempts - 1,
        backoff=backoff,
        exponential_backoff=True,
        maximum_backoff=backoff * 2,
    )
    time_start = time.time()
    with pytest.raises(RuntimeError):
        instance(failed)
    estimated_time = time.time() - time_start
    expected_time = get_exponential_backoff_time(attempts, backoff)
    assert backoff * attempts < estimated_time < expected_time


def test_retry__on_exception(failed):
    on_exception = Mock()
    instance = Retry(RuntimeError, on_exception=on_exception)
    with pytest.raises(RuntimeError):
        instance(failed)
    # on_exception.assert_called_once()
    assert on_exception.call_count == 2


@pytest.mark.asyncio()
async def test_retry__on_exception__async(async_failed):
    on_exception = AsyncMock()
    instance = RetryAsync(RuntimeError, on_exception=on_exception)
    with pytest.raises(RuntimeError):
        await instance(async_failed)
    # on_exception.assert_called_once()
    assert on_exception.call_count == 2
