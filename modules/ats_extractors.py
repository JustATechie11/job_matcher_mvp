import re
import json
import requests
from urllib.parse import urlparse, parse_qs

def extract_from_greenhouse(url: str) -> dict:
    # URL patterns:
    # https://boards.greenhouse.io/company/jobs/12345
    # https://boards.greenhouse.io/embed/job_app?for=company&token=12345
    
    board_token = None
    job_id = None
    
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    
    if "embed/job_app" in parsed.path:
        qs = parse_qs(parsed.query)
        board_token = qs.get('for', [None])[0]
        job_id = qs.get('token', [None])[0]
    elif len(path_parts) >= 3 and path_parts[1] == "jobs":
        board_token = path_parts[0]
        job_id = path_parts[2]
        
    if not board_token or not job_id:
        return {}
        
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
    try:
        r = requests.get(api_url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "job_role": data.get("title"),
                "description": data.get("content", ""),
                "posted_date": data.get("updated_at")
            }
    except Exception:
        pass
    
    return {}

def extract_from_smartrecruiters(url: str) -> dict:
    # URL patterns:
    # https://jobs.smartrecruiters.com/Company/7439999999-job-slug
    # https://www.smartrecruiters.com/Company/7439999999-job-slug
    
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    
    if len(path_parts) >= 2:
        company = path_parts[0]
        job_slug = path_parts[1]
        job_id = job_slug.split('-')[0]
        
        # Test if it's a UUID or just digits
        api_url = f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{job_id}"
        try:
            r = requests.get(api_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                
                # SmartRecruiters has sectioned descriptions
                desc_parts = []
                job_ad = data.get("jobAd", {})
                for section in ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]:
                    if job_ad.get(section):
                        desc_parts.append(job_ad.get(section).get("text", ""))
                        
                return {
                    "job_role": data.get("name"),
                    "description": "\n\n".join(desc_parts),
                    "posted_date": data.get("releasedDate", data.get("updatedAt"))
                }
        except Exception:
            pass
            
    return {}

def extract_from_ashby(url: str) -> dict:
    # URL patterns:
    # https://jobs.ashbyhq.com/company/job_id
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            # Look for NEXT_DATA JSON
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', r.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                try:
                    job_data = data["props"]["pageProps"]["jobBoard"]["jobPosting"]
                    return {
                        "job_role": job_data.get("title"),
                        "description": job_data.get("descriptionHtml", ""),
                        "posted_date": job_data.get("publishedAt")
                    }
                except KeyError:
                    pass
    except Exception:
        pass
        
    return {}

def extract_from_lever(url: str) -> dict:
    # https://jobs.lever.co/company/job_id
    
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    
    if len(path_parts) >= 2:
        company = path_parts[0]
        job_id = path_parts[1]
        
        api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
        try:
            r = requests.get(api_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "job_role": data.get("text"),
                    "description": data.get("descriptionPlain", data.get("description", "")),
                    "posted_date": data.get("createdAt")
                }
        except Exception:
            pass
            
    return {}

def enhance_job_with_ats_api(job: dict) -> dict:
    """
    Takes a job dictionary from SerpAPI and attempts to fetch
    more accurate details using public ATS endpoints.
    """
    url = job.get("job_link", "")
    if not url:
        return job
        
    extracted_data = {}
    
    if "greenhouse.io" in url:
        extracted_data = extract_from_greenhouse(url)
    elif "smartrecruiters.com" in url:
        extracted_data = extract_from_smartrecruiters(url)
    elif "ashbyhq.com" in url:
        extracted_data = extract_from_ashby(url)
    elif "lever.co" in url:
        extracted_data = extract_from_lever(url)
        
    if extracted_data:
        # Update fields if we got valid data back
        if extracted_data.get("job_role"):
            job["job_role"] = extracted_data["job_role"]
        
        # We replace the SerpAPI snippet description with the full ATS description
        if extracted_data.get("description") and len(extracted_data["description"]) > len(job.get("description", "")):
            job["description"] = extracted_data["description"]
            
        # ATS APIs usually provide true ISO timestamps. We can store this or just use it to verify freshness.
        if extracted_data.get("posted_date"):
            job["ats_posted_date"] = extracted_data["posted_date"]
            
        job["source"] = job.get("source", "") + "_enhanced_by_ats_api"
        
    return job
