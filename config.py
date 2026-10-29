"""
配置模块 - 对应知识点: Model-Agnostic 设计 + 成本控制

多 Agent 系统特别注意成本控制（每个角色可配不同模型）：
- 规划/审查用强模型 → 需要深度推理
- 编码用平衡模型 → 量大但不需要最深度推理
"""

import os


def get_model_config():
    return {
        "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "planner_model": os.environ.get("PLANNER_MODEL", "claude-sonnet-4-20250514"),
        "coder_model": os.environ.get("CODER_MODEL", "claude-sonnet-4-20250514"),
        "reviewer_model": os.environ.get("REVIEWER_MODEL", "claude-opus-4-20250514"),
        "max_tokens": int(os.environ.get("TEAM_MAX_TOKENS", "4096")),
        "base_url": os.environ.get("ANTHROPIC_BASE_URL"),
        "global_max_turns": int(os.environ.get("TEAM_MAX_TURNS", "12")),
    }


def validate_config(config):
    if not config["api_key"]:
        raise ValueError("请设置 ANTHROPIC_API_KEY 环境变量")
    return True


def is_online(config):
    """是否启用真实 LLM（没配 key 则走离线模拟）"""
    return bool(config["api_key"])
