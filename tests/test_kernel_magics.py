from mock import MagicMock
from nose.tools import with_setup, raises, assert_equals
from IPython.core.magic import magics_class

import remotespark.utils.configuration as conf
from remotespark.kernels.kernelmagics import KernelMagics
from remotespark.utils.constants import Constants

magic = None
spark_controller = None
shell = None
ipython_display = None


@magics_class
class TestKernelMagics(KernelMagics):
    def __init__(self, shell, data=None):
        super(TestKernelMagics, self).__init__(shell)

    @staticmethod
    def get_configuration(language):
        return "user", "pass", "url"


def _setup():
    global magic, spark_controller, shell, ipython_display

    conf.override_all({})

    magic = TestKernelMagics(shell=None)
    magic.shell = shell = MagicMock()
    magic.ipython_display = ipython_display = MagicMock()
    magic.spark_controller = spark_controller = MagicMock()


def _teardown():
    pass


@with_setup(_setup, _teardown)
def test_start_session():
    line = ""
    assert not magic.session_started

    magic._start_session(line)

    assert magic.session_started
    spark_controller.add_session.assert_called_once_with(magic.session_name, magic.connection_string, False,
                                                         {"kind": Constants.session_kind_pyspark})

    # Call a second time
    magic._start_session(line)
    assert magic.session_started
    assert spark_controller.add_session.call_count == 1


@with_setup(_setup, _teardown)
def test_delete_session():
    line = ""
    magic.session_started = True

    magic._delete_session(line)

    assert not magic.session_started
    spark_controller.delete_session_by_name.assert_called_once_with(magic.session_name)

    # Call a second time
    magic._delete_session(line)
    assert not magic.session_started
    assert spark_controller.delete_session_by_name.call_count == 1


@with_setup(_setup, _teardown)
def test_change_language():
    language = Constants.lang_python.upper()
    line = "-l {}".format(language)

    magic._change_language(line)

    assert_equals(Constants.lang_python, magic.language)


@with_setup(_setup, _teardown)
@raises(AssertionError)
def test_change_language_session_started():
    language = Constants.lang_python
    line = "-l {}".format(language)
    magic.session_started = True

    magic._change_language(line)


@with_setup(_setup, _teardown)
@raises(ValueError)
def test_change_language_not_valid():
    language = "not_valid"
    line = "-l {}".format(language)

    magic._change_language(line)


@with_setup(_setup, _teardown)
def test_info():
    magic.print_endpoint_info = print_info_mock = MagicMock()
    line = ""
    session_info = ["1", "2"]
    spark_controller.get_all_sessions_endpoint_info = MagicMock(return_value=session_info)

    magic.info(line)

    print_info_mock.assert_called_once_with(session_info)


@with_setup(_setup, _teardown)
def test_logs():
    logs = "logs"
    line = ""

    magic.logs(line)
    ipython_display.write.assert_called_once_with("No logs yet.")

    ipython_display.write.reset_mock()

    magic.session_started = True

    spark_controller.get_logs = MagicMock(return_value=(True, logs))
    magic.logs(line)
    ipython_display.write.assert_called_once_with(logs)

    spark_controller.get_logs = MagicMock(return_value=(False, logs))
    magic.logs(line)
    ipython_display.send_error.assert_called_once_with(logs)


@with_setup(_setup, _teardown)
def test_configure():
    # Session not started
    conf.override_all({})
    magic.configure('{"extra": "yes"}')
    assert conf.session_configs() == {"extra": "yes"}

    # Session started - no -f
    magic.session_started = True
    conf.override_all({})
    try:
        magic.configure("{\"extra\": \"yes\"}")
        assert False
    except ValueError:
        assert conf.session_configs() == {}

    # Session started - with -f
    conf.override_all({})
    magic.configure("-f {\"extra\": \"yes\"}")
    assert conf.session_configs() == {"extra": "yes"}
    spark_controller.delete_session_by_name.assert_called_once_with(magic.session_name)
    spark_controller.add_session.assert_called_once_with(magic.session_name, magic.connection_string, False,
                                                         {"kind": Constants.session_kind_pyspark, "extra": "yes"})


@with_setup(_setup, _teardown)
def test_get_session_settings():
    assert magic.get_session_settings("something", False) == "something"
    assert magic.get_session_settings("something    ", False) == "something"
    assert magic.get_session_settings("    something", False) == "something"
    assert magic.get_session_settings("-f something", True) == "something"
    assert magic.get_session_settings("something -f", True) == "something"
    try:
        magic.get_session_settings("something", True)
        assert False
    except ValueError:
        pass


