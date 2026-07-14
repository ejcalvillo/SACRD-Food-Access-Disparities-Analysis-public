"""Generates a fully synthetic dataset with the same shape as the real
SACRD export (raw monthly interaction/share/portal/pageview/zipcode logs,
a program directory, and ZIP population data).

Every organization name, address, and count below is fictional and
randomly generated. Only the ZIP codes are real (public San Antonio ZIP
codes), used purely so the dashboard has a realistic-looking map.

Run from the repo root:
    python Data/sample_data/generate_sample_data.py

Re-running regenerates every file deterministically (fixed random seed).
"""

import csv
import os
import random

random.seed(42)

HERE = os.path.dirname(os.path.abspath(__file__))

# Real, public San Antonio ZIP codes with plausible (not authoritative) lat/lng/population.
# 78205 is included on purpose: the real pipeline treats it as a "default" ZIP
# assigned when a site visitor doesn't enter one, and explicitly excludes it
# from Gap Score results (see README "Known Issues").
ZIP_INFO = {
    "78201": (29.4715, -98.5195, 26200),
    "78202": (29.4325, -98.4725, 9800),
    "78203": (29.4180, -98.4630, 12100),
    "78205": (29.4246, -98.4900, 4200),
    "78207": (29.4270, -98.5240, 32700),
    "78210": (29.4090, -98.4560, 24900),
    "78211": (29.3670, -98.5540, 33800),
    "78214": (29.3690, -98.4970, 18700),
    "78218": (29.4830, -98.4160, 21300),
    "78228": (29.4610, -98.5680, 34900),
    "78237": (29.4130, -98.5760, 29600),
}
PROGRAM_ZIPS = [z for z in ZIP_INFO if z != "78205"]

ORG_NAMES = [
    "Riverside Community Table", "Eastside Neighbors Pantry", "Alamo Harvest Alliance",
    "Westside Family Resource Center", "Mission Trail Food Collective", "Northside Helping Hands",
    "San Pedro Springs Outreach", "Southtown Mutual Aid", "Brooks City Base Cares",
    "Culebra Road Community Center", "Loop 410 Family Services", "Blanco Basin Neighbors",
    "Comal Creek Support Network", "Palo Alto Community Partners", "Guadalupe River Relief",
]

STREETS = [
    "Broadway St", "Culebra Rd", "Zarzamora St", "Blanco Rd", "Military Dr W",
    "Commerce St", "Nogalitos St", "Fredericksburg Rd", "New Braunfels Ave",
    "Pleasanton Rd", "Bandera Rd", "Roosevelt Ave", "Rigsby Ave", "Ingram Rd", "Marbach Rd",
]

# subcat -> (program name template, url slug)
SUBCATS = {
    "Food Pantry": ("Food Pantry", "food-pantry"),
    "Emergency Food": ("Emergency Food Program", "emergency-food"),
    "Free Meals": ("Community Meals", "free-meals"),
    "Nutrition Education": ("Nutrition Workshops", "nutrition-education"),
    "Help Pay for Food": ("Food Assistance Fund", "help-pay-for-food"),
    "Community Garden": ("Community Garden", "community-garden"),
    "Affordable Fresh Food": ("Fresh Food Market", "affordable-fresh-food"),
    "Food Delivery": ("Home Delivery Program", "food-delivery"),
    "Childcare": ("Childcare Services", "childcare"),
    "Clothing": ("Clothing Closet", "clothing"),
    "Counseling": ("Counseling Center", "counseling"),
    "Senior Programs": ("Senior Services", "senior-programs"),
    "Youth Programs": ("Youth Program", "youth-programs"),
    "Transportation Assistance": ("Transportation Assistance", "transportation-assistance"),
    "Dental Care": ("Dental Clinic", "dental-care"),
    "Financial Education": ("Financial Literacy Program", "financial-education"),
    "Job Training": ("Job Training Program", "job-training"),
    "Mental Healthcare": ("Mental Health Services", "mental-healthcare"),
}
FOOD_SUBCATS = [
    "Food Pantry", "Emergency Food", "Free Meals", "Nutrition Education",
    "Help Pay for Food", "Community Garden", "Affordable Fresh Food", "Food Delivery",
]
NON_FOOD_SUBCATS = [s for s in SUBCATS if s not in FOOD_SUBCATS]

