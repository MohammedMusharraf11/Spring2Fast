"""Scheduler converter agent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class SchedulerConverterAgent(BaseConverterAgent):
    def _get_component_type(self) -> str:
        return "scheduled_task"

    def _get_output_path(self, component: dict[str, Any]) -> str:
        return "app/scheduler.py"

    def _get_prompt_template_path(self) -> Path:
        return PROMPTS_DIR / "synthesize_scheduler.md"

    def _build_llm_prompt(
        self,
        *,
        java_source: str,
        contract: str,
        existing_code: dict[str, str],
        discovered_technologies: list[str],
        docs_context: str,
        component: dict[str, Any],
    ) -> str:
        template_path = self._get_prompt_template_path()
        if template_path.exists():
            template = template_path.read_text(encoding="utf-8")
        else:
            template = (
                "Convert scheduled tasks to APScheduler jobs.\n\n"
                "### JAVA SOURCE\n{java_source}\n\n"
                "### CONTRACT\n{contract_md}\n\n"
                "### EXISTING SERVICES\n{existing_services}\n\n"
                "### DOCS CONTEXT\n{docs_context}\n\n"
                "### DETECTED TECHNOLOGIES\n{tech_text}\n"
            )

        return template.replace(
            "{java_source}", java_source
        ).replace(
            "{contract_md}", contract
        ).replace(
            "{existing_services}", existing_code.get("services", "# No existing services")
        ).replace(
            "{docs_context}", docs_context or "No documentation context."
        ).replace(
            "{tech_text}", ", ".join(discovered_technologies) or "None"
        )

    def _deterministic_convert(
        self,
        *,
        component: dict[str, Any],
        java_ir: dict[str, Any],
        java_source: str,
    ) -> str | None:
        tasks = component.get("tasks") or []
        lines = [
            '"""Application scheduler migrated from @Scheduled tasks."""',
            "",
            "from __future__ import annotations",
            "",
            "from apscheduler.schedulers.asyncio import AsyncIOScheduler",
            "from apscheduler.triggers.cron import CronTrigger",
            "",
            "scheduler = AsyncIOScheduler()",
            "",
        ]

        for task in tasks:
            for method in task.get("method_details") or []:
                scheduled_annotation = next(
                    (ann for ann in method.get("raw_annotations", []) if "@Scheduled" in ann),
                    "",
                )
                func_name = self._to_snake(str(method.get("name", "scheduled_job")))
                trigger_line = self._build_trigger(scheduled_annotation)
                lines.extend(
                    [
                        f"@scheduler.scheduled_job({trigger_line})",
                        f"async def {func_name}() -> None:",
                        f'    """Migrated from {task.get("class_name", "ScheduledTask")}.{method.get("name", func_name)}."""',
                        "    # TODO: wire the migrated service call here",
                        "    return None",
                        "",
                    ]
                )
        return "\n".join(lines).strip() + "\n"

    def _build_trigger(self, annotation: str) -> str:
        fixed_rate = re.search(r"fixedRate\s*=\s*(\d+)", annotation)
        fixed_delay = re.search(r"fixedDelay\s*=\s*(\d+)", annotation)
        cron = re.search(r'cron\s*=\s*"([^"]+)"', annotation)
        if cron:
            cron_expr = cron.group(1).strip()
            parts = cron_expr.split()
            if len(parts) == 6:
                cron_expr = " ".join(parts[1:])
            return f'CronTrigger.from_crontab("{cron_expr}")'
        if fixed_rate:
            seconds = max(int(fixed_rate.group(1)) // 1000, 1)
            return f'"interval", seconds={seconds}'
        if fixed_delay:
            seconds = max(int(fixed_delay.group(1)) // 1000, 1)
            return f'"interval", seconds={seconds}'
        return '"interval", minutes=5'


scheduler_converter_agent = SchedulerConverterAgent()
