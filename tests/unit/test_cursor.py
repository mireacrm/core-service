"""Курсор keyset-пагинации."""

import uuid

import pytest
from mireacrm_common.errors import InvalidArgumentError
from mireacrm_common.pagination import decode_cursor, encode_cursor


def test_roundtrip():
    ident = uuid.uuid4()

    name = "Анна Специалистова"

    assert decode_cursor(encode_cursor(name, ident)) == (name, ident)


def test_survives_separator_in_name():
    name = "Анна-Мария ван дер Стрижка"

    assert decode_cursor(encode_cursor(name, uuid.uuid4()))[0] == name


@pytest.mark.parametrize("bad", ["", "не-base64!!", "aGVsbG8="])
def test_malformed_cursor_rejected(bad: str):
    with pytest.raises(InvalidArgumentError, match="курсор"):
        decode_cursor(bad)
