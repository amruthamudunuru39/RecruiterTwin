JD_EXTRACTION_PROMPT = """
Extract structured role DNA from the job description.

Required fields:
- role
- seniority
- domain
- must_have_skills
- nice_to_have_skills
- responsibilities
- success_traits

Keep the output concise and recruiter-friendly.
""".strip()
