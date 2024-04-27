from __future__ import annotations

import pytest

from mismo.block import sample_all_pairs


@pytest.mark.parametrize(
    "n_records,max_pairs",
    [
        (10_000, 0),
        (10_000, 1),
        (10_000, 2),
        (10_000, 10),
        (10_000, 100_000),
        # Stress test the implementation we
        # use to ensure that pairs are not duplicated.
        (2, 3),
        (10, 99),
    ],
)
def test_sample_all_pairs(table_factory, n_records: int, max_pairs: int):
    t = table_factory(
        {
            "record_id": range(n_records),
            # just have something here to check that the column is included in output
            "value": [i // 7 for i in range(n_records)],
        }
    )
    df = sample_all_pairs(t, t, max_pairs=max_pairs).execute()
    assert df.columns.tolist() == ["record_id_l", "record_id_r", "value_l", "value_r"]
    assert len(df) == max_pairs
    assert df.record_id_l.notnull().all()
    assert df.record_id_r.notnull().all()
    # We get no duplicates
    assert len(df.drop_duplicates()) == max_pairs

    # Only do these stats if we have a reasonable number of pairs
    if max_pairs >= 1000:
        # These two aren't correlated
        assert (df.record_id_l == df.record_id_r).mean() < 0.01
        # We get about an even distribution, the head or tail are not overrepresented
        # We expect the mean of record ids to be about half of the n_pairs
        expected = n_records / 2
        pct_err_l = abs(df.record_id_l.mean() - expected) / expected
        pct_err_r = abs(df.record_id_r.mean() - expected) / expected
        assert pct_err_l < 0.01
        assert pct_err_r < 0.01


@pytest.mark.parametrize("max_pairs", [None, 0, 1, 100_000])
def test_sample_all_pairs_empty(table_factory, max_pairs: int | None):
    t = table_factory({"record_id": []})
    df = sample_all_pairs(t, t, max_pairs=max_pairs).execute()
    assert df.columns.tolist() == ["record_id_l", "record_id_r"]
    assert len(df) == 0


def test_sample_all_pairs_warns(table_factory):
    t = table_factory({"record_id": range(100_000)})
    with pytest.warns(UserWarning):
        sample_all_pairs(t, t)
