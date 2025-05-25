import os
import logging
import pathlib
import httpx

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional

# ---------- LOGGING ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = pathlib.Path("/tmp")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "gpt_backend.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ---------- FASTAPI APP ----------
BACKEND_URL = os.getenv("BACKEND_URL", "https://gpt-github-backend.onrender.com")
app = FastAPI(
    title="GPT GitHub Backend",
    version="1.0.0",
    servers=[{"url": BACKEND_URL}],
)
security = HTTPBearer()

# ---------- ENV VARIABLES ----------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SLACK_URL = os.getenv("SLACK_URL")

# ---------- HEALTH ENDPOINT ----------
@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- NOTIFY ENDPOINT ----------
class NotifyPayload(BaseModel):
    subject: str
    text: str

@app.post("/notify")
async def send_notify(
    payload: NotifyPayload,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials.credentials != GITHUB_TOKEN:
        raise HTTPException(401, "Invalid master token")
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

@app.post(
    "/github/tree",
    summary="Get Repo Tree",
    response_model=List[str],
)
async def get_repo_tree(
    data: TreeRequest,
    prefix: str = "lib/",
    depth: Optional[int] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials.credentials != GITHUB_TOKEN:
        raise HTTPException(401, "Invalid master token")

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = (
        f"https://api.github.com/repos/{data.username}/{data.repo}"
        f"/git/trees/{data.branch}?recursive=1"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        logger.error(f"GitHub error {resp.status_code}: {resp.text}")
        raise HTTPException(resp.status_code, resp.text)

    raw_tree = resp.json().get("tree", [])
    logger.info(f"Fetched raw tree: {len(raw_tree)} items")

    base_depth = prefix.count("/")
    dirs: List[str] = []
    for item in raw_tree:
        if item.get("type") != "tree":
            continue
        path = item["path"]
        if not path.startswith(prefix):
            continue
        if depth is not None and path.count("/") > base_depth + depth:
            continue
        dirs.append(path)

    logger.info(f"Returning {len(dirs)} directories under '{prefix}'")
    return dirs

# ---------- /github/file ENDPOINT ----------
class WriteFileRequest(BaseModel):
    username: str
    repo: str
    branch: str
    path: str
    content_base64: str
    message: str

@app.post("/github/file", summary="Create or update a file on GitHub")
async def write_file(
    req: WriteFileRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials.credentials != GITHUB_TOKEN:
        raise HTTPException(401, "Invalid master token")

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    gh_url = (
        f"https://api.github.com/repos/{req.username}/{req.repo}"
        f"/contents/{req.path}"
    )

    # 1) Intentar obtener el SHA actual (si existe)
    sha: Optional[str] = None
    async with httpx.AsyncClient() as client:
        get_resp = await client.get(gh_url, headers=headers, timeout=5)
    if get_resp.status_code == 200:
        sha = get_resp.json().get("sha")

    # 2) Preparar payload incluyendo el sha si lo había
    payload = {
        "message": req.message,
        "content": req.content_base64,
        "branch": req.branch,
    }
    if sha:
        payload["sha"] = sha

    # 3) Hacer el PUT definitivo
    async with httpx.AsyncClient() as client:
        resp = await client.put(gh_url, headers=headers, json=payload, timeout=10)

    if resp.status_code not in (200, 201):
        logger.error(f"GitHub file write error {resp.status_code}: {resp.text}")
        raise HTTPException(resp.status_code, resp.text)

    logger.info(f"File '{req.path}' written to {req.repo}@{req.branch}")
    return {"status": "ok", "url": resp.json().get("content", {}).get("html_url")}

# ---------- /github/content ENDPOINT ----------
class ContentRequest(BaseModel):
    username: str
    repo: str
    branch: str
    path: str

class ContentResponse(BaseModel):
    sha: str
    content_base64: Optional[str] = None

@app.post(
    "/github/content",
    summary="Get file content and SHA",
    response_model=ContentResponse,
)
async def get_file_content(
    req: ContentRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials.credentials != GITHUB_TOKEN:
        raise HTTPException(401, "Invalid master token")

    gh_url = f"https://api.github.com/repos/{req.username}/{req.repo}/contents/{req.path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(gh_url, headers=headers, timeout=10)

    if resp.status_code == 404:
        raise HTTPException(404, "File not found")
    if resp.status_code != 200:
        logger.error(f"GitHub content error {resp.status_code}: {resp.text}")
        raise HTTPException(resp.status_code, resp.text)

    body = resp.json()
    return ContentResponse(
        sha=body["sha"],
        content_base64=body.get("content"),
    )
