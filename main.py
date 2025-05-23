from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List
import httpx

app = FastAPI()
security = HTTPBearer()

class TreeRequest(BaseModel):
    username: str
    repo: str
    branch: str

@app.post("/github/tree", response_model=List[str])
async def get_repo_tree(
    data: TreeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Paso 1: obtener el SHA del branch
    branch_url = f"https://api.github.com/repos/{data.username}/{data.repo}/branches/{data.branch}"
    async with httpx.AsyncClient() as client:
        branch_response = await client.get(branch_url, headers=headers)
    if branch_response.status_code != 200:
        raise HTTPException(status_code=branch_response.status_code, detail=f"Error getting branch SHA: {branch_response.text}")

    sha = branch_response.json()["commit"]["sha"]

    # Paso 2: obtener el árbol usando el SHA
    tree_url = f"https://api.github.com/repos/{data.username}/{data.repo}/git/trees/{sha}?recursive=1"
    async with httpx.AsyncClient() as client:
        tree_response = await client.get(tree_url, headers=headers)
    if tree_response.status_code != 200:
        raise HTTPException(status_code=tree_response.status_code, detail=tree_response.text)

    tree = tree_response.json().get("tree", [])
    dirs = [item["path"] for item in tree if item.get("type") == "tree"]
    return dirs
