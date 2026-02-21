"""
LLM Lead Qualification Engine.

Takes raw leads from scrapers, sends them through Claude for
relevance scoring, service matching, and confidence assessment.
"""
import json
import logging
from typing import Optional
from anthropic import AsyncAnthropic
from backend.scrapers.base import RawLead
from backend.reasoning.prompts import (
    LEAD_QUALIFICATION_SYSTEM,
    LEAD_QUALIFICATION_USER,
    BATCH_CLASSIFICATION_SYSTEM,
)
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class LeadQualifier:
    """Orchestrates LLM-based lead qualification."""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model

    async def qualify_lead(self, lead: RawLead) -> Optional[dict]:
        """
        Send a single lead through the LLM for full qualification.
        Returns a structured dict with scores and reasoning.
        """
        try:
            prompt = LEAD_QUALIFICATION_USER.format(
                title=lead.title,
                source_name=lead.source_name,
                source_type=lead.source_type,
                org_name=lead.org_name or "Unknown",
                source_url=lead.source_url,
                raw_text=lead.raw_text[:3000],  # Keep within token budget
            )

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=settings.llm_max_tokens,
                system=LEAD_QUALIFICATION_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse JSON response
            text = response.content[0].text.strip()
            # Handle potential markdown wrapping
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(text)

            # Validate required fields
            required = [
                "is_government", "org_name", "org_type", "summary",
                "service_matches", "intent_signals", "confidence_score",
                "relevance_reasoning",
            ]
            for field in required:
                if field not in result:
                    logger.warning(f"Missing field '{field}' in LLM response")
                    result[field] = None

            # Clamp confidence score
            if result.get("confidence_score") is not None:
                result["confidence_score"] = max(0.0, min(1.0, float(result["confidence_score"])))

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON for '{lead.title}': {e}")
            return None
        except Exception as e:
            logger.error(f"LLM qualification error for '{lead.title}': {e}")
            return None

    async def batch_classify(self, leads: list[RawLead]) -> list[bool]:
        """
        Quick pass/fail classification for a batch of leads.
        Used as a fast first-pass before full qualification.
        Returns a list of booleans (True = passes filter).
        """
        if not leads:
            return []

        # Build batch description
        items = []
        for i, lead in enumerate(leads):
            items.append(
                f"[{i}] Title: {lead.title}\n"
                f"Org: {lead.org_name or 'Unknown'}\n"
                f"Source: {lead.source_name}\n"
                f"Text: {lead.raw_text[:500]}\n"
            )

        batch_text = "\n---\n".join(items)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=settings.llm_max_tokens,
                system=BATCH_CLASSIFICATION_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": f"Classify these {len(leads)} items:\n\n{batch_text}",
                    }
                ],
            )

            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            results = json.loads(text)

            # Build boolean list
            pass_map = {r["index"]: r["pass"] for r in results}
            return [pass_map.get(i, False) for i in range(len(leads))]

        except Exception as e:
            logger.error(f"Batch classification error: {e}")
            # Default to passing all through if LLM fails
            return [True] * len(leads)
