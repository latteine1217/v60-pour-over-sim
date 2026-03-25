"""
v60_sim.py — 向後相容 thin wrapper。

此檔案已重構為 pour_over/ 套件，本檔案僅做 re-export 以維持舊有 import 路徑。
新程式碼請直接使用：

    from pour_over import V60Params, RoastProfile, PourProtocol
    from pour_over import simulate_brew, find_optimal_grind, ...

    # 或整包執行：
    uv run python -m pour_over
"""

# re-export 全部公開 API
from pour_over import *                          # noqa: F401, F403
from pour_over import (                          # noqa: F401
    RHO, G, H_MIN, R_GAS,
    RoastProfile, V60Params, PourProtocol,
    simulate_brew, print_summary,
    plot_results, plot_tds,
    compare_tds_grind, compare_corrections,
    compare_grind_sizes, compare_thermal, compare_flavor,
    fit_brew_params, demo_fitting,
    sensitivity_analysis, compare_grind_linkage, find_optimal_grind,
)

if __name__ == "__main__":
    from pour_over.__main__ import main
    main()
