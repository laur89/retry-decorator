#!/usr/bin/env python3

import asyncio
import sys
from contextlib import suppress
from functools import partial

from retry_deco import Retry, RetryAsync, retry


def print_separator(f):
    print(f"--------------- {f.__name__}():")


def run(f):
    print_separator(f)
    with suppress(Exception):
        f()


async def run_async(f):
    print_separator(f)
    with suppress(Exception):
        await f()


def throw_err(msg):
    print(f"  -> raising exception for [{msg}]...", file=sys.stderr)
    raise Exception(f"from {msg}()")


async def throw_err_async(msg):
    print(f"  -> raising exception for [{msg}]...", file=sys.stderr)
    raise Exception(f"from {msg}()")


def callback(msg):
    print(f"    -> on-exception callback called for [{msg}]", file=sys.stderr)


async def async_callback(msg):
    print(f"    -> async on-exception callback called for [{msg}]", file=sys.stderr)


@retry(Exception, retries=3, backoff=0.1, on_exception=partial(callback, "retry-via-deco"))
def test_retry_via_decorator():
    throw_err("retry-via-deco")


def test_retry_via_instance():
    r = Retry(on_exception=partial(callback, "retry-via-instance"))
    r(throw_err, "retry-via-instance")


# note this usage is recommended against
def test_retry_via_deco_instance():
    on_exception = {Exception: lambda: callback("retry-via-deco-instance")}
    retry(retries=3, on_exception=on_exception)(throw_err)("retry-via-deco-instance")


@retry(Exception, retries=2, backoff=0.1, on_exception=partial(async_callback, "retry-via-async-deco"))
async def test_async_retry_via_decorator():
    throw_err("retry-via-async-deco")


async def test_retry_via_async_instance():
    r = RetryAsync(retries=3, on_exception=partial(async_callback, "retry-via-async-instance"))
    await r(throw_err_async, "retry-via-async-instance")


# note this usage is recommended against
async def test_retry_via_async_deco_instance():
    on_exception = {Exception: partial(async_callback, "retry-via-async-deco-instance")}
    r = retry(retries=2, on_exception=on_exception)(throw_err_async)
    await r("retry-via-async-deco-instance")


async def async_examples():
    await run_async(test_async_retry_via_decorator)
    await run_async(test_retry_via_async_instance)
    await run_async(test_retry_via_async_deco_instance)


if __name__ == "__main__":
    run(test_retry_via_decorator)
    run(test_retry_via_instance)
    run(test_retry_via_deco_instance)

    asyncio.run(async_examples())
