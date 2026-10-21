import pytest
from pydantic import ValidationError

from app.schemas import PasswordResetRequest, RegisterRequest
from app.schemas import OntologyRelationRequest, OntologySkillRequest
from app.utils.security import hash_password, verify_password
from fastapi.testclient import TestClient
from app.main import app
from app.db.postgres import get_db
from unittest.mock import MagicMock
from app.api.candidates import _extract_text
from fastapi import HTTPException
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from app.core.hybrid_matcher import calibrated_score


def test_bcrypt_length_does_not_allow_silent_truncation():
    hashed = hash_password("a" * 72)
    assert verify_password("a" * 72, hashed)
    assert not verify_password("a" * 73, hashed)
    with pytest.raises(ValueError):
        hash_password("a" * 73)


def test_multibyte_password_length_is_checked():
    with pytest.raises(ValidationError):
        RegisterRequest(email="test@example.org", password="\u00e9" * 40, role="candidate", full_name="Test")
    with pytest.raises(ValidationError):
        PasswordResetRequest(token="a" * 43, new_password="\u00e9" * 40)


def test_login_throttling_and_security_headers():
    database = MagicMock()
    database.scalar.return_value = None
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: database
    try:
        with TestClient(app) as client:
            for _ in range(10):
                assert client.post("/api/auth/login", json={"email": "test@example.org", "password": "wrong"}).status_code == 401
            response = client.post("/api/auth/login", json={"email": "test@example.org", "password": "wrong"})
            assert response.status_code == 429
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_ontology_rejects_invalid_names_and_weights():
    with pytest.raises(ValidationError):
        OntologySkillRequest(name=" ", category="Programming", source="Reviewed")
    with pytest.raises(ValidationError):
        OntologyRelationRequest(source_skill="SQL", target_skill=" sql ", weight=0.5, source="Reviewed")
    with pytest.raises(ValidationError):
        OntologyRelationRequest(source_skill="SQL", target_skill="Python", weight=2, source="Reviewed")


@pytest.mark.parametrize("filename", ["resume.pdf", "resume.docx"])
def test_resume_extension_is_not_sufficient(filename):
    with pytest.raises(HTTPException) as failure:
        _extract_text(filename, b"not a document")
    assert failure.value.status_code == 415


def _text_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
               b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    document, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(document)
    document += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1) + b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    return document + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)


def test_valid_pdf_resume_text_and_skills_are_extracted():
    from app.api.candidates import _skills_from_text

    text = _extract_text("resume.pdf", _text_pdf("Data analyst skilled in Python and SQL"))
    assert "Python and SQL" in text
    assert {"python", "sql"} <= set(_skills_from_text(text))


def test_docx_expansion_limit():
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"a" * (31 * 1024 * 1024))
    with pytest.raises(HTTPException) as failure:
        _extract_text("resume.docx", buffer.getvalue())
    assert failure.value.status_code == 413


def test_model_rejects_nonfinite_features():
    with pytest.raises(ValueError):
        calibrated_score(float("nan"), 0.5, 0.5)
    assert 0 <= calibrated_score(0.7, 0.8, 0.5)[0] <= 1