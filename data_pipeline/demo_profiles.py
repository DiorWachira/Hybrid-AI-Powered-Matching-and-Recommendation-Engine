"""Fictional Kenyan demonstration identities and job-aligned profile variants."""
import uuid

FIRST_NAMES = ("Amina", "Brian", "Faith", "David", "Grace", "Hassan", "Irene", "James", "Joy", "Kevin", "Mercy", "Moses", "Naomi", "Peter", "Ruth", "Samuel", "Sharon", "Victor", "Winnie", "Yusuf")
LAST_NAMES = ("Wanjiku", "Otieno", "Mutua", "Chebet", "Mwangi", "Achieng", "Kiptoo", "Njeri", "Omondi", "Wambui", "Muthoni", "Kipchoge", "Naliaka", "Musyoka", "Barasa", "Wairimu", "Juma", "Nyambura", "Kamau", "Wekesa")
COMPANIES = ("Mwangaza Digital Studio", "Tujenge Analytics", "Pamoja Cloud Works", "Jabali Business Services", "Upeo Finance Studio")


def kenyan_name(identifier: uuid.UUID) -> str:
    index = identifier.int
    return f"{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]}"


def job_variants(job: dict) -> list[dict]:
    required = list(job.get("required_skills") or [])
    certifications = list(job.get("mandatory_certifications") or [])
    minimum = int(job.get("required_experience_years") or 0)
    ceiling = job.get("salary_range_max")
    profiles = []
    for variant in ("strong", "developing", "ineligible"):
        identifier = uuid.uuid5(uuid.NAMESPACE_URL, f"jobbridge-demo-v2:{job['job_id']}:{variant}")
        skills = required if variant == "strong" else required[:max(1, len(required) // 2)]
        description = str(job.get("description") or "")
        resume = (
            f"Experienced {job['title']}. Delivered production projects using {', '.join(skills)}. {description}"
            if variant == "strong" else
            f"Professional developing skills in {', '.join(skills)}. Supported team reporting, documentation and service delivery; seeking a broader role."
        )
        profiles.append({
            "candidate_id": str(identifier), "full_name": kenyan_name(identifier),
            "location": "Demo location outside job area" if variant == "ineligible" else job.get("location"),
            "years_experience": 0 if variant == "ineligible" else minimum + (4 if variant == "strong" else 0),
            "expected_salary_kes": float(ceiling) * (1.25 if variant == "ineligible" else 0.85) if ceiling is not None else None,
            "skills": skills, "certifications": certifications if variant != "ineligible" else [],
            "work_authorized": variant != "ineligible", "resume_text": resume,
        })
    return profiles