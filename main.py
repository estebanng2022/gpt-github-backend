import os
import logging
import pathlib
import base64
import httpx

from fastapi import FastAPI, HTTPException, Request, Body, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# ---------- LOGGING ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = pathlib.Path("/tmp")
LOG_FILE = LOG_DIR / "gpt_backend.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ---------- FASTAPI APP ----------
app = FastAPI()
security = HTTPBearer()

# ---------- HEALTH ENDPOINT ----------
@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- /notify ENDPOINT ----------
NOTIFY_SECRET = os.getenv("NOTIFY_SECRET")
SLACK_URL = os.getenv("SLACK_URL")

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

# ---------- /github/tree ENDPOINT ----------
class TreeRequest(BaseModel):
    username: str
    repo: str
    branch: str

@app.post("/github/tree")
async def get_repo_tree(request: TreeRequest):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(500, "GITHUB_TOKEN not set")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    url = f"https://api.github.com/repos/{request.username}/{request.repo}/git/trees/{request.branch}?recursive=1"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=10)

    if resp.status_code != 200:
        logger.error(f"GitHub error {resp.status_code}: {resp.text}")
        raise HTTPException(resp.status_code, resp.text)

    tree = resp.json()
    logger.info(f"Fetched tree for {request.username}/{request.repo}@{request.branch}")
    return tree
