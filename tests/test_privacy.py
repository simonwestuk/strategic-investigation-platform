from sip.privacy.gateway import sanitise_text


def test_redacts_email_and_uk_phone():
    result = sanitise_text("Contact jane@example.com or 07700 900 123")
    assert "jane@example.com" not in result.sanitised_text
    assert "07700" not in result.sanitised_text
    assert result.detections == 2
