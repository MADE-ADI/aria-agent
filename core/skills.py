"""
Skill loader — discovers and registers skills from the skills/ directory.
Each skill is a folder with a SKILL.md (metadata) and a main.py (logic).
"""
import os
import json
import importlib.util
import logging
from dataclasses import dataclass, field
from typing import Callable, Any

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Represents a loaded skill."""
    name: str
    description: str
    triggers: list[str]
    parameters: dict[str, Any]
    execute: Callable
    examples: list[str] = field(default_factory=list)

    def matches(self, text: str) -> bool:
        text_lower = text.lower()
        return any(t.lower() in text_lower for t in self.triggers)


class SkillRegistry:
    """Registry that discovers and manages skills."""

    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self.skills: dict[str, Skill] = {}
        self._discover()

    def _discover(self):
        if not os.path.isdir(self.skills_dir):
            os.makedirs(self.skills_dir, exist_ok=True)
            return

        for name in sorted(os.listdir(self.skills_dir)):
            skill_path = os.path.join(self.skills_dir, name)
            if not os.path.isdir(skill_path):
                continue
            meta_file = os.path.join(skill_path, "skill.json")
            main_file = os.path.join(skill_path, "main.py")

            if not os.path.exists(meta_file) or not os.path.exists(main_file):
                logger.warning(f"Skipping incomplete skill: {name}")
                continue

            try:
                with open(meta_file) as f:
                    meta = json.load(f)

                spec = importlib.util.spec_from_file_location(f"skill_{name}", main_file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                if not hasattr(mod, "execute"):
                    logger.warning(f"Skill '{name}' missing execute() function")
                    continue

                skill = Skill(
                    name=meta.get("name", name),
                    description=meta.get("description", ""),
                    triggers=meta.get("triggers", []),
                    parameters=meta.get("parameters", {}),
                    execute=mod.execute,
                    examples=meta.get("examples", []),
                )
                self.skills[name] = skill
                logger.info(f"Loaded skill: {name}")

            except Exception as e:
                logger.error(f"Failed to load skill '{name}': {e}")

    def find(self, text: str) -> list[Skill]:
        """Find skills matching the input text."""
        return [s for s in self.skills.values() if s.matches(text)]

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def list_all(self) -> list[dict]:
        return [
            {"name": s.name, "description": s.description, "triggers": s.triggers}
            for s in self.skills.values()
        ]
