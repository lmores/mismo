from __future__ import annotations

from typing import Iterable, Type

from ibis import _
from ibis.expr import types as ir

from mismo._util import sample_table
from mismo.block import KeyBlocker, sample_all_pairs
from mismo.compare import LevelComparer, MatchLevel

from ._weights import ComparerWeights, LevelWeights, Weights


def level_proportions(
    levels: Type[MatchLevel], labels: ir.IntegerColumn | ir.StringColumn
) -> list[float]:
    """
    Return the proportion of labels that fall into each [MatchLevel](mismo.compare.MatchLevel).
    """  # noqa: E501
    counts = (
        levels(labels)
        .as_integer()
        .name("level")
        .as_table()
        .group_by("level")
        .agg(n=_.count())
    )
    counts_dict: dict = counts.execute().set_index("level")["n"].to_dict()
    # If we didn't see a level, that won't be present in the value_counts table.
    # Add it in, with a count of 1 to regularaize it.
    # If a level shows shows up 0 times among nonmatches, this would lead to an odds
    # of M/0 = infinity.
    # If it shows up 0 times among matches, this would lead to an odds of 0/M = 0.
    # To avoid this, for any levels that we didn't see, we pretend we saw them once.
    int_levels = [levels(lev).as_integer() for lev in levels]
    for lev in int_levels:
        counts_dict.setdefault(lev, 1)
    n_total = sum(counts_dict.values())
    return [counts_dict[lev] / n_total for lev in int_levels]


def train_us_using_sampling(
    comparer: LevelComparer,
    left: ir.Table,
    right: ir.Table,
    *,
    max_pairs: int | None = None,
) -> list[float]:
    """Estimate the u weight using random sampling.

    This is from splink's `estimate_u_using_random_sampling()`

    The u parameters represent the proportion of record pairs
    that fall into each MatchLevel amongst truly non-matching records.

    This procedure takes a sample of `left` and `right` and generates the cartesian
    product of record pairs.
    The validity of the u values rests on the assumption that nearly all of the
    resultant pairs are non-matches. For large datasets, this is typically true.

    The results of estimate_u_using_random_sampling, and therefore an
    entire splink model, can be made reproducible by setting the seed
    parameter. Setting the seed will have performance implications as
    additional processing is required.

    Args:
        max_pairs:
            The maximum number of pairwise record pairs to sample.
            Larger will give more accurate estimates but lead to longer runtimes.
            In our experience at least 1e9 (one billion)
            gives best results but can take a long time to compute.
            1e7 (ten million) is often adequate whilst testing different model
            specifications, before the final model is estimated.
    """
    if max_pairs is None:
        max_pairs = 1_000_000_000
    sample = sample_all_pairs(left, right, max_pairs=max_pairs)
    labels = comparer(sample)[comparer.name]
    return level_proportions(comparer.levels, labels)


def train_ms_from_labels(
    comparer: LevelComparer,
    left: ir.Table,
    right: ir.Table,
    *,
    max_pairs: int | None = None,
    seed: int | None = None,
) -> list[float]:
    """Using the true labels in the dataset, estimate the m weight.

    The m parameter represent the proportion of record pairs
    that fall into each MatchLevel amongst truly matching pairs.

    The `label_true` column is used to generate true-match record pairs.

    For example, if the entity being matched is persons, and your
    input dataset(s) contain social security number, this could be
    used to estimate the m values for the model.

    Note that this column does not need to be fully populated.
    A common case is where a unique identifier such as social
    security number is only partially populated.
    When NULL values are encountered in the ground truth column,
    that record is simply ignored.

    Parameters
    ----------
    comparer
        The comparer to train.
    left
        The left dataset. Must contain a column "label_true".
    right
        The right dataset. Must contain a column "label_true".
    max_pairs
        The maximum number of pairs to sample.
    seed
        The random seed to use for sampling.

    Returns
    -------
    list[float]
        The estimated m weights.
    """
    pairs = _true_pairs_from_labels(left, right)
    if max_pairs is None:
        max_pairs = 1_000_000_000
    n_pairs = min(pairs.count().execute(), max_pairs)
    sample = sample_table(pairs, n_pairs, seed=seed)
    labels = comparer(sample)[comparer.name]
    return level_proportions(comparer.levels, labels)


def _true_pairs_from_labels(left: ir.Table, right: ir.Table) -> ir.Table:
    if "label_true" not in left.columns:
        raise ValueError(
            f"Left dataset must have a label_true column. Found: {left.columns}"
        )
    if "label_true" not in right.columns:
        raise ValueError(
            f"Right dataset must have a label_true column. Found: {right.columns}"
        )
    return KeyBlocker("label_true")(left, right)


def _train_using_labels(
    comparer: LevelComparer,
    left: ir.Table,
    right: ir.Table,
    *,
    max_pairs: int | None = None,
) -> ComparerWeights:
    ms = train_ms_from_labels(comparer, left, right, max_pairs=max_pairs)
    us = train_us_using_sampling(comparer, left, right, max_pairs=max_pairs)
    return make_weights(comparer, ms, us)


def train_using_labels(
    comparers: Iterable[LevelComparer],
    left: ir.Table,
    right: ir.Table,
    *,
    max_pairs: int | None = None,
) -> Weights:
    """Estimate all Weights for a set of LevelComparers using labeled data."""
    return Weights(
        [_train_using_labels(c, left, right, max_pairs=max_pairs) for c in comparers]
    )


def make_weights(comparer: LevelComparer, ms: list[float], us: list[float]):
    levels = comparer.levels
    assert len(ms) == len(us) == len(levels)
    level_weights = [
        LevelWeights(level, m=m, u=u) for level, m, u in zip(levels, ms, us)
    ]
    level_weights = [lw for lw in level_weights if lw.name != "else"]
    return ComparerWeights(comparer.name, level_weights)
