"""Services for preparing and populating migration workspaces."""

from __future__ import annotations

from dataclasses import dataclass
import shutil
from pathlib import Path
from zipfile import ZipFile

from git import Repo


@dataclass(slots=True)
class IngestionResult:
    """Workspace paths and metadata created during ingestion."""

    input_dir: Path
    artifacts_dir: Path
    output_dir: Path
    metadata: dict[str, str]


class IngestionService:
    """Creates and fills a predictable directory layout for a migration job."""

    def ingest_source(
        self,
        *,
        job_id: str,
        workspace_dir: str,
        source_type: str,
        source_url: str,
        branch: str | None = None,
    ) -> IngestionResult:
        """Prepare workspace directories and populate the input directory."""
        job_root = Path(workspace_dir) / job_id
        input_dir = job_root / "input"
        artifacts_dir = job_root / "artifacts"
        output_dir = job_root / "output"

        if job_root.exists():
            shutil.rmtree(job_root)

        input_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "job_root": str(job_root),
            "source_type": source_type,
            "source_url": source_url,
        }
        if branch:
            metadata["branch"] = branch
        metadata["resolved_source_path"] = self._populate_input_dir(
            source_type=source_type,
            source_url=source_url,
            input_dir=input_dir,
            branch=branch,
        )

        return IngestionResult(
            input_dir=input_dir,
            artifacts_dir=artifacts_dir,
            output_dir=output_dir,
            metadata=metadata,
        )

    def _populate_input_dir(
        self,
        *,
        source_type: str,
        source_url: str,
        input_dir: Path,
        branch: str | None,
    ) -> str:
        """Populate the input directory based on the provided source type."""
        if source_type == "github":
            clone_kwargs = {"to_path": str(input_dir)}
            if branch:
                clone_kwargs["branch"] = branch
                clone_kwargs["single_branch"] = True
            Repo.clone_from(source_url, **clone_kwargs)
            return str(input_dir)

        if source_type == "upload":
            archive_path = Path(source_url)
            with ZipFile(archive_path, "r") as archive:
                archive.extractall(input_dir)
            return str(archive_path.resolve())

        if source_type == "folder":
            source_path = Path(source_url)
            if not source_path.exists():
                raise FileNotFoundError(f"Source folder does not exist: {source_url}")
            self._copy_directory_contents(source_path, input_dir)
            return str(source_path.resolve())

        raise ValueError(f"Unsupported source_type: {source_type}")

    def _copy_directory_contents(self, source_dir: Path, destination_dir: Path) -> None:
        """Copy a source directory into an existing destination directory."""
        for item in source_dir.iterdir():
            destination = destination_dir / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(item, destination)
