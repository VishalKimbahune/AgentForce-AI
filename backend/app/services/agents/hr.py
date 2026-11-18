"""HR AI Employee: resume parsing (pypdf, python-docx), JD matching, and candidate ranking."""

import io
import json
import logging
import re
from typing import Any, Dict, List, Optional
from pathlib import Path

import pypdf
import docx

from app.schemas.workflow import CandidateRanking
from app.services.guardrails import prompt_injection_guard, security_logger

logger = logging.getLogger("agent.hr")

# Sample resumes for seed data and automated tests
SAMPLE_RESUMES = [
    {
        "name": "Aarav Patel",
        "email": "aarav.patel@example.com",
        "raw_text": (
            "Aarav Patel\n"
            "aarav.patel@example.com | +91 98765 43210\n"
            "Senior Backend Engineer with 6 years of experience in Python, FastAPI, Django, PostgreSQL, "
            "and Docker. Built distributed microservices, designed async task workers with Redis and Celery, "
            "and deployed scalable Kubernetes clusters. Skilled in CI/CD, Git, and automated testing."
        ),
    },
    {
        "name": "Neha Sharma",
        "email": "neha.sharma@example.com",
        "raw_text": (
            "Neha Sharma\n"
            "neha.sharma@example.com\n"
            "Python Developer with 3.5 years of experience developing REST APIs using FastAPI and Flask. "
            "Strong database knowledge in PostgreSQL and MySQL. Proficient in Docker containerization, "
            "Git, and Pytest. Knowledgeable in LangChain and basic LLM integration."
        ),
    },
    {
        "name": "Rohan Deshmukh",
        "email": "rohan.deshmukh@example.com",
        "raw_text": (
            "Rohan Deshmukh\n"
            "rohan.deshmukh@example.com\n"
            "Frontend Engineer transitioning to Full Stack. 4 years of experience with React, Next.js, "
            "and TypeScript. Familiar with Python scripting and basic Django web development. "
            "Intermediate experience with SQL databases and Docker."
        ),
    },
    {
        "name": "Pooja Sundaram",
        "email": "pooja.sundaram@example.com",
        "raw_text": (
            "Pooja Sundaram\n"
            "pooja.sundaram@example.com\n"
            "Junior Software Engineer with 1 year of experience in Python and Java. Built academic "
            "projects using Flask and SQLite. Eager learner with foundational understanding of data structures "
            "and algorithms."
        ),
    },
    {
        "name": "Vikram Malhotra",
        "email": "vikram.malhotra@example.com",
        "raw_text": (
            "Vikram Malhotra\n"
            "vikram.malhotra@example.com\n"
            "Staff Systems Architect with 10 years of experience. Expert in Python, C++, Go, distributed systems, "
            "FastAPI high-throughput services, PostgreSQL performance tuning, Docker, and Kubernetes orchestration. "
            "Extensive experience leading backend engineering teams."
        ),
    },
]


def extract_text_from_pdf(content_bytes: bytes) -> str:
    """Extracts raw text from a PDF document using pypdf."""
    reader = pypdf.PdfReader(io.BytesIO(content_bytes))
    text_parts = []
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            text_parts.append(txt)
    return "\n".join(text_parts)


def extract_text_from_docx(content_bytes: bytes) -> str:
    """Extracts raw text from a DOCX document using python-docx."""
    doc = docx.Document(io.BytesIO(content_bytes))
    return "\n".join([p.text for p in doc.paragraphs if p.text])


