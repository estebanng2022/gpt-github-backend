# --- logging & health check ---
import logging, os, httpx
from fastapi import HTTPException, Request
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    filename="/mnt/data/gpt_backend.log",
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

@app.get("/health")
def health():
    return {"status": "ok"}

# --- /notify ---
NOTIFY_SECRET = os.getenv("NOTIFY_SECRET")   # define en Render
SLACK_URL     = os.getenv("SLACK_URL")       # define en Render

class NotifyPayload(BaseModel):
    subject: str
    text: str

@app.post("/notify")
async def send_notify(payload: NotifyPayload, request: Request):
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
