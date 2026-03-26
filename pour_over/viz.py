import numpy as np
import matplotlib.pyplot as plt

from .params import V60Params, PourProtocol, RoastProfile
from .core import simulate_brew


PALETTE = {
    "bg": "#f6f1e8",
    "panel": "#fffaf2",
    "grid": "#ddd4c4",
    "ink": "#2d241d",
    "muted": "#6e6256",
    "blue": "#2f6db2",
    "teal": "#147d6f",
    "orange": "#c46a2d",
    "red": "#a63d40",
    "purple": "#7d4f9e",
    "green": "#4f7d43",
    "gold": "#d1a43b",
    "lime": "#99b76b",
}


def _setup_style() -> None:
    """設定輸出圖的整體風格。

    What: 把所有圖改成暖底色、高對比重點線、低干擾網格。
    Why: 使用者看的是沖煮判讀，不是 Matplotlib 預設主題。
    """
    plt.rcParams.update({
        "figure.facecolor": PALETTE["bg"],
        "axes.facecolor": PALETTE["panel"],
        "axes.edgecolor": PALETTE["grid"],
        "axes.labelcolor": PALETTE["ink"],
        "axes.titlecolor": PALETTE["ink"],
        "text.color": PALETTE["ink"],
        "xtick.color": PALETTE["muted"],
        "ytick.color": PALETTE["muted"],
        "font.size": 10.5,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "legend.frameon": False,
        "savefig.facecolor": PALETTE["bg"],
    })


def _style_ax(ax, title: str, ylabel: str, xlabel: str = "Time [s]") -> None:
    """統一子圖外觀，讓不同圖之間的閱讀習慣一致。"""
    ax.set_facecolor(PALETTE["panel"])
    ax.grid(True, color=PALETTE["grid"], linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontweight="bold", pad=10)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(PALETTE["grid"])


def _summary_band(fig, title: str, stats: list[tuple[str, str]]) -> None:
    """在圖頂部放關鍵數值，讓讀者先抓結論再看曲線。"""
    fig.text(0.015, 0.985, title, ha="left", va="top",
             fontsize=18, fontweight="bold", color=PALETTE["ink"])
    x = 0.985
    for label, value in reversed(stats):
        fig.text(
            x, 0.985, f"{label}\n{value}",
            ha="right", va="top", fontsize=9.2, color=PALETTE["ink"],
            bbox=dict(boxstyle="round,pad=0.35", fc=PALETTE["panel"], ec=PALETTE["grid"], lw=0.8),
        )
        x -= 0.145


def _add_time_guides(ax, results: dict) -> None:
    """加上 brew end / drain end 的垂直參考線。"""
    t = results["t"]
    ymax = ax.get_ylim()[1]
    brew_time = float(results.get("brew_time", np.nan))
    drain_time = float(results.get("drain_time", np.nan))
    if np.isfinite(brew_time) and 0 < brew_time < t[-1]:
        ax.axvline(brew_time, color=PALETTE["muted"], lw=1.0, ls="--", alpha=0.8)
        ax.text(brew_time, ymax, " brew end", color=PALETTE["muted"],
                fontsize=8.2, va="top", ha="left")
    if np.isfinite(drain_time) and brew_time < drain_time < t[-1]:
        ax.axvline(drain_time, color=PALETTE["grid"], lw=1.0, ls=":", alpha=1.0)
        ax.text(drain_time, ymax, " drain end", color=PALETTE["muted"],
                fontsize=8.2, va="top", ha="left")


def _annotate_endpoint(ax, x: float, y: float, text: str, color: str, dx: float = 6, dy: float = 0) -> None:
    """在曲線終點或重點位置標數值，減少 legend 往返。"""
    ax.scatter([x], [y], s=28, color=color, edgecolor="white", linewidth=0.8, zorder=5)
    ax.annotate(
        text, (x, y), xytext=(dx, dy), textcoords="offset points",
        fontsize=8.3, color=color, va="center",
        bbox=dict(boxstyle="round,pad=0.22", fc=PALETTE["panel"], ec=color, lw=0.8),
    )


