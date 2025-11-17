import unittest
from decimal import Decimal
from functools import partial
from contextlib import suppress

from retry_deco import OnErrOpts, Retry, retry


class ClassForTesting:
    hello: str | None = None
    cb_counter: int  # counts how many times on_exception callback was invoked
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
        with suppress(ExampleTestError):
            cb_for_specific_exception_type()
        self.assertEqual(class_for_testing.hello, "world1")
        self.assertEqual(class_for_testing.cb_counter, 2)

    def test_two_expected_exceptions__cb_invoked_for_only_one(self):
        with suppress(AttributeError):
            invoke_cb_for_only_one_expected_exc()
        self.assertEqual(class_for_testing.hello, "fish1")
        self.assertEqual(class_for_testing.cb_counter, 2)
        self.assertEqual(class_for_testing.exe_counter, 3)

    def test_on_exception_type_may_be_function(self):
        with suppress(TypeError):
            on_exception_type_is_a_function()
        self.assertEqual(class_for_testing.hello, "foo1")

    def test_on_exception_type_may_be_tuple(self):
        with suppress(TypeError):
            on_exception_type_is_a_tuple()
        self.assertEqual(class_for_testing.hello, "bar1")

    def test_verify_correct_amount_of_retries_and_callback_invokations(self):
        with suppress(TypeError):
            multiple_on_exceptions_both_should_be_called()
        self.assertEqual(class_for_testing.hello, "bar2")
        self.assertEqual(class_for_testing.cb_counter, 12)
        self.assertEqual(class_for_testing.exe_counter, 7)

    def test_verify_correct_amount_of_retries_and_callback_invokations2(self):
        with suppress(ExampleTestError):
            multiple_on_exceptions_only_one_should_be_called()
        self.assertEqual(class_for_testing.hello, "foo3")
        self.assertEqual(class_for_testing.cb_counter, 6)
        self.assertEqual(class_for_testing.exe_counter, 7)

    def test_verify_breakout_from_cb_works(self):
        with suppress(TypeError):
            on_exception_cb_has_break_out_opt_set()
        self.assertEqual(class_for_testing.hello, "baz1")
        self.assertEqual(class_for_testing.cb_counter, 7)
        self.assertEqual(class_for_testing.exe_counter, 8)

    def test_verify_run_on_last_try_works(self):
        with suppress(TypeError):
            on_exception_cb_has_run_on_last_try_opt_set()
        self.assertEqual(class_for_testing.hello, "bar4")  # note it's not 'foo5' due to RUN_ON_LAST_TRY
        self.assertEqual(class_for_testing.cb_counter, 17)  # note value is one more due to RUN_ON_LAST_TRY
        self.assertEqual(class_for_testing.exe_counter, 9)  # value almost twice smaller due to BREAK_OUT

    def test_verify_run_on_last_try_and_breakout_opts_work_together(self):
        with suppress(ExampleTestError):
            on_exception_cb_has_run_on_last_try__and__break_out_opts_set()
        self.assertEqual(class_for_testing.hello, "foo6")  # note it's not 'bar5' due to RUN_ON_LAST_TRY
        self.assertEqual(class_for_testing.cb_counter, 9)  # value not 17 due to BREAK_OUT; and not 8 due to RUN_ON_LAST_TRY
        self.assertEqual(class_for_testing.exe_counter, 9)

    # very similar to previous, but different callbacks
    def test_verify_run_on_last_try_and_breakout_opts_work_together2(self):
        with suppress(TypeError):
            on_exception_cb_has_run_on_last_try__and__break_out_opts_set__single_cb()
        self.assertEqual(class_for_testing.hello, "bar6")
        self.assertEqual(class_for_testing.cb_counter, 9)
        self.assertEqual(class_for_testing.exe_counter, 9)

    def test_verify_single_retry_is_ok(self):
        with suppress(TypeError):
            single_retry()
        self.assertEqual(class_for_testing.hello, "foo7")
        self.assertEqual(class_for_testing.cb_counter, 1)
        self.assertEqual(class_for_testing.exe_counter, 2)

    def test_verify_run_last_time_false_with_2_retries(self):
        with suppress(TypeError):
            two_retries_and_cb_has_run_on_last_try_opt_set()
        self.assertEqual(class_for_testing.hello, "foo8")
        self.assertEqual(class_for_testing.cb_counter, 3)
        self.assertEqual(class_for_testing.exe_counter, 3)

    def test_verify_args_are_passed_and_returned__with_retry_decorator(self):
        result = my_test_func_11("a", "B", 1)

        self.assertEqual(class_for_testing.hello, None)
        self.assertEqual(class_for_testing.cb_counter, 0)
        self.assertEqual(class_for_testing.exe_counter, 2)
        self.assertEqual(result, "aB")

    def test_verify_args_are_passed_and_returned__with_retry_instance(self):
        result = Retry(retries=2)(add_two_values_after, "a", "B", 2)

        self.assertEqual(class_for_testing.hello, None)
        self.assertEqual(class_for_testing.cb_counter, 0)
        self.assertEqual(class_for_testing.exe_counter, 3)
        self.assertEqual(result, "aB")

    def test_verify_args_are_passed_and_returned__with_direct_decorator_method_call(self):
        result = retry()(add_two_values_after)(Decimal("2.3"), Decimal("5.6"), 1)

        self.assertEqual(class_for_testing.hello, None)
        self.assertEqual(class_for_testing.cb_counter, 0)
        self.assertEqual(class_for_testing.exe_counter, 2)
        self.assertEqual(result, Decimal("7.9"))

    def test_verify_exception_is_returned_if_on_exhaustion_set_to_true(self):
        result = on_exhaustion_true_set()
        self.assertEqual(str(result), "returning this exception")
        self.assertEqual(class_for_testing.hello, "fish2")
        self.assertEqual(class_for_testing.cb_counter, 2)
        self.assertEqual(class_for_testing.exe_counter, 3)

    def test_verify_on_exhaustion_callback_result_is_returned(self):
        result = on_exhaustion_callback_set()
        self.assertEqual(result, "from on_exhaustion()")
        self.assertEqual(class_for_testing.hello, None)
        self.assertEqual(class_for_testing.cb_counter, 0)
        self.assertEqual(class_for_testing.exe_counter, 3)

    def test_infinite_retries(self):
        result = infinite_retries_set(500)  # not quite infinite, but close enough
        self.assertEqual(result, "success")
        self.assertEqual(class_for_testing.hello, "fish")
        self.assertEqual(class_for_testing.cb_counter, 499)
        self.assertEqual(class_for_testing.exe_counter, 500)


