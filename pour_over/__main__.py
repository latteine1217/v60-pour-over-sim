"""
pour_over 套件入口點。

使用方式：
    uv run python -m pour_over
    uv run python -m pour_over benchmark

預設輸出（5 張圖）：
    v60_simulation.png  — 流體診斷（水位/流量/體積/旁路/k衰減/飽和度）
    v60_tds.png         — 萃取品質（床濃度/出口濃度/TDS/EY）
    v60_grind.png       — 三種研磨度綜合對比（流體 + 萃取）
    v60_thermal.png     — 三種水溫熱力學對比
    data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png
                        — 實測流動擬合展示圖（含 wetbed χ 校準）

CLI 子命令：
    benchmark           — 依序執行 formal fit、benchmark suite、identifiability
"""

import argparse

from .params import V60Params, PourProtocol
from .core import simulate_brew, print_summary
from .viz import plot_results, plot_tds, compare_grind, compare_thermal
from .analysis import find_optimal_grind
from .benchmark import run_benchmark_suite
from .identifiability import analyze_fit_identifiability
from .fitting import fit_measured_benchmark, generate_measured_flow_fit_artifacts


def run_showcase() -> None:
    """
    執行原本的展示型主流程。

    Why:
        保持 `uv run python -m pour_over` 的既有行為不變，
        避免新增 CLI 子命令後破壞既有使用者工作流。
    """
    protocol = PourProtocol.standard_v60()

    # ── 1. 標準模擬：流體診斷 + 萃取品質 ─────────────────────────────────────
    print("=== 標準 V60 手沖模擬 ===")
    params = V60Params()
    results = simulate_brew(params, protocol, t_end=500)
    print_summary(results, label="中研磨，93°C")
    plot_results(
        results,
        title="V60 Standard Brew — Medium Grind, 93°C",
        save_as="v60_simulation.png",
    )
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

    # ── 5. 量測流動擬合展示產物 ──────────────────────────────────────────────
    print("\n=== 量測流動擬合（含 wetbed χ 校準）===")
    generate_measured_flow_fit_artifacts(verbose=True)


def run_benchmark_command(
    *,
    ident_n_eval: int = 700,
    verbose: bool = True,
) -> None:
    """
    一次執行 measured benchmark 的正式校準、benchmark suite 與可識別性分析。

    What:
        1. `fit_measured_benchmark()`：更新 calibrated summary / plot
        2. `run_benchmark_suite()`：檢查 regression gates
        3. `analyze_fit_identifiability()`：輸出局部 loss slices 與 heatmap

    Why:
        讓使用者只需一個 CLI 子命令，就能完成
        「校準 → 回歸檢查 → 可識別性檢查」。
    """
    print("=== Measured Benchmark Fit ===")
    fit_measured_benchmark(verbose=verbose)

    print("\n=== Regression Gates ===")
    run_benchmark_suite(refit=False, verbose=verbose)

    print("\n=== Local Identifiability ===")
    analyze_fit_identifiability(refit=False, verbose=verbose, n_eval=ident_n_eval)


def build_parser() -> argparse.ArgumentParser:
    """
    建立 CLI parser。

    Why:
        子命令應明確表達 intent，而不是把所有流程都塞進無參數主入口。
    """
    parser = argparse.ArgumentParser(
        prog="python -m pour_over",
        description="V60 手沖物理模擬與量測 benchmark 工具。",
    )
    subparsers = parser.add_subparsers(dest="command")

    bench = subparsers.add_parser(
        "benchmark",
        help="依序執行 formal fit、benchmark suite 與 identifiability 分析。",
    )
    bench.add_argument(
        "--ident-n-eval",
        type=int,
        default=700,
        help="identifiability 分析的 ODE 評估點數，越大越慢。",
    )
    bench.add_argument(
        "--quiet",
        action="store_true",
        help="減少 fitting / benchmark 過程輸出。",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """
    CLI 入口。

    What:
        無子命令 → 跑既有 showcase 流程。
        `benchmark` → 跑 measured benchmark 全套檢查。
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "benchmark":
        run_benchmark_command(
            ident_n_eval=int(args.ident_n_eval),
            verbose=not bool(args.quiet),
        )
        return

    run_showcase()


if __name__ == "__main__":
    main()
