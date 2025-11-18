import asyncio
import logging
import random
import time
from inspect import iscoroutinefunction
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import Flag
from functools import partial, wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=BaseException)
C = Callable[..., Any | Awaitable[Any]]
N = int | float  # number
X = Callable[[Exception], Any]


class OnErrOpts(Flag):
    RUN_ON_LAST_TRY = 1
    BREAK_OUT = 2
    # NEXT_OPT = 4


DEFAULT_ONEX_OPTS = OnErrOpts(0)


def get_fn_name(f: C) -> str:
    if isinstance(f, partial):
        return get_fn_name(f.func)
    return getattr(f, "__name__", f.__class__.__name__)  # from https://github.com/Kludex/starlette/pull/2648


def attempts_exceeded(f: C, count: int):
    logger.error(f"exceeded {count} attempts for {get_fn_name(f)}")


def validate_backoff(
    backoff: N,
    exponential_backoff: bool,
    max_backoff: N,
    jitter: N | tuple[N, N],
):
    if exponential_backoff:
        assert backoff > 0, "with exponential_backoff backoff must be greater than 0."
        if max_backoff:
            assert max_backoff > backoff, "max_backoff must be greater than backoff."
    else:
        assert backoff >= 0, "backoff must be >= 0."
        assert not max_backoff, "max_backoff does not make sense without exponential_backoff."

    if jitter:
        if isinstance(jitter, tuple):
            assert len(jitter) == 2, "jitter, when defined as a tuple, must be a range of length 2"
            # j = max([abs(x) for x in jitter])
            j = max(abs(jitter[0]), abs(jitter[1]))
        else:
            j = abs(jitter)
        assert j <= backoff, "jitter extreme must be <= backoff."


def sanitize_on_exception(onex: None | dict | tuple[C, OnErrOpts] | C, is_async: bool) -> dict:
    def assert_callable(c):
        if is_async:
            assert iscoroutinefunction(c), "on_exception must be async as decorating function"
        else:
            assert not iscoroutinefunction(c), "on_exception must not be async as decorating function"
            assert callable(c), "c must be callable"

    def assert_iter(i):
        assert len(i) == 2, "on_exception tuple needs to be of length 2"
        assert isinstance(i[1], OnErrOpts), "second item in on_exception tuple must be OnErrOpts"
        assert_callable(i[0])

    if onex is None:
        return {}
    elif isinstance(onex, dict):
        for c in onex.values():
            if isinstance(c, tuple):
                assert_iter(c)
            else:
                assert_callable(c)
        return onex
    elif callable(onex):
        assert_callable(onex)
        return {Exception: onex}
    else:  # i.e.  elif isinstance(onex, tuple):
        assert_iter(onex)
        return {Exception: onex}


def handle_delay(
    exception: Exception,
    count: int,
    retries: int,
    attempts: int,
    on_exhaustion: bool | X,
    backoff: N,
    exponential_backoff: bool,
    max_backoff: N,
    jitter: N | tuple[N, N],
    function: C,
) -> tuple[int, float, Any]:
    count += 1
    logger.warning(f"{count}. attempt: caught error in [{get_fn_name(function)}]: {repr(exception)}")

    if retries != -1 and count >= attempts:
        if on_exhaustion:
            if on_exhaustion is True:
                return count, 0, exception
            return count, 0, on_exhaustion(exception)
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
    if max_backoff:
        current_backoff = min(current_backoff, max_backoff)

    return count, current_backoff, None


def unpack_callback(cb: tuple[C, OnErrOpts] | C) -> tuple[C, OnErrOpts]:
    opts: OnErrOpts = DEFAULT_ONEX_OPTS
    if isinstance(cb, tuple):
        cb, opts = cb
    return cb, opts


def should_skip_cb(opts: OnErrOpts, last_try: bool) -> bool:
    return last_try and not bool(opts & OnErrOpts.RUN_ON_LAST_TRY)


