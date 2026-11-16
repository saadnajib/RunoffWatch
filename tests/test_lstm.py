"""Smoke tests for the LSTM surrogate. Skipped when PyTorch is not installed."""
import warnings

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from runoffwatch import lstm  # noqa: E402
from runoffwatch.features import build_feature_table  # noqa: E402
from test_models_whatif import _synthetic_interim  # noqa: E402


@pytest.fixture(scope="module")
def interim(tmp_path_factory):
    root = tmp_path_factory.mktemp("lstm") / "interim"
    _synthetic_interim(root, n_files=20)
    return root


def test_run_sequences_shapes_and_masks():
    idx = pd.date_range("1990-01-01", "1993-12-31", freq="D")
    daily = pd.DataFrame({"rain_mm": 1.0, "temp_c": 10.0, "pan_evap_mm": 2.0, "runoff_mm": 0.5,
                          "pest_runoff_gha": 0.1, "days_since_app": 5.0}, index=idx)
    X, Y, M, meta = lstm.run_sequences(daily, (81, 81, 86, 91), pd.Timestamp("1992-03-01"), [1990, 1991, 1992, 1993])
    assert [m[0] for m in meta] == [1990, 1991, 1992, 1993][:len(meta)] and len(meta) >= 3
    assert X[0].shape == (lstm.LENGTH, len(lstm.DYNAMIC)) and Y[0].shape == (lstm.LENGTH, 2)
    assert M[0][:lstm.WARMUP].sum() == 0                       # warm-up days are never scored
    assert M[0][lstm.WARMUP:, 0].min() == 1                    # runoff is scored on every later day
    assert M[0][lstm.WARMUP:, 1].min() == 1                    # 1990 and 1991 are before clean_until
    assert M[2][:, 1].sum() == 0                               # 1992 starts at clean_until: pesticide not trusted
    assert M[2][lstm.WARMUP:, 0].max() == 1                    # ... but runoff still is
    np.testing.assert_allclose(Y[0][lstm.WARMUP, 0], np.log1p(0.5), rtol=1e-6)
    np.testing.assert_allclose(Y[0][lstm.WARMUP, 1], np.log1p(lstm.LOSS_SCALE * 0.1), rtol=1e-6)


def test_run_sequences_skips_year_of_early_crash():
    idx = pd.date_range("1990-01-01", "1991-05-01", freq="D")
    daily = pd.DataFrame({"rain_mm": 0.0, "temp_c": 5.0, "pan_evap_mm": 1.0, "runoff_mm": 0.0,
                          "pest_runoff_gha": 0.0, "days_since_app": 1.0}, index=idx)
    _, _, _, meta = lstm.run_sequences(daily, (81, 81, 86, 91), pd.Timestamp("1995-03-01"), [1990, 1991])
    assert [m[0] for m in meta] == [1990]


def test_build_dataset_split_matches_tree_split(interim):
    data = lstm.build_dataset(interim)
    meta = data["meta"]
    assert len(meta) == len(data["X"]) == len(data["S"])
    assert set(meta.loc[meta["split"] == "test", "app_year"]) <= {1992, 1996}
    assert set(meta.loc[meta["split"] == "val", "app_year"]) == {1994}
    assert not set(meta.loc[meta["split"] == "train", "app_year"]) & {1992, 1994, 1996}
    test_runs, train_runs = set(meta.loc[meta["split"] == "test", "run"]), set(meta.loc[meta["split"] == "train", "run"])
    assert test_runs and train_runs and not test_runs & train_runs
    assert np.isfinite(data["X"]).all() and np.isfinite(data["S"]).all()


def test_fit_predict_and_compare(interim, tmp_path):
    features = tmp_path / "features.parquet"
    build_feature_table(interim, features)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = lstm.train_and_compare(interim, features, model_dir=tmp_path, results=tmp_path, figures=tmp_path,
                                     epochs=2, threads=1)
    assert (tmp_path / "lstm_vs_trees.json").exists() and (tmp_path / "lstm.pt").exists()
    assert (tmp_path / "m8_lstm_vs_trees.png").exists()
    assert out["rows_compared"] > 0 and out["epochs_run"] == 2
    for key in ("lstm", "trees"):
        assert np.isfinite(out[key]["runoff"]["r2_daily"]) and np.isfinite(out[key]["loss"]["r2_daily"])
    assert out["trees"]["runoff"]["r2_daily"] > 0.5            # the known synthetic relation is learnable
