"""Load the central agent router and enforce each agent's Markdown task policy."""
from __future__ import annotations

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

    lines = own_text.splitlines()
    valid_identity_lines = {f"agent_id: {agent_id}", f"`agent_id: {agent_id}`"}
    if not any(line.strip() in valid_identity_lines for line in lines):
        raise ValueError("agent instruction identity does not match the executing agent")

    try:
        section_start = lines.index("## Çalıştırılabilir görevler") + 1
    except ValueError as exc:
        raise ValueError("agent instruction file has no executable-task section") from exc
    section_lines = []
    for line in lines[section_start:]:
        if line.startswith("## "):
            break
        section_lines.append(line.strip())
    allowed_tasks = {
        line[3:-1]
        for line in section_lines
        if line.startswith("- `") and line.endswith("`")
    }
    if task_type not in allowed_tasks:
        raise ValueError("task is not permitted by this agent's instruction file")


    return {
        "router": str(ROUTER_PATH),
        "agent_file": str(own_path),
        "agent_id": agent_id,
        "task_type": task_type,
        "router_text": router_text,
        "agent_text": own_text,
    }
