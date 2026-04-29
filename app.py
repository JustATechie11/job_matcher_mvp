import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from modules.resume_parser import extract_resume_text
from modules.job_search import search_jobs
from modules.job_verifier import verify_job_link
from modules.ats_scorer import calculate_ats_score
from modules.exporter import export_jobs_to_excel, export_jobs_to_json
from modules.utils import (
    current_timestamp,
    extract_job_required_experience_years,
    extract_resume_experience_years,
    format_experience_years,
    is_blocked_seniority_title,
    is_duplicate_job,
    job_experience_allowed,
)

load_dotenv()

MIN_ATS_SCORE = int(os.getenv("MIN_ATS_SCORE", "70"))
RELEVANT_MIN_ATS_SCORE = int(os.getenv("RELEVANT_MIN_ATS_SCORE", "35"))
TARGET_JOB_COUNT = int(os.getenv("TARGET_JOB_COUNT", "50"))


st.set_page_config(
    page_title="Accurate Job Matcher MVP",
    page_icon="🎯",
    layout="wide",
)

st.title("Accurate Job Matcher MVP")
st.caption("Resume-based job discovery with verified links and ATS scoring")


if "verified_jobs" not in st.session_state:
    st.session_state.verified_jobs = []

if "relevant_jobs" not in st.session_state:
    st.session_state.relevant_jobs = []

if "shown_jobs" not in st.session_state:
    st.session_state.shown_jobs = []

if "search_diagnostics" not in st.session_state:
    st.session_state.search_diagnostics = {}

if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""

if "resume_experience_years" not in st.session_state:
    st.session_state.resume_experience_years = None


with st.sidebar:
    st.header("Candidate Details")

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    job_role = st.text_input("Job Role Applying For")
    location = st.text_input("Location", value="United States", disabled=True, help="Locked to USA as per strict filters.")
    salary_expectation = st.text_input("Salary Expectation", value="$70,000+", disabled=True, help="Filtering explicitly for $70k+.")

    resume_file = st.file_uploader("Upload Resume PDF", type=["pdf"])

    st.markdown("---")
    #st.write(f"Minimum ATS Score: **{MIN_ATS_SCORE}**")
    #st.write(f"Relevant Score Floor: **{RELEVANT_MIN_ATS_SCORE}**")
    st.write("Max Age: **9 Days**")
    st.write("Target Results: **50 Unique Jobs**")
    #st.write("Excludes Staffing & Recruitment Agencies")


def process_jobs(raw_jobs, resume_text, job_role, resume_experience_years=None, max_results=TARGET_JOB_COUNT):
    scored_jobs = []
    processed_jobs = []
    diagnostics = {
        "raw_candidates": len(raw_jobs),
        "duplicates": 0,
        "missing_links": 0,
        "blocked_seniority_titles": 0,
        "experience_rejected": 0,
        "verification_rejected": 0,
        "scored_candidates": 0,
        "below_relevant_score": 0,
        "resume_experience_years": resume_experience_years,
    }

    for job in raw_jobs:
        if is_blocked_seniority_title(job.get("job_role", "")):
            diagnostics["blocked_seniority_titles"] += 1
            continue

        if is_duplicate_job(job, processed_jobs):
            diagnostics["duplicates"] += 1
            continue

        if not job.get("job_link"):
            diagnostics["missing_links"] += 1
            continue

        verification = verify_job_link(job["job_link"], job_context=job)

        if not verification["is_valid"]:
            processed_jobs.append(job)
            diagnostics["verification_rejected"] += 1
            continue

        job["job_link"] = verification["final_url"]
        job["verification_result"] = verification["reason"]
        job["platform"] = verification.get("platform") or job.get("platform")

        verified_page_text = verification.get("page_text", "")
        if verified_page_text:
            job["verified_page_text"] = verified_page_text
            if len(verified_page_text) > len(job.get("description", "")):
                job["description"] = verified_page_text

        if verification.get("salary_text"):
            job["salary"] = verification["salary_text"]

        experience_text = " ".join(
            [
                job.get("job_role", ""),
                job.get("description", ""),
                job.get("verified_page_text", ""),
            ]
        )
        required_experience_years = extract_job_required_experience_years(experience_text)
        job["experience_required"] = format_experience_years(required_experience_years)

        if not job_experience_allowed(required_experience_years, resume_experience_years):
            processed_jobs.append(job)
            diagnostics["experience_rejected"] += 1
            continue

        score_result = calculate_ats_score(
            resume_text=resume_text,
            job=job,
            target_role=job_role,
        )

        job.update(score_result)
        job.pop("verified_page_text", None)
        job["generated_at"] = current_timestamp()
        processed_jobs.append(job)
        diagnostics["scored_candidates"] += 1

        if job["ats_score"] >= RELEVANT_MIN_ATS_SCORE:
            scored_jobs.append(job)
        else:
            diagnostics["below_relevant_score"] += 1

    scored_jobs = sorted(scored_jobs, key=lambda item: item.get("ats_score", 0), reverse=True)
    verified_jobs = []
    relevant_jobs = []

    for job in scored_jobs:
        if len(verified_jobs) >= max_results:
            break
        if job["ats_score"] >= MIN_ATS_SCORE:
            job["result_type"] = "Verified"
            verified_jobs.append(job)

    remaining_slots = max(max_results - len(verified_jobs), 0)
    for job in scored_jobs:
        if len(relevant_jobs) >= remaining_slots:
            break
        if job in verified_jobs:
            continue
        job["result_type"] = "Relevant"
        relevant_jobs.append(job)

    st.session_state.shown_jobs = verified_jobs + relevant_jobs
    st.session_state.search_diagnostics = diagnostics
    return verified_jobs, relevant_jobs


