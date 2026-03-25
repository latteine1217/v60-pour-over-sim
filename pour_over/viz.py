import numpy as np
import matplotlib.pyplot as plt

from .params import V60Params, PourProtocol, RoastProfile
from .core import simulate_brew, print_summary


def plot_results(
    results: dict,
    title: str = "V60 手沖模擬",
    save_as: str = "v60_simulation.png",
) -> None:
    """六格診斷圖：水位 / 流量 / 累積體積 / 旁路比 / k 衰減 / 飽和度"""
    t = results["t"]

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle(title, fontsize=13, fontweight="bold")

    # 1. Water Level
    ax = axes[0, 0]
    ax.plot(t, results["h_mm"], color="#1565C0", linewidth=2)
    ax.axhline(results["k_vals"][0] and 48, color="gray", lw=1, ls="--",
               label=f"h_bed = 48 mm")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Water Level [mm]")
    ax.set_title("Water Level  h(t)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # 2. Flow Decomposition
    ax = axes[0, 1]
    ax.stackplot(t, results["q_ext_mlps"], results["q_bp_mlps"],
                 labels=["Q_extract (Darcy)", "Q_bypass (Rib)"],
                 colors=["#1E88E5", "#FB8C00"], alpha=0.75)
    ax.plot(t, results["q_in_eff_mlps"], "g--", lw=1.5, label="Q_in_eff (net pour)")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Flow Rate [mL/s]")
    ax.set_title("Flow Rate Decomposition")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)

    # 3. Cumulative Volume
    ax = axes[0, 2]
    ax.plot(t, results["v_in_ml"],      color="#2E7D32", lw=2,   label="Total In (poured)")
    ax.plot(t, results["v_in_eff_ml"],  color="#81C784", lw=1.5, ls="--", label="Effective In")
    ax.plot(t, results["v_out_ml"],     color="#C62828", lw=2,   label="Total Out")
    ax.plot(t, results["v_extract_ml"], color="#1565C0", lw=1.5, ls="--", label="Extract Out")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Volume [mL]")
    ax.set_title("Cumulative Volume")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # 4. Bypass Ratio
    ax = axes[1, 0]
    bp = results["bypass_ratio"] * 100
    ax.fill_between(t, bp, alpha=0.35, color="#FB8C00")
    ax.plot(t, bp, color="#FB8C00", lw=1.5)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Bypass Ratio [%]")
    ax.set_title("Bypass Fraction  Q_bp / Q_total")
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.3)

    # 5. k Decay
    ax = axes[1, 1]
    ax.plot(t, results["k_vals"] * 1e11, color="#6A1B9A", lw=2)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("k_eff  [×10⁻¹¹ m²]")
    ax.set_title("Permeability Decay  k(V_out)")
    ax.grid(alpha=0.3)

    # 6. Saturation (Bloom)
    ax = axes[1, 2]
    ax.fill_between(t, results["sat"] * 100, alpha=0.4, color="#00695C")
    ax.plot(t, results["sat"] * 100, color="#00695C", lw=1.5)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Saturation [%]")
    ax.set_title("Bloom Saturation  V_poured / V_absorb")
    ax.set_ylim(0, 105)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_as, dpi=150, bbox_inches="tight")
    print(f"圖表已儲存至 {save_as}")


