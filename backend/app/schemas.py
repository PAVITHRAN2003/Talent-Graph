from typing import Literal
from pydantic import BaseModel, Field


class JDRequirements(BaseModel):
    title: str = Field(description="Job title")
    seniority: Literal["Entry-level", "Mid-level", "Senior-level"]
    min_years_experience: float = Field(description="Minimum years of experience required, 0 if unspecified")
    must_have_skills: list[str] = Field(description="Hard requirements, short skill names")
    nice_to_have_skills: list[str]
    responsibilities: list[str] = Field(description="Top 8 key responsibilities, one line each")


class ResumeProfile(BaseModel):
    name: str = Field(description="Candidate full name, 'Unknown' if absent")
    email: str | None = None
    current_title: str | None = None
    total_years_experience: float = Field(description="Total professional years, estimated from dates")
    skills: list[str]
    education: list[str]
    summary: str = Field(description="Two sentence professional summary")


class ExperienceCategory(BaseModel):
    level: Literal["Entry-level", "Mid-level", "Senior-level"]
    rationale: str


class SkillAssessment(BaseModel):
    match_score: int = Field(ge=0, le=100, description="Overall fit to the JD, 0-100")
    matched_skills: list[str]
    missing_skills: list[str]
    strengths: list[str] = Field(description="Max 3")
    concerns: list[str] = Field(description="Max 3")
    reasoning: str = Field(description="2-3 sentence justification")


class InterviewQuestions(BaseModel):
    questions: list[str] = Field(description="5 tailored interview questions")


class RejectionFeedback(BaseModel):
    feedback: str = Field(description="Polite, specific, 2-3 sentence feedback for the candidate")