FOOD_SEARCH_TERMS = [
    "food pantry", "free meals", "grocery help", "nutrition class", "comida",
    "despensa", "food delivery", "community garden",
]
OTHER_SEARCH_TERMS = ["childcare", "job training", "dental clinic", "housing help", "counseling"]
EXTERNAL_REFERRERS = [
    "https://www.google.com/", "https://www.facebook.com/", "https://www.instagram.com/",
    "(direct)",
]
METHODS = ["-", "click", "website", "phone", "email", "see-more"]

MONTHS = ["2024-01", "2024-02", "2024-03"]


def jitter(value, spread):
    return round(value + random.uniform(-spread, spread), 7)


def build_programs():
    """Builds the raw program directory (mirrors Data/new_programs.csv)."""
    programs = []
    program_id = 1000
    for org_id, org_name in enumerate(ORG_NAMES, start=1):
        for _ in range(random.randint(4, 12)):
            zipcode = random.choice(PROGRAM_ZIPS)
            lat, lng, _pop = ZIP_INFO[zipcode]
            n_subcats = random.choice([1, 1, 2, 3])
            weighted_pool = FOOD_SUBCATS * 2 + NON_FOOD_SUBCATS  # food subcats are ~1/3 of the directory
            chosen = random.sample(weighted_pool, k=min(n_subcats, len(set(weighted_pool))))
            chosen = list(dict.fromkeys(chosen))  # de-dup, preserve order
            primary_label, _slug = SUBCATS[chosen[0]]

            programs.append({
                "id": program_id,
                "name": f"{org_name} {primary_label}",
                "org": org_name,
                "service_address": f"{random.randint(100, 14999)} {random.choice(STREETS)}, San Antonio, TX, {zipcode}",
                "subcats": ", ".join(chosen),
                "inactive": random.choices(["False", "True"], weights=[88, 12])[0],
                "zipcode": zipcode,
                "lat": jitter(lat, 0.01),
                "lng": jitter(lng, 0.01),
                "org_id": org_id,
            })
            program_id += 1
    return programs


def write_pipe_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="|")
        writer.writeheader()
        writer.writerows(rows)