def _save_fig(fig, save_as: str, message: str) -> None:
    """統一輸出圖檔與關閉 figure，避免互動式殘留狀態。"""
    fig.savefig(save_as, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(message)


def plot_results(
    results: dict,
    title: str = "V60 Flow Diagnostics",
    save_as: str = "v60_simulation.png",
) -> None:
    """六格流體診斷圖。

    What: 呈現水位、流量分解、體積守恆、旁路、滲透率與飽和度。
    Why:  先把流動讀清楚，才能討論後面的萃取品質是不是合理。
    """
    _setup_style()
    t = results["t"]

    fig, axes = plt.subplots(2, 3, figsize=(15.6, 8.8), constrained_layout=True)
    _summary_band(fig, title, [
        ("Brew time", f"{results['brew_time']:.0f} s"),
        ("Drain time", f"{results['drain_time']:.0f} s"),
        ("Avg bypass", f"{results['bypass_ratio'].mean() * 100:.1f}%"),
        ("D10", f"{results['D10_um']:.0f} μm"),
    ])

    ax = axes[0, 0]
    ax.fill_between(t, results["h_mm"], color=PALETTE["blue"], alpha=0.16)
    ax.plot(t, results["h_mm"], color=PALETTE["blue"], lw=2.4)
    ax.axhline(48, color=PALETTE["muted"], lw=1.0, ls="--")
    _style_ax(ax, "Water head over time", "Water Level [mm]")
    _add_time_guides(ax, results)
    _annotate_endpoint(ax, t[-1], results["h_mm"][-1], f"{results['h_mm'][-1]:.1f} mm", PALETTE["blue"], dx=-78)

    ax = axes[0, 1]
    ax.stackplot(
        t, results["q_ext_mlps"], results["q_bp_mlps"],
        labels=["Bed extraction", "Bypass"],
        colors=[PALETTE["teal"], PALETTE["orange"]], alpha=0.72,
    )
    ax.plot(t, results["q_in_eff_mlps"], color=PALETTE["blue"], lw=1.6, ls="--", label="Effective pour")
    _style_ax(ax, "Where the liquid goes", "Flow Rate [mL/s]")
    _add_time_guides(ax, results)
    ax.legend(loc="upper right", fontsize=8.4)

    ax = axes[0, 2]
    ax.plot(t, results["v_in_ml"], color=PALETTE["green"], lw=2.3, label="Total in")
    ax.plot(t, results["v_in_eff_ml"], color="#8fbf7f", lw=1.7, ls="--", label="Effective in")
    ax.plot(t, results["v_out_ml"], color=PALETTE["red"], lw=2.3, label="Total out")
    ax.plot(t, results["v_extract_ml"], color=PALETTE["blue"], lw=1.7, ls="--", label="Extract out")
    _style_ax(ax, "Cumulative volume balance", "Volume [mL]")
    _add_time_guides(ax, results)
    ax.legend(fontsize=8.2, loc="lower right")

    ax = axes[1, 0]
    bypass_pct = results["bypass_ratio"] * 100
    ax.fill_between(t, bypass_pct, color=PALETTE["orange"], alpha=0.28)
    ax.plot(t, bypass_pct, color=PALETTE["orange"], lw=2.2)
    _style_ax(ax, "Bypass activation", "Bypass Ratio [%]")
    ax.set_ylim(0, 100)
    _add_time_guides(ax, results)
    _annotate_endpoint(ax, t[-1], bypass_pct[-1], f"{bypass_pct[-1]:.1f}%", PALETTE["orange"], dx=-54)

    ax = axes[1, 1]
    k_retained = results["k_vals"] / results["k_vals"][0] * 100
    ax.fill_between(t, k_retained, 100, color=PALETTE["purple"], alpha=0.10)
    ax.plot(t, k_retained, color=PALETTE["purple"], lw=2.2)
    _style_ax(ax, "Permeability retained", "k_eff / k_0 [%]")
    ax.set_ylim(0, 105)
    _add_time_guides(ax, results)
    _annotate_endpoint(ax, t[-1], k_retained[-1], f"{k_retained[-1]:.0f}%", PALETTE["purple"], dx=-48)

    ax = axes[1, 2]
    sat_pct = results["sat"] * 100
    ax.fill_between(t, sat_pct, color=PALETTE["teal"], alpha=0.35)
    ax.plot(t, sat_pct, color=PALETTE["teal"], lw=2.2)
    _style_ax(ax, "Bed wetting and saturation", "Saturation [%]")
    ax.set_ylim(0, 105)
    _add_time_guides(ax, results)
    reached = np.where(results["sat"] >= 0.995)[0]
    if reached.size > 0:
        i = int(reached[0])
        ax.scatter([t[i]], [sat_pct[i]], s=28, color=PALETTE["teal"], edgecolor="white", linewidth=0.8)
        ax.annotate("fully wetted", (t[i], sat_pct[i]), xytext=(8, -14), textcoords="offset points",
                    fontsize=8.3, color=PALETTE["teal"])

    _save_fig(fig, save_as, f"圖表已儲存至 {save_as}")


def plot_tds(
    results: dict,
    title: str = "V60 Extraction Quality",
    save_as: str = "v60_tds.png",
) -> None:
    """四格萃取品質圖。

    What: 呈現床內濃度、出液濃度、杯中 TDS、以及 EY 分流。
    Why:  讓讀者先看到杯中結果，再回推是濃度不足、旁路稀釋，還是保留液造成。
    """
    _setup_style()
    t = results["t"]

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.6), constrained_layout=True)
    fast_share = results["EY_fast_cup_pct"][-1] / max(results["EY_cup_pct"][-1], 1e-9) * 100
    _summary_band(fig, title, [
        ("Cup TDS", f"{results['TDS_gl'][-1] / 10:.2f}%"),
        ("Cup EY", f"{results['EY_cup_pct'][-1]:.1f}%"),
        ("Fast share", f"{fast_share:.0f}%"),
        ("Final LRR", f"{results['f_abs']:.2f} mL/g"),
    ])

    ax = axes[0, 0]
    ax.plot(t, results["C_bed_gl"], color=PALETTE["purple"], lw=2.3, label="Bed concentration")
    ax.plot(t, results["C_sat_eff_gl"], color="#bb8fd2", lw=1.7, ls="--", label="Effective saturation")
    _style_ax(ax, "Concentration inside the bed", "Concentration [g/L]")
    _add_time_guides(ax, results)
    ax.legend(fontsize=8.4, loc="upper right")

    ax = axes[0, 1]
    ax.plot(t, results["C_out_gl"], color=PALETTE["blue"], lw=2.4, label="Cup inflow concentration")
    ax.plot(t, results["C_bed_gl"], color=PALETTE["purple"], lw=1.2, ls="--", alpha=0.55, label="Bed concentration")
    _style_ax(ax, "What actually leaves the cone", "Concentration [g/L]")
    _add_time_guides(ax, results)
    ax.legend(fontsize=8.4, loc="upper right")
    _annotate_endpoint(ax, t[-1], results["C_out_gl"][-1], f"{results['C_out_gl'][-1]:.1f} g/L", PALETTE["blue"], dx=-80)

    ax = axes[1, 0]
    ax.plot(t, results["TDS_gl"], color=PALETTE["orange"], lw=2.4, label="Cup TDS")
    ax.axhspan(11.5, 14.5, alpha=0.15, color=PALETTE["lime"], label="SCA band")
    ax2 = ax.twinx()
    ax2.plot(t, results["M_sol_g"], color=PALETTE["muted"], lw=1.6, ls=":", label="Remaining solubles")
    ax2.set_ylabel("Solubles Remaining [g]", color=PALETTE["muted"])
    ax2.tick_params(axis="y", labelcolor=PALETTE["muted"])
    _style_ax(ax, "Cup strength and depletion", "TDS [g/L]")
    _add_time_guides(ax, results)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8.0, loc="lower right")
    _annotate_endpoint(ax, t[-1], results["TDS_gl"][-1], f"{results['TDS_gl'][-1] / 10:.2f}%", PALETTE["orange"], dx=-52)

    ax = axes[1, 1]
    ax.plot(t, results["EY_cup_pct"], color=PALETTE["teal"], lw=2.4, label="In cup")
    ax.plot(t, results["EY_dissolved_pct"], color="#7fb7ad", lw=1.7, ls="--", label="Dissolved from solid")
    ax.fill_between(
        t, results["EY_cup_pct"], results["EY_dissolved_pct"],
        alpha=0.18, color="#7fb7ad", label="Retained in bed",
    )
    ax.axhspan(18, 22, alpha=0.10, color=PALETTE["lime"], label="SCA target")
    _style_ax(ax, "Extraction yield split", "Extraction Yield [%]")
    _add_time_guides(ax, results)
    ax.legend(fontsize=8.0, loc="lower right")
    _annotate_endpoint(ax, t[-1], results["EY_cup_pct"][-1], f"{results['EY_cup_pct'][-1]:.1f}%", PALETTE["teal"], dx=-50)

    _save_fig(fig, save_as, f"TDS 圖表已儲存至 {save_as}")


