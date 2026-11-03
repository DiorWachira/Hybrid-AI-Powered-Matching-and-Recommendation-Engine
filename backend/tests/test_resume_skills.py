from io import BytesIO

import numpy as np
from docx import Document

from app.api.candidates import _extract_text, _merged_skills
from app.core import hybrid_matcher
from app.core.skill_vocabulary import detect_skills


def test_detects_the_skills_it_roles_require():
    text = "Network Security, SIEM, Incident Response, Linux, Windows Server, Active Directory, Penetration Testing, Cloud Security"
    assert {"Network Security", "SIEM", "Incident Response", "Linux", "Windows Server", "Active Directory", "Penetration Testing", "Cloud Security"} <= set(detect_skills(text))


def test_detection_matches_whole_terms_only():
    assert detect_skills("MySQL and GitHub Actions") == ["GitHub", "GitHub Actions", "MySQL"]
    assert "Java" not in detect_skills("JavaScript developer")
    assert "C++" in detect_skills("Wrote C++ services")


def test_everyday_words_are_not_skills_unless_capitalised():
    assert detect_skills("I react quickly, excel at support and swift delivery") == []
    assert {"React", "Excel"} <= set(detect_skills("Built React dashboards and Excel models"))


def test_other_spellings_use_the_canonical_name():
    assert detect_skills("Designed a RESTful service, cicd pipelines on Postgres") == ["CI/CD", "PostgreSQL", "REST APIs"]


def test_non_it_skills_are_not_detected():
    assert detect_skills("Financial Accounting and Taxation with IFRS Reporting") == []


def test_uploading_a_resume_keeps_skills_already_on_the_profile():
    assert _merged_skills(["Rust", "python"], ["Python", "SQL"]) == ["Rust", "python", "SQL"]
    assert _merged_skills(None, ["SQL"]) == ["SQL"]
    assert len(_merged_skills([f"skill {index}" for index in range(50)], ["SQL"])) == 50


def test_docx_text_includes_table_cells():
    document = Document()
    document.add_paragraph("Profile")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Skills"
    table.rows[0].cells[1].text = "SIEM and Incident Response"
    merged = document.add_table(rows=1, cols=2)
    merged.rows[0].cells[0].merge(merged.rows[0].cells[1]).text = "Only once"
    content = BytesIO()
    document.save(content)
    text = _extract_text("resume.docx", content.getvalue())
    assert "SIEM and Incident Response" in text
    assert text.count("Only once") == 1


def _counting_encoder(monkeypatch):
    calls = []

    class Encoder:
        def encode(self, texts, **options):
            calls.append(list(texts))
            return np.asarray([[1.0, 0.0] for _ in texts])

    encoder = Encoder()
    monkeypatch.setattr(hybrid_matcher, "_get_model", lambda: encoder)
    return calls


def test_repeat_scoring_reuses_cached_embeddings(monkeypatch):
    calls = _counting_encoder(monkeypatch)
    assert hybrid_matcher.semantic_similarities(["first", "second"], "job") == [1.0, 1.0]
    assert hybrid_matcher.semantic_similarities(["first", "second"], "job") == [1.0, 1.0]
    assert calls == [["first", "second", "job"]]
    hybrid_matcher.semantic_similarities(["first", "third"], "job")
    assert calls[-1] == ["third"]


def test_duplicate_texts_are_encoded_once_and_still_scored_individually(monkeypatch):
    calls = _counting_encoder(monkeypatch)
    assert hybrid_matcher.semantic_similarities(["same", "same"], "job") == [1.0, 1.0]
    assert calls == [["same", "job"]]


def test_cache_is_bounded_and_cleared_for_a_new_model(monkeypatch):
    calls = _counting_encoder(monkeypatch)
    monkeypatch.setattr(hybrid_matcher, "EMBEDDING_CACHE_SIZE", 2)
    hybrid_matcher.semantic_similarities(["a", "b"], "job")
    assert len(hybrid_matcher._embedding_cache) == 2
    calls.clear()
    second = _counting_encoder(monkeypatch)
    hybrid_matcher.semantic_similarities(["a"], "job")
    assert second == [["a", "job"]] and calls == []
