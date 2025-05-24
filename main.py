from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import httpx

app = FastAPI()
security = HTTPBearer()

# ---------- MODELOS ----------
class TreeRequest(BaseModel):
    username: str
    repo: str
    branch: str

class AnalyzeRequest(BaseModel):
    dirs: List[str]
# --------------------------------


# ========= ENDPOINT /github/tree =========
@app.post("/github/tree", response_model=List[str])
async def get_repo_tree(
    data: TreeRequest,
    prefix: str = "lib/",               # solo carpetas dentro de lib/
    depth: Optional[int] = None,        # None = sin límite
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 1. Obtener SHA del branch
    branch_url = (
        f"https://api.github.com/repos/{data.username}/{data.repo}"
        f"/branches/{data.branch}"
    )
    async with httpx.AsyncClient() as client:
        branch_resp = await client.get(branch_url, headers=headers)
    if branch_resp.status_code != 200:
        raise HTTPException(
            status_code=branch_resp.status_code,
            detail=f"Error getting branch SHA: {branch_resp.text}",
        )
    sha = branch_resp.json()["commit"]["sha"]

    # 2. Obtener árbol completo
    tree_url = (
        f"https://api.github.com/repos/{data.username}/{data.repo}"
        f"/git/trees/{sha}?recursive=1"
    )
    async with httpx.AsyncClient() as client:
        tree_resp = await client.get(tree_url, headers=headers)
    if tree_resp.status_code != 200:
        raise HTTPException(
            status_code=tree_resp.status_code,
            detail=tree_resp.text,
        )

    tree = tree_resp.json().get("tree", [])

    # 3. Filtrar por prefix y depth
    dirs: List[str] = []
    base_depth = prefix.count("/")
    for item in tree:
        if item.get("type") != "tree":
            continue
        path = item["path"]
        if not path.startswith(prefix):
            continue
        if depth is not None and path.count("/") > base_depth + depth:
            continue
        dirs.append(path)

    return dirs
# ========== FIN /github/tree ==========


# ============ ENDPOINT /analyze ============
@app.post("/analyze")
def analyze_structure(req: AnalyzeRequest):
    issues = []

    # 1. theme/enums mal nombrada
    if "lib/core/theme/enums" in req.dirs:
        issues.append({
            "path": "lib/core/theme/enums",
            "recommendation": "Renombrar a lib/core/theme/models o lib/core/theme/tokens."
        })

    # 2. .../screens/sections redundante
    for d in req.dirs:
        if d.endswith("/presentation/screens/sections"):
            issues.append({
                "path": d,
                "recommendation": "Mover secciones a presentation/widgets o eliminarlas."
            })

    # 3. shared/widgets/helpers mal ubicado
    if "lib/shared/widgets/helpers" in req.dirs:
        issues.append({
            "path": "lib/shared/widgets/helpers",
            "recommendation": "Mover a lib/shared/utils."
        })

    # 4. tests duplicados
    for d in req.dirs:
        if "/test/features/auth/onboarding/screens" in d:
            issues.append({
                "path": d,
                "recommendation": "Unificar jerarquía de tests; eliminar duplicados."
            })

    return {"count": len(issues), "issues": issues}
# ============ FIN /analyze ============
