"""Provider-independent AI assistant for advisory extraction, classification, and explanations.

AI outputs are strictly advisory and never independently approve or reject applications.
"""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.platform_config import get_effective_integrations_config


class _GeminiDocAssistSchema(BaseModel):
    predicted_doc_type: str = Field(
        description="One of PAN_CARD, AADHAAR_FRONT, AADHAAR_BACK, CLASS_10_MARKSHEET, BANK_DOCUMENT, APPLICANT_SELFIE, UNKNOWN"
    )
    explanation: str = Field(
        description="Concise factual summary of document legibility, extracted details, and any missing fields."
    )


@dataclass(frozen=True)
class AIAssistResult:
    provider: str
    advisory_only: bool
    suggested_doc_type: str | None
    explanation: str


class AIAssistant(Protocol):
    provider_name: str
    configured: bool

    def summarize_document(
        self,
        *,
        doc_type: str,
        quality_status: str,
        ocr_confidence: float | None,
        extracted_fields: dict[str, str],
        missing_fields: list[str],
        masked_ocr_text: str,
    ) -> AIAssistResult: ...


class LocalHeuristicAIAssistant:
    provider_name = "LOCAL_HEURISTIC"
    configured = True

    def summarize_document(
        self,
        *,
        doc_type: str,
        quality_status: str,
        ocr_confidence: float | None,
        extracted_fields: dict[str, str],
        missing_fields: list[str],
        masked_ocr_text: str,  # noqa: ARG002
    ) -> AIAssistResult:
        parts = [f"Quality status: {quality_status}."]
        if ocr_confidence is not None:
            parts.append(f"OCR confidence: {round(ocr_confidence * 100)}%.")
        if extracted_fields:
            keys = ", ".join(sorted(extracted_fields.keys()))
            parts.append(f"Extracted fields: {keys}.")
        if missing_fields:
            parts.append(f"Missing fields requiring review or clearer upload: {', '.join(missing_fields)}.")
        else:
            parts.append("All expected fields for this document slot were captured.")
        parts.append("Advisory summary only; deterministic rules and human reviewers control decisions.")
        return AIAssistResult(
            provider=self.provider_name,
            advisory_only=True,
            suggested_doc_type=None,
            explanation=" ".join(parts),
        )


class GeminiAIAssistant:
    provider_name = "GEMINI"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.configured = True

    def summarize_document(
        self,
        *,
        doc_type: str,
        quality_status: str,
        ocr_confidence: float | None,
        extracted_fields: dict[str, str],
        missing_fields: list[str],
        masked_ocr_text: str,
    ) -> AIAssistResult:
        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            prompt = (
                "You assist insurance onboarding reviewers. Summarize document extraction quality "
                "using masked OCR text only. Never approve or reject an application.\n"
                f"Expected slot: {doc_type}\n"
                f"Quality: {quality_status}, OCR confidence: {ocr_confidence}\n"
                f"Extracted fields: {extracted_fields}\n"
                f"Missing fields: {missing_fields}\n"
                f"Masked OCR text:\n{masked_ocr_text[:2000]}"
            )
            interaction = client.interactions.create(
                model=self.model,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": _GeminiDocAssistSchema.model_json_schema(),
                },
                store=False,
            )
            parsed = _GeminiDocAssistSchema.model_validate_json(interaction.output_text or "{}")
            return AIAssistResult(
                provider=self.provider_name,
                advisory_only=True,
                suggested_doc_type=parsed.predicted_doc_type,
                explanation=parsed.explanation,
            )
        except Exception:  # noqa: BLE001
            fallback = LocalHeuristicAIAssistant().summarize_document(
                doc_type=doc_type,
                quality_status=quality_status,
                ocr_confidence=ocr_confidence,
                extracted_fields=extracted_fields,
                missing_fields=missing_fields,
                masked_ocr_text=masked_ocr_text,
            )
            return AIAssistResult(
                provider="GEMINI_FALLBACK_LOCAL",
                advisory_only=True,
                suggested_doc_type=None,
                explanation=fallback.explanation,
            )


def get_ai_assistant(db: Session | None = None) -> AIAssistant:
    s = get_effective_integrations_config(db)
    if s.ai_provider == "gemini" and s.gemini_api_key:
        return GeminiAIAssistant(api_key=s.gemini_api_key, model=s.gemini_model)
    return LocalHeuristicAIAssistant()
