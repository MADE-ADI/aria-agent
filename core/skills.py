"""
Skill loader — discovers and registers skills from multiple directories.
Loads built-in skills (shipped with source) and user skills (~/.aria/skills/).
User skills override built-in skills with the same name.
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
    source: str = "builtin"  # "builtin" or "user"

    def matches(self, text: str) -> bool:
        text_lower = text.lower()
        return any(t.lower() in text_lower for t in self.triggers)


class SkillRegistry:
    """Registry that discovers and manages skills from multiple directories."""

    def __init__(self, user_skills_dir: str, builtin_skills_dir: str | None = None):
        self.user_skills_dir = user_skills_dir
        self.builtin_skills_dir = builtin_skills_dir
        self.skills: dict[str, Skill] = {}
        self._discover()

    def _load_from_dir(self, skills_dir: str, source: str):
        """Load skills from a directory."""
        if not os.path.isdir(skills_dir):
            os.makedirs(skills_dir, exist_ok=True)
            return

        for name in sorted(os.listdir(skills_dir)):
            skill_path = os.path.join(skills_dir, name)
            if not os.path.isdir(skill_path):
                continue
            meta_file = os.path.join(skill_path, "skill.json")
            main_file = os.path.join(skill_path, "main.py")

            if not os.path.exists(meta_file) or not os.path.exists(main_file):
                logger.debug(f"Skipping incomplete skill: {name} (in {source})")
                continue

            try:
                with open(meta_file) as f:
                    meta = json.load(f)

                spec = importlib.util.spec_from_file_location(
                    f"skill_{source}_{name}", main_file
                )
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
                    source=source,
                )
                self.skills[name] = skill
                logger.info(f"Loaded skill: {name} ({source})")

            except Exception as e:
                logger.error(f"Failed to load skill '{name}' from {source}: {e}")

    def _discover(self):
        """Load built-in skills first, then user skills (user overrides builtin)."""
        if self.builtin_skills_dir:
            self._load_from_dir(self.builtin_skills_dir, "builtin")
        self._load_from_dir(self.user_skills_dir, "user")

    def find(self, text: str) -> list[Skill]:
        """Find skills matching the input text."""
        return [s for s in self.skills.values() if s.matches(text)]

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def list_all(self) -> list[dict]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "triggers": s.triggers,
                "source": s.source,
            }
            for s in self.skills.values()
        ]
