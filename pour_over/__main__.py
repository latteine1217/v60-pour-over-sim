"""
pour_over 套件入口點。

使用方式：
    uv run python -m pour_over

預設輸出（4 張圖）：
    v60_simulation.png  — 流體診斷（水位/流量/體積/旁路/k衰減/飽和度）
    v60_tds.png         — 萃取品質（床濃度/出口濃度/TDS/EY）
    v60_grind.png       — 三種研磨度綜合對比（流體 + 萃取）
    v60_thermal.png     — 三種水溫熱力學對比

其他可呼叫函式（非預設）：
    compare_corrections()    # 各物理修正影響量級
    compare_flavor()         # Fast/Slow 風味組分詳細分析
    sensitivity_analysis()   # 龍捲風敏感度 + 2D 熱圖
    compare_grind_linkage()  # k–M 聯動機制圖
    find_optimal_grind()     # SCA 黃金杯最佳研磨度搜尋
    demo_fitting()           # 參數擬合示範
"""

from .params import V60Params, PourProtocol
from .core import simulate_brew, print_summary
from .viz import plot_results, plot_tds, compare_grind, compare_thermal
from .analysis import find_optimal_grind


def main() -> None:
    protocol = PourProtocol.standard_v60()

    # ── 1. 標準模擬：流體診斷 + 萃取品質 ─────────────────────────────────────
    print("=== 標準 V60 手沖模擬 ===")
    params  = V60Params()
    results = simulate_brew(params, protocol, t_end=500)
    print_summary(results, label="中研磨，93°C")
    plot_results(results, title="V60 Standard Brew — Medium Grind, 93°C",
                 save_as="v60_simulation.png")
    plot_tds(results)

    # ── 2. 研磨度綜合對比（流體 + 萃取）──────────────────────────────────────
    print("\n=== 研磨度綜合對比 ===")
    compare_grind(protocol)

    # ── 3. 熱力學耦合：水溫對比 ──────────────────────────────────────────────
    print("\n=== 熱力學耦合：水溫對比 ===")
    compare_thermal(protocol)

    # ── 4. 最佳研磨度搜尋 ────────────────────────────────────────────────────
    print("\n=== 最佳研磨度搜尋（SCA 黃金杯目標）===")
    find_optimal_grind(protocol)


if __name__ == "__main__":
    main()
