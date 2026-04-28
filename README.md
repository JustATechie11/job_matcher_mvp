# Job Matcher MVP

A streamlined application designed to match user resumes to relevant job postings by searching, filtering, and scoring jobs from multiple sources.

## Overview

Job Matcher MVP takes a user's resume and a target role, then:
1. **Generates search titles:** Creates title variations (e.g., Data Analyst, Healthcare Data Analyst) based on the target role.
2. **Searches multiple sources:** Uses SerpAPI to search Google Jobs and Google Search for direct ATS/company career links.
3. **Extracts job cards:** Retrieves job postings and finds original company career pages.
4. **Verifies URLs:** Ensures strict verification that the URL is valid, points to an active job, and matches criteria.
5. **Scores resume match:** Evaluates how well the resume matches the job description.
6. **Filters listings:** Removes duplicates, expired posts, "Easy Apply" only jobs, staffing agencies, and government listings.
7. **Returns the top results:** Presents the best matching jobs to the user.

## Tech Stack
- **Frontend / UI:** Streamlit
- **Document Parsing:** PyMuPDF, pdfplumber (for extracting text from resumes)
- **Search & Scraping:** SerpAPI, requests, BeautifulSoup4
- **Data & Matching:** pandas, rapidfuzz
- **Environment Management:** python-dotenv

## Setup Instructions

1. **Clone the repository.**
2. **Install the dependencies:**
   It is recommended to use a virtual environment.
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment Variables:**
   You will need to set up your API keys. Create a `.env` file in the root directory and add the required keys (e.g., SerpAPI).
4. **Run the Application:**
   ```bash
   streamlit run app.py
   ```

## Verification Rules
The app applies strict verification to ensure quality matches:
- URL opens successfully.
- Page title contains the job/company or ATS job ID.
- Page has an apply button/form.
- Job is not expired/closed.
- Location matches user preferences.
- Posted within the last 7 days.
- Company name matches the source.
- Not an "Easy Apply" only job.
- Not a staffing agency.
- Not government (unless explicitly allowed).
