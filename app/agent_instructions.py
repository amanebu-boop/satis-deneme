"""Load the central agent router and enforce each agent's Markdown task policy."""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROUTER_PATH = PROJECT_ROOT / "AGENTS.md"
AGENT_FILES = {
    "company": "agents/company.md",
    "product": "agents/product.md",
    "meeting": "agents/meeting.md",
    "quotation": "agents/quotation.md",
    "warehouse": "agents/warehouse.md",
    "sales": "agents/sales.md",
    "reporting": "agents/reporting.md",
    "audit": "agents/audit.md",
}


def load_agent_instructions(agent_id: str, task_type: str) -> dict[str, str]:
    """Read router first, then the agent's own file; reject tasks outside its policy."""
    relative_path = AGENT_FILES.get(agent_id)
    if relative_path is None:
        raise ValueError("unknown agent instruction profile")

    try:
        router_text = ROUTER_PATH.read_text(encoding="utf-8")
        own_path = PROJECT_ROOT / relative_path
        own_text = own_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("agent instruction file is missing or unreadable") from exc

    route = f"]({relative_path})"
    if route not in router_text:
        raise ValueError("agent router does not route to the expected instruction file")

    identity = re.search(r"(?m)^agent_id:\\s*([a-z_]+)\\s*$", own_text)
    if identity is None:
        identity = re.search(r"(?m)^\\s*`agent_id:\\s*([a-z_]+)`\\s*$", own_text)
    if identity is None or identity.group(1) != agent_id:
        raise ValueError("agent instruction identity does not match the executing agent")

    section = re.search(
        r"(?ms)^##\s+Çalıştırılabilir görevler\s*\n(.*?)(?=^##\s+|\Z)",
        own_text,
    )
    if section is None:
        raise ValueError("agent instruction file has no executable-task section")
    allowed_tasks = set(re.findall(r"(?m)^\s*-\s*`([a-z0-9_]+)`\s*$", section.group(1)))
    if task_type not in allowed_tasks:
        raise ValueError("task is not permitted by this agent's instruction file")

    return {
        "router": str(ROUTER_PATH),
        "agent_file": str(own_path),
        "agent_id": agent_id,
        "task_type": task_type,
    }
