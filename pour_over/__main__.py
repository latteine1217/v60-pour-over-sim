"""
pour_over 套件入口點。

使用方式：
    uv run python -m pour_over
"""

from .params import V60Params, PourProtocol
from .core import simulate_brew, print_summary
from .viz import (
    plot_results, plot_tds,
    compare_tds_grind, compare_corrections,
    compare_grind_sizes, compare_thermal, compare_flavor,
)
from .fitting import demo_fitting
from .analysis import sensitivity_analysis, compare_grind_linkage, find_optimal_grind


def main() -> None:
    protocol = PourProtocol.standard_v60()

    # ── 1. 標準模擬（含 TDS）────────────────────────────────────────────────
    print("=== 標準 V60 手沖模擬 ===")
    params  = V60Params()
    results = simulate_brew(params, protocol, t_end=500)
    print_summary(results, label="中研磨，93°C")
    plot_results(results, title="V60 Standard Brew — Medium Grind, 93°C",
                 save_as="v60_simulation.png")
    plot_tds(results)

    # ── 2. TDS 研磨度對比 ────────────────────────────────────────────────────
    print("\n=== TDS / EY 研磨度比較 ===")
    compare_tds_grind(protocol)

    # ── 3. 修正項逐一對比 ─────────────────────────────────────────────────────
    print("\n=== 物理修正對比 ===")
    compare_corrections(protocol)

    # ── 4. 研磨度流體比較 ─────────────────────────────────────────────────────
    print("\n=== 研磨度流體比較 ===")
    compare_grind_sizes(protocol)

    # ── 5. 熱力學耦合 ─────────────────────────────────────────────────────────
    print("\n=== 熱力學耦合：水溫對比 ===")
    compare_thermal(protocol)

    # ── 6. 風味組分對比 ───────────────────────────────────────────────────────
    print("\n=== 多組分萃取：風味平衡 vs 水溫 ===")
    compare_flavor(protocol)

    # ── 7. 參數擬合示範 ───────────────────────────────────────────────────────
    demo_fitting(protocol)

    # ── 8. 靈敏度分析 ─────────────────────────────────────────────────────────
    print("\n=== 靈敏度分析 ===")
    sensitivity_analysis(protocol)

    # ── 9. k–M 聯動對比 ───────────────────────────────────────────────────────
    print("\n=== k–M 聯動：研磨度-萃取耦合比較 ===")
    compare_grind_linkage(protocol)

    # ── 10. 最佳研磨度搜尋 ───────────────────────────────────────────────────
    print("\n=== 最佳研磨度搜尋（SCA 黃金杯目標）===")
    find_optimal_grind(protocol)


if __name__ == "__main__":
    main()