# ─────────────────────────────────────────────────────────────────────────────
#  TDS 診斷圖
# ─────────────────────────────────────────────────────────────────────────────
def plot_tds(
    results: dict,
    title: str = "V60 TDS Analysis",
    save_as: str = "v60_tds.png",
) -> None:
    """
    四格 TDS 診斷圖：粉層濃度 / 下壺濃度 / 累積 TDS / 萃取率 EY。

    What: 呈現萃取動力學與旁路稀釋對最終杯中品質的影響
    Why:  流體模型只告訴你「水怎麼流」；TDS 模型才告訴你「咖啡好不好喝」
    """
    t = results["t"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(title, fontsize=13, fontweight="bold")

    # 1. 粉層濃度 C_bed(t) 與有效 C_sat(t)
    ax = axes[0, 0]
    ax.plot(t, results["C_bed_gl"],     color="#6A1B9A", lw=2,   label="C_bed")
    ax.plot(t, results["C_sat_eff_gl"], color="#AB47BC", lw=1.5, ls="--", label="C_sat_eff = κ·M_sol")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Concentration [g/L]")
    ax.set_title("Bed Concentration  C_bed(t)  &  C_sat_eff(t)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # 2. 下壺瞬時濃度 C_out(t)（旁路稀釋後）
    ax = axes[0, 1]
    ax.plot(t, results["C_out_gl"], color="#1565C0", lw=2, label="C_out (after bypass dilution)")
    ax.plot(t, results["C_bed_gl"], color="#9C27B0", lw=1, ls="--", alpha=0.6, label="C_bed (no dilution)")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Concentration [g/L]")
    ax.set_title("Outflow Concentration  C_out(t)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # 3. 累積 TDS + 固相剩餘
    ax = axes[1, 0]
    ax.plot(t, results["TDS_gl"], color="#E65100", lw=2, label="TDS (g/L)")
    ax.axhspan(11.5, 14.5, alpha=0.15, color="green", label="SCA Golden Cup (1.15–1.45%)")
    ax2 = ax.twinx()
    ax2.plot(t, results["M_sol_g"], color="#78909C", lw=1.5, ls=":", label="M_sol remaining [g]")
    ax2.set_ylabel("M_sol [g]", color="#78909C")
    ax2.tick_params(axis="y", labelcolor="#78909C")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("TDS [g/L]")
    ax.set_title("Cumulative TDS  +  Solute Depletion")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=7)
    ax.grid(alpha=0.3)

    # 4. EY 雙重定義（入壺 vs 已溶出）
    ax = axes[1, 1]
    ax.plot(t, results["EY_cup_pct"],       color="#2E7D32", lw=2,   label="EY_cup (in your cup)")
    ax.plot(t, results["EY_dissolved_pct"], color="#81C784", lw=1.5, ls="--", label="EY_dissolved (from solid)")
    ax.fill_between(t, results["EY_cup_pct"], results["EY_dissolved_pct"],
                    alpha=0.2, color="#81C784", label="retained in filter")
    ax.axhspan(18, 22, alpha=0.1, color="green", label="SCA target (18–22%)")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Extraction Yield [%]")
    ax.set_title("EY: In-Cup  vs  Dissolved-from-Solid")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_as, dpi=150, bbox_inches="tight")
    print(f"TDS 圖表已儲存至 {save_as}")


def compare_tds_grind(protocol: PourProtocol | None = None) -> None:
    """
    不同研磨度的 TDS / EY 對比圖。

    Why: 揭示「旁路比高 × 接觸時間短」如何造成細研磨 TDS 悖論
         —— 粉層濃度高但下壺 TDS 反而可能低於中研磨（旁路稀釋）
    """
    if protocol is None:
        protocol = PourProtocol.standard_v60()

    configs = {
        "Coarse (粗研磨)": V60Params(k=2e-10),
        "Medium (中研磨)": V60Params(k=6e-11),
        "Fine   (細研磨)": V60Params(k=1.5e-11),
    }
    colors = ["#4CAF50", "#1E88E5", "#E53935"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Grind Size — TDS & EY Comparison", fontsize=13, fontweight="bold")

    for (label, params), color in zip(configs.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        axes[0].plot(res["t"], res["C_out_gl"],  color=color, lw=2, label=label)
        axes[1].plot(res["t"], res["TDS_gl"],    color=color, lw=2, label=label)
        axes[2].plot(res["t"], res["EY_pct"],    color=color, lw=2, label=label)
        print(f"{label}: TDS={res['TDS_gl'][-1]:.1f} g/L  EY={res['EY_pct'][-1]:.1f}%  bypass_avg={res['bypass_ratio'].mean()*100:.1f}%")

    for ax in axes:
        ax.axhspan(11.5, 14.5, alpha=0.1, color="green")
        ax.set_xlabel("Time [s]")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

    axes[0].set_ylabel("C_out [g/L]")
    axes[0].set_title("Outflow Concentration")
    axes[1].set_ylabel("TDS [g/L]")
    axes[1].set_title("Cumulative TDS")
    axes[2].set_ylabel("EY [%]")
    axes[2].set_title("Extraction Yield")

    plt.tight_layout()
    fname = "v60_tds_grind.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"TDS 研磨度對比圖已儲存至 {fname}")


# ─────────────────────────────────────────────────────────────────────────────
#  比較：基礎模型 vs 各項修正
# ─────────────────────────────────────────────────────────────────────────────
def compare_corrections(protocol: PourProtocol | None = None) -> None:
    """
    四種模型設定的水位曲線對比。

    Why: 讓使用者直觀看到每項物理修正對動態曲線的影響量級
         確認哪些修正是一階效應、哪些是細節調整
    """
    if protocol is None:
        protocol = PourProtocol.standard_v60()

    base = dict(k=2e-11, mu=3e-4, psi=2e-6)
    scenarios = {
        "Baseline (v1)":             V60Params(**base, h_bed=1.0,   k_beta=0,   dose_g=0),
        "+ h_bed correction":        V60Params(**base, h_bed=0.048, k_beta=0,   dose_g=0),
        "+ fines migration k(V)":    V60Params(**base, h_bed=0.048, k_beta=3e3, dose_g=0),
        "+ bloom absorption (full)": V60Params(**base, h_bed=0.048, k_beta=3e3, dose_g=20),
    }
    colors = ["#9E9E9E", "#1E88E5", "#E53935", "#2E7D32"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Physical Correction Impact — V60 Model v1 → v2", fontsize=13, fontweight="bold")

    for (label, params), color in zip(scenarios.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        axes[0].plot(res["t"], res["h_mm"],       color=color, lw=2,   label=label)
        axes[1].plot(res["t"], res["q_out_mlps"], color=color, lw=2,   label=label)

    for ax, ylabel, subtitle in zip(axes,
        ["Water Level [mm]", "Outflow Rate [mL/s]"],
        ["Water Level  h(t)", "Total Outflow  Q(t)"],
    ):
        ax.set_xlabel("Time [s]")
        ax.set_ylabel(ylabel)
        ax.set_title(subtitle)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    plt.tight_layout()
    fname = "v60_corrections.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"修正對比圖已儲存至 {fname}")


# ─────────────────────────────────────────────────────────────────────────────
#  研磨度比較
# ─────────────────────────────────────────────────────────────────────────────
def compare_grind_sizes(protocol: PourProtocol | None = None) -> None:
    """三種研磨度的水位與流速對比（使用完整 v2 模型）。"""
    if protocol is None:
        protocol = PourProtocol.standard_v60()

    configs = {
        "Coarse (粗研磨)": V60Params(k=2e-10),
        "Medium (中研磨)": V60Params(k=6e-11),
        "Fine   (細研磨)": V60Params(k=1.5e-11),
    }
    colors = ["#4CAF50", "#1E88E5", "#E53935"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Grind Size Comparison — V60 Simulation v2", fontsize=13, fontweight="bold")

    for (label, params), color in zip(configs.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        axes[0].plot(res["t"], res["h_mm"],       color=color, lw=2, label=label)
        axes[1].plot(res["t"], res["q_out_mlps"], color=color, lw=2, label=label)
        axes[2].plot(res["t"], res["bypass_ratio"] * 100, color=color, lw=2, label=label)

    titles = ["Water Level h(t)", "Outflow Rate Q(t)", "Bypass Ratio"]
    ylabels = ["Water Level [mm]", "Flow Rate [mL/s]", "Bypass [%]"]
    for ax, title, ylabel in zip(axes, titles, ylabels):
        ax.set_xlabel("Time [s]")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    plt.tight_layout()
    fname = "v60_grind_comparison.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"研磨度比較圖已儲存至 {fname}")


# ─────────────────────────────────────────────────────────────────────────────
#  熱力學耦合對比（修正 [6]）
# ─────────────────────────────────────────────────────────────────────────────
def compare_thermal(protocol: PourProtocol | None = None) -> None:
    """
    比較三種初始水溫（83 / 93 / 99°C）對沖煮結果的影響。

    What: 固定所有其他參數，僅改變 T_brew，觀察溫度對流速、TDS、EY 的影響。

    Why:  μ(T) 影響流速（低溫→黏度大→流慢）；
          k_ext(T) 影響萃取（低溫→擴散弱→萃取不足）；
          兩者都透過 T 狀態變數即時耦合。
    """
    if protocol is None:
        protocol = PourProtocol.standard_v60()

    configs = {
        "83°C  (cool)":  V60Params(T_brew=356.15),
        "93°C  (standard)": V60Params(T_brew=366.15),
        "99°C  (hot)":   V60Params(T_brew=372.15),
    }
    colors = ["#1E88E5", "#E53935", "#F9A825"]

    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    fig.suptitle("Thermal Coupling — Brew Temperature Effect (v5)", fontsize=13, fontweight="bold")

    results_all = {}
    for label, params in configs.items():
        res = simulate_brew(params, protocol, t_end=300)
        results_all[label] = res
        ey_f  = res["EY_fast_cup_pct"][-1]
        ey_s  = res["EY_slow_cup_pct"][-1]
        ratio = ey_f / (ey_f + ey_s) * 100 if (ey_f + ey_s) > 0 else 50
        print(f"  {label}: TDS={res['TDS_gl'][-1]:.1f} g/L  "
              f"EY={res['EY_cup_pct'][-1]:.1f}%  "
              f"Fast={ratio:.0f}%  "
              f"T_drop={res['T_C'][0]-res['T_C'][-1]:.1f}°C")

    for (label, res), color in zip(results_all.items(), colors):
        t = res["t"]
        axes[0, 0].plot(t, res["h_mm"],            color=color, lw=2, label=label)
        axes[0, 1].plot(t, res["q_out_mlps"],      color=color, lw=2, label=label)
        axes[0, 2].plot(t, res["T_C"],             color=color, lw=2, label=label)
        axes[1, 0].plot(t, res["TDS_gl"],          color=color, lw=2, label=label)
        axes[1, 1].plot(t, res["EY_cup_pct"],      color=color, lw=2, label=label)
        axes[1, 2].plot(t, res["bypass_ratio"]*100, color=color, lw=2, label=label)

    titles  = ["Water Level h(t)", "Outflow Rate Q(t)", "Brew Temperature T(t)",
               "TDS [g/L]",        "EY Cup [%]",        "Bypass Ratio [%]"]
    ylabels = ["Level [mm]", "Q [mL/s]", "T [°C]",
               "TDS [g/L]",  "EY [%]",  "Bypass [%]"]
    for ax, title, ylabel in zip(axes.flat, titles, ylabels):
        ax.set_xlabel("Time [s]")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    plt.tight_layout()
    fname = "v60_thermal.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"熱力學對比圖已儲存至 {fname}")


# ─────────────────────────────────────────────────────────────────────────────
#  風味組分對比（修正 [7]）
# ─────────────────────────────────────────────────────────────────────────────
def compare_flavor(protocol: PourProtocol | None = None) -> None:
    """
    三種水溫下的 Fast/Slow 組分萃取對比。

    What: 固定所有物理參數，僅改變 T_brew，觀察溫度如何重新分配 Fast/Slow 比例。

    Why:  Ea_slow >> Ea_fast → 溫度升高使 Slow 速率比 Fast 增長更快（指數差異）；
          這解釋了「高溫萃出更多苦味」的物理根源。
          Fast% = EY_fast/(EY_fast+EY_slow) 可作為「明亮度指標」。
    """
    if protocol is None:
        protocol = PourProtocol.standard_v60()

    configs = {
        "83°C  (cool)":    V60Params(T_brew=356.15),
        "93°C  (standard)": V60Params(T_brew=366.15),
        "99°C  (hot)":     V60Params(T_brew=372.15),
    }
    colors = ["#1E88E5", "#E53935", "#F9A825"]

    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    fig.suptitle("Multi-Component Extraction — Flavor Balance vs Temperature (v7)",
                 fontsize=12, fontweight="bold")

    print("  溫度       | TDS    | EY     | Fast%  | TDS_fast | TDS_slow")
    print("  " + "-"*65)
    for (label, params), color in zip(configs.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        t   = res["t"]
        ey_f  = res["EY_fast_cup_pct"][-1]
        ey_s  = res["EY_slow_cup_pct"][-1]
        ratio = ey_f / (ey_f + ey_s) * 100 if (ey_f + ey_s) > 0 else 50
        print(f"  {label}: TDS={res['TDS_gl'][-1]:.1f}  "
              f"EY={res['EY_cup_pct'][-1]:.1f}%  "
              f"Fast={ratio:.0f}%  "
              f"fast_TDS={res['TDS_fast_gl'][-1]:.1f}  "
              f"slow_TDS={res['TDS_slow_gl'][-1]:.1f}")

        axes[0, 0].plot(t, res["EY_fast_cup_pct"],  color=color, lw=2,     label=label)
        axes[0, 1].plot(t, res["EY_slow_cup_pct"],  color=color, lw=2,     label=label)
        axes[0, 2].plot(t, res["TDS_fast_gl"],      color=color, lw=2,     label=label)

        # 風味平衡比例
        total_ey = res["EY_fast_cup_pct"] + res["EY_slow_cup_pct"]
        _total_safe = np.where(total_ey > 0.1, total_ey, 1.0)
        fast_pct = np.where(total_ey > 0.1, res["EY_fast_cup_pct"] / _total_safe * 100, 50.0)
        axes[1, 0].plot(t, fast_pct,                color=color, lw=2,     label=label)
        axes[1, 1].plot(t, res["TDS_slow_gl"],      color=color, lw=2,     label=label)
        axes[1, 2].plot(t, res["TDS_gl"],           color=color, lw=2,     label=label)

    titles  = ["Fast EY (Bright/Acid)",  "Slow EY (Bitter/Astringent)",
               "Fast TDS [g/L]",
               "Flavor Balance Fast% (→明亮)", "Slow TDS [g/L]",   "Total TDS [g/L]"]
    ylabels = ["EY [%]", "EY [%]", "TDS [g/L]", "Fast% [%]", "TDS [g/L]", "TDS [g/L]"]
    for ax, title, ylabel in zip(axes.flat, titles, ylabels):
        ax.set_xlabel("Time [s]")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    plt.tight_layout()
    fname = "v60_flavor.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"風味組分對比圖已儲存至 {fname}")
