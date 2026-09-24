from __future__ import annotations

from neo4j import GraphDatabase

from app.config import get_settings

settings = get_settings()


def get_neo4j_driver():
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        connection_acquisition_timeout=10,
        max_connection_lifetime=60,
    )


def verify_neo4j_connection() -> bool:
    driver = get_neo4j_driver()
    try:
        with driver.session(database="neo4j") as session:
            result = session.run("RETURN 1 AS ok")
            return result.single()["ok"] == 1
    except Exception:
        return False
    finally:
        driver.close()


def seed_neo4j_ontology() -> dict[str, int]:
    driver = get_neo4j_driver()
    try:
        with driver.session(database="neo4j") as session:
            constraint_statements = [
                "CREATE CONSTRAINT skill_name_unique IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
                "CREATE CONSTRAINT certification_name_unique IF NOT EXISTS FOR (c:Certification) REQUIRE c.name IS UNIQUE",
                "CREATE CONSTRAINT jobrole_title_unique IF NOT EXISTS FOR (j:JobRole) REQUIRE j.title IS UNIQUE",
                "CREATE CONSTRAINT industry_name_unique IF NOT EXISTS FOR (i:Industry) REQUIRE i.name IS UNIQUE",
            ]
            for statement in constraint_statements:
                session.run(statement)

            seed_data = {
                "Skill": [
                    ("Python", "Programming"),
                    ("SQL", "Data"),
                    ("Data Analysis", "Data"),
                    ("Financial Accounting", "Accounting"),
                    ("Taxation", "Accounting"),
                    ("Project Management", "Management"),
                    ("Business Analysis", "Business"),
                ],
                "Certification": [
                    ("CPA", "Certification"),
                    ("AWS Certified Cloud Practitioner", "Certification"),
                    ("Google Data Analytics", "Certification"),
                ],
                "JobRole": [
                    ("Software Engineer", "Role"),
                    ("Data Analyst", "Role"),
                    ("Accountant", "Role"),
                ],
                "Industry": [
                    ("Technology", "Industry"),
                    ("Finance", "Industry"),
                    ("Healthcare", "Industry"),
                ],
            }

            for label, payload in seed_data.items():
                for name, category in payload:
                    if label == "JobRole":
                        session.run(
                            "MERGE (j:JobRole {title: $name, name: $name, category: $category})",
                            {"name": name, "category": category},
                        )
                    else:
                        session.run(
                            f"MERGE ({label.lower()}:`{label}` {{name: $name, category: $category}})",
                            {"name": name, "category": category},
                        )

            relationship_statements = [
                "MATCH (s:Skill {name: 'Python'}), (t:Skill {name: 'Data Analysis'}) MERGE (s)-[:RELATED_TO {weight: 0.8}]->(t)",
                "MATCH (s:Skill {name: 'SQL'}), (t:Skill {name: 'Data Analysis'}) MERGE (s)-[:RELATED_TO {weight: 0.7}]->(t)",
                "MATCH (s:Skill {name: 'Financial Accounting'}), (t:Skill {name: 'Taxation'}) MERGE (s)-[:RELATED_TO {weight: 0.9}]->(t)",
                "MATCH (s:JobRole {title: 'Software Engineer'}), (t:Skill {name: 'Python'}) MERGE (s)-[:SKILL_REQUIRED {weight: 0.9}]->(t)",
                "MATCH (s:JobRole {title: 'Software Engineer'}), (t:Skill {name: 'SQL'}) MERGE (s)-[:SKILL_REQUIRED {weight: 0.6}]->(t)",
                "MATCH (s:JobRole {title: 'Data Analyst'}), (t:Skill {name: 'Data Analysis'}) MERGE (s)-[:SKILL_REQUIRED {weight: 0.9}]->(t)",
                "MATCH (s:JobRole {title: 'Accountant'}), (t:Skill {name: 'Financial Accounting'}) MERGE (s)-[:SKILL_REQUIRED {weight: 0.9}]->(t)",
                "MATCH (s:JobRole {title: 'Accountant'}), (t:Certification {name: 'CPA'}) MERGE (s)-[:REQUIRES_CERT]->(t)",
                "MATCH (s:JobRole {title: 'Software Engineer'}), (t:Certification {name: 'AWS Certified Cloud Practitioner'}) MERGE (s)-[:REQUIRES_CERT]->(t)",
            ]
            for statement in relationship_statements:
                session.run(statement)

            counts = session.run("MATCH (s:Skill) RETURN count(s) AS skills").single()
            certs = session.run("MATCH (c:Certification) RETURN count(c) AS certifications").single()
            roles = session.run("MATCH (j:JobRole) RETURN count(j) AS job_roles").single()
            rels = session.run("MATCH ()-[r]->() RETURN count(r) AS relationships").single()

            return {
                "skills": int(counts["skills"]),
                "certifications": int(certs["certifications"]),
                "job_roles": int(roles["job_roles"]),
                "relationships": int(rels["relationships"]),
            }
    finally:
        driver.close()
