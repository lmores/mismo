from __future__ import annotations

import ibis
from ibis.expr import types as ir


def normalize_name_field(field: ir.StringValue) -> ir.StringValue:
    """Convert to uppercase, normalize whitespace, and remove non-alphanumeric.

    Parameters
    ----------
    name :
        The name to normalize.

    Returns
    -------
    name_normed :
        The normalized name.
    """
    field = field.upper()
    field = field.re_replace(r"[^A-Za-z0-9]+", " ")
    field = field.re_replace(r"\s+", " ")
    field = field.strip()
    return field


def normalize_name(name: ir.StructValue) -> ir.StructValue:
    """Convert to uppercase, normalize whitespace, and remove non-alphanumeric.

    Parameters
    ----------
    name :
        The name to normalize.

    Returns
    -------
    name_normed :
        The normalized name.
    """
    return ibis.struct(
        {
            "prefix": normalize_name_field(name["prefix"]),
            "first": normalize_name_field(name["first"]),
            "middle": normalize_name_field(name["middle"]),
            "last": normalize_name_field(name["last"]),
            "suffix": normalize_name_field(name["suffix"]),
            "nickname": normalize_name_field(name["nickname"]),
        }
    )


def name_tokens(name: ir.StructValue) -> ir.ArrayValue:
    """Get all the tokens from a name."""
    return (
        ibis.array(
            [
                name["prefix"].re_split(r"\s+"),
                name["first"].re_split(r"\s+"),
                name["middle"].re_split(r"\s+"),
                name["last"].re_split(r"\s+"),
                name["suffix"].re_split(r"\s+"),
                name["nickname"].re_split(r"\s+"),
            ]
        )
        .flatten()
        .unique()
    )
