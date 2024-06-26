from __future__ import annotations

import ibis
from ibis import _
from ibis.expr import types as ir

from mismo import _util

_ARRAY_AGGS = {}


def _get_array_agg(array: ir.ArrayValue, name: str) -> ir.Column:
    t = array.type()
    if not isinstance(array, ir.ArrayValue):
        raise ValueError(f"Expected an array, got {t}")

    key = (t, name)
    if key not in _ARRAY_AGGS:

        @ibis.udf.scalar.builtin(name=name, signature=((t,), t.value_type()))
        def f(array): ...

        _ARRAY_AGGS[key] = f

    return _ARRAY_AGGS[key](array)


def array_min(array: ir.ArrayValue) -> ir.NumericValue:
    """Get the minimum value of an array."""
    return _get_array_agg(array, "list_min")


def array_max(array: ir.ArrayValue) -> ir.NumericValue:
    """Get the maximum value of an array."""
    return _get_array_agg(array, "list_max")


@ibis.udf.scalar.builtin(name="list_bool_or")
def array_any(array) -> bool: ...


@ibis.udf.scalar.builtin(name="list_bool_and")
def array_all(array) -> bool: ...


def array_combinations(left: ir.ArrayValue, right: ir.ArrayValue) -> ir.ArrayValue:
    """Generate all combinations of elements from two arrays.

    This is the cartesian product of the two arrays.

    Parameters
    ----------
    array1 :
        The first array.
    array2 :
        The second array.

    Returns
    -------
    combinations : ArrayValue
        An `array<struct<l: T, r: U>>` where `T` is the type of the
        elements in `array1` and `U` is the type of the elements in `array2`.
    """
    return left.map(
        lambda le: right.map(lambda r: ibis.struct(dict(l=le, r=r)))
    ).flatten()


def array_filter_isin_other(
    t: ir.Table,
    array: ir.ArrayColumn | str,
    other: ir.Column,
    *,
    result_format: str = "{name}_filtered",
) -> ir.Table:
    """
    Equivalent to t.mutate(result_name=t[array].filter(lambda x: x.isin(other)))

    We can't have subqueries in the filter lambda (need this to avoid
    https://stackoverflow.com/questions/77559936/how-to-implementlist-filterarray-elem-elem-in-column-in-other-table)

    See https://github.com/NickCrews/mismo/issues/32 for more info.

    Parameters
    ----------
    t :
        The table containing the array column.
    array :
        A reference to the array column.
    other :
        The column to filter against.
    result_format :
        The format string to use for the result column name. The format string
        should have a single placeholder, `{name}`, which will be replaced with
        the name of the array column.

    Returns
    -------
    ir.Table
        The table with a new column named following `result_format` with the
        filtered array.
    """  # noqa E501
    array_col = _util.get_column(t, array)
    t = t.mutate(__array=array_col, __id=ibis.row_number())
    temp = t.select("__id", __unnested=_.__array.unnest())
    filtered = temp.filter(temp.__unnested.isin(other))
    re_agged = filtered.group_by("__id").agg(__filtered=_.__unnested.collect())
    re_joined = t.join(re_agged, "__id").drop(["__id", "__array"])
    result_name = result_format.format(name=array_col.get_name())
    return re_joined.rename({result_name: "__filtered"})


@ibis.udf.scalar.builtin(
    name="list_select",
    signature=(("array<string>", "array<int64>"), "array<string>"),
)
def _list_select(x: list, indexes: list) -> list:
    """Selects elements from a list by index."""


@ibis.udf.scalar.builtin(
    name="list_grade_up",
    signature=(("array<float64>",), "array<int64>"),
)
def _list_grade_up(x):
    """Works like sort, but returns the indexes instead of the actual values."""


def array_shuffle(a: ir.ArrayValue) -> ir.ArrayValue:
    """Shuffle an array."""
    idxs = a.map(lambda x: ibis.random())
    return _list_select(a, _list_grade_up(idxs))


def array_choice(a: ir.ArrayValue, n: int) -> ir.ArrayValue:
    """Randomly select `n` elements from an array."""
    return array_shuffle(a)[:n]
