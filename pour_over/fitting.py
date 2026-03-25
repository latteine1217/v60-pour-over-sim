"""
fitting.py — 參數擬合模組

What:
  提供兩階段反向擬合（fit_brew_params）與示範用流程（demo_fitting）。

Why:
  流體動力學（k, psi）與化學萃取（k_ext_coef, max_EY）在物理上解耦，
  分兩階段獨立優化可降低維度、避免高維非凸陷阱。
"""

import dataclasses

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from scipy.interpolate import interp1d

from .params import V60Params, PourProtocol
from .core import simulate_brew
from .viz import plot_results


# ─────────────────────────────────────────────────────────────────────────────
#  參數擬合（兩階段，利用因果解耦）
# ─────────────────────────────────────────────────────────────────────────────
def fit_brew_params(
    t_obs: np.ndarray,
    V_out_obs_ml: np.ndarray,
    TDS_final_gl: float,
    protocol: "PourProtocol",
    params_init: "V60Params | None" = None,
    verbose: bool = True,
) -> tuple["V60Params", dict]:
    """
    兩階段參數擬合（因果解耦）。

    What:
      Stage 1 — 從 V_out(t) 觀測序列擬合流體參數 (k, psi)。
      Stage 2 — 從最終杯中 TDS 擬合萃取參數 (k_ext_coef, max_EY)。

    Why:
      流體動力學（k, psi）決定 V_out(t)，且與化學無關；
      化學（k_ext_coef, max_EY）在流體解已知後才能被識別。
      解耦使優化問題維度各半，避免高維非凸陷阱。

    Args:
        t_obs          : 觀測時間戳 [s]，shape (N,)
        V_out_obs_ml   : 對應時刻的累積出液量 [mL]，shape (N,)
        TDS_final_gl   : 最終杯中 TDS 量測值 [g/L]
        protocol       : 注水協議
        params_init    : 初始猜測（None → 使用預設值）
        verbose        : 是否印出擬合過程

    Returns:
        (fitted_params, info_dict)
        info_dict keys: stage1_res, stage2_res, TDS_pred, EY_pred
    """
    if params_init is None:
        params_init = V60Params()

    # ── Stage 1：擬合流體參數 k, psi ──────────────────────────────────────────
    # 目標：最小化 V_out(t) 的均方誤差（log 空間優化，因參數跨越多個數量級）
    def _flow_residual(log_x: np.ndarray) -> float:
        k_try   = 10.0 ** log_x[0]
        psi_try = 10.0 ** log_x[1]
        p = dataclasses.replace(params_init, k=k_try, psi=psi_try)
        res = simulate_brew(p, protocol, t_end=float(t_obs[-1]) + 10, n_eval=500)
        # 內插模型預測值至觀測時間點
        interp = interp1d(res["t"], res["v_out_ml"], kind="linear",
                          bounds_error=False, fill_value="extrapolate")
        V_pred = interp(t_obs)
        rmse = float(np.sqrt(np.mean((V_pred - V_out_obs_ml) ** 2)))
        return rmse

    x0_s1 = np.array([np.log10(params_init.k), np.log10(params_init.psi)])
    bounds_s1 = [(-13, -9), (-8, -4)]  # log10 範圍

    if verbose:
        print("  [Stage 1] 擬合流體參數 k, psi...")

    res1 = minimize(
        _flow_residual, x0_s1,
        method="Nelder-Mead",
        bounds=bounds_s1,
        options={"xatol": 0.01, "fatol": 0.1, "maxiter": 300, "disp": False},
    )
    k_fit   = 10.0 ** res1.x[0]
    psi_fit = 10.0 ** res1.x[1]

    params_s1 = dataclasses.replace(params_init, k=k_fit, psi=psi_fit)

    if verbose:
        print(f"    k   = {k_fit:.3e}  (初始: {params_init.k:.3e})")
        print(f"    psi = {psi_fit:.3e}  (初始: {params_init.psi:.3e})")
        print(f"    V_out RMSE = {res1.fun:.2f} mL")

    # ── Stage 2：擬合萃取參數 k_ext_coef, max_EY ─────────────────────────────
    # 固定流體參數，只擬合化學參數使 TDS_final 吻合
    def _chem_residual(log_x: np.ndarray) -> float:
        kext_try   = 10.0 ** log_x[0]
        max_ey_try = float(np.clip(10.0 ** log_x[1], 0.10, 0.40))
        p = dataclasses.replace(params_s1, k_ext_coef=kext_try, max_EY=max_ey_try)
        res = simulate_brew(p, protocol, t_end=float(t_obs[-1]) + 30, n_eval=800)
        # 使用模擬結束時的 TDS（最後非零點）
        tds_arr = res["TDS_gl"]
        last_valid = tds_arr[tds_arr > 0]
        tds_pred = float(last_valid[-1]) if len(last_valid) > 0 else 0.0
        return (tds_pred - TDS_final_gl) ** 2

    x0_s2 = np.array([
        np.log10(params_s1.k_ext_coef),
        np.log10(params_s1.max_EY),
    ])
    bounds_s2 = [(-9, -5), (-1.3, -0.4)]  # log10(k_ext_coef), log10(max_EY)

    if verbose:
        print(f"  [Stage 2] 擬合萃取參數，目標 TDS = {TDS_final_gl:.2f} g/L...")

    res2 = minimize(
        _chem_residual, x0_s2,
        method="Nelder-Mead",
        options={"xatol": 0.01, "fatol": 1e-4, "maxiter": 300, "disp": False},
    )
    kext_fit   = 10.0 ** res2.x[0]
    max_ey_fit = float(np.clip(10.0 ** res2.x[1], 0.10, 0.40))

    params_fit = dataclasses.replace(params_s1, k_ext_coef=kext_fit, max_EY=max_ey_fit)

    # 驗證：用最終參數跑一次完整模擬
    res_final = simulate_brew(params_fit, protocol, t_end=float(t_obs[-1]) + 30, n_eval=800)
    tds_arr   = res_final["TDS_gl"]
    last_valid = tds_arr[tds_arr > 0]
    tds_pred   = float(last_valid[-1]) if len(last_valid) > 0 else 0.0
    ey_pred    = float(res_final["EY_cup_pct"][-1])

    if verbose:
        print(f"    k_ext_coef = {kext_fit:.3e}  (初始: {params_init.k_ext_coef:.3e})")
        print(f"    max_EY     = {max_ey_fit:.3f}  (初始: {params_init.max_EY:.3f})")
        print(f"    TDS 預測   = {tds_pred:.2f} g/L  (目標: {TDS_final_gl:.2f} g/L)")
        print(f"    EY 預測    = {ey_pred:.1f}%")

    info = {
        "stage1_res": res1,
        "stage2_res": res2,
        "TDS_pred":   tds_pred,
        "EY_pred":    ey_pred,
        "sim_final":  res_final,
    }
    return params_fit, info


