"""
CLI 入口 - 对应知识点: Agent-as-a-Service（程序化调用多 Agent 系统）

用法:
  离线模拟（无需 API Key）:
    python main.py "实现一个用户注册功能"
  在线（需 ANTHROPIC_API_KEY）:
    set ANTHROPIC_API_KEY=your-key
    python main.py "实现一个用户注册功能"
"""

import argparse
import sys
from config import get_model_config, is_online
from orchestrator import TeamOrchestrator


def main():
    parser = argparse.ArgumentParser(description="多 Agent 软件开发团队")
    parser.add_argument("feature", help="功能需求描述")
    parser.add_argument("-t", "--max-turns", type=int, default=12, help="全局最大轮次")
    args = parser.parse_args()

    config = get_model_config()
    config["global_max_turns"] = args.max_turns

    mode = "在线 (真实 Claude)" if is_online(config) else "离线 (模拟响应)"
    print(f"运行模式: {mode}")
    print(f"全局轮次上限: {config['global_max_turns']}")

    team = TeamOrchestrator(config)
    result = team.execute(args.feature)

    sys.exit(0 if result["status"] == "done" else 1)


if __name__ == "__main__":
    main()
