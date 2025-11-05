import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import Flag
from functools import partial, wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=BaseException)
T = Callable[..., Any | Awaitable[Any]]
F = int | float


class OnErrOpts(Flag):
    DO_NOT_RUN_ON_LAST_TRY = 1
    BREAK_OUT = 2
    # NEXT_OPT = 4


DEFAULT_ONEX_OPTS = OnErrOpts(0)


# see https://github.com/Kludex/starlette/pull/2648
def get_f_name(f: T) -> str:
    return getattr(f, "__name__", f.__class__.__name__)


def attempts_exceeds(f: T):
    # logger.error(f"Retry decorator exceeds attempts in {f.__name__}")
    logger.error(f"Retry decorator exceeds attempts in {get_f_name(f)}")


def validate_backoff(
    backoff: F,
    exponential_backoff: bool,
    maximum_backoff: F,
    jitter: F | tuple[F, F],
):
    if exponential_backoff:
        assert backoff > 0, "with exponential_backoff backoff must be greater than 0."
        if maximum_backoff:
            assert maximum_backoff > backoff, "maximum_backoff must be greater than backoff."
    else:
        assert backoff >= 0, "backoff must be >= 0."
        assert not maximum_backoff, "maximum_backoff does not make sense without exponential_backoff."

    if jitter:
        if isinstance(jitter, tuple):
            assert len(jitter) == 2, "jitter, when defined as a tuple, must be a range of length 2"
            # j = max([abs(x) for x in jitter])
            j = max(abs(jitter[0]), abs(jitter[1]))
        else:
            j = abs(jitter)
        assert j <= backoff, "jitter extreme must be <= backoff."


def sanitize_on_exception(onex: None | dict | list | tuple | T, is_async: bool) -> dict:
    def assert_callable(c):
        if is_async:
            assert asyncio.iscoroutinefunction(c), "on_exception must be async as decorating function"
        else:
            assert not asyncio.iscoroutinefunction(c), "on_exception must not be async as decorating function"
            assert callable(c), "c must be callable"

    def assert_iter(i):
        assert len(i) == 2, "on_exception iterable needs to be of length 2"
        assert isinstance(i[1], OnErrOpts), "second item in on_exception iterable must be OnErrOpts"
        assert_callable(i[0])

    if onex is None:
        return {}
    elif isinstance(onex, dict):
        for c in onex.values():
            if isinstance(c, (list, tuple)):
                assert_iter(c)
            else:
                assert_callable(c)
        return onex
    elif callable(onex):
        assert_callable(onex)
        return {Exception: onex}
    elif isinstance(onex, (list, tuple)):
        assert_iter(onex)
        return {Exception: onex}

    raise TypeError("[on_exception] arg needs to be of (callable, dict) or (list, tuple) of length 2 type")


def handle_delay(
    exception: Exception,
    count: int,
    retries: int,
    attempts: int,
    raise_on_no_retries: bool,
    backoff: F,
    exponential_backoff: bool,
    maximum_backoff: F,
    jitter: F | tuple[F, F],
    function: T,
) -> tuple[int, float]:
    # logger.warning(f"Retry decorator catch error in {function.__name__}: {repr(exception)}")
    logger.warning(f"Retry decorator catch error in {get_f_name(function)}: {repr(exception)}")

    count += 1
    # TODO: shouldn't this be if retries != -1 and count >= attempts?
    if retries == -1 or count >= attempts:
        if not raise_on_no_retries:
            return count, 0
        raise exception

    current_backoff: float = backoff
    if exponential_backoff:
        current_backoff *= 2 ** (count - 1)

    if jitter:
        if isinstance(jitter, tuple):
            current_backoff += random.uniform(*jitter)
        else:
            # deviation = jitter * random.random() * random.choice((-1, 1))
            # deviation = jitter * (-1 + 2 * random.random())
            deviation = jitter * random.uniform(-1, 1)
            current_backoff += deviation
    if maximum_backoff:
        current_backoff = min(current_backoff, maximum_backoff)

    return count, current_backoff


def unpack_callback(cb: list | tuple | T) -> tuple[T, OnErrOpts]:
    opts: OnErrOpts = DEFAULT_ONEX_OPTS
    if not callable(cb):
        cb, opts = cb
    return cb, opts


