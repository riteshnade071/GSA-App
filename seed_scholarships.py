"""
Run from the project root:  python seed_scholarships.py
Safe to re-run: matches by name. New ones are inserted; existing ones only get
application_steps / required_documents filled in if they are empty (your admin edits are never overwritten).

Everything is inserted as NEEDS_REVIEW with no last_verified date on purpose —
check each one on the official portal, then press "Verify" in the admin panel.
"""
from datetime import datetime
from app.database import SessionLocal, Base, engine
from app.models.core import Opportunity
from sqlalchemy import text, inspect

NSP = "https://scholarships.gov.in"
DEADLINE = datetime(2026, 10, 31)
DOCS = ["Caste certificate", "Income certificate (current financial year)",
        "Aadhaar card (linked to bank account)", "Bank passbook"]


def nsp_steps(scheme_name):
    return [
        "Go to scholarships.gov.in and open the Students section. Keep your Aadhaar and mobile number ready.",
        "Do One Time Registration (OTR) first — it uses Aadhaar and face authentication through the NSP OTR app. "
        "You get a 14-digit OTR number that works for your whole academic career. Note it down.",
        "Log in with your OTR number and password, then choose 'Apply for Scholarship'.",
        f"From the list of schemes, select '{scheme_name}'. Choose the scheme that matches your category.",
        "Fill in personal, course, institute and bank details. The bank account must be your own and Aadhaar-linked.",
        "Upload scanned documents: " + ", ".join(DOCS) + ".",
        "Submit the form and save your Application ID. Your application then goes to your school/college for verification.",
        "Track the status by logging in on NSP. If it is marked 'defective', correct it with 'Fill/Edit Application Form' before the deadline.",
    ]


def nsp_steps_hi(scheme_name):
    return [
        "scholarships.gov.in पर जाकर Students सेक्शन खोलें। अपना आधार और मोबाइल नंबर पास रखें।",
        "सबसे पहले One Time Registration (OTR) करें — इसमें आधार और NSP OTR ऐप से चेहरे की पहचान (face authentication) होती है। आपको 14 अंकों का OTR नंबर मिलेगा जो पूरी पढ़ाई में काम आएगा। इसे लिखकर रख लें।",
        "OTR नंबर और पासवर्ड से लॉगिन करें, फिर 'Apply for Scholarship' चुनें।",
        f"योजनाओं की सूची में से '{scheme_name}' चुनें। अपनी कैटेगरी वाली योजना ही चुनें।",
        "व्यक्तिगत, कोर्स, संस्थान और बैंक की जानकारी भरें। बैंक खाता आपका अपना और आधार से लिंक होना चाहिए।",
        "दस्तावेज़ों की स्कैन कॉपी अपलोड करें: जाति प्रमाण पत्र, आय प्रमाण पत्र (चालू वित्त वर्ष), आधार कार्ड (बैंक से लिंक), बैंक पासबुक।",
        "फॉर्म सबमिट करें और Application ID सेव कर लें। इसके बाद आपका आवेदन आपके स्कूल/कॉलेज के पास सत्यापन के लिए जाता है।",
        "NSP पर लॉगिन करके स्थिति (status) देखते रहें। अगर 'defective' दिखे, तो अंतिम तारीख से पहले 'Fill/Edit Application Form' से सुधार करें।",
    ]


SCHOLARSHIPS = [
    dict(name="Post-Matric Scholarship for Scheduled Castes (PMS-SC)",
         description="Central scheme for SC students studying after Class 10.",
         benefits="Tuition/fee reimbursement plus monthly maintenance allowance, paid by DBT to your bank account.",
         source_organization="Ministry of Social Justice and Empowerment",
         eligibility_rules={"category": {"eq": "sc"}, "family_income": {"lte": 250000}}),
    dict(name="Post-Matric Scholarship for Scheduled Tribes (PMS-ST)",
         description="Central scheme for ST students studying after Class 10.",
         benefits="Tuition/fee reimbursement plus monthly maintenance allowance, paid by DBT to your bank account.",
         source_organization="Ministry of Tribal Affairs",
         eligibility_rules={"category": {"eq": "st"}, "family_income": {"lte": 250000}}),
    dict(name="Post-Matric Scholarship for OBC (PMS-OBC)",
         description="Central scheme for OBC students (non-creamy layer) studying after Class 10.",
         benefits="Maintenance allowance and fee support, paid by DBT to your bank account.",
         source_organization="Ministry of Social Justice and Empowerment",
         eligibility_rules={"category": {"eq": "obc"}, "family_income": {"lte": 150000}}),
]

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    for _col in ("application_steps", "application_steps_hi"):
        if _col not in [c["name"] for c in inspect(engine).get_columns("opportunities")]:
            with engine.begin() as c:
                c.execute(text(f"ALTER TABLE opportunities ADD COLUMN {_col} JSON"))

    db = SessionLocal()
    for s in SCHOLARSHIPS:
        steps = nsp_steps(s["name"])
        steps_hi = nsp_steps_hi(s["name"])
        row = db.query(Opportunity).filter(Opportunity.name == s["name"]).first()
        if row:
            if not row.application_steps: row.application_steps = steps
            if not row.application_steps_hi: row.application_steps_hi = steps_hi
            if not row.required_documents: row.required_documents = DOCS
            print("updated  ", s["name"])
        else:
            db.add(Opportunity(category="scholarship", country="IN", state=None, deadline=DEADLINE,
                               required_documents=DOCS, application_steps=steps, application_steps_hi=steps_hi, official_url=NSP,
                               verification_status="NEEDS_REVIEW", **s))
            print("inserted ", s["name"])
    db.commit()
    db.close()
