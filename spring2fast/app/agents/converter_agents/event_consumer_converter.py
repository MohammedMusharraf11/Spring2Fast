"""Event consumer converter agent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class EventConsumerConverterAgent(BaseConverterAgent):
    def _get_component_type(self) -> str:
        return "event_consumer"

    def _get_output_path(self, component: dict[str, Any]) -> str:
        return f"app/consumers/{self._to_snake(str(component.get('class_name', 'consumer')))}_consumer.py"

    def _get_prompt_template_path(self) -> Path:
        return PROMPTS_DIR / "synthesize_event_consumer.md"

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
                "Convert event listeners into async consumers.\n\n"
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
        methods = component.get("method_details") or []
        consumer_kind = "kafka" if "@KafkaListener" in java_source else "rabbitmq"
        class_name = str(component.get("class_name", "Consumer"))
        lines = [
            f'"""Event consumer migrated from {class_name}."""',
            "",
            "from __future__ import annotations",
            "",
        ]
        if consumer_kind == "kafka":
            lines.extend(
                [
                    "import json",
                    "from aiokafka import AIOKafkaConsumer",
                    "from app.core.config import settings",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "import json",
                    "import aio_pika",
                    "from app.core.config import settings",
                    "",
                ]
            )

        for method in methods:
            raw_annotations = method.get("raw_annotations") or []
            listener = next((ann for ann in raw_annotations if "Listener" in ann), "")
            target = self._extract_value(listener, "topics" if consumer_kind == "kafka" else "queues") or "events"
            group_id = self._extract_value(listener, "groupId") or "default-group"
            handler_name = self._to_snake(str(method.get("name", "handle_event")))
            if consumer_kind == "kafka":
                lines.extend(
                    [
                        f"async def {handler_name}() -> None:",
                        "    consumer = AIOKafkaConsumer(",
                        f'        "{target}",',
                        "        bootstrap_servers=settings.kafka_bootstrap_servers,",
                        f'        group_id="{group_id}",',
                        "    )",
                        "    await consumer.start()",
                        "    try:",
                        "        async for message in consumer:",
                        "            data = json.loads(message.value)",
                        "            # TODO: wire the migrated service call here",
                        "            _ = data",
                        "    finally:",
                        "        await consumer.stop()",
                        "",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"async def {handler_name}() -> None:",
                        "    connection = await aio_pika.connect_robust(settings.rabbitmq_url)",
                        "    async with connection:",
                        "        channel = await connection.channel()",
                        f'        queue = await channel.declare_queue("{target}", durable=True)',
                        "        async for message in queue:",
                        "            async with message.process():",
                        "                data = json.loads(message.body)",
                        "                # TODO: wire the migrated service call here",
                        "                _ = data",
                        "",
                    ]
                )
        return "\n".join(lines).strip() + "\n"

    def _extract_value(self, annotation: str, key: str) -> str | None:
        match = re.search(rf'{key}\s*=\s*"([^"]+)"', annotation)
        if match:
            return match.group(1)
        match = re.search(r'"([^"]+)"', annotation)
        return match.group(1) if match else None


event_consumer_converter_agent = EventConsumerConverterAgent()