def compare_grind(protocol: PourProtocol | None = None) -> None:
    """研磨度比較圖。

    What: 左邊看動態曲線，右下角看最終杯子落點。
    Why:  這比把六張小圖塞滿更容易讀出「哪一個 grind 落在合理區間」。
    """
    if protocol is None:
        protocol = PourProtocol.standard_v60()
    _setup_style()

    configs = {
        "Coarse": V60Params(k=2e-10),
        "Medium": V60Params(k=6e-11),
        "Fine": V60Params(k=1.5e-11),
    }
    colors = [PALETTE["green"], PALETTE["blue"], PALETTE["red"]]

    fig, axes = plt.subplots(2, 2, figsize=(14.4, 8.8), constrained_layout=True)
    _summary_band(fig, "Grind Size Comparison", [
        ("Coarse D10", f"{V60Params(k=2e-10).D10 * 1e6:.0f} μm"),
        ("Medium D10", f"{V60Params(k=6e-11).D10 * 1e6:.0f} μm"),
        ("Fine D10", f"{V60Params(k=1.5e-11).D10 * 1e6:.0f} μm"),
    ])

    finals = []
    for (label, params), color in zip(configs.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        t = res["t"]
        axes[0, 0].plot(t, res["h_mm"], color=color, lw=2.3, label=label)
        axes[0, 1].plot(t, res["q_out_mlps"], color=color, lw=2.3, label=label)
        axes[1, 0].plot(t, res["TDS_gl"], color=color, lw=2.3, label=label)
        finals.append((label, color, res["EY_cup_pct"][-1], res["TDS_gl"][-1], res["brew_time"], res["bypass_ratio"].mean() * 100))
        print(
            f"{label}: TDS={res['TDS_gl'][-1]:.1f} g/L  "
            f"EY={res['EY_cup_pct'][-1]:.1f}%  "
            f"bypass_avg={res['bypass_ratio'].mean()*100:.1f}%"
        )

    _style_ax(axes[0, 0], "Water head by grind", "Water Level [mm]")
    _style_ax(axes[0, 1], "Outflow rate by grind", "Flow Rate [mL/s]")
    _style_ax(axes[1, 0], "Cup TDS trajectory", "TDS [g/L]")
    axes[1, 0].axhspan(11.5, 14.5, alpha=0.12, color=PALETTE["lime"])
    for ax in (axes[0, 0], axes[0, 1], axes[1, 0]):
        ax.legend(fontsize=8.2, loc="best")

    ax = axes[1, 1]
    _style_ax(ax, "Final cup map", "TDS [g/L]", xlabel="Extraction Yield [%]")
    ax.axhspan(11.5, 14.5, alpha=0.12, color=PALETTE["lime"])
    ax.axvspan(18, 22, alpha=0.10, color="#bed5a0")
    ax.text(21.8, 14.35, "target window", fontsize=8.4, color=PALETTE["green"], ha="right", va="top")
    for label, color, ey, tds, brew_t, bypass in finals:
        size = 40 + brew_t * 0.9
        ax.scatter(ey, tds, s=size, color=color, alpha=0.88, edgecolor="white", linewidth=1.0)
        ax.annotate(
            f"{label}\n{brew_t:.0f}s · {bypass:.1f}% bp",
            (ey, tds), xytext=(7, 5), textcoords="offset points",
            fontsize=8.2, color=color,
        )

    _save_fig(fig, "v60_grind.png", "研磨度綜合對比圖已儲存至 v60_grind.png")


def compare_tds_grind(protocol: PourProtocol | None = None) -> None:
    """不同研磨度的濃度與萃取對比圖（保留供獨立呼叫）。"""
    if protocol is None:
        protocol = PourProtocol.standard_v60()
    _setup_style()

    configs = {
        "Coarse": V60Params(k=2e-10),
        "Medium": V60Params(k=6e-11),
        "Fine": V60Params(k=1.5e-11),
    }
    colors = [PALETTE["green"], PALETTE["blue"], PALETTE["red"]]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5), constrained_layout=True)
    _summary_band(fig, "Grind vs Extraction Curves", [("View", "Concentration / TDS / EY")])

    for (label, params), color in zip(configs.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        axes[0].plot(res["t"], res["C_out_gl"], color=color, lw=2.3, label=label)
        axes[1].plot(res["t"], res["TDS_gl"], color=color, lw=2.3, label=label)
        axes[2].plot(res["t"], res["EY_cup_pct"], color=color, lw=2.3, label=label)

    _style_ax(axes[0], "Outflow concentration", "Concentration [g/L]")
    _style_ax(axes[1], "Cup TDS", "TDS [g/L]")
    _style_ax(axes[2], "Cup EY", "Extraction Yield [%]")
    axes[1].axhspan(11.5, 14.5, alpha=0.12, color=PALETTE["lime"])
    axes[2].axhspan(18, 22, alpha=0.10, color=PALETTE["lime"])
    for ax in axes:
        ax.legend(fontsize=8.2, loc="best")

    _save_fig(fig, "v60_tds_grind.png", "TDS 研磨度對比圖已儲存至 v60_tds_grind.png")


def compare_corrections(protocol: PourProtocol | None = None) -> None:
    """基礎修正影響量級圖。"""
    if protocol is None:
        protocol = PourProtocol.standard_v60()
    _setup_style()

    base = dict(k=2e-11, mu=3e-4, psi=2e-6)
    scenarios = {
        "Baseline": V60Params(**base, h_bed=1.0, k_beta=0, dose_g=0),
        "+ bed height": V60Params(**base, h_bed=0.048, k_beta=0, dose_g=0),
        "+ clogging": V60Params(**base, h_bed=0.048, k_beta=3e3, dose_g=0),
        "+ absorption": V60Params(**base, h_bed=0.048, k_beta=3e3, dose_g=20),
    }
    colors = ["#9e9487", PALETTE["blue"], PALETTE["red"], PALETTE["green"]]

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4), constrained_layout=True)
    _summary_band(fig, "Correction Impact", [("Purpose", "order of magnitude check")])

    for (label, params), color in zip(scenarios.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        axes[0].plot(res["t"], res["h_mm"], color=color, lw=2.2, label=label)
        axes[1].plot(res["t"], res["q_out_mlps"], color=color, lw=2.2, label=label)

    _style_ax(axes[0], "Water level response", "Water Level [mm]")
    _style_ax(axes[1], "Outflow response", "Flow Rate [mL/s]")
    for ax in axes:
        ax.legend(fontsize=8.0, loc="best")

    _save_fig(fig, "v60_corrections.png", "修正對比圖已儲存至 v60_corrections.png")


def compare_grind_sizes(protocol: PourProtocol | None = None) -> None:
    """三種研磨度的水位、流量、旁路對比。"""
    if protocol is None:
        protocol = PourProtocol.standard_v60()
    _setup_style()

    configs = {
        "Coarse": V60Params(k=2e-10),
        "Medium": V60Params(k=6e-11),
        "Fine": V60Params(k=1.5e-11),
    }
    colors = [PALETTE["green"], PALETTE["blue"], PALETTE["red"]]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.4), constrained_layout=True)
    _summary_band(fig, "Grind Flow Comparison", [("Focus", "head / flow / bypass")])

    for (label, params), color in zip(configs.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        axes[0].plot(res["t"], res["h_mm"], color=color, lw=2.2, label=label)
        axes[1].plot(res["t"], res["q_out_mlps"], color=color, lw=2.2, label=label)
        axes[2].plot(res["t"], res["bypass_ratio"] * 100, color=color, lw=2.2, label=label)

    _style_ax(axes[0], "Water head", "Water Level [mm]")
    _style_ax(axes[1], "Outflow", "Flow Rate [mL/s]")
    _style_ax(axes[2], "Bypass ratio", "Bypass [%]")
    for ax in axes:
        ax.legend(fontsize=8.0, loc="best")

    _save_fig(fig, "v60_grind_comparison.png", "研磨度比較圖已儲存至 v60_grind_comparison.png")


def compare_thermal(protocol: PourProtocol | None = None) -> None:
    """不同初始水溫的熱耦合對比。

    What: 用四張圖看溫度衰減、流量、TDS、EY。
    Why:  使用者通常想知道「變熱之後，流動變多少、杯子變多少」。
    """
    if protocol is None:
        protocol = PourProtocol.standard_v60()
    _setup_style()

    configs = {
        "83°C": V60Params(T_brew=356.15),
        "93°C": V60Params(T_brew=366.15),
        "99°C": V60Params(T_brew=372.15),
    }
    colors = [PALETTE["blue"], PALETTE["red"], PALETTE["gold"]]

    fig, axes = plt.subplots(2, 2, figsize=(14.4, 8.8), constrained_layout=True)
    _summary_band(fig, "Thermal Coupling Comparison", [
        ("Cool", "83°C"),
        ("Baseline", "93°C"),
        ("Hot", "99°C"),
    ])

    all_results = []
    for (label, params), color in zip(configs.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        all_results.append((label, color, res))
        fast = res["EY_fast_cup_pct"][-1]
        slow = res["EY_slow_cup_pct"][-1]
        ratio = fast / max(fast + slow, 1e-9) * 100
        print(
            f"{label}: TDS={res['TDS_gl'][-1]:.1f} g/L  "
            f"EY={res['EY_cup_pct'][-1]:.1f}%  "
            f"Fast={ratio:.0f}%  "
            f"T_drop={res['T_C'][0] - res['T_C'][-1]:.1f}°C"
        )

    for label, color, res in all_results:
        t = res["t"]
        axes[0, 0].plot(t, res["T_C"], color=color, lw=2.3, label=label)
        axes[0, 1].plot(t, res["q_out_mlps"], color=color, lw=2.3, label=label)
        axes[1, 0].plot(t, res["TDS_gl"], color=color, lw=2.3, label=label)
        axes[1, 1].plot(t, res["EY_cup_pct"], color=color, lw=2.3, label=label)

    _style_ax(axes[0, 0], "Temperature decay in the slurry", "Temperature [°C]")
    _style_ax(axes[0, 1], "Outflow response to temperature", "Flow Rate [mL/s]")
    _style_ax(axes[1, 0], "Cup strength by brew temperature", "TDS [g/L]")
    axes[1, 0].axhspan(11.5, 14.5, alpha=0.12, color=PALETTE["lime"])
    _style_ax(axes[1, 1], "Cup yield by brew temperature", "Extraction Yield [%]")
    axes[1, 1].axhspan(18, 22, alpha=0.10, color=PALETTE["lime"])

    for ax in axes.flat:
        ax.legend(fontsize=8.2, loc="best")

    for _, color, res in all_results:
        _annotate_endpoint(axes[1, 0], res["t"][-1], res["TDS_gl"][-1], f"{res['TDS_gl'][-1] / 10:.2f}%", color, dx=-54)
        _annotate_endpoint(axes[1, 1], res["t"][-1], res["EY_cup_pct"][-1], f"{res['EY_cup_pct'][-1]:.1f}%", color, dx=-50)

    _save_fig(fig, "v60_thermal.png", "熱力學對比圖已儲存至 v60_thermal.png")


def compare_flavor(protocol: PourProtocol | None = None) -> None:
    """Fast/Slow 組分的溫度對比圖。"""
    if protocol is None:
        protocol = PourProtocol.standard_v60()
    _setup_style()

    configs = {
        "83°C": V60Params(T_brew=356.15),
        "93°C": V60Params(T_brew=366.15),
        "99°C": V60Params(T_brew=372.15),
    }
    colors = [PALETTE["blue"], PALETTE["red"], PALETTE["gold"]]

    fig, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    _summary_band(fig, "Flavor Balance vs Temperature", [("View", "fast vs slow components")])

    print("  溫度       | TDS    | EY     | Fast%  | TDS_fast | TDS_slow")
    print("  " + "-" * 65)
    for (label, params), color in zip(configs.items(), colors):
        res = simulate_brew(params, protocol, t_end=300)
        t = res["t"]
        ey_f = res["EY_fast_cup_pct"][-1]
        ey_s = res["EY_slow_cup_pct"][-1]
        ratio = ey_f / max(ey_f + ey_s, 1e-9) * 100
        print(
            f"  {label}: TDS={res['TDS_gl'][-1]:.1f}  "
            f"EY={res['EY_cup_pct'][-1]:.1f}%  "
            f"Fast={ratio:.0f}%  "
            f"fast_TDS={res['TDS_fast_gl'][-1]:.1f}  "
            f"slow_TDS={res['TDS_slow_gl'][-1]:.1f}"
        )

        axes[0, 0].plot(t, res["EY_fast_cup_pct"], color=color, lw=2.2, label=label)
        axes[0, 1].plot(t, res["EY_slow_cup_pct"], color=color, lw=2.2, label=label)
        axes[0, 2].plot(t, res["TDS_fast_gl"], color=color, lw=2.2, label=label)

        total = res["EY_fast_cup_pct"] + res["EY_slow_cup_pct"]
        total_safe = np.where(total > 0.1, total, 1.0)
        fast_pct = np.where(total > 0.1, res["EY_fast_cup_pct"] / total_safe * 100, 50.0)
        axes[1, 0].plot(t, fast_pct, color=color, lw=2.2, label=label)
        axes[1, 1].plot(t, res["TDS_slow_gl"], color=color, lw=2.2, label=label)
        axes[1, 2].plot(t, res["TDS_gl"], color=color, lw=2.2, label=label)

    titles = [
        "Fast EY (bright / acid)", "Slow EY (bitter / astringent)", "Fast TDS",
        "Fast share in cup", "Slow TDS", "Total TDS",
    ]
    ylabels = ["EY [%]", "EY [%]", "TDS [g/L]", "Fast Share [%]", "TDS [g/L]", "TDS [g/L]"]
    for ax, title, ylabel in zip(axes.flat, titles, ylabels):
        _style_ax(ax, title, ylabel)
        ax.legend(fontsize=8.0, loc="best")

    _save_fig(fig, "v60_flavor.png", "風味組分對比圖已儲存至 v60_flavor.png")
