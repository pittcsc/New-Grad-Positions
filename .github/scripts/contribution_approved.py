import sys
import json
import subprocess
import sys
import uuid
from datetime import datetime
import os
import util
import re


def add_https_to_url(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def getData(body, is_edit, username):
    data = {"date_updated": int(datetime.now().timestamp())}
    
    # Use regex patterns to find fields instead of relying on line positions
    
    # URL/Link - look for the pattern after "Link to Job Posting"
    url_match = re.search(r'Link to Job Posting[^\n]*\n\s*([^\n]+)', body, re.IGNORECASE)
    if url_match and "no response" not in url_match.group(1).lower():
        data["url"] = add_https_to_url(url_match.group(1).strip())
    
    # Company Name
    company_match = re.search(r'Company Name[^\n]*\n\s*([^\n]+)', body, re.IGNORECASE)
    if company_match and "no response" not in company_match.group(1).lower():
        data["company_name"] = company_match.group(1).strip()
    
    # Job Title
    title_match = re.search(r'Job Title[^\n]*\n\s*([^\n]+)', body, re.IGNORECASE)
    if title_match and "no response" not in title_match.group(1).lower():
        data["title"] = title_match.group(1).strip()
    
    # Location
    location_match = re.search(r'Location[^\n]*\n\s*([^\n]+)', body, re.IGNORECASE)
    if location_match and "no response" not in location_match.group(1).lower():
        data["locations"] = [loc.strip() for loc in location_match.group(1).split("|")]
    
    # Category Selection
    category_match = re.search(r'What category does this job belong to\?[^\n]*\n\s*([^\n]+)', body, re.IGNORECASE)
    if category_match and "no response" not in category_match.group(1).lower():
        category_text = category_match.group(1).strip()
        # Map form selections to internal category names
        category_mapping = {
            "Software Engineering": "Software Engineering",
            "Product Management": "Product Management", 
            "Data Science, AI & Machine Learning": "Data Science, AI & Machine Learning",
            "Quantitative Finance": "Quantitative Finance",
            "Hardware Engineering": "Hardware Engineering",
            "Other": "Other"
        }
        data["category"] = category_mapping.get(category_text, "Other")
    
    # Advanced Degree Requirements - look for checkbox
    advanced_degree_pattern = r'Advanced Degree Requirements.*?\n.*?\[x\]'
    advanced_degree_checked = bool(re.search(advanced_degree_pattern, body, re.IGNORECASE | re.DOTALL))
    data["degrees"] = ["Master's"] if advanced_degree_checked else []
    
    # Sponsorship
    sponsorship_match = re.search(r'Does this job offer sponsorship\?[^\n]*\n\s*([^\n]+)', body, re.IGNORECASE)
    if sponsorship_match and "no response" not in sponsorship_match.group(1).lower():
        data["sponsorship"] = "Other"
        sponsorship_text = sponsorship_match.group(1)
        for option in ["Offers Sponsorship", "Does Not Offer Sponsorship", "U.S. Citizenship is Required"]:
            if option in sponsorship_text:
                data["sponsorship"] = option
    
    # Active status
    if is_edit:
        active_pattern = r'Is this job posting currently accepting applications\?[^\n]*\n\s*([^\n]+)'
    else:
        active_pattern = r'Is this job posting currently accepting applications\?[^\n]*\n\s*([^\n]+)'
    
    active_match = re.search(active_pattern, body, re.IGNORECASE)
    if active_match:
        response_text = active_match.group(1).lower()
        if "none" not in response_text and "no response" not in response_text:
            data["active"] = "yes" in response_text
        # If "none" or "no response", don't set active field - let downstream handle default
    # If no match found, don't set active field - let downstream handle default
    
    # Visibility (for edits only)
    if is_edit:
        remove_pattern = r'Permanently remove this job from the list\?.*?\n.*?\[x\]'
        should_remove = bool(re.search(remove_pattern, body, re.IGNORECASE | re.DOTALL))
        data["is_visible"] = not should_remove
    
    # Email
    email_match = re.search(r'Email associated with your GitHub account[^\n]*\n\s*([^\n]+)', body, re.IGNORECASE)
    email = "_no response_"
    if email_match:
        email = email_match.group(1).strip()
    
    if "no response" not in email.lower():
        util.setOutput("commit_email", email)
        util.setOutput("commit_username", username)
    else:
        util.setOutput("commit_email", "action@github.com")
        util.setOutput("commit_username", "GitHub Action")
    
    return data


def main():
    event_file_path = sys.argv[1]

    with open(event_file_path) as f:
        event_data = json.load(f)

    
    # CHECK IF NEW OR OLD JOB

    new_role = "new_role" in [label["name"] for label in event_data["issue"]["labels"]]
    edit_role = "edit_role" in [label["name"] for label in event_data["issue"]["labels"]]
    
    if not new_role and not edit_role:
        util.fail("Only new_role and edit_role issues can be approved")
    

    # GET DATA FROM ISSUE FORM

    issue_body = event_data['issue']['body']
    issue_user = event_data['issue']['user']['login']

    data = getData(issue_body, is_edit=edit_role, username=issue_user)
    
    if new_role:
        data["source"] = issue_user
        data["id"] = str(uuid.uuid4())
        data["date_posted"] = int(datetime.now().timestamp())
        data["company_url"] = ""
        data["is_visible"] = True
        # degrees field is already set by getData() based on form input
        
        # Ensure new jobs are active by default if not specified
        if "active" not in data:
            data["active"] = True

    # remove utm-source
    utm = data["url"].find("?utm_source")
    if utm == -1:
        utm = data["url"].find("&utm_source")
    if utm != -1:
        data["url"] = data["url"][:utm]


    # UPDATE LISTINGS

    listings = []
    with open(".github/scripts/listings.json", "r") as f:
        listings = json.load(f)

    listing_to_update = next(
        (item for item in listings if item["url"] == data["url"]), None)
    if listing_to_update:
        if new_role:
            util.fail("This role is already in our list. See CONTRIBUTING.md for how to edit a listing")
        for key, value in data.items():
            listing_to_update[key] = value
        
        util.setOutput("commit_message", "updated listing: " + listing_to_update["title"] + " at " + listing_to_update["company_name"])
    else:
        if edit_role:
            util.fail("We could not find this role in our list. Please double check you inserted the right url")
        listings.append(data)
        util.setOutput("commit_message", "added listing: " + data["title"] + " at " + data["company_name"])

    with open(".github/scripts/listings.json", "w") as f:
        f.write(json.dumps(listings, indent=4))


if __name__ == "__main__":
    main()