# function to verify on_exception callback invocations
def callback_logic(instance, attr_to_set, value_to_set):
    print(f"Callback called for {instance}; setting attr [{attr_to_set}] to value [{value_to_set}]")
    setattr(instance, attr_to_set, value_to_set)
    instance.cb_counter += 1


@retry(
    ExampleTestError,
    retries=2,
    on_exception={ExampleTestError: partial(callback_logic, class_for_testing, "hello", "world1")},
)
def cb_for_specific_exception_type():
    raise ExampleTestError("oh noes.")


@retry(
    (ExampleTestError, AttributeError),
    retries=2,
    on_exception={AttributeError: partial(callback_logic, class_for_testing, "hello", "fish1")},
)
def invoke_cb_for_only_one_expected_exc():
    class_for_testing.exe_counter += 1
    raise AttributeError("attribute oh noes.")


@retry(retries=2, on_exception=partial(callback_logic, class_for_testing, "hello", "foo1"))
def on_exception_type_is_a_function():
    raise TypeError("type oh noes.")


@retry(
    retries=2,
    on_exception=(partial(callback_logic, class_for_testing, "hello", "bar1"), OnErrOpts.BREAK_OUT),
)
def on_exception_type_is_a_tuple():
    raise TypeError("type oh noes.")


@retry(
    retries=6,
    on_exception={
        TypeError: partial(callback_logic, class_for_testing, "hello", "foo2"),
        Exception: partial(callback_logic, class_for_testing, "hello", "bar2"),
    },
)
def multiple_on_exceptions_both_should_be_called():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(
    ExampleTestError,
    retries=6,
    on_exception={
        TypeError: partial(callback_logic, class_for_testing, "hello", "bar3"),
        ExampleTestError: partial(callback_logic, class_for_testing, "hello", "foo3"),
    },
)
def multiple_on_exceptions_only_one_should_be_called():
    class_for_testing.exe_counter += 1
    raise ExampleTestError("oh noes.")


