"""Tests for RAG knowledge base, applicant recovery state monitoring, and AI Chatbot."""

from unittest.mock import MagicMock
import uuid

import pytest

from app.models.application import Application
from app.models.user import Role, User
from app.services import rag as rag_service


def test_rag_chunk_retrieval_for_name_variation():
    chunks = rag_service.retrieve_relevant_chunks("My name on bank account has initials and was rejected")
    assert len(chunks) > 0
    # Should retrieve Non-Auto-Reject or 8-Tier Name matching rules
    matched_ids = [c.id for c in chunks]
    assert "recovery_sec2_dont_reject_automatically" in matched_ids or "policy_ps01_name_matching_8tier" in matched_ids


def test_rag_chunk_retrieval_for_photo_glare():
    chunks = rag_service.retrieve_relevant_chunks("How to fix blurry photo with glare and reflection")
    assert len(chunks) > 0
    matched_ids = [c.id for c in chunks]
    assert "quickstart_step3_photo_upload_rules" in matched_ids or "recovery_sec3_correction_recovery" in matched_ids


def test_rag_chunk_retrieval_for_training_lms():
    chunks = rag_service.retrieve_relevant_chunks("How many hours of LMS training do I need to complete?")
    assert len(chunks) > 0
    matched_ids = [c.id for c in chunks]
    assert "recovery_sec4_training_not_started" in matched_ids or "quickstart_step4_path_to_certification" in matched_ids


def test_rag_chat_response_generation_without_application():
    db = MagicMock()
    res = rag_service.generate_rag_chat_response(
        db=db,
        query="What are the basic eligibility rules before I start?",
        user=None,
        language="EN",
    )
    assert res.query == "What are the basic eligibility rules before I start?"
    assert len(res.citations) > 0
    assert "18+" in res.answer or "Class 10" in res.answer or "PAN" in res.answer
    assert res.voice_script is not None
    assert res.language == "EN"


def test_rag_chat_response_in_hindi():
    db = MagicMock()
    res = rag_service.generate_rag_chat_response(
        db=db,
        query="दस्तावेज़ कैसे अपलोड करें?",
        user=None,
        language="HI",
    )
    assert "नमस्ते" in res.voice_script
    assert res.language == "HI"


if __name__ == "__main__":
    test_rag_chunk_retrieval_for_name_variation()
    test_rag_chunk_retrieval_for_photo_glare()
    test_rag_chunk_retrieval_for_training_lms()
    test_rag_chat_response_generation_without_application()
    test_rag_chat_response_in_hindi()
    print("All 5 RAG and Assistant tests passed successfully!")
