"""LangGraph screening pipeline (evolved from the original notebook).

START -> parse_resume -> categorize_experience -> assess_skillset -> (route)
            -> schedule_hr_interview | escalate_to_recruiter | reject_application -> END
"""
import json
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from . import config
from .llm import structured
from .schemas import (ResumeProfile, ExperienceCategory, SkillAssessment,
                      InterviewQuestions, RejectionFeedback)


class State(TypedDict, total=False):
    resume_text: str
    jd: dict
    threshold: int
    profile: dict
    experience_level: str
    experience_rationale: str
    assessment: dict
    skill_match: str          # "Match" | "No Match"  (derived from score, not LLM free-text)
    decision: str             # shortlist | escalate | reject
    response: str
    interview_questions: list[str]
    feedback: str


def _jd(state) -> str:
    return json.dumps(state["jd"])


async def parse_resume(state: State) -> State:
    p = await structured(ResumeProfile, "Extract a structured profile from this resume.\n\nRESUME:\n"
                         + state["resume_text"][: config.MAX_RESUME_CHARS])
    return {"profile": p.model_dump()}


async def categorize_experience(state: State) -> State:
    r = await structured(ExperienceCategory, (
        "Categorize the candidate as Entry-level (<2 yrs), Mid-level (2-6 yrs) or Senior-level (6+ yrs "
        "or clear technical leadership). Judge by depth of work, not only years.\n"
        f"PROFILE: {json.dumps(state['profile'])}"))
    return {"experience_level": r.level, "experience_rationale": r.rationale}


async def assess_skillset(state: State) -> State:
    a = await structured(SkillAssessment, (
        "You are a strict technical recruiter. Score how well this candidate fits the job (0-100). "
        "Weight must-have skills most, then experience vs. requirement, then nice-to-haves. "
        "Only credit skills evidenced in the resume.\n"
        f"JOB REQUIREMENTS: {_jd(state)}\n"
        f"CANDIDATE PROFILE: {json.dumps(state['profile'])}\n"
        f"CANDIDATE RESUME EXCERPT:\n{state['resume_text'][:8000]}"))
    match = "Match" if a.match_score >= state.get("threshold", 70) else "No Match"
    return {"assessment": a.model_dump(), "skill_match": match}


def route_app(state: State) -> str:
    # Same business rules as the notebook, but deterministic.
    if state["skill_match"] == "Match":
        return "schedule_hr_interview"
    if state["experience_level"] == "Senior-level":
        return "escalate_to_recruiter"
    return "reject_application"


async def schedule_hr_interview(state: State) -> State:
    q = await structured(InterviewQuestions, (
        "Write 5 tailored interview questions: probe the candidate's strongest claims and gently "
        "test the missing skills.\n"
        f"JOB: {_jd(state)}\nASSESSMENT: {json.dumps(state['assessment'])}"))
    return {"decision": "shortlist", "interview_questions": q.questions,
            "response": "Candidate has been shortlisted for an HR interview."}


async def escalate_to_recruiter(state: State) -> State:
    return {"decision": "escalate",
            "response": "Senior-level candidate who falls short on core skills — needs human recruiter review."}


async def reject_application(state: State) -> State:
    f = await structured(RejectionFeedback, (
        "Write brief, kind, specific feedback explaining why the candidate was not selected.\n"
        f"JOB: {_jd(state)}\nASSESSMENT: {json.dumps(state['assessment'])}"))
    return {"decision": "reject", "feedback": f.feedback,
            "response": "Candidate doesn't meet the JD requirements and has been rejected."}


def build_graph():
    g = StateGraph(State)
    for fn in (parse_resume, categorize_experience, assess_skillset,
               schedule_hr_interview, escalate_to_recruiter, reject_application):
        g.add_node(fn.__name__, fn)
    g.add_edge(START, "parse_resume")
    g.add_edge("parse_resume", "categorize_experience")
    g.add_edge("categorize_experience", "assess_skillset")
    g.add_conditional_edges("assess_skillset", route_app)
    for end in ("schedule_hr_interview", "escalate_to_recruiter", "reject_application"):
        g.add_edge(end, END)
    return g.compile()


graph = build_graph()


async def screen_resume(resume_text: str, jd: dict, threshold: int) -> dict:
    out = await graph.ainvoke({"resume_text": resume_text, "jd": jd, "threshold": threshold})
    p, a = out["profile"], out["assessment"]
    return {
        "name": p["name"], "email": p.get("email"), "current_title": p.get("current_title"),
        "years_experience": p["total_years_experience"], "skills": p["skills"], "summary": p["summary"],
        "experience_level": out["experience_level"], "experience_rationale": out["experience_rationale"],
        "score": a["match_score"], "skill_match": out["skill_match"],
        "matched_skills": a["matched_skills"], "missing_skills": a["missing_skills"],
        "strengths": a["strengths"], "concerns": a["concerns"], "reasoning": a["reasoning"],
        "decision": out["decision"], "response": out["response"],
        "interview_questions": out.get("interview_questions", []), "feedback": out.get("feedback"),
    }
