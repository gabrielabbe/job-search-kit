"""Fill resumes/resume template/ATS_Resume_Template.docx from a JSON spec and write a .docx.

Usage: python scripts/build_resume.py <spec.json> <out.docx>
Spec keys: name, contact, summary, skills, experience[{title, company, meta, bullets[]}],
           education[], certifications[] (optional, in-progress items allowed),
           labels{} (optional section headings for non-English resumes)
"""
import copy
import json
import sys
from pathlib import Path

import docx

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "resumes" / "resume template" / "ATS_Resume_Template.docx"


def _linkedin_url():
    """The candidate's LinkedIn URL from data/profile/outreach.json (written during onboarding); empty if not set."""
    p = ROOT / "data" / "profile" / "outreach.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("linkedin", "")
    except (OSError, ValueError):
        return ""


LINKEDIN_URL = _linkedin_url()
LINKEDIN_LABEL = "LinkedIn (click here)"


# Point sizes used to keep the resume on one page (template defaults are 11 / 13.5).
SIZES = {"name": 15, "contact": 9.5, "head": 11.5, "body": 10, "job": 10, "meta": 9.5, "bullet": 10, "edu": 10}


# (space_before, space_after) in points, to keep the page count down.
SPACING = {"name": (0, 0), "contact": (0, 2), "head": (6, 2), "body": (0, 2), "job": (4, 0),
           "meta": (0, 1), "bullet": (0, 1), "edu": (0, 1)}


def set_text(par, text, bold=None, size=None):
    runs = par.runs
    runs[0].text = text
    if bold is not None:
        runs[0].bold = bold
    if size:
        runs[0].font.size = docx.shared.Pt(size)
    for r in runs[1:]:
        r._element.getparent().remove(r._element)


def add_hyperlink(par, text, url, size):
    """Append a real, absolute hyperlink run so the PDF link opens the web page."""
    r_id = par.part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = docx.oxml.OxmlElement("w:hyperlink")
    link.set(docx.oxml.ns.qn("r:id"), r_id)
    run = docx.oxml.OxmlElement("w:r")
    rpr = docx.oxml.OxmlElement("w:rPr")
    color = docx.oxml.OxmlElement("w:color")
    color.set(docx.oxml.ns.qn("w:val"), "0563C1")
    underline = docx.oxml.OxmlElement("w:u")
    underline.set(docx.oxml.ns.qn("w:val"), "single")
    sz = docx.oxml.OxmlElement("w:sz")
    sz.set(docx.oxml.ns.qn("w:val"), str(int(size * 2)))
    for e in (color, underline, sz):
        rpr.append(e)
    run.append(rpr)
    t = docx.oxml.OxmlElement("w:t")
    t.text = text
    run.append(t)
    link.append(run)
    par._p.append(link)


def main(spec_path, out_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    d = docx.Document(str(TEMPLATE))
    ps = d.paragraphs
    proto = {
        "name": ps[0], "contact": ps[1], "head": ps[2], "body": ps[3], "job": ps[7],
        "meta": ps[8], "bullet": ps[9], "edu": ps[17],
    }
    proto = {k: copy.deepcopy(v._element) for k, v in proto.items()}
    body = d.element.body
    for p in list(d.paragraphs):
        body.remove(p._element)
    sect = body.find(docx.oxml.ns.qn("w:sectPr"))

    def add(kind, text, bold=None, link=None):
        el = copy.deepcopy(proto[kind])
        sect.addprevious(el)
        par = docx.text.paragraph.Paragraph(el, d._body)
        set_text(par, text, bold, SIZES[kind])
        before, after = SPACING[kind]
        par.paragraph_format.space_before = docx.shared.Pt(before)
        par.paragraph_format.space_after = docx.shared.Pt(after)
        if link:
            add_hyperlink(par, link[0], link[1], SIZES[kind])

    L = {"summary": "SUMMARY", "skills": "SKILLS", "experience": "WORK EXPERIENCE", "education": "EDUCATION",
         "certifications": "CERTIFICATIONS (IN PROGRESS)", **spec.get("labels", {})}
    contact = "  |  ".join(s for s in spec["contact"].split("  |  ") if "linkedin.com" not in s)
    add("name", spec["name"])
    add("contact", contact + ("  |  " if LINKEDIN_URL else ""), link=(LINKEDIN_LABEL, LINKEDIN_URL) if LINKEDIN_URL else None)
    add("head", L["summary"])
    add("body", spec["summary"])
    add("head", L["skills"])
    add("body", spec["skills"])
    add("head", L["experience"])
    for job in spec["experience"]:
        add("job", f"{job['title']} | {job['company']}")
        add("meta", job["meta"])
        for b in job["bullets"]:
            add("bullet", b)
    add("head", L["education"])
    for e in spec["education"]:
        add("edu", e)
    if spec.get("certifications"):
        add("head", L["certifications"])
        for c in spec["certifications"]:
            add("edu", c)
    d.save(out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
