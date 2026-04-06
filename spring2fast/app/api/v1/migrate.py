"""Migration API endpoints — Supabase-backed."""

import asyncio
import json
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.models.schemas import (
    GitHubMigrateRequest,
    MigrationJobResponse,
    MigrationStatusResponse,
)
from app.supabase_client import get_supabase
from app.services.migration_orchestrator import MigrationOrchestrator

router = APIRouter()

TABLE = "migration_jobs"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_job(job_id: str) -> dict | None:
    """Fetch a job row from Supabase. Returns None if not found."""
    db = get_supabase()
    response = db.table(TABLE).select("*").eq("id", job_id).maybe_single().execute()
    return response.data  # None if not found


def _insert_job(job: dict) -> None:
    db = get_supabase()
    db.table(TABLE).insert(job).execute()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/github", response_model=MigrationJobResponse)
async def migrate_from_github(
    request: GitHubMigrateRequest,
    background_tasks: BackgroundTasks,
):
    """Start a migration job from a GitHub repository URL."""
    job_id = str(uuid.uuid4())

    await asyncio.get_event_loop().run_in_executor(None, _insert_job, {
        "id": job_id,
        "source_type": "github",
        "source_url": str(request.github_url),
        "branch": request.branch,
        "status": "pending",
        "progress_pct": 0,
    })

    orchestrator = MigrationOrchestrator()
    background_tasks.add_task(
        orchestrator.run_migration,
        job_id=job_id,
        source_type="github",
        source_url=str(request.github_url),
        branch=request.branch,
    )

    return MigrationJobResponse(
        job_id=job_id,
        status="pending",
        message=f"Migration job created. Cloning {request.github_url}...",
    )


