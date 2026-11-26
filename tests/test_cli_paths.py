"""Tests for the --dataset switch: paths.DATASETS and how the command line fills its defaults."""

from __future__ import annotations

import pytest

from runoffwatch.__main__ import DATASET_ARGS, build_parser, parse_args, resolve_paths
from runoffwatch.paths import DATASETS, DEFAULT_DATASET

KEYS = {"runs", "interim", "features", "models", "results", "figures", "france_out", "trust", "features_from", "fields_interim"}


def test_datasets_have_the_same_keys():
    assert set(DATASETS) == {"corrected", "delivered", "varied", "dosecheck"}
    assert set(DATASETS["corrected"]) == set(DATASETS["delivered"]) == set(DATASETS["varied"]) == KEYS
    # the test-only data set has the same keys plus what makes it a test
    assert set(DATASETS["dosecheck"]) == KEYS | {"test_only", "compare_with", "what_is_new", "rerun"}
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
    assert (a.interim, a.features, a.models, a.out) == (p["fields_interim"], p["features"], p["models"], p["france_out"])
    a = parse_args(["--dataset", dataset, "features"])
    assert (a.interim, a.out) == (p["features_from"], p["features"])


def test_varied_dataset_builds_on_the_corrected_runs():
    v = DATASETS["varied"]
    assert v["runs"] == "data/raw/runs_varied" and v["trust"] == "balance"
    assert v["features_from"] == ["data/interim_fixed", "data/interim_varied"]      # 1 March runs plus the copies
    assert v["fields_interim"] == "data/interim_fixed"                              # one run per field for the long run
    assert v["models"] != DATASETS["corrected"]["models"] and v["results"] != DATASETS["corrected"]["results"]
    a = parse_args(["--dataset", "varied", "features", "--interim", "A", "B"])
    assert a.interim == ["A", "B"]
    a = parse_args(["whatif", "--dose", "0.24"])
    assert a.dose == 0.24
    a = parse_args(["france", "--spray", "15.10", "--dose", "1.2"])
    assert (a.spray, a.dose) == ("15.10", 1.2)


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


# --------------------------------------------------------------------------- #
# rerun: --out and --fields-from defaults depend on --variants
# --------------------------------------------------------------------------- #
from pathlib import Path  # noqa: E402

from runoffwatch.__main__ import RERUN_OUT, RERUN_VARIED_OUT, main  # noqa: E402

RR = ["rerun", "--exe", "WINPRZM.exe"]


def test_rerun_out_constants():
    assert (RERUN_OUT, RERUN_VARIED_OUT) == ("data/raw/runs_fixed", "data/raw/runs_varied")


@pytest.mark.parametrize("dataset", ["corrected", "delivered"])
@pytest.mark.parametrize("fixed_exists", [False, True])
def test_rerun_plain_defaults(tmp_path, monkeypatch, dataset, fixed_exists):
    monkeypatch.chdir(tmp_path)
    if fixed_exists:
        (tmp_path / "data/raw/runs_fixed").mkdir(parents=True)
    a = parse_args(["--dataset", dataset] + RR)
    assert (a.runs, a.out, a.fields_from, a.variants) == ("data/raw/runs", "data/raw/runs_fixed", None, 0)
    assert (a.spray_windows, a.doses, a.seed) == (None, None, 1)


def test_rerun_variants_defaults_without_fixed_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = parse_args(RR + ["--variants", "3"])
    assert (a.out, a.fields_from, a.variants) == ("data/raw/runs_varied", None, 3)


def test_rerun_variants_defaults_with_fixed_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/raw/runs_fixed").mkdir(parents=True)
    a = parse_args(RR + ["--variants", "2"])
    assert (a.out, a.fields_from) == ("data/raw/runs_varied", "data/raw/runs_fixed")


def test_rerun_fixed_must_be_a_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/raw").mkdir(parents=True)
    (tmp_path / "data/raw/runs_fixed").write_text("not a folder")
    assert parse_args(RR + ["--variants", "2"]).fields_from is None


