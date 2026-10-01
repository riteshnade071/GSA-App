"""
Maharashtra state schemes — read from the official MahaDBT scheme pages (mahadbt.maharashtra.gov.in) on 30 Sep 2026.
Run:  python seed_maharashtra.py      (safe to re-run; matches by name, only fills blanks on existing rows)

Inserted as NEEDS_REVIEW with no last_verified date on purpose — re-check on the portal, then press "Verify" in admin.
OBC and EBC(Art) come from the official scheme pages; the Girls-fee and VJNT entries come from DTE Maharashtra / MahaDBT snippets and have partial document lists. See QUEUE at the bottom for the rest.
"""
from app.database import SessionLocal, Base, engine
from app.models.core import Opportunity
from sqlalchemy import text, inspect

PORTAL = "https://mahadbt2.maharashtra.gov.in/"   # AY 2026-27 fresh + renewal applications: MahaDBT 2.0 only (official notice)

COMMON_STEPS = [
    "Open the MahaDBT 2.0 portal (mahadbt2.maharashtra.gov.in). For AY 2026-27, fresh and renewal applications are accepted only here, not on the old MahaDBT 1.0 site.",
    "Click 'New Applicant Registration'. Register with your Aadhaar number: choose OTP (if your mobile is linked to Aadhaar) or Biometric. Your name, address and bank details are auto-filled from UIDAI.",
    "Create a username and password, verify your mobile number with an OTP (email is optional but useful for updates), then log in.",
    "Complete your profile fully: personal, caste, income, domicile, address, parents/guardian, current course, past qualification, and hostel or day-scholar details. Keep the certificate numbers/barcodes handy.",
    "Go to 'All Schemes', pick the scheme below and apply. If you qualify for more than one scheme, apply to each and set your scheme preference — the money is paid under only one.",
    "Upload the required documents (list on this card) and submit the form. Save your Application ID.",
    "Your application is scrutinised first by your college/institute and then by the department. Track it under 'My Applied Scheme'.",
    "If it is 'sent back', read the reason, fix the profile or documents, and press 'Re-apply'.",
    "Your bank account must be seeded with Aadhaar or the money won't arrive. If it isn't, the portal suggests opening an India Post Payments Bank account, which can be done at a post office with Aadhaar and mobile number.",
]

COMMON_STEPS_HI = [
    "MahaDBT 2.0 पोर्टल (mahadbt2.maharashtra.gov.in) खोलें। शैक्षणिक वर्ष 2026-27 के नए और नवीनीकरण (renewal) आवेदन सिर्फ यहीं स्वीकार होते हैं, पुरानी MahaDBT 1.0 साइट पर नहीं।",
    "'New Applicant Registration' पर क्लिक करें और आधार नंबर से रजिस्टर करें: OTP (अगर मोबाइल आधार से लिंक है) या Biometric चुनें। आपका नाम, पता और बैंक विवरण UIDAI से अपने आप भर जाएंगे।",
    "यूज़रनेम और पासवर्ड बनाएं, मोबाइल नंबर OTP से सत्यापित करें (ईमेल वैकल्पिक है), फिर लॉगिन करें।",
    "अपनी प्रोफ़ाइल पूरी भरें: व्यक्तिगत, जाति, आय, अधिवास (domicile), पता, माता-पिता/अभिभावक, वर्तमान कोर्स, पिछली योग्यता, और हॉस्टल या डे-स्कॉलर की जानकारी। प्रमाण पत्रों के नंबर पास रखें।",
    "'All Schemes' में जाकर इस कार्ड वाली योजना चुनें और आवेदन करें। अगर आप एक से ज़्यादा योजनाओं के पात्र हैं, तो सभी में आवेदन करें और अपनी प्राथमिकता (preference) तय करें — पैसा सिर्फ एक योजना के तहत मिलता है।",
    "ज़रूरी दस्तावेज़ अपलोड करें (सूची इसी कार्ड में है) और फॉर्म सबमिट करें। Application ID सेव कर लें।",
    "आपके आवेदन की जाँच पहले आपके कॉलेज/संस्थान में और फिर विभाग में होती है। 'My Applied Scheme' में स्थिति देखें।",
    "अगर आवेदन 'sent back' हो जाए, तो कारण पढ़ें, प्रोफ़ाइल या दस्तावेज़ ठीक करें और 'Re-apply' दबाएं।",
    "आपका बैंक खाता आधार से सीडेड होना चाहिए, वरना पैसा नहीं आएगा। अगर नहीं है, तो पोर्टल India Post Payments Bank खाता खुलवाने का सुझाव देता है, जो आधार और मोबाइल नंबर के साथ पोस्ट ऑफिस में खुल जाता है।",
]

