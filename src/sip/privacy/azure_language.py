"""Azure AI Language PII adapter (Text Analytics "PiiEntityRecognition").

Runs inside the privacy boundary: raw text is sent to the organisation's own Azure AI Language
resource, never to the investigation LLM. Documents are chunked to the synchronous API's size limit.
Special-category screening still runs locally because the PII service does not classify it.
"""

from __future__ import annotations

import httpx

from sip.privacy.detectors import LocalDetector
from sip.privacy.models import Detection, EntityType

API_VERSION = "2024-11-01"
MAX_CHARS = 5000

_CATEGORY_MAP = {
    "Person": EntityType.PERSON,
    "PersonType": None,
    "Organization": EntityType.EMPLOYER,
    "Email": EntityType.EMAIL,
    "PhoneNumber": EntityType.PHONE,
    "UKNationalInsuranceNumber": EntityType.NATIONAL_ID,
    "UKPostcode": EntityType.POSTCODE,
    "Address": EntityType.POSTCODE,
}


class AzureLanguageDetector:
    name = "azure-ai-language-pii"

    def __init__(
        self,
        endpoint: str,
        api_key: str | None,
        client: httpx.AsyncClient | None = None,
        token_provider: object | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.client = client or httpx.AsyncClient(timeout=30)
        self.token_provider = token_provider
        self._local = LocalDetector()

    async def _headers(self) -> dict[str, str]:
        if self.api_key:
            return {"Ocp-Apim-Subscription-Key": self.api_key}
        if self.token_provider is not None:
            token = await self.token_provider()  # type: ignore[operator]
            return {"Authorization": f"Bearer {token}"}
        raise RuntimeError("Azure AI Language requires an API key or Entra ID token provider.")

    async def detect(self, text: str) -> list[Detection]:
        detections = [d for d in self._local.detect_sync(text) if d.entity_type == EntityType.SPECIAL_CATEGORY]
        url = f"{self.endpoint}/language/:analyze-text?api-version={API_VERSION}"
        headers = await self._headers()
        for offset in range(0, len(text), MAX_CHARS):
            chunk = text[offset : offset + MAX_CHARS]
            body = {
                "kind": "PiiEntityRecognition",
                "parameters": {"modelVersion": "latest", "loggingOptOut": True},
                "analysisInput": {"documents": [{"id": "1", "language": "en", "text": chunk}]},
            }
            resp = await self.client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            for doc in resp.json()["results"]["documents"]:
                for ent in doc.get("entities", []):
                    et = _CATEGORY_MAP.get(ent["category"])
                    if et is None:
                        continue
                    start = offset + ent["offset"]
                    end = start + ent["length"]
                    detections.append(
                        Detection(
                            et,
                            start,
                            end,
                            text[start:end],
                            float(ent["confidenceScore"]),
                            self.name,
                            ent.get("subcategory"),
                        )
                    )
        detections.sort(key=lambda d: d.start)
        taken: list[tuple[int, int]] = []
        result = []
        for d in detections:
            if any(d.start < e and s < d.end for s, e in taken):
                continue
            taken.append((d.start, d.end))
            result.append(d)
        return result
