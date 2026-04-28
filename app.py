import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from modules.resume_parser import extract_resume_text
from modules.job_search import search_jobs
from modules.job_verifier import verify_job_link
from modules.ats_scorer import calculate_ats_score
from modules.exporter import export_jobs_to_excel, export_jobs_to_json
from modules.utils import is_duplicate_job, current_timestamp

load_dotenv()

MIN_ATS_SCORE = int(os.getenv("MIN_ATS_SCORE", "70"))
MAX_INITIAL_JOBS = int(os.getenv("MAX_INITIAL_JOBS", "20"))
MAX_MORE_JOBS = int(os.getenv("MAX_MORE_JOBS", "10"))


st.set_page_config(
    page_title="Accurate Job Matcher MVP",
    page_icon="🎯",
    layout="wide",
)

st.title("Accurate Job Matcher MVP")
st.caption("Resume-based job discovery with verified links and ATS scoring")


if "verified_jobs" not in st.session_state:
    st.session_state.verified_jobs = []

if "shown_jobs" not in st.session_state:
    st.session_state.shown_jobs = []

if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""


with st.sidebar:
    st.header("Candidate Details")

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    job_role = st.text_input("Job Role Applying For")
    location = st.text_input("Location", value="United States")
    salary_expectation = st.text_input("Salary Expectation (Optional)")

    resume_file = st.file_uploader("Upload Resume PDF", type=["pdf"])

    st.markdown("---")
    st.write(f"Minimum ATS Score: **{MIN_ATS_SCORE}**")


def process_jobs(raw_jobs, resume_text, job_role, max_results):
    verified_jobs = []

    for job in raw_jobs:
        if len(verified_jobs) >= max_results:
            break

        if is_duplicate_job(job, st.session_state.shown_jobs):
            continue

        if not job.get("job_link"):
            continue

        verification = verify_job_link(job["job_link"])

        if not verification["is_valid"]:
            continue

        job["job_link"] = verification["final_url"]
        job["verification_status"] = verification["reason"]

        score_result = calculate_ats_score(
            resume_text=resume_text,
            job=job,
            target_role=job_role,
        )

        job.update(score_result)

        #if job["ats_score"] < MIN_ATS_SCORE:
         # continue
        
        if job["ats_score"] < MIN_ATS_SCORE:
        # allow low score temporarily for debugging
            job["low_score_flag"] = True

        job["status"] = "ready_to_apply"
        job["generated_at"] = current_timestamp()

        verified_jobs.append(job)
        st.session_state.shown_jobs.append(job)

    return verified_jobs


col1, col2 = st.columns([1, 1])

with col1:
    search_button = st.button("Find 20 Verified Jobs", use_container_width=True)

with col2:
    more_button = st.button("Find 10 More Jobs", use_container_width=True)


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

            with st.spinner("Searching and verifying jobs..."):
                raw_jobs = search_jobs(job_role, location, limit=50)

                verified = process_jobs(
                    raw_jobs=raw_jobs,
                    resume_text=st.session_state.resume_text,
                    job_role=job_role,
                    max_results=MAX_INITIAL_JOBS,
                )

                st.session_state.verified_jobs = verified

            if not verified:
                st.warning("No verified jobs found yet. Add SERPAPI_API_KEY or next we will add Greenhouse/Lever/Ashby direct search.")
            else:
                st.success(f"Found {len(verified)} verified jobs.")


if more_button:
    if not st.session_state.resume_text:
        st.error("Please run initial search first.")
    elif not job_role or not location:
        st.error("Please enter Job Role and Location.")
    else:
        with st.spinner("Finding 10 more verified jobs..."):
            raw_jobs = search_jobs(job_role, location, limit=80)

            more_verified = process_jobs(
                raw_jobs=raw_jobs,
                resume_text=st.session_state.resume_text,
                job_role=job_role,
                max_results=MAX_MORE_JOBS,
            )

            st.session_state.verified_jobs.extend(more_verified)

        if not more_verified:
            st.warning("No additional verified jobs found. We need to add more direct sources next.")
        else:
            st.success(f"Added {len(more_verified)} more verified jobs.")


if st.session_state.verified_jobs:
    st.subheader("Verified Job Results")

    df = pd.DataFrame(st.session_state.verified_jobs)

    preferred_columns = [
        "job_role",
        "company",
        "ats_score",
        "verdict",
        "experience_required",
        "platform",
        "location",
        "salary",
        "posted_date",
        "job_link",
        "match_reason",
        "verification_status",
        "status",
    ]

    available_columns = [col for col in preferred_columns if col in df.columns]
    st.dataframe(df[available_columns], use_container_width=True)

    st.markdown("### Export Results")

    export_col1, export_col2 = st.columns(2)

    with export_col1:
        if st.button("Export XLSX", use_container_width=True):
            file_path = export_jobs_to_excel(st.session_state.verified_jobs)

            with open(file_path, "rb") as f:
                st.download_button(
                    label="Download XLSX",
                    data=f,
                    file_name=os.path.basename(file_path),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

    with export_col2:
        if st.button("Export JSON", use_container_width=True):
            file_path = export_jobs_to_json(st.session_state.verified_jobs)

            with open(file_path, "rb") as f:
                st.download_button(
                    label="Download JSON",
                    data=f,
                    file_name=os.path.basename(file_path),
                    mime="application/json",
                    use_container_width=True,
                )