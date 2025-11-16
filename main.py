import os
from datetime import datetime, timezone, date
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import User, JournalEntry, Mantra, OracleConsult, MeditationSession, Lesson, Payment

app = FastAPI(title="WonderLens Chronicles API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"name": "WonderLens Chronicles API", "status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    return response


# -----------------------------
# Users & Onboarding
# -----------------------------

class UpsertUserRequest(BaseModel):
    display_name: str
    email: str
    auth_provider: Optional[str] = "anonymous"
    auth_uid: Optional[str] = None
    stage: Optional[str] = "Awakening"
    locale: Optional[str] = "en"


@app.post("/api/users/upsert")
def upsert_user(payload: UpsertUserRequest):
    if db is None:
        raise HTTPException(500, "Database not configured")

    # Try to find by email
    existing = db.user.find_one({"email": payload.email})
    data = User(
        display_name=payload.display_name,
        email=payload.email,
        auth_provider=payload.auth_provider or "anonymous",
        auth_uid=payload.auth_uid,
        stage=payload.stage or "Awakening",
        locale=payload.locale or "en",
    ).model_dump()

    if existing:
        db.user.update_one({"_id": existing["_id"]}, {"$set": {**data, "updated_at": datetime.now(timezone.utc)}})
        user_id = str(existing["_id"])
    else:
        user_id = create_document("user", data)

    return {"user_id": user_id, "stage": data["stage"]}


class StageUpdateRequest(BaseModel):
    user_id: str
    stage: str


@app.post("/api/users/stage")
def update_stage(req: StageUpdateRequest):
    if db is None:
        raise HTTPException(500, "Database not configured")
    from bson import ObjectId
    try:
        db.user.update_one({"_id": ObjectId(req.user_id)}, {"$set": {"stage": req.stage, "updated_at": datetime.now(timezone.utc)}})
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, f"Invalid user or stage: {e}")


# -----------------------------
# Daily Mantra Generator (AI or fallback)
# -----------------------------

class MantraRequest(BaseModel):
    user_id: str
    user_mood: Optional[str] = None
    user_stage: Optional[str] = None
    recent_journal_theme: Optional[str] = None


@app.post("/api/mantra/generate")
def generate_mantra(req: MantraRequest):
    openai_key = os.getenv("OPENAI_API_KEY")

    base_prompt = (
        "Create a daily mantra in an African spiritual tone. "
        "Inputs: mood={mood}, stage={stage}, theme={theme}. "
        "Output: Short mantra (1–2 lines) then a brief meaning."
    ).format(mood=req.user_mood or "", stage=req.user_stage or "", theme=req.recent_journal_theme or "")

    text = None
    meaning = None

    if openai_key:
        try:
            import requests
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            body = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a wise African mystic blending Yoruba, Kikuyu and Kemetian wisdom in gentle, empowering language."},
                    {"role": "user", "content": base_prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 120
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=20)
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]["content"].strip()
            # Simple split: mantra on first line, meaning on second
            parts = [p.strip("- •\n ") for p in msg.split("\n") if p.strip()]
            if len(parts) >= 2:
                text, meaning = parts[0], " ".join(parts[1:])
            else:
                text = msg
                meaning = "A reminder of your inner divinity and alignment with Ashe."
        except Exception:
            text = "I am Divine Flow. Ashe."
            meaning = "Return to breath and remember: your path is guided by ancestors and inner light."
    else:
        # Fallback without external API
        mood = req.user_mood or "centered"
        stage = req.user_stage or "Awakening"
        theme = req.recent_journal_theme or "clarity"
        text = f"I walk in {theme}, breathing {mood}, embodying {stage}. Ashe."
        meaning = "Let this guide your day with grounded presence and ancestral support."

    today = date.today().isoformat()
    doc = Mantra(user_id=req.user_id, text=text, meaning=meaning, stage=req.user_stage, mood=req.user_mood, journal_theme=req.recent_journal_theme, date=today)
    mantra_id = create_document("mantra", doc)
    return {"id": mantra_id, "date": today, "text": text, "meaning": meaning}


# -----------------------------
# Journal
# -----------------------------

@app.post("/api/journal")
def create_journal(entry: JournalEntry):
    entry_id = create_document("journalentry", entry)
    return {"id": entry_id}


@app.get("/api/journal/{user_id}")
def list_journal(user_id: str):
    items = get_documents("journalentry", {"user_id": user_id}, limit=50)
    for it in items:
        it["_id"] = str(it["_id"])
    return items


# -----------------------------
# Oracle (AI or fallback)
# -----------------------------

@app.post("/api/oracle")
def oracle(consult: OracleConsult):
    openai_key = os.getenv("OPENAI_API_KEY")
    interpretation = None
    refs: List[str] = []

    if openai_key:
        try:
            import requests
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            prompt = (
                "Interpret this using African spiritual wisdom (Yoruba, Kikuyu, Kemet). "
                "Explain metaphysical cause and lesson. Input:\n" + consult.prompt
            )
            body = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are The Lens Oracle, compassionate, culturally rooted, clear."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 300
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=20)
            resp.raise_for_status()
            interpretation = resp.json()["choices"][0]["message"]["content"].strip()
            refs = ["Wikipedia: Orishas", "Wikidata: Kemet symbols"]
        except Exception:
            interpretation = "Your dream reflects a call to balance. Honor breath, pour libation (water), and affirm your worth."
            refs = ["Proverb: A river that forgets its source will dry up."]
    else:
        interpretation = "This symbol speaks of alignment. Practice heart-centered breath and offer gratitude to ancestors."
        refs = ["Ashe (vital force)", "Ngai (divine source)"]

    doc = OracleConsult(user_id=consult.user_id, prompt=consult.prompt, interpretation=interpretation, references=refs)
    consult_id = create_document("oracleconsult", doc)
    return {"id": consult_id, "interpretation": interpretation, "references": refs}


# -----------------------------
# Meditation
# -----------------------------

@app.post("/api/meditation/start")
def start_meditation(sess: MeditationSession):
    sess.started_at = datetime.now(timezone.utc)
    sess_id = create_document("meditationsession", sess)
    return {"id": sess_id, "started_at": sess.started_at}


# -----------------------------
# Lessons (static seed)
# -----------------------------

LESSONS: List[Lesson] = [
    Lesson(slug="law-of-vibration", title="Understanding the Law of Vibration", body="Everything is energy; align your frequency.", badge="Initiate"),
    Lesson(slug="energy-centers", title="African Energy Centers Explained", body="From crown to root, breathe Ashe through each center.", badge="Seer"),
    Lesson(slug="inner-child-ancestral", title="Healing the Inner Child through Ancestral Wisdom", body="Reparent with gentleness, honor lineage.", badge="Sage"),
]


@app.get("/api/lessons")
def get_lessons():
    return [l.model_dump() for l in LESSONS]


# -----------------------------
# Payments (stubs)
# -----------------------------

class PaymentIntentRequest(BaseModel):
    user_id: str
    provider: str  # stripe | mpesa | paypal
    amount_cents: int
    currency: str = "USD"


@app.post("/api/payments/intent")
def create_payment_intent(req: PaymentIntentRequest):
    # In a real integration, call Stripe/M-Pesa/PayPal SDKs here.
    payment = Payment(user_id=req.user_id, provider=req.provider, amount_cents=req.amount_cents, currency=req.currency, status="pending", reference=f"SIM-{int(datetime.now().timestamp())}")
    pid = create_document("payment", payment)
    return {"id": pid, "reference": payment.reference, "status": payment.status}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
