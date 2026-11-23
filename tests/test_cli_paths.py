"""Tests for the --dataset switch: paths.DATASETS and how the command line fills its defaults."""

from __future__ import annotations

import pytest

from runoffwatch.__main__ import DATASET_ARGS, build_parser, parse_args, resolve_paths
from runoffwatch.paths import DATASETS, DEFAULT_DATASET

KEYS = {"runs", "interim", "features", "models", "results", "figures", "france_out", "trust"}


def test_datasets_have_the_same_keys():
    assert set(DATASETS) == {"corrected", "delivered"}
    assert set(DATASETS["corrected"]) == set(DATASETS["delivered"]) == KEYS
    assert DEFAULT_DATASET == "corrected"


def test_dataset_values():
    c, d = DATASETS["corrected"], DATASETS["delivered"]
    assert c["runs"] == "data/raw/runs_fixed" and d["runs"] == "data/raw/runs"
    assert c["trust"] == "balance" and d["trust"] == "envelope"
    assert d["models"] == "models/delivered" and c["models"] == "models"
    # the two data sets must never read from or write to the same place
    for k in KEYS - {"trust"}:
        assert c[k] != d[k], k


def test_dataset_args_only_name_known_keys():
    for cmd, mapping in DATASET_ARGS.items():
        assert set(mapping.values()) <= KEYS, cmd


def test_default_dataset_is_corrected():
    a = parse_args(["audit"])
    assert a.dataset == "corrected"


# command, attribute -> key in DATASETS
CASES = [(cmd, arg, key) for cmd, m in DATASET_ARGS.items() for arg, key in m.items()]


@pytest.mark.parametrize("dataset", ["corrected", "delivered"])
@pytest.mark.parametrize("cmd, arg, key", CASES)
def test_defaults_come_from_the_dataset(dataset, cmd, arg, key):
    a = parse_args(["--dataset", dataset, cmd])
    assert getattr(a, arg) == DATASETS[dataset][key]


@pytest.mark.parametrize("dataset", ["corrected", "delivered"])
def test_examples_by_hand(dataset):
    p = DATASETS[dataset]
    a = parse_args(["--dataset", dataset, "audit"])
    assert (a.runs, a.interim, a.trust, a.results, a.figures) == (
        p["runs"], p["interim"], p["trust"], p["results"], p["figures"])
    a = parse_args(["--dataset", dataset, "france"])
    assert (a.interim, a.features, a.models, a.out) == (p["interim"], p["features"], p["models"], p["france_out"])
    a = parse_args(["--dataset", dataset, "features"])
    assert (a.interim, a.out) == (p["interim"], p["features"])


@pytest.mark.parametrize("dataset", ["corrected", "delivered"])
def test_explicit_paths_win(dataset):
    a = parse_args(["--dataset", dataset, "audit", "--runs", "R", "--interim", "I", "--trust", "envelope"])
    assert (a.runs, a.interim, a.trust) == ("R", "I", "envelope")
    assert a.results == DATASETS[dataset]["results"]          # not given -> still from the data set
    a = parse_args(["--dataset", dataset, "train", "--features", "F.parquet", "--models", "M"])
    assert (a.features, a.models) == ("F.parquet", "M")
    a = parse_args(["--dataset", dataset, "qc", "--out", "O"])
    assert a.out == "O" and a.runs == DATASETS[dataset]["runs"]
    a = parse_args(["--dataset", dataset, "whatif", "--models", "M2"])
    assert a.models == "M2"


@pytest.mark.parametrize("dataset", ["corrected", "delivered"])
def test_extract_and_rerun_keep_fixed_defaults(dataset):
    a = parse_args(["--dataset", dataset, "extract"])
    assert (a.archives, a.out) == ("data/raw/archives", "data/raw/runs")
    a = parse_args(["--dataset", dataset, "rerun", "--exe", "WINPRZM.exe"])
    assert (a.runs, a.out) == ("data/raw/runs", "data/raw/runs_fixed")


def test_build_parser_leaves_paths_empty_until_resolved():
    a = build_parser().parse_args(["--dataset", "delivered", "train"])
    assert a.features is None and a.models is None
    assert resolve_paths(a) is a
    assert a.models == "models/delivered"


def test_dataset_must_come_before_the_command():
    with pytest.raises(SystemExit):
        parse_args(["audit", "--dataset", "delivered"])


def test_unknown_dataset_and_trust_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--dataset", "other", "audit"])
    with pytest.raises(SystemExit):
        parse_args(["audit", "--trust", "other"])
