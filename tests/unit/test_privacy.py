import httpx
import pytest
import respx

from sip.domain import Confidentiality, DataClassification, PersonalData, SourceType
from sip.privacy.detectors import LocalDetector
from sip.privacy.extraction import UnsupportedFile, safe_filename
from sip.privacy.gateway import PrivacyGateway, UploadTooLarge
from sip.privacy.models import EntityType
from sip.privacy.quarantine import LocalQuarantine, NullQuarantine
from sip.privacy.vault import InMemoryVault, SqlVault


def gateway(**kw) -> PrivacyGateway:  # type: ignore[no-untyped-def]
    return PrivacyGateway(LocalDetector(), InMemoryVault(), NullQuarantine(), **kw)


async def ingest(gw: PrivacyGateway, text: str, name: str = "n.txt", declared=None):  # type: ignore[no-untyped-def]
    return await gw.ingest(
        filename=name,
        content=text.encode(),
        title=None,
        source_type=SourceType.CRM_RECORD,
        declared=declared or DataClassification(),
        uploaded_by="u",
    )


async def test_pseudonymisation_preserves_linkage_across_mentions() -> None:
    doc = await ingest(gateway(), "Spoke with Jane Smith at Acme Logistics Ltd. Later Jane Smith called again.")
    assert "Jane" not in doc.sanitised_text and "Acme" not in doc.sanitised_text
    assert doc.sanitised_text.count("PERSON_0001") == 2
    assert "EMPLOYER_0001" in doc.sanitised_text


async def test_special_category_content_is_withheld_not_pseudonymised() -> None:
    doc = await ingest(gateway(), "Learner Ben Carter withdrew after a mental health diagnosis. Rates were stable.")
    assert "mental health" not in doc.sanitised_text and "Ben Carter" not in doc.sanitised_text
    assert "[WITHHELD:HEALTH]" in doc.sanitised_text
    assert doc.scan.classification.personal_data == PersonalData.SPECIAL_CATEGORY


async def test_confidentiality_is_classified_independently_of_personal_data() -> None:
    doc = await ingest(gateway(), "COMMERCIAL IN CONFIDENCE. Our pricing strategy changes in Q3.")
    assert doc.scan.classification.confidentiality == Confidentiality.COMMERCIALLY_CONFIDENTIAL
    assert doc.scan.classification.personal_data == PersonalData.NONE


async def test_allowlisted_public_names_are_not_pseudonymised() -> None:
    doc = await ingest(gateway(allowlist={"Northstar Learning Group"}), "Northstar Learning Group lost a tender.")
    assert "Northstar Learning Group" in doc.sanitised_text


def test_overlapping_name_candidates_regression() -> None:
    # Regression: "Customer Laura" consumed "Laura" before "Laura Bennett" was tested (found by evaluation).
    found = {d.text for d in LocalDetector().detect_sync("Customer Laura Bennett cancelled. Agent: Sam Kerr.")}
    assert "Laura Bennett" in found and "Sam Kerr" in found


def test_unicode_names_are_detected_whole() -> None:
    found = [d for d in LocalDetector().detect_sync("Learner Zofia Wiśniewska transferred.")]
    assert found[0].text == "Zofia Wiśniewska" and found[0].confidence < 0.75  # unfamiliar name -> review


def test_contact_details_are_detected() -> None:
    types = {
        d.entity_type
        for d in LocalDetector().detect_sync("Email a.b@example.com or call 07700 900123, NI AB 12 34 56 C")
    }
    assert {EntityType.EMAIL, EntityType.PHONE, EntityType.NATIONAL_ID} <= types


async def test_scan_summary_never_contains_raw_values() -> None:
    doc = await ingest(gateway(), "Contact: Jane Smith, jane@example.com")
    assert "Jane" not in doc.scan.model_dump_json() and "jane@" not in doc.scan.model_dump_json()


async def test_upload_constraints() -> None:
    gw = gateway(max_bytes=10)
    with pytest.raises(UploadTooLarge):
        await ingest(gw, "x" * 11)
    with pytest.raises(UnsupportedFile):
        await ingest(gateway(), "MZ...", name="evil.exe")
    with pytest.raises(UnsupportedFile):
        await ingest(gateway(), "not a pdf", name="fake.pdf")
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("..\\..\\win.ini") == "win.ini"


async def test_raw_content_goes_only_to_quarantine(tmp_path) -> None:  # type: ignore[no-untyped-def]
    gw = PrivacyGateway(LocalDetector(), InMemoryVault(), LocalQuarantine(tmp_path / "q"))
    doc = await ingest(gw, "Spoke with Jane Smith.")
    stored = tmp_path / "q" / f"{doc.id}.bin"
    assert stored.read_text() == "Spoke with Jane Smith."
    assert oct(stored.stat().st_mode)[-3:] == "600"


async def test_sql_vault_is_consistent_and_encrypts_values(tmp_path) -> None:  # type: ignore[no-untyped-def]
    vault = SqlVault.from_url(f"sqlite+aiosqlite:///{tmp_path}/v.db", key="test-key")
    await vault.create_schema()
    a = await vault.pseudonym_for(EntityType.PERSON, "Jane Smith")
    b = await vault.pseudonym_for(EntityType.PERSON, "jane   smith")
    c = await vault.pseudonym_for(EntityType.PERSON, "John Doe")
    assert a == b == "PERSON_0001" and c == "PERSON_0002"
    raw = (tmp_path / "v.db").read_bytes()
    assert b"Jane Smith" not in raw
    await vault.engine.dispose()


async def test_free_text_from_humans_is_sanitised() -> None:
    assert await gateway().sanitise_text("Ask Jane Smith (jane@x.com)") == "Ask PERSON_0001 (EMAIL_0001)"


@respx.mock
async def test_blob_quarantine_uses_bearer_token() -> None:
    from sip.privacy.quarantine import BlobQuarantine

    route = respx.put("https://acct.blob.core.windows.net/quarantine/doc_1.bin").mock(return_value=httpx.Response(201))

    async def token() -> str:
        return "tok"

    await BlobQuarantine("https://acct.blob.core.windows.net/quarantine/", token).put("doc_1", b"raw")
    req = route.calls[0].request
    assert req.headers["authorization"] == "Bearer tok" and req.headers["x-ms-blob-type"] == "BlockBlob"


def test_copy_protected_pdf_with_empty_password_is_readable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import io

    from pypdf import PdfWriter

    from sip.privacy.extraction import extract_text

    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    w.encrypt(user_password="", owner_password="owner-only")
    buf = io.BytesIO()
    w.write(buf)
    assert extract_text(buf.getvalue(), "application/pdf") == ""  # opens (blank page) instead of raising
