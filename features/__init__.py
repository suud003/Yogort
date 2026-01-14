"""
功能模块
包含各种业务功能的实现
"""

from .generate_prd import (
    generate_prd,
    ai_self_check
)

from .optimize_prd import (
    optimize_prd_initial,
    developer_review,
    planner_fix,
    reflection_loop
)

from .report_assistant import render_report_assistant
from .weekly_report import render_weekly_report
from .whitepaper import render_whitepaper_assistant

__all__ = [
    # 生成策划案
    "generate_prd",
    "ai_self_check",
    # 优化策划案
    "optimize_prd_initial",
    "developer_review",
    "planner_fix",
    "reflection_loop",
    # 各功能模块渲染
    "render_report_assistant",
    "render_weekly_report",
    "render_whitepaper_assistant"
]
