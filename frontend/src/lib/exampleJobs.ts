import type { JobInput } from "./api";

// Sample postings for demonstrations; only applied when the recruiter asks for one.
// Skills and certifications reuse the names in the seed data so the matcher recognises them. Remote roles leave
// location blank: the rule filter compares locations literally, so "Remote" would reject candidates in every city.
export const exampleJobs: JobInput[] = [
  { title: "Senior DevOps Engineer", description: "Own platform reliability, CI/CD delivery and cloud operations for a Nairobi fintech team.", location: "Nairobi", requiredExperienceYears: 5, salaryRangeMin: 180000, salaryRangeMax: 250000, requiresWorkAuthorization: false, requiredSkills: ["CI/CD", "AWS", "Kubernetes", "Docker"], mandatoryCertifications: ["AWS Certified Cloud Practitioner"] },
  { title: "Backend Developer (Python)", description: "Build the REST APIs behind a fleet-tracking platform, process GPS events at scale and ship containerised services with automated tests.", location: "Mombasa", requiredExperienceYears: 3, salaryRangeMin: 150000, salaryRangeMax: 220000, requiresWorkAuthorization: false, requiredSkills: ["Python", "REST APIs", "SQL", "Docker", "Git"], mandatoryCertifications: [] },
  { title: "Frontend Developer (React)", description: "Build accessible React interfaces for an online learning platform used by thousands of students on mobile connections.", location: "Eldoret", requiredExperienceYears: 2, salaryRangeMin: 110000, salaryRangeMax: 170000, requiresWorkAuthorization: false, requiredSkills: ["JavaScript", "React", "TypeScript", "REST APIs", "Git"], mandatoryCertifications: [] },
  { title: "Full Stack Developer", description: "Develop the web portal farmers and buyers use to trade produce, from the React front end to the Python API and SQL database.", location: "Nakuru", requiredExperienceYears: 2, salaryRangeMin: 130000, salaryRangeMax: 190000, requiresWorkAuthorization: false, requiredSkills: ["JavaScript", "React", "Python", "REST APIs", "SQL"], mandatoryCertifications: [] },
  { title: "Mobile Developer (Flutter)", description: "Ship features for a consumer savings app in Flutter, integrate REST APIs and keep the app fast on low-end devices. Remote within Kenya.", location: "", requiredExperienceYears: 2, salaryRangeMin: 150000, salaryRangeMax: 230000, requiresWorkAuthorization: false, requiredSkills: ["Flutter", "Dart", "REST APIs", "Git", "Firebase"], mandatoryCertifications: [] },
  { title: "Data Analyst", description: "Turn clinic operations data into Power BI dashboards and clear weekly reports that hospital managers can act on.", location: "Nairobi", requiredExperienceYears: 2, salaryRangeMin: 90000, salaryRangeMax: 140000, requiresWorkAuthorization: false, requiredSkills: ["SQL", "Python", "Power BI", "Data Analysis", "Excel"], mandatoryCertifications: [] },
  { title: "Data Engineer", description: "Design and run the pipelines that move sales and inventory data into an AWS data platform for reporting and forecasting.", location: "Kisumu", requiredExperienceYears: 3, salaryRangeMin: 170000, salaryRangeMax: 250000, requiresWorkAuthorization: false, requiredSkills: ["Python", "SQL", "AWS", "Data Analysis", "CI/CD"], mandatoryCertifications: [] },
  { title: "Machine Learning Engineer", description: "Build and deploy credit-risk and demand-forecasting models, and run them as monitored services in production. Remote within Kenya.", location: "", requiredExperienceYears: 3, salaryRangeMin: 200000, salaryRangeMax: 300000, requiresWorkAuthorization: false, requiredSkills: ["Python", "Machine Learning", "SQL", "Docker", "AWS"], mandatoryCertifications: [] },
  { title: "Cybersecurity Analyst (SOC)", description: "Monitor client environments from a security operations centre, investigate alerts and lead incident response for financial-services clients.", location: "Nairobi", requiredExperienceYears: 3, salaryRangeMin: 150000, salaryRangeMax: 230000, requiresWorkAuthorization: true, requiredSkills: ["Security Monitoring", "Incident Response", "Linux", "Networking", "Python"], mandatoryCertifications: ["CompTIA Security+"] },
  { title: "Cloud Engineer", description: "Provision and automate AWS environments for client projects and keep deployments repeatable and cost-efficient.", location: "Mombasa", requiredExperienceYears: 2, salaryRangeMin: 160000, salaryRangeMax: 240000, requiresWorkAuthorization: false, requiredSkills: ["AWS", "Docker", "Linux", "CI/CD", "Python"], mandatoryCertifications: ["AWS Certified Cloud Practitioner"] },
  { title: "QA Automation Engineer", description: "Write automated test suites for web and API releases and keep them running in the CI/CD pipeline.", location: "Thika", requiredExperienceYears: 1, salaryRangeMin: 90000, salaryRangeMax: 140000, requiresWorkAuthorization: false, requiredSkills: ["Test Automation", "Python", "Selenium", "CI/CD", "Git"], mandatoryCertifications: [] },
  { title: "Database Administrator", description: "Own the performance, backups and security of production PostgreSQL databases, and automate routine maintenance tasks.", location: "Eldoret", requiredExperienceYears: 4, salaryRangeMin: 140000, salaryRangeMax: 200000, requiresWorkAuthorization: false, requiredSkills: ["SQL", "PostgreSQL", "Linux", "Backup and Recovery", "Python"], mandatoryCertifications: [] },
  { title: "Systems Administrator", description: "Administer servers, networks and user directories across several hotel sites, and keep booking systems available.", location: "Kisumu", requiredExperienceYears: 3, salaryRangeMin: 90000, salaryRangeMax: 140000, requiresWorkAuthorization: false, requiredSkills: ["Linux", "Networking", "Active Directory", "Docker", "Git"], mandatoryCertifications: [] },
  { title: "IT Business Analyst", description: "Translate operations needs into system requirements, run user acceptance testing and report on adoption of new systems.", location: "Nairobi", requiredExperienceYears: 2, salaryRangeMin: 100000, salaryRangeMax: 150000, requiresWorkAuthorization: false, requiredSkills: ["Business Analysis", "SQL", "Excel", "Process Mapping", "Power BI"], mandatoryCertifications: [] },
  { title: "IT Helpdesk Technician", description: "Provide first-line IT support to office staff, resolve tickets within agreed service levels and set up devices for new starters.", location: "Nyeri", requiredExperienceYears: 1, salaryRangeMin: 50000, salaryRangeMax: 75000, requiresWorkAuthorization: false, requiredSkills: ["Technical Support", "Active Directory", "Networking", "Linux", "Excel"], mandatoryCertifications: [] },
];

// Deals examples like a shuffled deck: every role appears once before any repeats, and a reshuffle never
// starts with the role that was just shown, so each click changes the form.
export function createExampleJobPicker(examples: JobInput[] = exampleJobs, random: () => number = Math.random) {
  let remaining: JobInput[] = [];
  let last: JobInput | undefined;
  return (): JobInput => {
    if (remaining.length === 0) {
      remaining = [...examples];
      for (let i = remaining.length - 1; i > 0; i -= 1) {
        const j = Math.floor(random() * (i + 1));
        [remaining[i], remaining[j]] = [remaining[j], remaining[i]];
      }
      const top = remaining.length - 1;
      if (remaining[top] === last) [remaining[0], remaining[top]] = [remaining[top], remaining[0]];
    }
    last = remaining.pop() as JobInput;
    return last;
  };
}

export const nextExampleJob = createExampleJobPicker();