def should_skip_cb(opts: OnErrOpts, last_try: bool) -> bool:
    return bool(last_try and opts & OnErrOpts.DO_NOT_RUN_ON_LAST_TRY)


def retry_logic(
    f: Callable[..., Any],
    expected_exception: type[E] | tuple[type[E], ...],
    retries: int,
    backoff: F,
    exponential_backoff: bool,
    raise_on_no_retries: bool,
    jitter: F | tuple[F, F],
    maximum_backoff: F,
    onex: dict,
) -> Any:
    count = 0
    attempts = retries + 1
    while retries == -1 or count < attempts:
        try:
            return f()
        except expected_exception as e:
            # check if this exception is something the caller wants special handling for
            for error_type in onex:
                if isinstance(e, error_type):
                    cb, opts = unpack_callback(onex[error_type])
                    if should_skip_cb(opts, count == retries):
                        continue
                    cb()
                    if opts & OnErrOpts.BREAK_OUT:
                        break

            count, current_backoff = handle_delay(
                e,
                count,
                retries,
                attempts,
                raise_on_no_retries,
                backoff,
                exponential_backoff,
                maximum_backoff,
                jitter,
                f,
            )
            if current_backoff:
                time.sleep(current_backoff)
    attempts_exceeds(f)


async def retry_logic_async(
    f: Callable[..., Awaitable[Any]],
    expected_exception: type[E] | tuple[type[E], ...],
    retries: int,
    backoff: F,
    exponential_backoff: bool,
    raise_on_no_retries: bool,
    jitter: F | tuple[F, F],
    maximum_backoff: F,
    onex: dict,
) -> Any:
    count = 0
    attempts = retries + 1
    while retries == -1 or count < attempts:
        try:
            return await f()
        except expected_exception as e:
            # check if this exception is something the caller wants special handling for
            for error_type in onex:
                if isinstance(e, error_type):
                    cb, opts = unpack_callback(onex[error_type])
                    if should_skip_cb(opts, count == retries):
                        continue
                    await cb()
                    if opts & OnErrOpts.BREAK_OUT:
                        break

            count, current_backoff = handle_delay(
                e,
                count,
                retries,
                attempts,
                raise_on_no_retries,
                backoff,
                exponential_backoff,
                maximum_backoff,
                jitter,
                f,
            )
            if current_backoff:
                await asyncio.sleep(current_backoff)
    attempts_exceeds(f)


def retry(
    expected_exception: type[E] | tuple[type[E], ...] = BaseException,
    *,
    retries: int = 1,
    backoff: F = 0,
    exponential_backoff: bool = False,
    raise_on_no_retries: bool = True,
    jitter: F | tuple[F, F] = 0,
    maximum_backoff: F = 0,
    on_exception: None | dict | list | tuple | T = None,
):
    """Retry decorator for synchronous and asynchronous functions.

    Arguments:
        expected_exception:
            exception or tuple of exceptions (default BaseException).

    Keyword arguments:
        retries:
            how much times the function will be retried, value -1 is infinite (default 1).
            note total attempts will be retries + 1
        backoff:
            time interval between the attempts (default 0).
        exponential_backoff:
            current_backoff = backoff * 2 ** retries (default False).
        raise_on_no_retries:
            whether exception should be raised when all attempts fail (default True)
        jitter:
            maximum value of deviation from the current_backoff (default 0).
            define as (min, max) tuple to provide range to generate jitter from.
        maximum_backoff:
            current_backoff = min(current_backoff, maximum_backoff) (default 0).
        on_exception:
            function that called or await on error occurs (default None).
            Be aware if a decorating function is synchronous on_exception function must be
            synchronous too and accordingly for asynchronous function on_exception must be
            asynchronous.
    """

    validate_backoff(backoff, exponential_backoff, maximum_backoff, jitter)

    def decorator(f: T) -> T:
        if asyncio.iscoroutinefunction(f):
            is_async = True
        else:
            is_async = False
            assert callable(f), "function must be callable"

        onex: dict = sanitize_on_exception(on_exception, is_async)

        @wraps(f)
        def wrapper(*args, **kwargs) -> Any:
            return retry_logic(
                partial(f, *args, **kwargs),
                expected_exception,
                retries,
                backoff,
                exponential_backoff,
                raise_on_no_retries,
                jitter,
                maximum_backoff,
                onex,
            )

        @wraps(f)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await retry_logic_async(
                partial(f, *args, **kwargs),
                expected_exception,
                retries,
                backoff,
                exponential_backoff,
                raise_on_no_retries,
                jitter,
                maximum_backoff,
                onex,
            )

        return async_wrapper if is_async else wrapper

    return decorator