def write_dup_header_csv(path, header, rows):
    """Writes a CSV with a repeated column name, matching the real GA-style
    exports where 'Event count' legitimately appears twice (pandas reads the
    second copy back as 'Event count.1')."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def build_zips_external():
    rows = [{"Zipcode": z, "latitude": lat, "longitude": lng, "population": pop}
            for z, (lat, lng, pop) in ZIP_INFO.items()]
    return rows


def make_url(zipcode, program=None):
    if program and random.random() < 0.7:
        _label, slug = SUBCATS[program["subcats"].split(", ")[0]]
        return f"https://sacrd.org/directory/subcategory/{slug}?zipcode={zipcode}"
    return f"https://sacrd.org/directory/organization?zipcode={zipcode}"


def build_month_files(month_dir, programs):
    os.makedirs(month_dir, exist_ok=True)
    food_programs = [p for p in programs if any(s in FOOD_SUBCATS for s in p["subcats"].split(", "))]

    # interaction.csv / share.csv: URL,Search,Entity type,Entity ID,Method,Event count,Event count
    header = ["URL", "Search", "Entity type", "Entity ID", "Method", "Event count", "Event count"]
    for filename, n_rows in (("interaction.csv", 220), ("share.csv", 70)):
        rows = []
        for _ in range(n_rows):
            zipcode = random.choice(list(ZIP_INFO))
            entity_type = random.choices(
                ["program", "prog", "org", "iframe"], weights=[55, 15, 25, 5]
            )[0]
            if entity_type in ("program", "prog"):
                use_food = random.random() < 0.6
                program = random.choice(food_programs if use_food else programs)
                entity_id = program["id"]
                url = make_url(zipcode, program)
            elif entity_type == "org":
                org = random.choice(programs)
                entity_id = org["org_id"]
                url = make_url(zipcode)
            else:
                entity_id = random.randint(1, 50)
                url = f"https://sacrd.org/embed/widget?zipcode={zipcode}"

            search = random.choice(FOOD_SEARCH_TERMS + OTHER_SEARCH_TERMS) if random.random() < 0.3 else ""
            if search:
                url = f"https://sacrd.org/directory/search?s={search.replace(' ', '+')}&zipcode={zipcode}"
            method = random.choice(METHODS)
            count = random.choices([1, 2, 3, 5, 8], weights=[45, 25, 15, 10, 5])[0]
            rows.append([url, search, entity_type, entity_id, method, count, count])
        write_dup_header_csv(os.path.join(month_dir, filename), header, rows)

    # portal.csv: URL,Search,Entity type,Entity ID,Event count,Event count (not consumed by the pipeline;
    # included so the sample data mirrors the real export's full schema)
    header = ["URL", "Search", "Entity type", "Entity ID", "Event count", "Event count"]
    rows = []
    for _ in range(120):
        zipcode = random.choice(list(ZIP_INFO))
        program = random.choice(programs)
        url = make_url(zipcode, program)
        count = random.choices([1, 2, 3, 5], weights=[50, 25, 15, 10])[0]
        rows.append([url, "", "program", program["id"], count, count])
    write_dup_header_csv(os.path.join(month_dir, "portal.csv"), header, rows)

    # pageview.csv: Page location,Page referrer,Event count,Event count (not consumed by the pipeline)
    header = ["Page location", "Page referrer", "Event count", "Event count"]
    rows = []
    for _ in range(250):
        zipcode = random.choice(list(ZIP_INFO))
        page = make_url(zipcode, random.choice(programs))
        referrer = random.choice([make_url(random.choice(list(ZIP_INFO)))] + EXTERNAL_REFERRERS)
        count = random.choices([1, 2, 3], weights=[60, 25, 15])[0]
        rows.append([page, referrer, count, count])
    write_dup_header_csv(os.path.join(month_dir, "pageview.csv"), header, rows)

    # zipcode.csv: URL,ZIP code,Event count,Event count (not consumed by the pipeline)
    header = ["URL", "ZIP code", "Event count", "Event count"]
    rows = []
    for _ in range(100):
        zipcode = random.choice(list(ZIP_INFO))
        url = make_url(zipcode, random.choice(programs))
        count = random.choices([1, 2, 3], weights=[60, 25, 15])[0]
        rows.append([url, zipcode, count, count])
    write_dup_header_csv(os.path.join(month_dir, "zipcode.csv"), header, rows)


def main():
    programs = build_programs()
    write_pipe_csv(
        os.path.join(HERE, "new_programs.csv"),
        programs,
        fieldnames=["id", "name", "org", "service_address", "subcats", "inactive", "zipcode", "lat", "lng", "org_id"],
    )

    ext_dir = os.path.join(HERE, "External_Data")
    os.makedirs(ext_dir, exist_ok=True)
    with open(os.path.join(ext_dir, "zips_external.csv"), "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["Zipcode", "latitude", "longitude", "population"])
        writer.writeheader()
        writer.writerows(build_zips_external())

    for month in MONTHS:
        build_month_files(os.path.join(HERE, month), programs)

    print(f"Generated {len(programs)} synthetic programs across {len(ORG_NAMES)} orgs")
    print(f"Generated monthly logs for: {', '.join(MONTHS)}")
    print(f"ZIP codes used: {', '.join(ZIP_INFO)}")


if __name__ == "__main__":
    main()
