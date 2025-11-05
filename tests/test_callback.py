import unittest
from decimal import Decimal
from functools import partial

from retry_deco import DEFAULT_ONEX_OPTS, OnErrOpts, Retry, retry


class ClassForTesting:
    hello: str | None = None
    cb_counter: int  # counts how many times callback was invoked
    exe_counter: int  # counts how many times our retriable logic was invoked

    def __init__(self) -> None:
        self.reset()

    def reset(self):
        self.hello = None
        self.cb_counter = 0
        self.exe_counter = 0


class ExampleTestError(Exception):
    pass


class_for_testing = ClassForTesting()


class MyTestCase(unittest.TestCase):
    def setUp(self):
        class_for_testing.reset()

    def test_callback_invoked_on_configured_exception_type(self):
        try:
            my_test_func()
        except Exception:  # for the dangling exception (the "final" function execution)
            pass
        self.assertEqual(class_for_testing.hello, "world")

    def test_two_exceptions_to_check_use_one(self):
        try:
            my_test_func_2()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "fish")
        self.assertEqual(class_for_testing.cb_counter, 3)
        self.assertEqual(class_for_testing.exe_counter, 3)

    def test_on_exception_may_be_func(self):
        try:
            my_test_func_3()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "foo")

    def test_on_exception_may_be_tuple(self):
        try:
            my_test_func_4()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "bar")

    def test_verify_correct_amount_of_retries_and_callback_invokations(self):
        try:
            my_test_func_5()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "bar")
        self.assertEqual(class_for_testing.cb_counter, 14)
        self.assertEqual(class_for_testing.exe_counter, 7)

    def test_verify_correct_amount_of_retries_and_callback_invokations2(self):
        try:
            my_test_func_6()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "foo")
        self.assertEqual(class_for_testing.cb_counter, 7)
        self.assertEqual(class_for_testing.exe_counter, 7)

    def test_verify_breakout_true_works(self):
        try:
            my_test_func_7()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "baz")
        self.assertEqual(
            class_for_testing.cb_counter, 8
        )  # we had 2 handlers, but because of breakout=True only first of them was ever ran
        self.assertEqual(class_for_testing.exe_counter, 8)

    def test_verify_run_last_time_false_works(self):
        try:
            my_test_func_8()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "foo")  # note it's not 'bar' due to DO_NOT_RUN_ON_LAST_TRY
        self.assertEqual(class_for_testing.cb_counter, 17)  # note value is one less due to DO_NOT_RUN_ON_LAST_TRY
        self.assertEqual(class_for_testing.exe_counter, 9)

    def test_verify_run_last_time_and_breakout_works(self):
        try:
            my_test_func_8_1()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "bar")  # note it's not 'foo' due to DO_NOT_RUN_ON_LAST_TRY
        self.assertEqual(
            class_for_testing.cb_counter, 9
        )  # note value is not 8, as a single Exception's cb will run due to
           #TypeError's DO_NOT_RUN_ON_LAST_TRY, meaning BREAK_OUT is not reached
        self.assertEqual(class_for_testing.exe_counter, 9)

    def test_verify_run_last_time_and_breakout_works2(self):
        try:
            my_test_func_8_2()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "bar")
        self.assertEqual(class_for_testing.cb_counter, 8)
        self.assertEqual(class_for_testing.exe_counter, 9)

    def test_verify_retries_1_is_ok(self):
        try:
            my_test_func_9()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "foo2")
        self.assertEqual(class_for_testing.cb_counter, 2)
        self.assertEqual(class_for_testing.exe_counter, 2)

    def test_verify_run_last_time_false_with_2_retries(self):
        try:
            my_test_func_10()
        except Exception:
            pass
        self.assertEqual(class_for_testing.hello, "foo")
        self.assertEqual(class_for_testing.cb_counter, 2)
        self.assertEqual(class_for_testing.exe_counter, 3)

    def test_verify_args_are_passed_and_returned(self):
        result = my_test_func_11("a", "B", 1)

        self.assertEqual(class_for_testing.hello, None)
        self.assertEqual(class_for_testing.cb_counter, 0)
        self.assertEqual(class_for_testing.exe_counter, 2)
        self.assertEqual(result, "aB")

    def test_verify_args_are_passed_and_returned_2(self):
        result = Retry()(add_two_values_after, "a", "B", 1)

        self.assertEqual(class_for_testing.hello, None)
        self.assertEqual(class_for_testing.cb_counter, 0)
        self.assertEqual(class_for_testing.exe_counter, 2)
        self.assertEqual(result, "aB")

    def test_verify_args_are_passed_and_returned_3(self):
        result = retry()(add_two_values_after)(Decimal("2.3"), Decimal("5.6"), 1)

        self.assertEqual(class_for_testing.hello, None)
        self.assertEqual(class_for_testing.cb_counter, 0)
        self.assertEqual(class_for_testing.exe_counter, 2)
        self.assertEqual(result, Decimal("7.9"))


