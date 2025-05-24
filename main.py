# ---------- IMPORTS & LOGGING ----------
import os, logging, pathlib, httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel     # ← necesario para NotifyPayload

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# usa /tmp, siempre existe en Render
LOG_DIR  = pathlib.Path("/tmp")
LOG_FILE = LOG_DIR / "gpt_backend.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ---------- FASTAPI APP ----------
app = FastAPI()        # ←  ¡debe ir antes de los decoradores!

# ---------- HEALTH ENDPOINT ----------
@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- /notify ENDPOINT ----------
NOTIFY_SECRET = os.getenv("NOTIFY_SECRET")   # define en Render
SLACK_URL     = os.getenv("SLACK_URL")       # define en Render


class NotifyPayload(BaseModel):
    subject: str
    text: str


@app.post("/notify")
async def send_notify(payload: NotifyPayload, request: Request):
    # token simple en cabecera
    if request.headers.get("X-Notify-Token") != NOTIFY_SECRET:
        raise HTTPException(401, "Invalid token")

    if not SLACK_URL:
        raise HTTPException(500, "SLACK_URL not set")

    data = {"text": f"*{payload.subject}*\n{payload.text}"}

    async with httpx.AsyncClient() as client:
        r = await client.post(SLACK_URL, json=data, timeout=5)

    if r.status_code != 200:
        logger.error(f"Slack error {r.status_code}: {r.text}")
        raise HTTPException(r.status_code, r.text)

    logger.info(f"Notification sent: {payload.subject}")
    return {"status": "sent"}
