#
# License: MIT
# Copyright: Patrick Ng - 2012
#

from functools import wraps, partial
import logging
import time
import random

logging_logger = logging.getLogger(__name__)


def _is_valid_iter(i):
    if not isinstance(i, (list, tuple)):
        return False
    elif len(i) != 2:
        raise ValueError("provided list|tuple needs to have size of 2")
    return True


def validate_tries(tries):
    if not isinstance(tries, int):
        raise TypeError("[tries] arg needs to be of int type")
    elif tries < 1:
        raise ValueError("[tries] arg needs to be an int >= 1")


def sanitize_cbe(cbe):
    if cbe is None:
        return {}
    elif isinstance(cbe, dict):
        return cbe
    elif callable(cbe) or (isinstance(cbe, (list, tuple)) and len(cbe) == 2):
        return {Exception: cbe}

    raise TypeError("[callback_by_exception] arg needs to be of (callable, dict, list, tuple) type")


def _retry_logic(f, exc=Exception, tries=10, timeout_secs=1.0, logger=None, callback_by_exception={}):
    """
    Common function logic for the internal retry flows.
    :param f:
    :param exc:
    :param tries:
    :param timeout_secs:
    :param logger:
    :param callback_by_exception:
    :return:
    """

    mtries, mdelay = tries, timeout_secs
    run_one_last_time = True

    while mtries > 1:
        try:
            return f()
        except exc as e:
            # check if this exception is something the caller wants special handling for
            for error_type in callback_by_exception:
                if isinstance(e, error_type):
                    callback_logic = callback_by_exception[error_type]

                    should_break_out = False
                    run_one_last_time = True
                    if _is_valid_iter(callback_logic):
                        callback_logic, should_break_out = callback_logic
                        if _is_valid_iter(should_break_out):
                            should_break_out, run_one_last_time = should_break_out
                    callback_logic()
                    if should_break_out:  # caller requests we stop handling this exception
                        break
            half_interval = mdelay * 0.10  # interval size
            actual_delay = random.uniform(mdelay - half_interval, mdelay + half_interval)
            msg = "Retrying in %.2f seconds ..." % actual_delay
            logging_object = logger or logging_logger
            logging_object.exception(msg)
            time.sleep(actual_delay)
            mtries -= 1
            mdelay *= 2
    if run_one_last_time:  # one exception may be all the caller wanted in certain cases
        return f()


def retry(exc=Exception, tries=10, timeout_secs=1.0, logger=None, callback_by_exception=None):
    """
    Retry calling the decorated function using an exponential backoff.

    :param exc: catch all exceptions, a specific exception, or an iterable of exceptions
    :param tries: how many attempts to retry when catching those exceptions
    :param timeout_secs: general delay between retries (we do employ a jitter)
    :param logger: an optional logger object
    :param callback_by_exception: callback/method invocation on certain exceptions
    :type callback_by_exception: None, list, tuple, callable or dict
    """
    validate_tries(tries)
    callback_by_exception = sanitize_cbe(callback_by_exception)

    def retry_decorator(f):
        @wraps(f)
        def retry_wrapper(*args, **kwargs):
            return _retry_logic(
                partial(f, *args, **kwargs),
                exc,
                tries,
                timeout_secs,
                logger,
                callback_by_exception
            )

        return retry_wrapper
    return retry_decorator


class RetryHandler(object):
    """
    Class supporting a more programmatic approach (not requiring a decorator) for retrying logic.
    """
    __slots__ = ["exc", "tries", "timeout_secs", "logger", "callback_by_exception"]

    def __init__(
            self, exc=Exception, tries=10, timeout_secs=1.0, logger=None, callback_by_exception=None,
    ):
        validate_tries(tries)

        self.exc = exc
        self.tries = tries
        self.timeout_secs = timeout_secs
        self.logger = logger
        self.callback_by_exception = sanitize_cbe(callback_by_exception)
        super().__init__()

    def __call__(self, f, *args, **kwargs):
        return _retry_logic(
            partial(f, *args, **kwargs), self.exc, self.tries, self.timeout_secs, self.logger, self.callback_by_exception,
        )