search_button = st.button("Find 50 Jobs", width="stretch")


if search_button:
    if not first_name or not last_name or not job_role or not location or not resume_file:
        st.error("Please fill First Name, Last Name, Job Role, Location, and upload resume.")
    else:
        with st.spinner("Parsing resume..."):
            st.session_state.resume_text = extract_resume_text(resume_file)

        if not st.session_state.resume_text:
            st.error("Could not extract resume text. Please try another PDF.")
        else:
            st.success("Resume parsed successfully.")
            st.session_state.resume_experience_years = extract_resume_experience_years(st.session_state.resume_text)
            if st.session_state.resume_experience_years is not None:
                st.info(f"Detected resume experience: {st.session_state.resume_experience_years} years.")
            else:
                st.info("Could not clearly detect resume experience, so experience filtering will only display job requirements.")
            st.session_state.shown_jobs = []
            st.session_state.relevant_jobs = []
            st.session_state.search_diagnostics = {}

            with st.spinner("Searching and verifying jobs..."):
                raw_jobs = search_jobs(job_role, location, limit=TARGET_JOB_COUNT)

                verified, relevant = process_jobs(
                    raw_jobs=raw_jobs,
                    resume_text=st.session_state.resume_text,
                    job_role=job_role,
                    resume_experience_years=st.session_state.resume_experience_years,
                    max_results=TARGET_JOB_COUNT,
                )

                st.session_state.verified_jobs = verified
                st.session_state.relevant_jobs = relevant

            total_results = len(verified) + len(relevant)
            if total_results == 0:
                st.warning("No approved-source jobs survived the strict filters. The diagnostics below show where candidates were rejected.")
            elif not verified:
                st.warning("No jobs reached the verified ATS threshold. Showing approved-source relevant matches below.")
            else:
                st.success(f"Found {total_results} unique approved-source jobs.")
                if len(verified) < TARGET_JOB_COUNT:
                    st.info("Strict filtering returned fewer than 50 verified jobs. Approved-source close matches are shown below instead of irrelevant filler.")

            if st.session_state.search_diagnostics:
                with st.expander("Search diagnostics"):
                    st.json(st.session_state.search_diagnostics)


if st.session_state.verified_jobs:
    st.subheader("Verified Job Results")

    df = pd.DataFrame(st.session_state.verified_jobs)

    preferred_columns = [
        "job_role",
        "company",
        "experience_required",
        "ats_score",
        "platform",
        "location",
        "salary",
        "posted_date",
        "job_link",
        "matched_keywords",
        "missing_keywords",
        "ats_suggestion",
        "verification_result",
    ]

    available_columns = [col for col in preferred_columns if col in df.columns]
    st.dataframe(df[available_columns], width="stretch")


if st.session_state.relevant_jobs:
    st.subheader("Relevant Job Results")
    st.caption("Approved-source jobs that are close resume matches but below the verified ATS threshold.")

    relevant_df = pd.DataFrame(st.session_state.relevant_jobs)

    preferred_columns = [
        "job_role",
        "company",
        "experience_required",
        "ats_score",
        "platform",
        "location",
        "salary",
        "posted_date",
        "job_link",
        "matched_keywords",
        "missing_keywords",
        "ats_suggestion",
        "verification_result",
    ]

    available_columns = [col for col in preferred_columns if col in relevant_df.columns]
    st.dataframe(relevant_df[available_columns], width="stretch")


if st.session_state.verified_jobs or st.session_state.relevant_jobs:
    exportable_jobs = st.session_state.verified_jobs + st.session_state.relevant_jobs

    st.markdown("### Export Results")

    export_col1, export_col2 = st.columns(2)

    with export_col1:
        if st.button("Export XLSX", width="stretch"):
            file_path = export_jobs_to_excel(exportable_jobs)

            with open(file_path, "rb") as f:
                st.download_button(
                    label="Download XLSX",
                    data=f,
                    file_name=os.path.basename(file_path),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )

    with export_col2:
        if st.button("Export JSON", width="stretch"):
            file_path = export_jobs_to_json(exportable_jobs)

            with open(file_path, "rb") as f:
                st.download_button(
                    label="Download JSON",
                    data=f,
                    file_name=os.path.basename(file_path),
                    mime="application/json",
                    width="stretch",
                )