SCHEMES = [
    dict(
        name="Post Matric Scholarship to OBC Students (Maharashtra)",
        state="Maharashtra",
        description=("State scheme of the VJNT, OBC and SBC Welfare Department for OBC students in approved post-matric courses. "
                     "Parent/guardian annual income up to ₹2.5 lakh. Only 2 boys per parents are eligible (any number of girls). "
                     "75% attendance is mandatory. Professional courses must be entered through the CAP round. "
                     "NOTE: the MahaDBT scheme page states the ₹2.5 lakh limit, but some third-party sites quote ₹1.5 lakh with a non-creamy-layer certificate — confirm on the portal before applying."),
        benefits=("Tuition fee + exam fee + monthly maintenance allowance (hosteller ₹150–425/month, day scholar ₹90–190/month depending on course group). "
                  "100% benefit for girls (GR of 8 July 2024). In private unaided/non-government institutes tuition and exam fees are 50%."),
        source_organization="VJNT, OBC and SBC Welfare Department, Govt of Maharashtra (MahaDBT)",
        required_documents=["Caste certificate (issued by Govt of Maharashtra)", "Income certificate / declaration",
                            "Caste validity certificate (mandatory for professional degree & PG courses)",
                            "HSC/SSC or last exam marksheet", "Gap certificate (only if there is a gap)",
                            "Father/guardian death certificate (if applicable)", "Ration card (to show number of children)",
                            "Leaving certificate", "Parents' declaration about number of children"],
        eligibility_rules={"category": {"eq": "obc"}, "family_income": {"lte": 250000}},
    ),
    dict(
        name="Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulkh Shishyavrutti (EBC) — Directorate of Art courses",
        state="Maharashtra",
        description=("Fee-reimbursement scheme for economically weaker students of open (general) category who took admission to "
                     "professional courses under the Directorate of Art. Family income up to ₹8 lakh. Only the first two children are eligible. "
                     "Not for distance, virtual or part-time courses. You must not receive any other scholarship or stipend. "
                     "The same scheme name also runs under other departments (Higher Education, Technical Education, Medical, Agriculture) for their courses — check which applies to your course."),
        benefits=("Girls: 100% tuition fee for professional courses (and non-professional up to ₹8 lakh) plus 100% exam fee. "
                  "Boys: 50–100% depending on income (up to ₹2.5 lakh vs ₹2.5–8 lakh), type of college and course. See the official scheme page for the full table."),
        source_organization="Directorate of Art, Govt of Maharashtra (MahaDBT)",
        required_documents=["Domicile certificate", "Previous year annual income certificate", "CAP-related documents",
                            "Gap-related document (if any gap)", "Family declaration about two children",
                            "Attendance certificate", "Previous year marksheet"],
        eligibility_rules={"category": {"eq": "general"}, "family_income": {"lte": 800000}},
    ),
    dict(
        name="Rajarshi Chhatrapati Shahu Maharaj Tuition Fee Scheme for Girls (100% tuition + exam fee)",
        state="Maharashtra", 
        description=("Fee-reimbursement scheme for economically weaker students (EBC / EWS / SEBC) of Maharashtra. Family income up to ₹8 lakh. "
                     "Since AY 2024-25 girls get 100% of tuition and exam fee. Runs under several departments (Technical, Higher, Medical Education, Agriculture, Art) — "
                     "apply under the department of your course. The document list below is partial; the portal may ask for more."),
        benefits="100% tuition fee + 100% exam fee for girls. Paid in two instalments to your Aadhaar-linked bank account (per DTE Maharashtra).",
        source_organization="Directorate of Technical Education & other departments, Govt of Maharashtra (MahaDBT)",
        required_documents=["Domicile certificate", "Income certificate (previous financial year)", "Previous year marksheet"],
        eligibility_rules={"gender": {"eq": "female"}, "category": {"in": ["general", "ews", "sebc"]}, "family_income": {"lte": 800000}},
    ),
    dict(
        name="Post Matric Scholarship to VJNT Students (Maharashtra)",
        state="Maharashtra",
        description=("State scheme of the VJNT, OBC and SBC Welfare Department for Vimukta Jati & Nomadic Tribes students in approved post-matric courses, "
                     "Class 11 up to PhD. Parent/guardian annual income up to ₹1.5 lakh. Must be a resident of Maharashtra. "
                     "The document list below is partial; see the official scheme page for the full list."),
        benefits="Tuition fee + exam fee + monthly maintenance allowance (hosteller up to ₹425/month for Course Group A; other groups and day-scholar rates are lower — see the scheme page).",
        source_organization="VJNT, OBC and SBC Welfare Department, Govt of Maharashtra (MahaDBT)",
        required_documents=["VJNT caste certificate (issued in Maharashtra)", "Income certificate (issued by competent authority)"],
        eligibility_rules={"category": {"eq": "vjnt"}, "family_income": {"lte": 150000}},
    ),
]

