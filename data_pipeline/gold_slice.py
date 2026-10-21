"""Hand-labelled gold slice: a blind labelling sheet, then model scores against the human labels. Never promotes.

``export`` samples IT-role candidate-job pairs from the held-out (warm/cold test) pairs of a seeded synthetic
population that no model was trained on, stratified across the active model's score bands so labels are not
dominated by easy pairs. The sheet shows the profile and the job only: no model score, synthetic label or
latent field. The answer key freezes each pair's scoring inputs (semantic score, skills, experience) and its
synthetic label, so ``evaluate`` never regenerates the population: labels stay valid when the generator changes.
``evaluate`` scores one or more artifacts against the filled-in sheet, reports how often the synthetic label
agrees with the human one, and inter-annotator agreement when a second sheet is given.

    python -m data_pipeline.gold_slice export --pairs 150
    python -m data_pipeline.gold_slice evaluate --labels data_pipeline/gold_slice/<slice>/labelling_sheet.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import cohen_kappa_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "backend")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backend.app.core.hybrid_matcher import _artifact, _load_artifact, calibrated_score_for  # noqa: E402
from backend.app.core.match_features import contract_features  # noqa: E402
from backend.app.core.text_preprocessing import anonymize_resume_text  # noqa: E402
from data_pipeline.epoch_artifacts import _canonical_json  # noqa: E402
from data_pipeline.epoch_trainer import LABEL_SOURCES, LABEL_V3, classification_metrics, prepare_synthetic_data  # noqa: E402
from data_pipeline.evaluate_model import DEFAULT_SEED  # noqa: E402

DEFAULT_OUTPUT_ROOT = ROOT / "data_pipeline" / "gold_slice"
# Outside the checkout: the data cache is written with atomic replaces, which fail in OneDrive-synced folders.
DEFAULT_CACHE_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "JobBridge" / "gold-slice-cache"
# Fixed so re-exporting at a later commit samples the same population while the generator is unchanged.
DATASET_IDENTITY = "gold-slice-population-v1"
NON_IT_ROLES = {"Accountant"}
SCORE_BANDS = 5
HELD_OUT = ("warm_test", "cold_test")
SHEET_COLUMNS = ["pair_id", "job_title", "job_specialisation", "job_required_skills", "job_required_years", "job_mandatory_certifications", "job_description",
                 "candidate_target_role", "candidate_specialisation", "candidate_years", "candidate_education", "candidate_skills", "candidate_certifications",
                 "candidate_resume", "label", "notes"]


def _population(cache_root: Path, seed: int, label_source: str, artifact: dict) -> tuple:
    features, labels, partitions, manifest = prepare_synthetic_data(cache_root, code_commit=DATASET_IDENTITY, seed=seed, pinned_encoder_revision=artifact["encoder_revision"], feature_contract=artifact["feature_contract"], label_source=label_source)
    snapshot = json.loads((cache_root / _cache_key_dir(manifest) / "synthetic_snapshot.json").read_text(encoding="utf-8"))
    return features, labels, partitions, manifest, snapshot


def _cache_key_dir(manifest: dict) -> str:
    # prepare_synthetic_data keys its cache folder by the specification it records in the manifest.
    return hashlib.sha256(_canonical_json(manifest["specification"])).hexdigest()


def _score(artifact: dict, features: np.ndarray, rows: list[int]) -> np.ndarray:
    return np.asarray([calibrated_score_for(artifact, *map(float, features[row]))[0] for row in rows], dtype=float)


def export(output_root: Path, *, pairs: int = 150, seed: int = DEFAULT_SEED, label_source: str = LABEL_V3, cache_root: Path = DEFAULT_CACHE_ROOT) -> Path:
    active = _artifact()
    features, labels, partitions, manifest, snapshot = _population(cache_root, seed, label_source, active)
    candidates = {item["candidate_id"]: item for item in snapshot["candidates"]}
    jobs = {item["job_id"]: item for item in snapshot["jobs"]}
    identities = manifest["pair_identities"]
    pool = [int(row) for split in HELD_OUT for row in partitions[split] if jobs[identities[row]["job_id"]]["title"] not in NON_IT_ROLES]
    if len(pool) < pairs:
        raise ValueError(f"only {len(pool)} held-out IT pairs are available")
    scores = _score(active, features, pool)
    # Equal-count bands by the active model's score, then an equal draw from each, so hard pairs are labelled too.
    order = np.argsort(scores, kind="stable")
    rng = np.random.default_rng(seed)
    chosen = []
    for band, members in enumerate(np.array_split(order, SCORE_BANDS)):
        take = pairs // SCORE_BANDS + (band < pairs % SCORE_BANDS)
        chosen.extend((pool[index], band) for index in rng.choice(members, size=take, replace=False))
    chosen = [chosen[index] for index in rng.permutation(len(chosen))]
    slice_id = f"gold-seed{seed}-{len(chosen)}pairs"
    folder = output_root / slice_id
    if (folder / "labelling_sheet.csv").exists():
        raise FileExistsError(f"{folder} already has a labelling sheet; refusing to overwrite labels")
    folder.mkdir(parents=True, exist_ok=True)
    key = {"slice_id": slice_id, "seed": seed, "label_source": label_source, "dataset_identity": DATASET_IDENTITY, "dataset_sha256": manifest["dataset_version"],
           "encoder_revision": manifest["encoder_revision"], "sampled_with_model": active["model_version"], "score_bands": SCORE_BANDS, "excluded_roles": sorted(NON_IT_ROLES),
           "pairs": []}
    with (folder / "labelling_sheet.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for number, (row, band) in enumerate(chosen, start=1):
            identity = identities[row]
            candidate, job = candidates[identity["candidate_id"]], jobs[identity["job_id"]]
            pair_id = f"G{number:03d}"
            key["pairs"].append({"pair_id": pair_id, "row": row, "candidate_id": identity["candidate_id"], "job_id": identity["job_id"], "split": identity["split"], "score_band": int(band),
                                 "synthetic_label": int(labels[row]), "inputs": {"semantic": float(features[row][0]), "candidate_skills": candidate["skills"], "required_skills": job["required_skills"],
                                 "years_experience": candidate["years_experience"], "required_experience_years": job["required_experience_years"], "certification_count": len(candidate["certifications"])}})
            writer.writerow({
                "pair_id": pair_id, "job_title": job["title"], "job_specialisation": job["specialisation"], "job_required_skills": "; ".join(job["required_skills"]),
                "job_required_years": job["required_experience_years"], "job_mandatory_certifications": "; ".join(job["mandatory_certifications"]), "job_description": job["description"],
                "candidate_target_role": candidate["target_role"], "candidate_specialisation": candidate["specialisation"], "candidate_years": candidate["years_experience"],
                "candidate_education": candidate["education"], "candidate_skills": "; ".join(candidate["skills"]), "candidate_certifications": "; ".join(candidate["certifications"]),
                "candidate_resume": anonymize_resume_text(candidate["resume_text"]), "label": "", "notes": "",
            })
    # The key links pairs to model rows; keep it closed while labelling so scores and bands stay blind.
    (folder / "answer_key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    return folder


def _read_labels(path: Path) -> dict[str, int]:
    labels = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for line in csv.DictReader(stream):
            value = (line.get("label") or "").strip()
            if value == "":
                continue
            if value not in ("0", "1"):
                raise ValueError(f"{line['pair_id']}: label must be 0, 1 or blank, got {value!r}")
            labels[line["pair_id"]] = int(value)
    return labels


def _bootstrap_auc(human: np.ndarray, scores: np.ndarray, rounds: int = 2000, seed: int = 0) -> list[float] | None:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(rounds):
        sample = rng.integers(0, len(human), len(human))
        if len(np.unique(human[sample])) == 2:
            values.append(roc_auc_score(human[sample], scores[sample]))
    return [round(float(value), 4) for value in np.percentile(values, [2.5, 97.5])] if values else None


def _frozen_scores(artifact: dict, pairs: list[dict]) -> np.ndarray:
    scores = []
    for pair in pairs:
        inputs = pair["inputs"]
        skill, growth = contract_features(artifact["feature_contract"], candidate_skills=inputs["candidate_skills"], required_skills=inputs["required_skills"], years_experience=inputs["years_experience"], required_experience_years=inputs["required_experience_years"], certification_count=inputs["certification_count"])
        scores.append(calibrated_score_for(artifact, inputs["semantic"], skill, growth)[0])
    return np.asarray(scores, dtype=float)


def evaluate(labels_path: Path, *, artifacts: list[Path] | None = None, second_labels: Path | None = None) -> dict:
    key = json.loads((labels_path.parent / "answer_key.json").read_text(encoding="utf-8"))
    human_labels = _read_labels(labels_path)
    pairs = [pair for pair in key["pairs"] if pair["pair_id"] in human_labels]
    if len(pairs) < 20:
        raise ValueError(f"only {len(pairs)} pairs are labelled; label at least 20 before evaluating")
    human = np.asarray([human_labels[pair["pair_id"]] for pair in pairs])
    if any("inputs" not in pair for pair in pairs):
        raise ValueError("this answer key predates frozen scoring inputs; re-export the slice")
    report = {"slice_id": key["slice_id"], "labelled_pairs": len(pairs), "of_pairs": len(key["pairs"]), "human_positive_rate": round(float(human.mean()), 4), "models": {},
              "independent_quality_validated": False,
              "limitations": ["Profiles and jobs are synthetic even though the labels are human; this checks the model against human judgement, not hiring outcomes.",
                              "One labeller's judgement is not ground truth; report inter-annotator agreement before relying on these numbers.",
                              "Pairs were sampled using the active model's score bands, so metrics are over a score-stratified, not natural, mix."]}
    for path in [None, *(artifacts or [])]:
        artifact = _load_artifact(path) if path else _artifact()
        if artifact["encoder_revision"] != key["encoder_revision"]:
            raise ValueError("model uses a different encoder revision than the frozen semantic scores")
        scores = _frozen_scores(artifact, pairs)
        metrics = {name: (round(value, 4) if isinstance(value, float) else value) for name, value in classification_metrics(human, scores, float(artifact["decision_threshold"])).items()}
        metrics["roc_auc_95ci"] = _bootstrap_auc(human, scores)
        report["models"][f"{artifact['model_version']} ({artifact['feature_contract']})" + ("" if path else " [active]")] = metrics
    synthetic = np.asarray([pair["synthetic_label"] for pair in pairs])
    report["synthetic_label_vs_human"] = {"agreement": round(float(np.mean(synthetic == human)), 4), "cohen_kappa": round(float(cohen_kappa_score(human, synthetic)), 4), "synthetic_positive_rate": round(float(synthetic.mean()), 4)}
    if second_labels:
        other = _read_labels(second_labels)
        shared = [pair["pair_id"] for pair in pairs if pair["pair_id"] in other]
        report["inter_annotator"] = {"shared_pairs": len(shared), "agreement": round(float(np.mean([human_labels[name] == other[name] for name in shared])), 4) if shared else None,
                                     "cohen_kappa": round(float(cohen_kappa_score([human_labels[name] for name in shared], [other[name] for name in shared])), 4) if len(shared) >= 2 else None}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    exporting = commands.add_parser("export", help="write a blind labelling sheet and its answer key")
    exporting.add_argument("--pairs", type=int, default=150)
    exporting.add_argument("--seed", type=int, default=DEFAULT_SEED)
    exporting.add_argument("--label-source", choices=LABEL_SOURCES, default=LABEL_V3)
    exporting.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    exporting.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    evaluating = commands.add_parser("evaluate", help="score artifacts against a filled-in sheet")
    evaluating.add_argument("--labels", type=Path, required=True)
    evaluating.add_argument("--artifact", type=Path, action="append", help="candidate artifact to score alongside the active one; repeatable")
    evaluating.add_argument("--second-labels", type=Path, help="a second labeller's copy of the same sheet")
    evaluating.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "export":
        if not 20 <= args.pairs <= 500:
            parser.error("--pairs must be between 20 and 500")
        folder = export(args.output_root, pairs=args.pairs, seed=args.seed, label_source=args.label_source, cache_root=args.cache_root)
        print(json.dumps({"sheet": str(folder / "labelling_sheet.csv"), "answer_key": str(folder / "answer_key.json"), "promotion_performed": False}, indent=2))
        return
    report = evaluate(args.labels, artifacts=args.artifact, second_labels=args.second_labels)
    serialized = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
