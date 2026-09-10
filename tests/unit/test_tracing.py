"""Контекст трассировки W3C."""

import pytest
from mireacrm_common import tracing


def test_generated_header_is_valid():
    assert tracing._FORMAT.match(tracing.new_traceparent())


def test_valid_header_passed_through():
    incoming = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    assert tracing.parse(incoming) == incoming


@pytest.mark.parametrize(
    "bad",
    [None, "", "мусор", "00-short-00f067aa0ba902b7-01", "00-4bf92f3577b34da6a3ce929d0e0e4736-01"],
)
def test_broken_header_starts_new_trace(bad):
    """Чужой мусор не должен ронять запрос — начинаем новую трассу."""
    result = tracing.parse(bad)

    assert tracing._FORMAT.match(result)
    assert result != bad


def test_trace_id_extracted():
    header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    assert tracing.trace_id(header) == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_trace_id_empty_when_unset():
    assert tracing.trace_id("мусор") == ""