def demo_fitting(protocol: "PourProtocol | None" = None) -> None:
    """
    參數擬合示範：用「真實」參數產生合成資料，加入量測雜訊，
    再從雜訊資料反推參數，驗證兩階段擬合的恢復能力。

    Why:
      在沒有真實量測數據時，合成資料驗證是判斷擬合演算法
      是否可識別（identifiable）的必要步驟。
    """
    if protocol is None:
        protocol = PourProtocol.standard_v60()

    # ── 真實參數（產生合成觀測）────────────────────────────────────────────────
    true_params = V60Params(
        k          = 1.5e-11,
        psi        = 3.0e-6,
        k_ext_coef = 0.8e-7,
        max_EY     = 0.24,
    )

    print("\n=== 參數擬合示範（合成資料驗證）===")
    print(f"  真實參數：k={true_params.k:.2e}, psi={true_params.psi:.2e}, "
          f"k_ext={true_params.k_ext_coef:.2e}, max_EY={true_params.max_EY:.2f}")

    # ── 產生「量測」資料（含白雜訊）──────────────────────────────────────────
    res_true = simulate_brew(true_params, protocol, t_end=300, n_eval=1000)
    rng = np.random.default_rng(42)

    # 每 15 s 取一個 V_out 樣本，加 ±2 mL 量測雜訊
    t_sample = np.arange(30, 301, 15, dtype=float)
    interp_Vout = interp1d(res_true["t"], res_true["v_out_ml"],
                           kind="linear", bounds_error=False, fill_value="extrapolate")
    V_out_noisy = interp_Vout(t_sample) + rng.normal(0, 2.0, len(t_sample))
    V_out_noisy = np.clip(V_out_noisy, 0, None)

    # 最終 TDS 加 ±0.2 g/L 雜訊
    tds_arr   = res_true["TDS_gl"]
    last_valid = tds_arr[tds_arr > 0]
    TDS_true   = float(last_valid[-1]) if len(last_valid) > 0 else 10.0
    TDS_noisy  = TDS_true + rng.normal(0, 0.2)

    print(f"  合成 TDS（含雜訊）：{TDS_noisy:.2f} g/L  (真實: {TDS_true:.2f} g/L)")

    # ── 從雜訊資料擬合（初始猜測用預設值）───────────────────────────────────
    init_params = V60Params()  # 故意從錯誤起點出發
    print(f"  初始猜測：k={init_params.k:.2e}, psi={init_params.psi:.2e}, "
          f"k_ext={init_params.k_ext_coef:.2e}, max_EY={init_params.max_EY:.2f}")

    fitted_params, info = fit_brew_params(
        t_obs        = t_sample,
        V_out_obs_ml = V_out_noisy,
        TDS_final_gl = TDS_noisy,
        protocol     = protocol,
        params_init  = init_params,
        verbose      = True,
    )

    # ── 結果比較 ──────────────────────────────────────────────────────────────
    print("\n  ┌────────────────────────────────────────────────┐")
    print("  │              參數恢復結果對比                    │")
    print("  ├──────────────┬──────────────┬──────────────────┤")
    print("  │   參數       │   真實值     │   擬合值         │")
    print("  ├──────────────┼──────────────┼──────────────────┤")
    pairs = [
        ("k  [m²]",      true_params.k,          fitted_params.k,          "{:.2e}"),
        ("psi [m²/s]",   true_params.psi,         fitted_params.psi,        "{:.2e}"),
        ("k_ext [m³/s]", true_params.k_ext_coef,  fitted_params.k_ext_coef, "{:.2e}"),
        ("max_EY",       true_params.max_EY,       fitted_params.max_EY,     "{:.3f}"),
    ]
    for name, true_val, fit_val, fmt in pairs:
        err_pct = abs(fit_val - true_val) / abs(true_val) * 100
        print(f"  │ {name:<12} │ {fmt.format(true_val):>12} │ {fmt.format(fit_val):>12}  ({err_pct:5.1f}%) │")
    print("  └──────────────┴──────────────┴──────────────────┘")

    # ── 視覺化：擬合曲線 vs 合成觀測 vs 真實曲線 ─────────────────────────────
    res_fit = info["sim_final"]
    # 延伸真實模擬至相同時長
    res_true_ext = simulate_brew(true_params, protocol, t_end=330, n_eval=800)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Parameter Fitting Demo — Synthetic Data Validation", fontsize=12)

    # 左圖：V_out(t)
    ax = axes[0]
    ax.plot(res_true_ext["t"], res_true_ext["v_out_ml"],
            "k-", lw=2, label="True simulation")
    ax.scatter(t_sample, V_out_noisy,
               color="red", s=30, zorder=5, label="Noisy observations")
    ax.plot(res_fit["t"], res_fit["v_out_ml"],
            "b--", lw=2, label="Fitted model")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Cumulative Outflow [mL]")
    ax.set_title("Flow Fit (Stage 1)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # 右圖：TDS(t)
    ax = axes[1]
    ax.plot(res_true_ext["t"], res_true_ext["TDS_gl"],
            "k-", lw=2, label="True TDS")
    ax.axhline(TDS_noisy, color="red", ls=":", lw=1.5, label=f"Measured TDS = {TDS_noisy:.2f} g/L")
    ax.plot(res_fit["t"], res_fit["TDS_gl"],
            "b--", lw=2, label="Fitted TDS")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("TDS [g/L]")
    ax.set_title("TDS Fit (Stage 2)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    fname = "v60_fitting_demo.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n擬合示範圖已儲存至 {fname}")
