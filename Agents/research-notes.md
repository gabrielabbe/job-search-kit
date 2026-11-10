# Research and methodology notes

**Compiled:** 2026-11-06. The frameworks below are useful design foundations, not a universally validated recipe for recruiting success.

## Agent 1: Strategic Opportunity Scout

- **Steve Dalton, _The 2-Hour Job Search_.** LAMP (List, Alumni, Motivation, Posting) supports employer targeting and professional networking. Our fifth **Eligibility** gate is an engineering adaptation specifically for international remote work, not a feature we attribute to Dalton. [Book/publisher](https://www.penguinrandomhouse.com/books/809100/the-2-hour-job-search-third-edition-by-steve-dalton/).
- **Official public job-listing sources:** [Lever postings API](https://github.com/lever/postings-api), [Greenhouse job board API](https://developers.greenhouse.io/job-board.html), and [Ashby job board API](https://developers.ashbyhq.com/docs/public-job-posting-api). Actual access, scope, quotas, and terms vary. Do not claim unrestricted universal search is supported.
- Remote labels are unreliable proxies for global work authorization. Verify legal/contracting/region details from the employer.

## Agent 2: Evidence-Based Fit Analyst

- **O*NET Content Model:** Occupational attributes spanning worker requirements, work activities, context, and qualifications. Use as a skills/task vocabulary, not as a magic scoring engine. [O*NET](https://www.onetcenter.org/content.html).
- **ESCO:** European skills and occupations classification usable for normalization and job matching. [Official ESCO API](https://esco.ec.europa.eu/en/use-esco/use-esco-services-api).
- **U.S. Office of Personnel Management, Job Analysis:** Connect tasks to competencies and document relevance. [OPM guidance](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/).
- Our 0–4 rubric, weights, and priority thresholds are **proposed configurable heuristics** that must be empirically validated against the user's actual outcomes. They are not sourced as predictive coefficients from these institutions.

## Agent 3: Application and Networking Strategist

- **Phyl Terry, _Never Search Alone_.** Candidate-Market Fit and relational job search support tailoring positioning to actual demand and involving professional contacts. [Never Search Alone](https://www.neversearchalone.org/faq).
- **STAR method:** Situation, Task, Action, Result helps structure specific evidence for interviews and screening answers. [UK National Careers Service](https://nationalcareers.service.gov.uk/careers-advice/interview-advice/the-star-method).
- **Résumé-writing research:** Wiles, Munyikwa, and Horton investigate algorithmic writing assistance and hiring outcomes; improvements in readable writing should not be misrepresented as proof that AI-generated résumés or keyword stuffing guarantee interviews. [Publication DOI](https://doi.org/10.1287/mnsc.2024.04528).
- **Ethical contact discovery:** Official employer sites and authorized professional-data tools may support identification. Respect platform restrictions, privacy laws, opt-outs, and approvals. [LinkedIn policy context](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibition-of-scraping-software).

## What the evidence does *not* establish

- A 90% fit score does **not** mean a 90% interview probability.
- General observational differences between referral and inbound applicants do **not** establish that cold messaging causes a specific increase in interview rates.
- A generic "remote" tag does **not** establish eligibility from every country or while traveling.
- Contact information appearing on a website does **not** necessarily mean it may be harvested or used for unrestricted automated outreach.
- No ATS-wide keyword percentage or secret global resume template is proven universally optimal.

## Practical experiments after the MVP

Compare, with a sufficient sample and careful records: first-party vs aggregate sourcing; niche employer targeting vs broad job boards; narrowly tailored vs minimally tailored résumé variants; appropriate direct contact vs application-only; short personalized outreach vs generic outreach. Track outcomes and avoid claiming causality without an appropriate experimental design.