def test_rerun_explicit_out_and_fields_from_win(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/raw/runs_fixed").mkdir(parents=True)
    a = parse_args(RR + ["--variants", "2", "--out", "O", "--fields-from", "F"])
    assert (a.out, a.fields_from) == ("O", "F")
    a = parse_args(RR + ["--out", "O2"])
    assert (a.out, a.fields_from) == ("O2", None)
    a = parse_args(RR + ["--fields-from", "F2"])                     # also allowed without variants
    assert (a.out, a.fields_from) == ("data/raw/runs_fixed", "F2")
    a = parse_args(RR + ["--variants", "1", "--out", "O3"])
    assert (a.out, a.fields_from) == ("O3", "data/raw/runs_fixed")


def test_rerun_variant_options_are_parsed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = parse_args(RR + ["--variants", "4", "--spray-windows", "01.03-31.03,01.10-15.10", "--doses", "0.5,1.0",
                         "--seed", "9"])
    assert (a.variants, a.spray_windows, a.doses, a.seed) == (4, "01.03-31.03,01.10-15.10", "0.5,1.0", 9)


def test_rerun_main_passes_variant_options(tmp_path, monkeypatch):
    from runoffwatch import rerun
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/raw/runs_fixed").mkdir(parents=True)
    seen = {}

    def fake(runs, out, exe, work, **kw):
        seen.update(runs=runs, out=out, exe=exe, work=work, **kw)
        return [{"status": "ok"}]

    monkeypatch.setattr(rerun, "rerun_all", fake)
    assert main(RR + ["--variants", "2", "--spray-windows", " 01.03-31.03 , 01.10-15.10,", "--doses", "0.5,1.0",
                      "--seed", "9", "--henry", "keep"]) == 0
    assert (seen["runs"], seen["out"], seen["exe"]) == ("data/raw/runs", "data/raw/runs_varied", "WINPRZM.exe")
    assert seen["windows"] == ("01.03-31.03", "01.10-15.10") and seen["doses"] == ("0.5", "1.0")
    assert (seen["variants"], seen["seed"], seen["fields_from"]) == (2, 9, "data/raw/runs_fixed")
    assert seen["henry"] is None and seen["moisture_ref"] == rerun.MOISTURE_REF_FIXED
    seen.clear()
    assert main(RR) == 0
    assert seen["windows"] == rerun.DEFAULT_WINDOWS and seen["doses"] == rerun.DEFAULT_DOSES
    assert (seen["variants"], seen["out"], seen["fields_from"]) == (0, "data/raw/runs_fixed", None)


# add-weather is not tied to a data set: its defaults stay the same with every --dataset

@pytest.mark.parametrize("dataset", [[], ["--dataset", "delivered"], ["--dataset", "varied"]])
def test_cli_add_weather_defaults(dataset):
    a = parse_args([*dataset, "add-weather"])
    assert (a.runs, a.source) == ("data/raw/runs_varied", "data/raw/runs")
    a = parse_args(["add-weather", "--runs", "R", "--source", "S"])
    assert (a.runs, a.source) == ("R", "S")


def test_france_scenario_gets_its_own_folders():
    p = DATASETS["varied"]
    a = parse_args(["--dataset", "varied", "france", "--spray", "15.10", "--scenario", "autumn"])
    assert Path(a.results) == Path(p["results"]) / "autumn"
    assert Path(a.figures) == Path(p["figures"]) / "autumn"
    assert Path(a.out).name == Path(p["france_out"]).stem + "_autumn.parquet"
    plain = parse_args(["--dataset", "varied", "france"])
    assert (plain.results, plain.figures, plain.out) == (p["results"], p["figures"], p["france_out"])


def test_france_scenario_name_is_checked():
    import pytest
    with pytest.raises(SystemExit):
        parse_args(["france", "--scenario", "../elsewhere"])


# --------------------------------------------------------------------------- #
# The test-only data set (a dose the models have not seen) and the check command
# --------------------------------------------------------------------------- #
def test_dosecheck_never_writes_where_training_data_or_other_results_live():
    d = DATASETS["dosecheck"]
    assert d["test_only"] is True and d["models"] == DATASETS["varied"]["models"]       # tests the varied models
    for name in ("corrected", "delivered", "varied"):
        for k in ("runs", "interim", "features", "results", "figures", "france_out"):
            assert d[k] != DATASETS[name][k], (name, k)
        assert not set(d["features_from"]) & set(DATASETS[name]["features_from"]), name
    assert float(d["rerun"]["doses"]) not in (0.24, 1.2, 2.4)                           # a dose the models never saw
    assert d["rerun"]["seed"] != 1                                                      # other spray dates than in training


@pytest.mark.parametrize("cmd", ["train", "lstm", "design", "france"])
def test_dosecheck_refuses_everything_that_trains_or_reuses_it(cmd):
    with pytest.raises(SystemExit, match="only for testing the frozen models"):
        parse_args(["--dataset", "dosecheck", cmd])


def test_dosecheck_defaults_for_rerun_add_weather_and_check(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = DATASETS["dosecheck"]
    a = parse_args(["--dataset", "dosecheck", "rerun", "--exe", "x.exe"])
    assert (a.out, a.variants, a.doses, a.seed, a.sample) == (d["runs"], 1, "0.60", 2, 500)
    a = parse_args(["--dataset", "dosecheck", "rerun", "--exe", "x.exe", "--sample", "50", "--seed", "7"])
    assert (a.sample, a.seed, a.doses) == (50, 7, "0.60")                               # what is typed wins
    assert parse_args(["--dataset", "dosecheck", "add-weather"]).runs == d["runs"]
    a = parse_args(["--dataset", "dosecheck", "check"])
    assert (a.features, a.models, a.results) == (d["features"], d["models"], d["results"])
    a = parse_args(["--dataset", "dosecheck", "features"])
    assert a.interim == d["features_from"] and a.out == d["features"]
    # the other data sets keep their old defaults
    a = parse_args(["rerun", "--exe", "x.exe"])
    assert (a.variants, a.doses, a.seed, a.sample) == (0, None, 1, None)


def test_train_refuses_a_frozen_model_folder(tmp_path, monkeypatch):
    """`train` must not overwrite frozen models; `train --cv` writes no models and is not stopped here."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "models").mkdir()
    for f in ("runoff.txt", "conc.txt", "high_loss.txt", "meta.json"):
        (tmp_path / "models" / f).write_text("x")
    from runoffwatch import models
    models.write_frozen(["models"], "models/FROZEN.json", frozen_on="2026-11-26", reason="test")
    with pytest.raises(SystemExit, match="are frozen"):
        main(["train", "--features", "none.parquet"])
    seen = {}
    monkeypatch.setattr(models, "train_all", lambda *a, **k: seen.setdefault("trained", a[1]) and {} or
                        {"split": 0, "runoff": 0, "loss": 0, "high_loss": 0})
    assert main(["train", "--features", "none.parquet", "--models", "models/new"]) == 0     # another folder is fine
    assert seen["trained"] == "models/new"


def test_check_without_the_new_runs_says_what_to_do(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "FROZEN.json").write_text('{"frozen_on": "2026-11-26", "folders": {"models/varied": {}}}')
    with pytest.raises(SystemExit, match="Run the steps before it first"):
        main(["--dataset", "dosecheck", "check"])
    (tmp_path / "models" / "FROZEN.json").unlink()
    with pytest.raises(SystemExit, match="is not frozen"):
        main(["--dataset", "dosecheck", "check"])