class BaseRetry(ABC):
    """
    Class supporting a more programmatic approach (not requiring a decorator) for retrying logic.
    """

    __slots__ = [
        "expected_exception",
        "retries",
        "backoff",
        "exponential_backoff",
        "raise_on_no_retries",
        "jitter",
        "maximum_backoff",
        "on_exception",
    ]

    def __init__(
        self,
        is_async: bool,
        expected_exception: type[E] | tuple[type[E], ...],
        retries: int,
        backoff: F,
        exponential_backoff: bool,
        raise_on_no_retries: bool,
        jitter: F | tuple[F, F],
        maximum_backoff: F,
        on_exception: None | dict | list | tuple | T,
    ):
        validate_backoff(backoff, exponential_backoff, maximum_backoff, jitter)

        self.expected_exception = expected_exception
        self.retries = retries
        self.backoff = backoff
        self.exponential_backoff = exponential_backoff
        self.raise_on_no_retries = raise_on_no_retries
        self.jitter = jitter
        self.maximum_backoff = maximum_backoff
        self.on_exception = sanitize_on_exception(on_exception, is_async)
        super().__init__()

    @abstractmethod
    def __call__(self, f: T, *args, **kwargs) -> Any:
        pass


class Retry(BaseRetry):
    """
    Class supporting a more programmatic approach (not requiring a decorator) for retrying logic.
    """

    __slots__ = [
        "expected_exception",
        "retries",
        "backoff",
        "exponential_backoff",
        "raise_on_no_retries",
        "jitter",
        "maximum_backoff",
        "on_exception",
    ]

    def __init__(
        self,
        expected_exception: type[E] | tuple[type[E], ...] = BaseException,
        *,
        retries: int = 1,
        backoff: F = 0,
        exponential_backoff: bool = False,
        raise_on_no_retries: bool = True,
        jitter: F | tuple[F, F] = 0,
        maximum_backoff: F = 0,
        on_exception: None | dict | list | tuple | Callable[..., Any] = None,
    ):
        super().__init__(
            False,
            expected_exception,
            retries,
            backoff,
            exponential_backoff,
            raise_on_no_retries,
            jitter,
            maximum_backoff,
            on_exception,
        )

    def __call__(self, f: Callable[..., Any], *args, **kwargs) -> Any:
        return retry_logic(
            partial(f, *args, **kwargs),
            self.expected_exception,
            self.retries,
            self.backoff,
            self.exponential_backoff,
            self.raise_on_no_retries,
            self.jitter,
            self.maximum_backoff,
            self.on_exception,
        )


class RetryAsync(BaseRetry):
    """
    Class supporting a more programmatic approach (not requiring a decorator) for retrying logic.
    """

    __slots__ = [
        "expected_exception",
        "retries",
        "backoff",
        "exponential_backoff",
        "raise_on_no_retries",
        "jitter",
        "maximum_backoff",
        "on_exception",
    ]

    def __init__(
        self,
        expected_exception: type[E] | tuple[type[E], ...] = BaseException,
        *,
        retries: int = 1,
        backoff: F = 0,
        exponential_backoff: bool = False,
        raise_on_no_retries: bool = True,
        jitter: F | tuple[F, F] = 0,
        maximum_backoff: F = 0,
        on_exception: None | dict | list | tuple | Callable[..., Awaitable[Any]] = None,
    ):
        super().__init__(
            True,
            expected_exception,
            retries,
            backoff,
            exponential_backoff,
            raise_on_no_retries,
            jitter,
            maximum_backoff,
            on_exception,
        )

    async def __call__(self, f: Callable[..., Awaitable[Any]], *args, **kwargs) -> Awaitable[Any]:
        return await retry_logic_async(
            partial(f, *args, **kwargs),
            self.expected_exception,
            self.retries,
            self.backoff,
            self.exponential_backoff,
            self.raise_on_no_retries,
            self.jitter,
            self.maximum_backoff,
            self.on_exception,
        )
