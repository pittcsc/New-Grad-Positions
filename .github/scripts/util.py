import json
import re
from datetime import date, datetime, timezone, timedelta
import random
import os

# SIMPLIFY_BUTTON = "https://i.imgur.com/kvraaHg.png"
SIMPLIFY_BUTTON = "https://i.imgur.com/MXdpmi0.png" # says apply
SHORT_APPLY_BUTTON = "https://i.imgur.com/fbjwDvo.png"
SQUARE_SIMPLIFY_BUTTON = "https://i.imgur.com/aVnQdox.png"
LONG_APPLY_BUTTON = "https://i.imgur.com/G5Bzlx3.png"


def setOutput(key, value):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'{key}={value}', file=fh)

def fail(why):
    setOutput("error_message", why)
    exit(1)

def getLocations(listing):
    locations = "</br>".join(listing["locations"])
    if len(listing["locations"]) <= 3:
        return locations
    num = str(len(listing["locations"])) + " locations"
    return f'<details><summary>**{num}**</summary>{locations}</details>'

def getSponsorship(listing):
    if listing["sponsorship"] == "Does Not Offer Sponsorship":
        return " 🛂"
    elif listing["sponsorship"] == "U.S. Citizenship is Required":
        return " 🇺🇸"
    return ""

def getLink(listing):
    if not listing["active"]:
        return "🔒"
    link = listing["url"]
    if "?" not in link:
        link += "?utm_source=Simplify&ref=Simplify"
    else:
        link += "&utm_source=Simplify&ref=Simplify"
    # return f'<a href="{link}" style="display: inline-block;"><img src="{SHORT_APPLY_BUTTON}" width="160" alt="Apply"></a>'

    if listing["source"] != "Simplify":
        return f'<a href="{link}"><img src="{LONG_APPLY_BUTTON}" width="100" alt="Apply"></a>'
    
    simplifyLink = f"https://simplify.jobs/p/{listing['id']}?utm_source=GHList"
    return f'<a href="{link}"><img src="{SHORT_APPLY_BUTTON}" width="49" alt="Apply"></a> <a href="{simplifyLink}"><img src="{SQUARE_SIMPLIFY_BUTTON}" width="26" alt="Simplify"></a>'

def filter_active(listings):
    return [listing for listing in listings if listing.get("active", False)]

def create_md_table(listings):
    table = ""
    table = "| Company | Role | Location | Application | Age |\n"
    table += "| ------- | ---- | -------- | ---------- | --- |\n"
    prev_company = None
    prev_days_active = None

    for listing in listings:
        raw_url = listing.get("company_url", "").strip()
        company_url = raw_url + '?utm_source=GHList&utm_medium=company' if raw_url.startswith("http") else ""
        company = f"**[{listing['company_name']}]({company_url})**" if company_url else listing["company_name"]
        location = getLocations(listing)
        position = listing["title"] + getSponsorship(listing)
        link = getLink(listing)

        # Days active calculation
        days_active = (datetime.now() - datetime.fromtimestamp(listing["date_posted"])).days
        days_active = max(days_active, 0)

        days_display = (
            "0d" if days_active == 0 else
            f"{(days_active // 30)}mo" if days_active >= 30 else
            f"{days_active}d"
        )

        if prev_company == listing['company_name'] and prev_days_active == days_active:
            company = "↳"
        else:
            prev_company = listing['company_name']
            prev_days_active = days_active

        table += f"| {company} | {position} | {location} | {link} | {days_display} |\n"

    return table

def filterListings(listings, earliest_date):
    final_listings = []
    inclusion_terms = ["software eng", "software dev", "data scientist", "data engineer", "founding eng", "research eng", "product manage", "apm", "frontend", "front end", "front-end", "backend", "back end", "full-stack", "full stack", "full-stack", "devops", "android", "ios", "mobile dev", "sre", "site reliability eng", "quantitative trad", "quantitative research", "quantitative trad", "quantitative dev", "security eng", "compiler eng", "machine learning eng", "infrastructure eng"]
    new_grad_terms = ["new grad", "early career", "college grad", "entry level", "founding", "early in career", "university grad", "fresh grad", "2024 grad", "2025 grad", "engineer 0", "engineer 1", "engineer i ", "junior", "sde 1", "sde i"]
    for listing in listings:
        if listing["is_visible"] and listing["date_posted"] > earliest_date:
            if listing['source'] != "Simplify" or (any(term in listing["title"].lower() for term in inclusion_terms) and (any(term in listing["title"].lower() for term in new_grad_terms) or (listing["title"].lower().endswith("engineer i")))):
                final_listings.append(listing)

    return final_listings

def getListingsFromJSON(filename=".github/scripts/listings.json"):
    with open(filename) as f:
        listings = json.load(f)
        print("Recieved " + str(len(listings)) +
              " listings from listings.json")
        return listings


def embedTable(listings):
    filepath = "README.md"
    newText = ""
    readingTable = False
    with open(filepath, "r") as f:
        for line in f.readlines():
            if readingTable:
                if "|" not in line and "TABLE_END" in line:
                    newText += line
                    readingTable = False
                continue
            else:
                newText += line
                if "TABLE_START" in line:
                    readingTable = True
                    newText += "\n" + \
                        create_md_table(listings) + "\n"
     # Calculate active count
    active_listings = filter_active(listings)
    total_active = len(active_listings)

    # Regex replace "Browse ### Roles" section
    browse_section_pattern = r"(### Browse )(.*?)( New Grad Roles by Category\s*-+\n)"
    newText = re.sub(browse_section_pattern, f"### Browse {total_active} New Grad Roles by Category\n\n---\n", newText, count=1, flags=re.DOTALL)

    with open(filepath, "w") as f:
        f.write(newText)

def sortListings(listings):
    oldestListingFromCompany = {}
    linkForCompany = {}

    for listing in listings:
        date_posted = listing["date_posted"]
        if listing["company_name"].lower() not in oldestListingFromCompany or oldestListingFromCompany[listing["company_name"].lower()] > date_posted:
            oldestListingFromCompany[listing["company_name"].lower()] = date_posted
        if listing["company_name"] not in linkForCompany or len(listing["company_url"]) > 0:
            linkForCompany[listing["company_name"]] = listing["company_url"]

    listings.sort(
        key=lambda x: (
            x["active"],  # Active listings first
            x['date_posted'],
            x['company_name'].lower(),
            x['date_updated']
        ),
        reverse=True
    )

    for listing in listings:
        listing["company_url"] = linkForCompany[listing["company_name"]]

    return listings


def checkSchema(listings):
    props = ["source", "company_name",
             "id", "title", "active", "date_updated", "is_visible",
             "date_posted", "url", "locations", "company_url",
             "sponsorship"]
    for listing in listings:
        for prop in props:
            if prop not in listing:
                fail("ERROR: Schema check FAILED - object with id " +
                      listing["id"] + " does not contain prop '" + prop + "'")