# Official MahaDBT schemes seen on the portal's scheme list but NOT yet read/verified — research these next:
QUEUE = [
    "Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulkh Shishyavrutti (EBC) — DHE / DTE / DMER / Agriculture versions",
    "Post Matric Scholarship to SBC Students (income limit not confirmed)",
    "Tuition Fees and Examination Fees to OBC / SBC / VJNT Students",
    "Dr. Panjabrao Deshmukh Vasatigruh Nirvah Bhatta Yojna (hostel maintenance; DHE/DTE/DOA/AGR/MAFSU)",
    "Tuition Fee & Exam Fee for Tribal Students (Freeship)", "Eklavya Scholarship", "State Government Open Merit Scholarship",
    "State Minority Scholarship Part II (DHE) and the DTE/DMER/MCAER minority schemes",
    "Post-Matric Scholarship for persons with disability", "Rajarshi Chhatrapati Shahu Maharaj Merit Scholarship (VJNT/SBC 11th-12th)",
]

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    for _col in ("application_steps", "application_steps_hi"):
        if _col not in [c["name"] for c in inspect(engine).get_columns("opportunities")]:
            with engine.begin() as c:
                c.execute(text(f"ALTER TABLE opportunities ADD COLUMN {_col} JSON"))
    db = SessionLocal()
    for s in SCHEMES:
        steps = COMMON_STEPS
        row = db.query(Opportunity).filter(Opportunity.name == s["name"]).first()
        if row:
            if not row.application_steps: row.application_steps = steps
            if not row.application_steps_hi: row.application_steps_hi = COMMON_STEPS_HI
            if not row.required_documents: row.required_documents = s["required_documents"]
            print("updated ", s["name"])
        else:
            db.add(Opportunity(category="scholarship", country="IN", deadline=None, official_url=PORTAL,
                               application_steps=steps, application_steps_hi=COMMON_STEPS_HI, verification_status="NEEDS_REVIEW", **s))
            print("inserted", s["name"])
    db.commit(); db.close()