class HRAgent:
    """Specialized AI Employee for talent acquisition, resume screening, and JD ranking."""

    def parse_resume(self, text_or_bytes: Any, filename: Optional[str] = None) -> Dict[str, Any]:
        """Parses a resume from bytes (PDF/DOCX) or string into structured candidate data."""
        if isinstance(text_or_bytes, bytes):
            if filename and filename.lower().endswith(".pdf"):
                raw_text = extract_text_from_pdf(text_or_bytes)
            elif filename and filename.lower().endswith((".docx", ".doc")):
                raw_text = extract_text_from_docx(text_or_bytes)
            else:
                raw_text = text_or_bytes.decode("utf-8", errors="ignore")
        else:
            raw_text = str(text_or_bytes)

        # Guardrail Check: Neutralize indirect prompt injection embedded in resume
        sanitized_text, injection_detected, categories = prompt_injection_guard.sanitize_document(raw_text)
        if injection_detected:
            security_logger.record_incident(
                event_type="security.document_indirect_injection",
                threat_category="resume_prompt_injection",
                risk_level="high",
                detail=f"Indirect prompt injection neutralized in resume: {', '.join(categories)}",
                payload_sample={"filename": filename, "categories": categories},
            )

        # Extract email
        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", sanitized_text)
        email = email_match.group(0) if email_match else None

        # Extract name heuristic (first line or before email)
        lines = [l.strip() for l in sanitized_text.splitlines() if l.strip()]
        name = lines[0] if lines else "Candidate"
        if len(name) > 50:
            name = name[:50]

        return {
            "name": name,
            "email": email,
            "raw_text": sanitized_text,
            "injection_detected": injection_detected,
            "threat_categories": categories,
        }

    async def rank_candidates_against_jd(
        self,
        resumes: List[Dict[str, Any]],
        jd_text: str,
        gateway: Optional[Any] = None,
    ) -> List[CandidateRanking]:
        """Matches candidate resumes against a Job Description, producing ranked candidate list."""
        # Normalize JD criteria
        jd_lower = jd_text.lower()
        core_skills = ["python", "fastapi", "postgresql", "docker", "asyncio", "kubernetes", "testing"]

        rankings: List[CandidateRanking] = []

        for candidate in resumes:
            text_lower = candidate.get("raw_text", "").lower()
            name = candidate.get("name", "Unknown Candidate")
            email = candidate.get("email")
            injection_detected = candidate.get("injection_detected", False)

            # Extract matched and missing skills
            matched = [s for s in core_skills if s in text_lower]
            missing = [s for s in core_skills if s not in text_lower and s in jd_lower]

            # Compute match score based on genuine skill match and experience mentions
            base_score = int((len(matched) / max(len(core_skills), 1)) * 80)
            
            # Experience bonus
            exp_match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", text_lower)
            exp_years = float(exp_match.group(1)) if exp_match else 2.0
            if exp_years >= 5:
                base_score += 20
            elif exp_years >= 3:
                base_score += 15
            elif exp_years >= 1:
                base_score += 10
            else:
                base_score += 5

            score = min(max(base_score, 10), 98)

            # Red-team guardrail enforcement: If candidate attempted prompt injection, score is penalized and flagged
            if injection_detected:
                score = min(score, 35)
                summary = f"Flagged candidate: Adversarial instruction detected in profile; genuine experience evaluated at {exp_years}y."
                rationale = "[SECURITY WARNING] Candidate profile contained adversarial prompt injection attempts; score penalized and flagged for manual security review."
            elif score >= 85:
                summary = f"Strong senior match with {exp_years}y experience and deep expertise in {', '.join(matched[:3])}."
                rationale = "Candidate exceeds technical qualifications for the Python role; recommend immediate interview."
            elif score >= 65:
                summary = f"Solid mid-level candidate with {exp_years}y experience; proficient in {', '.join(matched[:3])}."
                rationale = "Candidate meets core FastAPI & PostgreSQL requirements; good fit for technical screening."
            else:
                summary = f"Early career or transitioning candidate with {exp_years}y experience."
                rationale = f"Candidate lacks experience in key JD requirements ({', '.join(missing[:2]) or 'advanced backend architecture'})."

            rankings.append(
                CandidateRanking(
                    candidate_name=name,
                    email=email,
                    score=score,
                    matched_skills=matched,
                    missing_skills=missing,
                    experience_years=exp_years,
                    summary=summary,
                    rationale=rationale,
                )
            )

        # Sort descending by score
        rankings.sort(key=lambda x: x.score, reverse=True)
        return rankings


hr_agent = HRAgent()
