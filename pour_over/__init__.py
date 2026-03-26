"""
pour_over — V60 手沖咖啡流體模擬套件

公開 API：
    from pour_over import V60Params, RoastProfile, PourProtocol
    from pour_over import simulate_brew, print_summary
    from pour_over import find_optimal_grind, fit_brew_params
"""

from .params import (
    RHO, G, H_MIN, R_GAS,
    RoastProfile,
    V60Params,
    PourProtocol,
)
from .core import simulate_brew, print_summary
from .viz import (
    plot_results,
    plot_tds,
    compare_grind,
    compare_tds_grind,
    compare_corrections,
    compare_grind_sizes,
    compare_thermal,
    compare_flavor,
)
from .fitting import fit_brew_params, demo_fitting
from .analysis import sensitivity_analysis, compare_grind_linkage, find_optimal_grind

__all__ = [
    # 常數
    "RHO", "G", "H_MIN", "R_GAS",
    # 參數類別
    "RoastProfile", "V60Params", "PourProtocol",
    # 模擬引擎
    "simulate_brew", "print_summary",
    # 視覺化
    "plot_results", "plot_tds",
    "compare_grind",
    "compare_tds_grind", "compare_corrections",
    "compare_grind_sizes", "compare_thermal", "compare_flavor",
    # 擬合
    "fit_brew_params", "demo_fitting",
    # 分析
    "sensitivity_analysis", "compare_grind_linkage", "find_optimal_grind",
]
