"""Узлы мультиагентного графа: critic, human review."""

from agents.critic import run_critic
from agents.human_review import prompt_approve_program, prompt_reject_action

__all__ = ["prompt_approve_program", "prompt_reject_action", "run_critic"]