def retry_logic(
    f: Callable[..., Any],
    expected_exception: type[E] | tuple[type[E], ...],
    retries: int,
    backoff: N,
    exponential_backoff: bool,
    on_exhaustion: bool | X,
    jitter: N | tuple[N, N],
    max_backoff: N,
    onex: dict,
) -> Any:
    count = 0
    attempts = retries + 1
    # return_val = None
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

            count, current_backoff, return_val = handle_delay(
                e,
                count,
                retries,
                attempts,
                on_exhaustion,
                backoff,
                exponential_backoff,
                max_backoff,
                jitter,
                f,
            )
            if current_backoff:
                time.sleep(current_backoff)
    attempts_exceeded(f, count)
    return return_val


async def retry_logic_async(
    f: Callable[..., Awaitable[Any]],
    expected_exception: type[E] | tuple[type[E], ...],
    retries: int,
    backoff: N,
    exponential_backoff: bool,
    on_exhaustion: bool | X,
    jitter: N | tuple[N, N],
    max_backoff: N,
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

            count, current_backoff, return_val = handle_delay(
                e,
                count,
                retries,
                attempts,
                on_exhaustion,
                backoff,
                exponential_backoff,
                max_backoff,
                jitter,
                f,
            )
            if current_backoff:
                await asyncio.sleep(current_backoff)
    attempts_exceeded(f, count)
    return return_val


def retry(
    expected_exception: type[E] | tuple[type[E], ...] = BaseException,
    *,
    retries: int = 1,
    backoff: N = 0,
    exponential_backoff: bool = False,
    on_exhaustion: bool | X = False,
    jitter: N | tuple[N, N] = 0,
    max_backoff: N = 0,
    on_exception: None | dict | tuple[C, OnErrOpts] | C = None,
):
    """Retry decorator for synchronous and asynchronous functions.

    Arguments:
        expected_exception:
            exception or tuple of exceptions to catch. default: BaseException

    Keyword arguments:
        retries:
            how much times the function will be retried, -1 for infinite. default: 1
            note total attempts will be retries + 1
        backoff:
            time interval between the attempts. default: 0
        exponential_backoff:
            current_backoff = backoff * 2 ** retries. default: False
        on_exhaustion:
            - False if exception should be re-raised when all attempts fail (default).
            - True if raised exception should be returned, not re-raised.
            - if callable, then on attempt exhaustion it'll be invoked with the
              causing exception, and its return value will be returned.
              This callable must always be synchronous.
        jitter:
            maximum value of deviation from the current_backoff.
            - if a number, then jitter will be in the range (-value, value)
            - if a (min, max) tuple then it defines the range to generate jitter from.
            default: 0
        max_backoff:
            current_backoff = min(current_backoff, max_backoff).
            disabled on 0. default: 0
        on_exception:
            defines callback(s) that should be invoked on failed attempts. Types can be:
            - dict for exception type to callable|(callable, opt) mappings
            - callable
            - (callable, opts) tuple
            The options modify the callback behavior:
            - RUN_ON_LAST_TRY to invoke callback even if there are no attempts remaining
            - BREAK_OUT to stop processing remaining callbacks when dict with
                        multiple exception types was given
            Be aware if the decorated function is synchronous, on_exception function(s)
            must be synchronous as well and vice versa: for async function they need
            to be asynchronous. default: None
    """

    validate_backoff(backoff, exponential_backoff, max_backoff, jitter)
    assert isinstance(on_exhaustion, bool) or not iscoroutinefunction(on_exhaustion), (
        "on_exhaustion can either be bool or synchronous function"
    )

    def decorator(f: C) -> C:
        if iscoroutinefunction(f):
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
                on_exhaustion,
                jitter,
                max_backoff,
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
                on_exhaustion,
                jitter,
                max_backoff,
                onex,
            )

        return async_wrapper if is_async else wrapper

    return decorator


