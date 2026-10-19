"""Gold-slice export stays blind and IT-only; evaluation scores against human labels and guards drift."""
import csv
import json

import numpy as np
import pytest

from data_pipeline import epoch_trainer, gold_slice


@pytest.fixture
def small_population(monkeypatch):
    def encoder(texts):
        vectors = np.random.default_rng(len(texts)).normal(size=(len(texts), 8))
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    def prepare(cache_root, *, pinned_encoder_revision, **options):
        return epoch_trainer.prepare_synthetic_data(cache_root, candidate_count=200, job_count=100, encode=encoder, **options)

    monkeypatch.setattr(gold_slice, "prepare_synthetic_data", prepare)


def _sheet(folder):
    with (folder / "labelling_sheet.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_labels(folder, labels, name="labelling_sheet.csv"):
    rows = _sheet(folder)
    for row in rows:
        row["label"] = labels.get(row["pair_id"], "")
    with (folder / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=gold_slice.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return folder / name


def test_export_is_blind_it_only_held_out_and_band_balanced(tmp_path, small_population):
    folder = gold_slice.export(tmp_path / "out", pairs=40, cache_root=tmp_path / "cache")
    rows = _sheet(folder)
    key = json.loads((folder / "answer_key.json").read_text(encoding="utf-8"))
    assert len(rows) == len(key["pairs"]) == 40
    assert list(rows[0]) == gold_slice.SHEET_COLUMNS and all(row["label"] == "" for row in rows)
    assert not any("latent" in column or "score" in column for column in rows[0])
    assert {row["job_title"] for row in rows}.isdisjoint(gold_slice.NON_IT_ROLES)
    assert {pair["split"] for pair in key["pairs"]} <= set(gold_slice.HELD_OUT)
    assert sorted(np.bincount([pair["score_band"] for pair in key["pairs"]])) == [8] * gold_slice.SCORE_BANDS
    with pytest.raises(FileExistsError):
        gold_slice.export(tmp_path / "out", pairs=40, cache_root=tmp_path / "cache")


def test_evaluate_scores_models_against_human_labels_and_agreement(tmp_path, small_population):
    folder = gold_slice.export(tmp_path / "out", pairs=40, cache_root=tmp_path / "cache")
    key = json.loads((folder / "answer_key.json").read_text(encoding="utf-8"))
    _, labels, _, _ = gold_slice.prepare_synthetic_data(tmp_path / "cache", pinned_encoder_revision=None, code_commit=gold_slice.DATASET_IDENTITY, seed=key["seed"], label_source=key["label_source"])
    synthetic = {pair["pair_id"]: str(labels[pair["row"]]) for pair in key["pairs"]}
    if len(set(synthetic.values())) < 2:
        synthetic["G001"] = str(1 - int(synthetic["G001"]))
    sheet = _write_labels(folder, synthetic)
    second = _write_labels(folder, {**synthetic, "G002": str(1 - int(synthetic["G002"]))}, "second.csv")
    report = gold_slice.evaluate(sheet, second_labels=second, cache_root=tmp_path / "cache")
    assert report["labelled_pairs"] == 40 and report["independent_quality_validated"] is False
    [(name, metrics)] = report["models"].items()
    assert name.endswith("[active]") and 0 <= metrics["roc_auc"] <= 1 and metrics["count"] == 40
    assert report["synthetic_label_vs_human"]["agreement"] >= 39 / 40
    assert report["inter_annotator"]["shared_pairs"] == 40 and report["inter_annotator"]["agreement"] == 39 / 40


def test_evaluate_rejects_bad_labels_too_few_labels_and_population_drift(tmp_path, small_population):
    folder = gold_slice.export(tmp_path / "out", pairs=40, cache_root=tmp_path / "cache")
    with pytest.raises(ValueError, match="at least 20"):
        gold_slice.evaluate(_write_labels(folder, {"G001": "1"}), cache_root=tmp_path / "cache")
    with pytest.raises(ValueError, match="must be 0, 1 or blank"):
        gold_slice.evaluate(_write_labels(folder, {"G001": "yes"}), cache_root=tmp_path / "cache")
    sheet = _write_labels(folder, {f"G{number:03d}": str(number % 2) for number in range(1, 41)})
    key_path = folder / "answer_key.json"
    key_path.write_text(json.dumps({**json.loads(key_path.read_text(encoding="utf-8")), "dataset_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(ValueError, match="population differs"):
        gold_slice.evaluate(sheet, cache_root=tmp_path / "cache")