@retry(
    retries=7,
    on_exception={
        TypeError: (
            partial(callback_logic, class_for_testing, "hello", "baz1"),
            OnErrOpts.BREAK_OUT,
        ),
        Exception: partial(callback_logic, class_for_testing, "hello", "foo4"),
    },
)
# note Exception cb should also run, but TypeError's break_out opt causes it to be skipped
def on_exception_cb_has_break_out_opt_set():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(
    retries=8,
    on_exception={
        TypeError: partial(callback_logic, class_for_testing, "hello", "foo5"),
        Exception: (
            partial(callback_logic, class_for_testing, "hello", "bar4"),
            OnErrOpts.RUN_ON_LAST_TRY,
        ),
    },
)
def on_exception_cb_has_run_on_last_try_opt_set():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(
    retries=8,
    on_exception={
        ExampleTestError: (
            partial(callback_logic, class_for_testing, "hello", "foo6"),
            OnErrOpts.RUN_ON_LAST_TRY | OnErrOpts.BREAK_OUT,
        ),
        Exception: partial(callback_logic, class_for_testing, "hello", "bar5"),
    },
)
def on_exception_cb_has_run_on_last_try__and__break_out_opts_set():
    class_for_testing.exe_counter += 1
    raise ExampleTestError("type oh noes.")


@retry(
    retries=8,
    on_exception={
        Exception: (
            partial(callback_logic, class_for_testing, "hello", "bar6"),
            OnErrOpts.RUN_ON_LAST_TRY | OnErrOpts.BREAK_OUT,
        ),
    },
)
def on_exception_cb_has_run_on_last_try__and__break_out_opts_set__single_cb():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(retries=1, on_exception=partial(callback_logic, class_for_testing, "hello", "foo7"))
def single_retry():
    class_for_testing.exe_counter += 1
    raise TypeError("type oh noes.")


@retry(
    retries=2,
    on_exception=(
        partial(callback_logic, class_for_testing, "hello", "foo8"),
        OnErrOpts.RUN_ON_LAST_TRY,
    ),
)
def two_retries_and_cb_has_run_on_last_try_opt_set():
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


@retry(
    AttributeError,
    retries=2,
    on_exhaustion=True,
    on_exception={AttributeError: partial(callback_logic, class_for_testing, "hello", "fish2")},
)
def on_exhaustion_true_set():
    class_for_testing.exe_counter += 1
    raise AttributeError("returning this exception")


@retry(
    AttributeError,
    retries=2,
    on_exhaustion=lambda ex: "from on_exhaustion()",
    on_exception={OSError: partial(callback_logic, class_for_testing, "hello", "fish")},
)
def on_exhaustion_callback_set():
    class_for_testing.exe_counter += 1
    raise AttributeError("returning this exception")


@retry(
    Exception,
    retries=-1,
    on_exception=partial(callback_logic, class_for_testing, "hello", "fish"),
)
def infinite_retries_set(succeed_after: int):
    class_for_testing.exe_counter += 1
    if class_for_testing.exe_counter == succeed_after:
        return 'success'
    raise AttributeError()


if __name__ == "__main__":
    unittest.main()