class BaseRetry(ABC):
    """
    Class supporting a more programmatic approach, i.e. w/o a decorator, for retrying logic.
    """

    __slots__ = [
        "expected_exception",
        "retries",
        "backoff",
        "exponential_backoff",
        "on_exhaustion",
        "jitter",
        "max_backoff",
        "on_exception",
    ]

    def __init__(
        self,
        expected_exception: type[E] | tuple[type[E], ...],
        retries: int,
        backoff: N,
        exponential_backoff: bool,
        on_exhaustion: bool | X,
        jitter: N | tuple[N, N],
        max_backoff: N,
        on_exception: dict,
    ):
        validate_backoff(backoff, exponential_backoff, max_backoff, jitter)

        self.expected_exception = expected_exception
        self.retries = retries
        self.backoff = backoff
        self.exponential_backoff = exponential_backoff
        self.on_exhaustion = on_exhaustion
        self.jitter = jitter
        self.max_backoff = max_backoff
        self.on_exception = on_exception
        super().__init__()

    @abstractmethod
    def __call__(self, f: C, *args, **kwargs) -> Any:
        pass


class Retry(BaseRetry):
    """
    Class supporting a more programmatic approach, i.e. w/o a decorator, for retrying logic.
    """

    __slots__ = [
        "expected_exception",
        "retries",
        "backoff",
        "exponential_backoff",
        "on_exhaustion",
        "jitter",
        "max_backoff",
        "on_exception",
    ]

    def __init__(
        self,
        expected_exception: type[E] | tuple[type[E], ...] = BaseException,
        *,
        retries: int = 1,
        backoff: N = 0,
        exponential_backoff: bool = False,
        on_exhaustion: bool | X = False,
        jitter: N | tuple[N, N] = 0,
        max_backoff: N = 0,
        on_exception: None | dict | tuple[C, OnErrOpts] | Callable[..., Any] = None,
    ):
        super().__init__(
            expected_exception,
            retries,
            backoff,
            exponential_backoff,
            on_exhaustion,
            jitter,
            max_backoff,
            sanitize_on_exception(on_exception, False),
        )

    def __call__(self, f: Callable[..., Any], *args, **kwargs) -> Any:
        return retry_logic(
            partial(f, *args, **kwargs),
            self.expected_exception,
            self.retries,
            self.backoff,
            self.exponential_backoff,
            self.on_exhaustion,
            self.jitter,
            self.max_backoff,
            self.on_exception,
        )


class RetryAsync(BaseRetry):
    """
    Class supporting a more programmatic approach, i.e. w/o a decorator, for retrying logic.
    """

    __slots__ = [
        "expected_exception",
        "retries",
        "backoff",
        "exponential_backoff",
        "on_exhaustion",
        "jitter",
        "max_backoff",
        "on_exception",
    ]

    def __init__(
        self,
        expected_exception: type[E] | tuple[type[E], ...] = BaseException,
        *,
        retries: int = 1,
        backoff: N = 0,
        exponential_backoff: bool = False,
        on_exhaustion: bool | X = False,
        jitter: N | tuple[N, N] = 0,
        max_backoff: N = 0,
        on_exception: None | dict | tuple[C, OnErrOpts] | Callable[..., Awaitable[Any]] = None,
    ):
        super().__init__(
            expected_exception,
            retries,
            backoff,
            exponential_backoff,
            on_exhaustion,
            jitter,
            max_backoff,
            sanitize_on_exception(on_exception, True),
        )

    async def __call__(self, f: Callable[..., Awaitable[Any]], *args, **kwargs) -> Awaitable[Any]:
        return await retry_logic_async(
            partial(f, *args, **kwargs),
            self.expected_exception,
            self.retries,
            self.backoff,
            self.exponential_backoff,
            self.on_exhaustion,
            self.jitter,
            self.max_backoff,
            self.on_exception,
        )