def callback_logic(instance, attr_to_set, value_to_set):
    print(f"Callback called for {instance}; setting attr [{attr_to_set}] to value [{value_to_set}]")
    setattr(instance, attr_to_set, value_to_set)
    instance.cb_counter += 1


@retry(
    ExampleTestError,
    retries=2,
    on_exception={ExampleTestError: partial(callback_logic, class_for_testing, "hello", "world")},
)
def my_test_func():
    raise ExampleTestError("oh noes.")


@retry(
    (ExampleTestError, AttributeError),
    retries=2,
    on_exception={AttributeError: partial(callback_logic, class_for_testing, "hello", "fish")},
)
def my_test_func_2():
    class_for_testing.exe_counter += 1
    raise AttributeError("attribute oh noes.")


@retry(retries=2, on_exception=partial(callback_logic, class_for_testing, "hello", "foo"))
def my_test_func_3():
    raise TypeError("type oh noes.")


@retry(
    retries=2,
    on_exception=(partial(callback_logic, class_for_testing, "hello", "bar"), DEFAULT_ONEX_OPTS | OnErrOpts.BREAK_OUT),
)
def my_test_func_4():
    raise TypeError("type oh noes.")


@retry(
    retries=6,
    on_exception={
        TypeError: partial(callback_logic, class_for_testing, "hello", "foo"),
        Exception: partial(callback_logic, class_for_testing, "hello", "bar"),
    },
)
def my_test_func_5():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(
    ExampleTestError,
    retries=6,
    on_exception={
        TypeError: partial(callback_logic, class_for_testing, "hello", "bar"),
        ExampleTestError: partial(callback_logic, class_for_testing, "hello", "foo"),
    },
)
def my_test_func_6():
    class_for_testing.exe_counter += 1
    raise ExampleTestError("oh noes.")


@retry(
    retries=7,
    on_exception={
        TypeError: (
            partial(callback_logic, class_for_testing, "hello", "baz"),
            DEFAULT_ONEX_OPTS | OnErrOpts.BREAK_OUT,
        ),
        Exception: partial(callback_logic, class_for_testing, "hello", "foo"),
    },
)
def my_test_func_7():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(
    retries=8,
    on_exception={
        TypeError: partial(callback_logic, class_for_testing, "hello", "foo"),
        Exception: (
            partial(callback_logic, class_for_testing, "hello", "bar"),
            DEFAULT_ONEX_OPTS | OnErrOpts.DO_NOT_RUN_ON_LAST_TRY,
        ),
    },
)
def my_test_func_8():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(
    retries=8,
    on_exception={
        TypeError: (
            partial(callback_logic, class_for_testing, "hello", "foo"),
            DEFAULT_ONEX_OPTS | OnErrOpts.DO_NOT_RUN_ON_LAST_TRY | OnErrOpts.BREAK_OUT,
        ),
        Exception: partial(callback_logic, class_for_testing, "hello", "bar"),
    },
)
def my_test_func_8_1():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(
    retries=8,
    on_exception={
        Exception: (
            partial(callback_logic, class_for_testing, "hello", "bar"),
            DEFAULT_ONEX_OPTS | OnErrOpts.DO_NOT_RUN_ON_LAST_TRY | OnErrOpts.BREAK_OUT,
        ),
        # TypeError: partial(callback_logic, class_for_testing, 'hello', 'foo')
    },
)
def my_test_func_8_2():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(retries=1, on_exception=partial(callback_logic, class_for_testing, "hello", "foo2"))
def my_test_func_9():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(
    retries=2,
    on_exception=(
        partial(callback_logic, class_for_testing, "hello", "foo"),
        DEFAULT_ONEX_OPTS | OnErrOpts.DO_NOT_RUN_ON_LAST_TRY,
    ),
)
def my_test_func_10():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


def add_two_values_after(val1, val2, after):
    class_for_testing.exe_counter += 1

    if class_for_testing.exe_counter <= after:
        raise TypeError("type oh noes.")
    return val1 + val2


@retry(retries=2)
def my_test_func_11(val1, val2, after):
    return add_two_values_after(**locals())


if __name__ == "__main__":
    unittest.main()
