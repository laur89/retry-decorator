#!/usr/bin/env python

#
# License: MIT
# Copyright: Patrick Ng - 2012
#

from __future__ import print_function
import sys
from retry_decorator import retry


def throw_err(msg):
    print('hello', file=sys.stderr)
    raise Exception('throwing err for {}'.format(msg))


def callback(msg):
    print('callback called: {}'.format(msg), file=sys.stderr)


@retry(Exception, tries=3, timeout_secs=0.1)
def retry_test_via_decorator():
    throw_err('retry-via-deco')


def test_decorator():
    try:
        retry_test_via_decorator()
    except Exception as e:
        print('Received the last exception')


def test_instance():
    cbe = {
        Exception: lambda: callback('retry-via-instance')
    }

    try:
        retry(tries=3, callback_by_exception=cbe)(throw_err)('retry-via-instance')
    except Exception as e:
        print('Received the last exception')
