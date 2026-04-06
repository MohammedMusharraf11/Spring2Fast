"""Migration API endpoints."""
import json
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.schemas import (
    GitHubMigrateRequest,
    MigrationJobResponse,
    MigrationStatusResponse,
)
from app.models.db_models import MigrationJob, JobStatus
from app.services.migration_orchestrator import MigrationOrchestrator

router = APIRouter()


@router.post("/github", response_model=MigrationJobResponse)
async def migrate_from_github(
    request: GitHubMigrateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a migration job from a GitHub repository URL.
    """
    job_id = str(uuid.uuid4())

    job = MigrationJob(
        id=job_id,
        source_type="github",
        source_url=str(request.github_url),
        branch=request.branch,
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()

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
    db: AsyncSession = Depends(get_db),
):
    """
    Start a migration job from an uploaded ZIP file.
    """
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

    job = MigrationJob(
        id=job_id,
        source_type="upload",
        source_url=str(archive_path),
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()

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
async def get_migration_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the current status of a migration job."""
    job = await db.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return MigrationStatusResponse(
        job_id=job.id,
        status=job.status.value,
        current_step=job.current_step,
        progress_pct=job.progress_pct,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get("/{job_id}/state")
async def get_full_job_state(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the full migration state including metadata, artifacts, logs, etc.
    Reads the persisted state JSON from the workspace directory.
    """
    job = await db.get(MigrationJob, job_id)
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
        "job_id": job.id,
        "source_type": job.source_type,
        "source_url": job.source_url,
        "branch": job.branch,
        "status": job.status.value,
        "current_step": job.current_step,
        "progress_pct": job.progress_pct,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "output_path": job.output_path,
        # State data from the persisted graph state
        "logs": state_data.get("logs", []),
        "discovered_technologies": state_data.get("discovered_technologies", []),
        "business_rules": state_data.get("business_rules", []),
        "generated_files": state_data.get("generated_files", []),
        "validation_errors": state_data.get("validation_errors", []),
        "analysis_artifacts": state_data.get("analysis_artifacts", {}),
        "metadata": state_data.get("metadata", {}),
        # Subgraph conversion results
        "component_inventory": state_data.get("component_inventory", {}),
        "completed_conversions": state_data.get("completed_conversions", []),
        "failed_conversions": state_data.get("failed_conversions", []),
        "conversion_queue": state_data.get("conversion_queue", []),
    }


@router.get("/{job_id}/result")
async def get_migration_result(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download the migrated FastAPI project as a ZIP file."""
    job = await db.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed yet. Current status: {job.status.value}",
        )

    output_zip = job.output_path
    if not output_zip:
        raise HTTPException(status_code=500, detail="Output file not found")

    return FileResponse(
        path=output_zip,
        media_type="application/zip",
        filename=f"fastapi_project_{job_id[:8]}.zip",
    )


@router.get("/{job_id}/artifact/{filename}")
async def get_artifact(
    job_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific artifact file content."""
    job = await db.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    artifact_path = Path(settings.workspace_path) / job_id / "artifacts" / filename

    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact {filename} not found")

    try:
        content = artifact_path.read_text(encoding='utf-8')
        return {"content": content, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read artifact: {str(e)}")


@router.get("/{job_id}/artifacts")
async def list_artifacts(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all artifact files for a job."""
    job = await db.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    artifacts_dir = Path(settings.workspace_path) / job_id / "artifacts"

    if not artifacts_dir.exists():
        return {"artifacts": []}

    artifacts = []
    for f in sorted(artifacts_dir.iterdir()):
        if f.is_file() and not f.name.startswith("_"):
            artifacts.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "extension": f.suffix,
            })

    return {"artifacts": artifacts}


@router.get("/{job_id}/source-tree")
async def get_source_tree(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the file tree of the ingested (cloned) source project."""
    job = await db.get(MigrationJob, job_id)
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
                rel_path = str(entry.relative_to(base)).replace("\\", "/")
                # Skip hidden files/dirs like .git
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    children = build_tree(entry, base, max_depth, depth + 1)
                    items.append({
                        "name": entry.name,
                        "path": rel_path,
                        "type": "directory",
                        "children": children,
                    })
                else:
                    items.append({
                        "name": entry.name,
                        "path": rel_path,
                        "type": "file",
                        "size": entry.stat().st_size,
                        "extension": entry.suffix,
                    })
        except PermissionError:
            pass
        return items

    tree = build_tree(input_dir, input_dir)

    def count_files(nodes):
        total = 0
        for node in nodes:
            if node["type"] == "file":
                total += 1
            else:
                total += count_files(node.get("children", []))
        return total

    return {"tree": tree, "total_files": count_files(tree)}


@router.get("/{job_id}/source-file")
async def get_source_file(
    job_id: str,
    path: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the content of a source file from the ingested project."""
    job = await db.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    input_dir = Path(settings.workspace_path) / job_id / "input"
    file_path = input_dir / path

    # Security: ensure the path doesn't escape the input directory
    try:
        file_path.resolve().relative_to(input_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        content = file_path.read_text(encoding='utf-8')
        return {
            "content": content,
            "path": path,
            "filename": file_path.name,
            "extension": file_path.suffix,
            "size": file_path.stat().st_size,
        }
    except UnicodeDecodeError:
        return {
            "content": "[Binary file - cannot display]",
            "path": path,
            "filename": file_path.name,
            "extension": file_path.suffix,
            "size": file_path.stat().st_size,
            "binary": True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.get("/{job_id}/output-tree")
async def get_output_tree(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the file tree of the generated output project."""
    job = await db.get(MigrationJob, job_id)
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
                rel_path = str(entry.relative_to(base)).replace("\\", "/")
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    children = build_tree(entry, base, max_depth, depth + 1)
                    items.append({
                        "name": entry.name,
                        "path": rel_path,
                        "type": "directory",
                        "children": children,
                    })
                else:
                    items.append({
                        "name": entry.name,
                        "path": rel_path,
                        "type": "file",
                        "size": entry.stat().st_size,
                        "extension": entry.suffix,
                    })
        except PermissionError:
            pass
        return items

    tree = build_tree(output_dir, output_dir)

    def count_files(nodes):
        total = 0
        for node in nodes:
            if node["type"] == "file":
                total += 1
            else:
                total += count_files(node.get("children", []))
        return total

    return {"tree": tree, "total_files": count_files(tree)}


@router.get("/{job_id}/output-file")
async def get_output_file(
    job_id: str,
    path: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the content of a generated output file."""
    job = await db.get(MigrationJob, job_id)
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
        content = file_path.read_text(encoding='utf-8')
        return {
            "content": content,
            "path": path,
            "filename": file_path.name,
            "extension": file_path.suffix,
            "size": file_path.stat().st_size,
        }
    except UnicodeDecodeError:
        return {
            "content": "[Binary file - cannot display]",
            "path": path,
            "filename": file_path.name,
            "extension": file_path.suffix,
            "size": file_path.stat().st_size,
            "binary": True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.get("/jobs/list")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
):
    """List all migration jobs, ordered by creation date descending."""
    from sqlalchemy import select

    result = await db.execute(
        select(MigrationJob).order_by(MigrationJob.created_at.desc()).limit(50)
    )
    jobs = result.scalars().all()

    return {
        "jobs": [
            {
                "job_id": job.id,
                "source_type": job.source_type,
                "source_url": job.source_url,
                "branch": job.branch,
                "status": job.status.value,
                "current_step": job.current_step,
                "progress_pct": job.progress_pct,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
            for job in jobs
        ]
    }