@router.post("/upload", response_model=MigrationJobResponse)
async def migrate_from_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="ZIP file of Java Spring Boot project"),
):
    """Start a migration job from an uploaded ZIP file."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")

    job_id = str(uuid.uuid4())
    upload_dir = settings.workspace_path / "_uploads" / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    archive_path = upload_dir / file.filename

    async with aiofiles.open(archive_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            await buffer.write(chunk)
    await file.close()

    await asyncio.get_event_loop().run_in_executor(None, _insert_job, {
        "id": job_id,
        "source_type": "upload",
        "source_url": str(archive_path),
        "status": "pending",
        "progress_pct": 0,
    })

    orchestrator = MigrationOrchestrator()
    background_tasks.add_task(
        orchestrator.run_migration,
        job_id=job_id,
        source_type="upload",
        source_url=str(archive_path),
    )

    return MigrationJobResponse(
        job_id=job_id,
        status="pending",
        message=f"Migration job created from uploaded file: {file.filename}",
    )


@router.get("/{job_id}/status", response_model=MigrationStatusResponse)
async def get_migration_status(job_id: str):
    """Get the current status of a migration job."""
    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return MigrationStatusResponse(
        job_id=job["id"],
        status=job["status"],
        current_step=job.get("current_step"),
        progress_pct=job.get("progress_pct", 0),
        error_message=job.get("error_message"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
    )


@router.get("/{job_id}/state")
async def get_full_job_state(job_id: str):
    """Get full migration state including artifacts, logs, etc."""
    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    state_file = Path(settings.workspace_path) / job_id / "artifacts" / "_state.json"
    state_data = {}
    if state_file.exists():
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            state_data = {}

    return {
        "job_id": job["id"],
        "source_type": job.get("source_type"),
        "source_url": job.get("source_url"),
        "branch": job.get("branch"),
        "status": job["status"],
        "current_step": job.get("current_step"),
        "progress_pct": job.get("progress_pct", 0),
        "error_message": job.get("error_message"),
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
        "output_path": job.get("output_path"),
        "logs": state_data.get("logs", []),
        "discovered_technologies": state_data.get("discovered_technologies", []),
        "business_rules": state_data.get("business_rules", []),
        "generated_files": state_data.get("generated_files", []),
        "validation_errors": state_data.get("validation_errors", []),
        "analysis_artifacts": state_data.get("analysis_artifacts", {}),
        "metadata": state_data.get("metadata", {}),
        "component_inventory": state_data.get("component_inventory", {}),
        "completed_conversions": state_data.get("completed_conversions", []),
        "failed_conversions": state_data.get("failed_conversions", []),
        "conversion_queue": state_data.get("conversion_queue", []),
    }


@router.get("/{job_id}/result")
async def get_migration_result(job_id: str):
    """Download the migrated FastAPI project as a ZIP file."""
    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed yet. Current status: {job['status']}",
        )

    output_zip = job.get("output_path")
    if not output_zip:
        raise HTTPException(status_code=500, detail="Output file not found")

    return FileResponse(
        path=output_zip,
        media_type="application/zip",
        filename=f"fastapi_project_{job_id[:8]}.zip",
    )


@router.get("/{job_id}/artifact/{filename}")
async def get_artifact(job_id: str, filename: str):
    """Get a specific artifact file content."""
    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    artifact_path = Path(settings.workspace_path) / job_id / "artifacts" / filename
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact {filename} not found")

    try:
        return {"content": artifact_path.read_text(encoding="utf-8"), "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read artifact: {e}")


@router.get("/{job_id}/artifacts")
async def list_artifacts(job_id: str):
    """List all artifact files for a job."""
    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    artifacts_dir = Path(settings.workspace_path) / job_id / "artifacts"
    if not artifacts_dir.exists():
        return {"artifacts": []}

    return {
        "artifacts": [
            {"filename": f.name, "size": f.stat().st_size, "extension": f.suffix}
            for f in sorted(artifacts_dir.iterdir())
            if f.is_file() and not f.name.startswith("_")
        ]
    }


@router.get("/{job_id}/source-tree")
async def get_source_tree(job_id: str):
    """Get the file tree of the ingested source project."""
    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    input_dir = Path(settings.workspace_path) / job_id / "input"
    if not input_dir.exists():
        return {"tree": [], "total_files": 0}

    def build_tree(directory: Path, base: Path, max_depth: int = 5, depth: int = 0):
        items = []
        if depth > max_depth:
            return items
        try:
            for entry in sorted(directory.iterdir()):
                if entry.name.startswith("."):
                    continue
                rel_path = str(entry.relative_to(base)).replace("\\", "/")
                if entry.is_dir():
                    items.append({"name": entry.name, "path": rel_path, "type": "directory",
                                  "children": build_tree(entry, base, max_depth, depth + 1)})
                else:
                    items.append({"name": entry.name, "path": rel_path, "type": "file",
                                  "size": entry.stat().st_size, "extension": entry.suffix})
        except PermissionError:
            pass
        return items

    tree = build_tree(input_dir, input_dir)

    def count_files(nodes):
        return sum(1 if n["type"] == "file" else count_files(n.get("children", [])) for n in nodes)

    return {"tree": tree, "total_files": count_files(tree)}


@router.get("/{job_id}/source-file")
async def get_source_file(job_id: str, path: str):
    """Get the content of a source file from the ingested project."""
    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    input_dir = Path(settings.workspace_path) / job_id / "input"
    file_path = input_dir / path
    try:
        file_path.resolve().relative_to(input_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        return {"content": file_path.read_text(encoding="utf-8"), "path": path,
                "filename": file_path.name, "extension": file_path.suffix,
                "size": file_path.stat().st_size}
    except UnicodeDecodeError:
        return {"content": "[Binary file - cannot display]", "path": path,
                "filename": file_path.name, "extension": file_path.suffix,
                "size": file_path.stat().st_size, "binary": True}


@router.get("/{job_id}/output-tree")
async def get_output_tree(job_id: str):
    """Get the file tree of the generated output project."""
    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    output_dir = Path(settings.workspace_path) / job_id / "output"
    if not output_dir.exists():
        return {"tree": [], "total_files": 0}

    def build_tree(directory: Path, base: Path, max_depth: int = 5, depth: int = 0):
        items = []
        if depth > max_depth:
            return items
        try:
            for entry in sorted(directory.iterdir()):
                if entry.name.startswith("."):
                    continue
                rel_path = str(entry.relative_to(base)).replace("\\", "/")
                if entry.is_dir():
                    items.append({"name": entry.name, "path": rel_path, "type": "directory",
                                  "children": build_tree(entry, base, max_depth, depth + 1)})
                else:
                    items.append({"name": entry.name, "path": rel_path, "type": "file",
                                  "size": entry.stat().st_size, "extension": entry.suffix})
        except PermissionError:
            pass
        return items

    tree = build_tree(output_dir, output_dir)

    def count_files(nodes):
        return sum(1 if n["type"] == "file" else count_files(n.get("children", [])) for n in nodes)

    return {"tree": tree, "total_files": count_files(tree)}


@router.get("/{job_id}/output-file")
async def get_output_file(job_id: str, path: str):
    """Get the content of a generated output file."""
    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    output_dir = Path(settings.workspace_path) / job_id / "output"
    file_path = output_dir / path
    try:
        file_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        return {"content": file_path.read_text(encoding="utf-8"), "path": path,
                "filename": file_path.name, "extension": file_path.suffix,
                "size": file_path.stat().st_size}
    except UnicodeDecodeError:
        return {"content": "[Binary file - cannot display]", "path": path,
                "filename": file_path.name, "extension": file_path.suffix,
                "size": file_path.stat().st_size, "binary": True}


@router.get("/jobs/list")
async def list_jobs():
    """List all migration jobs, ordered by creation date descending."""
    db = get_supabase()
    response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: db.table(TABLE).select("*").order("created_at", desc=True).limit(50).execute()
    )
    jobs = response.data or []

    return {
        "jobs": [
            {
                "job_id": job["id"],
                "source_type": job.get("source_type"),
                "source_url": job.get("source_url"),
                "branch": job.get("branch"),
                "status": job["status"],
                "current_step": job.get("current_step"),
                "progress_pct": job.get("progress_pct", 0),
                "error_message": job.get("error_message"),
                "created_at": job.get("created_at"),
                "completed_at": job.get("completed_at"),
            }
            for job in jobs
        ]
    }


# ── GitHub Push ───────────────────────────────────────────────────────────────

from pydantic import BaseModel as _BaseModel  # noqa: E402


class GitHubPushRequest(_BaseModel):
    github_token: str | None = None    # Optional — falls back to GITHUB_PAT in .env
    repo_name: str | None = None       # Defaults to fastapi-{job_id[:8]}
    org: str | None = None             # Push to org; None = personal account
    private: bool = True


@router.post("/{job_id}/push-github")
async def push_to_github(job_id: str, request: GitHubPushRequest):
    """Create a new GitHub repo and push the generated FastAPI project to it."""
    import os
    import subprocess

    import httpx

    job = await asyncio.get_event_loop().run_in_executor(None, _get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job['status']})")

    output_dir = Path(settings.workspace_path) / job_id / "output"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")

    # Resolve token: request overrides .env
    token = (
        (request.github_token or "").strip()
        or settings.github_pat
        or settings.github_token
        or None
    )
    if not token:
        raise HTTPException(status_code=400, detail="No GitHub token provided. Set GITHUB_PAT in .env or pass github_token in request.")

    repo_name = request.repo_name or f"fastapi-{job_id[:8]}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # 1 — Create the GitHub repo
    create_url = (
        f"https://api.github.com/orgs/{request.org}/repos"
        if request.org else
        "https://api.github.com/user/repos"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(create_url, headers=headers, json={
            "name": repo_name,
            "description": f"Migrated from {job.get('source_url', 'Spring Boot')} by Spring2Fast",
            "private": request.private,
            "auto_init": False,
        })

    if resp.status_code not in (200, 201, 422):  # 422 = repo already exists
        raise HTTPException(
            status_code=502,
            detail=f"GitHub repo creation failed: {resp.status_code} — {resp.text[:300]}"
        )

    resp_json = resp.json()
    clone_url = resp_json.get("clone_url", f"https://github.com/{request.org or '?'}/{repo_name}.git")
    auth_url = clone_url.replace("https://", f"https://{token}@")

    # 2 — Init git and push (runs in executor to not block event loop)
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Spring2Fast",
        "GIT_AUTHOR_EMAIL": "bot@spring2fast.dev",
        "GIT_COMMITTER_NAME": "Spring2Fast",
        "GIT_COMMITTER_EMAIL": "bot@spring2fast.dev",
    }

    def _push() -> str:
        git_dir = output_dir / ".git"
        cmds: list[list[str]] = []
        if not git_dir.exists():
            cmds += [
                ["git", "init"],
                ["git", "add", "-A"],
                ["git", "commit", "-m", "feat: Initial Spring Boot -> FastAPI migration via Spring2Fast"],
                ["git", "branch", "-M", "main"],
                ["git", "remote", "add", "origin", auth_url],
            ]
        else:
            cmds += [
                ["git", "add", "-A"],
                ["git", "commit", "-m", "chore: update migration output"],
            ]
        cmds.append(["git", "push", "-u", "origin", "main", "--force"])

        for cmd in cmds:
            r = subprocess.run(cmd, cwd=str(output_dir), capture_output=True, text=True, env=git_env)
            if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
                return f"FAIL [{' '.join(cmd)}]: {r.stderr[:300]}"
        return "OK"

    push_result = await asyncio.get_event_loop().run_in_executor(None, _push)
    if push_result != "OK":
        raise HTTPException(status_code=500, detail=f"Git push failed: {push_result}")

    owner = request.org or resp_json.get("owner", {}).get("login", "<user>")
    repo_url = f"https://github.com/{owner}/{repo_name}"
    return {
        "repo_url": repo_url,
        "repo_name": repo_name,
        "message": f"Successfully pushed {job_id[:8]} -> {repo_url}",
    }