@with_setup(_setup, _teardown)
def test_spark():
    line = ""
    cell = "some spark code"
    spark_controller.run_cell = MagicMock(return_value=(True, line))

    magic.spark(line, cell)

    ipython_display.write.assert_called_once_with(line)
    spark_controller.add_session.assert_called_once_with(magic.session_name, magic.connection_string, False,
                                                         {"kind": Constants.session_kind_pyspark})
    spark_controller.run_cell.assert_called_once_with(cell)


@with_setup(_setup, _teardown)
def test_spark_error():
    line = ""
    cell = "some spark code"
    spark_controller.run_cell = MagicMock(return_value=(False, line))

    magic.spark(line, cell)

    ipython_display.send_error.assert_called_once_with(line)
    spark_controller.add_session.assert_called_once_with(magic.session_name, magic.connection_string, False,
                                                         {"kind": Constants.session_kind_pyspark})
    spark_controller.run_cell.assert_called_once_with(cell)

@with_setup(_setup, _teardown)
def test_sql_without_output():
    line = ""
    cell = "some spark code"
    magic.execute_against_context_that_returns_df = MagicMock()

    magic.sql(line, cell)

    magic.execute_against_context_that_returns_df.assert_called_once_with(spark_controller.run_cell_sql, cell, None,
                                                                          None)

@with_setup(_setup, _teardown)
def test_sql_with_output():
    line = "-o my_var"
    cell = "some spark code"
    magic.execute_against_context_that_returns_df = MagicMock()

    magic.sql(line, cell)

    magic.execute_against_context_that_returns_df.assert_called_once_with(spark_controller.run_cell_sql, cell, None,
                                                                          "my_var")


@with_setup(_setup, _teardown)
def test_hive_without_output():
    line = ""
    cell = "some spark code"
    magic.execute_against_context_that_returns_df = MagicMock()

    magic.hive(line, cell)

    magic.execute_against_context_that_returns_df.assert_called_once_with(spark_controller.run_cell_hive, cell, None,
                                                                          None)

@with_setup(_setup, _teardown)
def test_hive_with_output():
    line = "-o my_var"
    cell = "some spark code"
    magic.execute_against_context_that_returns_df = MagicMock()

    magic.hive(line, cell)

    magic.execute_against_context_that_returns_df.assert_called_once_with(spark_controller.run_cell_hive, cell, None,
                                                                          "my_var")


@with_setup(_setup, _teardown)
@raises(ValueError)
def test_cleanup_without_force():
    line = ""
    cell = ""
    magic.session_started = True
    spark_controller.cleanup_endpoint = MagicMock()
    spark_controller.delete_session_by_name = MagicMock()

    magic.cleanup(line, cell)


@with_setup(_setup, _teardown)
def test_cleanup_with_force():
    line = "-f"
    cell = ""
    magic.session_started = True
    spark_controller.cleanup_endpoint = MagicMock()
    spark_controller.delete_session_by_name = MagicMock()

    magic.cleanup(line, cell)

    spark_controller.cleanup_endpoint.assert_called_once_with(magic.connection_string)
    spark_controller.delete_session_by_name.assert_called_once_with(magic.session_name)


@with_setup(_setup, _teardown)
@raises(ValueError)
def test_delete_without_force():
    session_id = "0"
    line = "-s {}".format(session_id)
    cell = ""
    spark_controller.delete_session_by_id = MagicMock()
    spark_controller.get_session_id_for_client = MagicMock(return_value=session_id)

    magic.delete(line, cell)


@with_setup(_setup, _teardown)
@raises(ValueError)
def test_delete_with_force_same_session():
    session_id = "0"
    line = "-f -s {}".format(session_id)
    cell = ""
    spark_controller.delete_session_by_id = MagicMock()
    spark_controller.get_session_id_for_client = MagicMock(return_value=session_id)

    magic.delete(line, cell)


@with_setup(_setup, _teardown)
def test_delete_with_force_none_session():
    # This happens when session has not been created
    session_id = "0"
    line = "-f -s {}".format(session_id)
    cell = ""
    spark_controller.delete_session_by_id = MagicMock()
    spark_controller.get_session_id_for_client = MagicMock(return_value=None)

    magic.delete(line, cell)

    spark_controller.get_session_id_for_client.assert_called_once_with(magic.session_name)
    spark_controller.delete_session_by_id.assert_called_once_with(magic.connection_string, session_id)


@with_setup(_setup, _teardown)
def test_delete_with_force_different_session():
    # This happens when session has not been created
    session_id = "0"
    line = "-f -s {}".format(session_id)
    cell = ""
    spark_controller.delete_session_by_id = MagicMock()
    spark_controller.get_session_id_for_client = MagicMock(return_value="1")

    magic.delete(line, cell)

    spark_controller.get_session_id_for_client.assert_called_once_with(magic.session_name)
    spark_controller.delete_session_by_id.assert_called_once_with(magic.connection_string, session_id)
