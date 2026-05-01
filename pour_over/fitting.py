"""
fitting.py — 參數擬合模組

What:
  提供兩階段反向擬合（fit_brew_params）、實測沖煮紀錄解析、
  杯中最終溫度的等效熱容反推，以及示範用流程（demo_fitting）。

Why:
  流體動力學（k, psi）與化學萃取（k_ext_coef, max_EY）在物理上解耦，
  分兩階段獨立優化可降低維度、避免高維非凸陷阱。
"""

import dataclasses
import csv
import time
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from scipy.interpolate import interp1d

from .params import V60Params, PourProtocol, RoastProfile
from .core import simulate_brew
from .measured_io import (
    MEASURED_BED_HEIGHT_CM,
    MEASURED_VESSEL_EQUIV_ML,
    MEASURED_AMBIENT_TEMP_C,
    MEASURED_LIQUID_DRIPPER_LAMBDA,
    _meta_float,
    _measured_setup_overrides,
    load_brew_log_csv,
    load_flow_profile_csv,
    protocol_from_brew_log,
    protocol_from_cumulative_input,
)
from .observation import (
    mixed_cup_temperature_C,
    observed_stop_time_from_layer,
    apply_outflow_lag,
)
from .viz import (
    PALETTE,
    _setup_style,
    _style_ax,
    _summary_band,
    _save_fig,
    plot_results,
)
from .calibration_state import (
    DEFAULT_PREF_FLOW_OPEN_RATE_FIXED,
    DEFAULT_PREF_FLOW_TAU_DECAY_FIXED,
)

DEFAULT_MEASURED_FLOW_CSV = "data/kinu_29_light/4:11/kinu29_light_20g_flow_profile.csv"
DEFAULT_MEASURED_FLOW_FIT_PLOT = "data/kinu_29_light/4:11/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png"
DEFAULT_MEASURED_FLOW_FIT_SUMMARY = "data/kinu_29_light/4:11/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"


def evaluate_measured_flow_fit(
    csv_path: str | Path,
    params_try: V60Params,
    tau_lag_s: float,
    weights: dict | None = None,
    vessel_equivalent_ml: float | None = MEASURED_VESSEL_EQUIV_ML,
    n_eval: int = 1200,
    rtol: float = 1e-6,
    atol: float = 1e-8,
    max_step: float = 0.5,
) -> dict:
    """
    用 measured flow case 評估單一參數組的觀測層 loss 與指標。

    What:
        對給定 `params_try` 與 `tau_lag_s`：
        1. 重建 measured `PourProtocol`
        2. 跑完整模擬與杯中 lag layer
        3. 回傳 `V_out RMSE`、`q_out RMSE`、停流誤差、杯溫誤差與總 loss

    Why:
        benchmark、identifiability 與正式 fitting 應共享同一套評分定義，
        否則每個工具都在優化不同目標，結果不可比較。
    """
    prof = load_flow_profile_csv(csv_path)
    meta = prof["meta"]
    t_obs = np.asarray(prof["t_s"], dtype=float)
    v_in_obs = np.maximum.accumulate(np.asarray(prof["v_in_ml"], dtype=float))
    v_out_obs = np.asarray(prof["v_out_ml"], dtype=float)
    fit_mask = np.asarray(prof["use_for_fit"], dtype=bool)
    obs_interval_mask = fit_mask[1:] & fit_mask[:-1]
    dt_obs = np.diff(t_obs)
    q_obs_mlps = np.diff(v_out_obs) / np.maximum(dt_obs, 1e-12)
    stop_flow_time_s = float(prof["stop_flow_time_s"])
    final_cup_temp_C = prof["final_cup_temp_C"]
    final_tds_gl_obs = prof.get("final_tds_gl")  # measured cup TDS in g/L (Brix×0.85×10)
    if weights is None:
        weights = {
            "volume": 1.0,
            "velocity": 0.8,
            "drain_time": 0.5,
            "temperature": 0.35,
            "tds": 0.6,         # 量級：TDS RMSE 量值 ~5 g/L 同 V_RMSE 14 mL，0.6 weight 約等價於 V_RMSE 影響
            "regularization": 0.02,
        }

    protocol = PourProtocol.from_cumulative_profile(list(zip(t_obs, v_in_obs)))
    sim = simulate_brew(
        params_try,
        protocol,
        t_end=max(float(t_obs[-1]) + 30.0, 180.0),
        n_eval=n_eval,
        rtol=rtol,
        atol=atol,
        max_step=max_step,
    )
    ambient_temp_C = float(meta.get("ambient_temp_C", MEASURED_AMBIENT_TEMP_C))
    obs_layer = apply_outflow_lag(
        sim,
        tau_lag_s,
        ambient_temp_C=ambient_temp_C,
        vessel_equivalent_ml=0.0 if vessel_equivalent_ml is None else vessel_equivalent_ml,
        lambda_server_ambient=float(getattr(params_try, "lambda_server_ambient", 0.0)),
    )
    interp = interp1d(
        sim["t"], obs_layer["v_cup_ml"], kind="linear",
        bounds_error=False, fill_value="extrapolate",
    )
    v_pred_obs = np.asarray(interp(t_obs), dtype=float)
    q_pred_mlps = np.diff(v_pred_obs) / np.maximum(dt_obs, 1e-12)
    stop_model_s = observed_stop_time_from_layer(obs_layer, np.asarray(sim["t"], dtype=float), protocol)

    volume_rmse = float(np.sqrt(np.mean((v_pred_obs[fit_mask] - v_out_obs[fit_mask]) ** 2)))
    velocity_rmse = float(np.sqrt(np.mean((q_pred_mlps[obs_interval_mask] - q_obs_mlps[obs_interval_mask]) ** 2)))
    drain_dt = float(stop_model_s - stop_flow_time_s)

    temp_rmse = 0.0
    mixed_temp = None
    if final_cup_temp_C is not None and vessel_equivalent_ml is not None:
        mixed_temp = mixed_cup_temperature_C(
            {
                **sim,
                "q_out_mlps": obs_layer["q_cup_mlps"],
                "T_C": obs_layer["T_cup_C"],
                "T_server_C": obs_layer["T_server_C"],
            },
            ambient_temp_C=ambient_temp_C,
            vessel_equivalent_ml=vessel_equivalent_ml,
        )
        temp_rmse = abs(mixed_temp - final_cup_temp_C)

    # 量測 TDS（Brix×0.85×10）vs 模型最終 TDS [g/L]
    tds_pred = float(sim["TDS_gl"][-1]) if "TDS_gl" in sim else None
    tds_err = (
        float(tds_pred - final_tds_gl_obs)
        if (tds_pred is not None and final_tds_gl_obs is not None)
        else None
    )
    tds_rmse = abs(tds_err) if tds_err is not None else 0.0

    phys_penalty = 0.0
    if params_try.k < 2.0e-11 or params_try.k > 1.5e-10:
        phys_penalty += 3.0 * abs(np.log10(params_try.k / np.clip(params_try.k, 2.0e-11, 1.5e-10)))
    if params_try.k_beta < 5.0e2 or params_try.k_beta > 6.0e3:
        phys_penalty += 2.0 * abs(np.log10(params_try.k_beta / np.clip(params_try.k_beta, 5.0e2, 6.0e3)))
    if tau_lag_s < 0.5 or tau_lag_s > 5.0:
        phys_penalty += 1.5 * abs(np.log10(tau_lag_s / np.clip(tau_lag_s, 0.5, 5.0)))

    total_loss = float(
        weights["volume"] * volume_rmse
        + weights["velocity"] * velocity_rmse
        + weights["drain_time"] * abs(drain_dt)
        + weights["temperature"] * temp_rmse
        + weights.get("tds", 0.0) * tds_rmse
        + phys_penalty
    )
    return {
        "csv_path": str(csv_path),
        "meta": meta,
        "protocol": protocol,
        "sim": sim,
        "obs_layer": obs_layer,
        "t_obs_s": t_obs,
        "v_in_obs_ml": v_in_obs,
        "v_out_obs_ml": v_out_obs,
        "q_obs_mlps": q_obs_mlps,
        "v_pred_obs_ml": v_pred_obs,
        "q_pred_obs_mlps": q_pred_mlps,
        "fit_mask": fit_mask,
        "volume_rmse": volume_rmse,
        "velocity_rmse": velocity_rmse,
        "drain_time_error_s": drain_dt,
        "stop_flow_time_s": stop_flow_time_s,
        "cup_stop_time_s": float(stop_model_s),
        "mixed_cup_temp_C": mixed_temp,
        "final_cup_temp_C": final_cup_temp_C,
        "cup_temp_error_C": None if mixed_temp is None or final_cup_temp_C is None else float(mixed_temp - final_cup_temp_C),
        "final_tds_gl_obs": final_tds_gl_obs,
        "final_tds_gl_pred": tds_pred,
        "tds_error_gl": tds_err,
        "tds_rmse_gl": float(tds_rmse),
        "phys_penalty": float(phys_penalty),
        "total_loss": total_loss,
        "weights": weights,
        "tau_lag_s": float(tau_lag_s),
    }


def fit_vessel_equivalent_ml(
    results: dict,
    final_cup_temp_C: float,
    ambient_temp_C: float,
) -> float:
    """
    由最終杯溫反推容器等效水體積。

    What: 反推出一個 `V_eq`，使 `T_mix = (V_cup*T_energy + V_eq*T_amb)/(V_cup+V_eq)`。
    Why:  單一終點溫度不足以識別濾杯內部冷卻係數，但足以識別「杯器吸熱量級」。
    """
    t = np.asarray(results["t"], dtype=float)
    q_out_mlps = np.asarray(results["q_out_mlps"], dtype=float)
    T_out_C = np.asarray(results["T_C"], dtype=float)
    dt = np.diff(t, prepend=t[0])
    cup_volume_ml = float(np.sum(q_out_mlps * dt))
    if cup_volume_ml <= 0:
        return 0.0

    T_energy_C = float(np.sum(q_out_mlps * T_out_C * dt) / cup_volume_ml)
    denominator = final_cup_temp_C - ambient_temp_C
    if denominator <= 1e-9:
        raise ValueError("最終杯溫必須高於環境溫度，否則無法反推容器熱容")

    vessel_equivalent_ml = cup_volume_ml * (T_energy_C - final_cup_temp_C) / denominator
    return max(vessel_equivalent_ml, 0.0)


def fit_brew_log_final_temp(
    csv_path: str | Path,
    params_init: V60Params | None = None,
    vessel_equivalent_ml: float | None = MEASURED_VESSEL_EQUIV_ML,
    verbose: bool = True,
) -> tuple[V60Params, PourProtocol, dict]:
    """
    以實測 CSV 擬合「可識別」的熱容參數。

    What:
      1. 從 CSV 重建注水協議
      2. 套用實測的粉量、粉層高度、水溫與烘焙度
      3. 用量測給定的分享壺等效水體積計算最終杯溫；
         若顯式傳入 `None`，才改用杯溫反推 `vessel_equivalent_ml`

    Why:
      玻璃壺質量與材質已足以估計容器熱容時，`vessel_equivalent_ml` 就是可量測量，
      不應再讓 optimizer 或反推流程吸收其他模型誤差。
    """
    rows, meta = load_brew_log_csv(csv_path)
    protocol = protocol_from_brew_log(rows)

    roast_map = {
        "light": RoastProfile.LIGHT,
        "medium": RoastProfile.MEDIUM,
        "dark": RoastProfile.DARK,
    }
    roast_key = meta["roast"].strip().lower()
    profile = roast_map.get(roast_key)
    if profile is None:
        raise ValueError(f"未知烘焙度：{meta['roast']}")

    if params_init is None:
        params_init = V60Params.for_roast(profile)
    else:
        params_init = V60Params.for_roast(profile, base=params_init)

    params_fit = dataclasses.replace(
        params_init,
        dose_g=_meta_float(meta, "dose_g"),
        h_bed=_meta_float(meta, "bed_height_cm", MEASURED_BED_HEIGHT_CM) / 100.0,
        T_brew=_meta_float(meta, "brew_temp_C") + 273.15,
        **_measured_setup_overrides(meta, flow_csv_path=csv_path),
    )

    t_end = 180.0
    sim = simulate_brew(params_fit, protocol, t_end=t_end, n_eval=3000)

    final_cup_temp_C = _meta_float(meta, "final_coffee_temp_C")
    ambient_temp_C = params_fit.T_amb - 273.15
    if vessel_equivalent_ml is None:
        vessel_equivalent_ml = fit_vessel_equivalent_ml(sim, final_cup_temp_C, ambient_temp_C)
    mixed_temp_C = mixed_cup_temperature_C(sim, ambient_temp_C, vessel_equivalent_ml)

    info = {
        "csv_path": str(csv_path),
        "roast": roast_key,
        "protocol": protocol,
        "sim_final": sim,
        "final_cup_temp_target_C": final_cup_temp_C,
        "ambient_temp_C": ambient_temp_C,
        "vessel_equivalent_ml": vessel_equivalent_ml,
        "mixed_cup_temp_C": mixed_temp_C,
        "cup_volume_ml": float(sim["v_out_ml"][-1]),
        "brew_time_s": float(sim["brew_time"]),
        "drain_time_s": float(sim["drain_time"]),
        "T_out_end_C": float(sim["T_C"][-1]),
        "h_bed_cm": float(params_fit.h_bed * 100.0),
        "rho_bulk_dry_g_ml": float(params_fit.rho_bulk_dry_g_ml),
    }

    if verbose:
        print("=== 實測沖煮紀錄擬合 ===")
        print(f"  CSV               : {csv_path}")
        print(f"  Roast             : {roast_key}")
        print(f"  Dose              : {params_fit.dose_g:.1f} g")
        print(f"  Bed height        : {params_fit.h_bed*100:.1f} cm")
        print(f"  Dry bulk density  : {params_fit.rho_bulk_dry_g_ml:.3f} g/mL")
        print(f"  Brew temperature  : {params_fit.T_brew-273.15:.1f} °C")
        print(f"  Final cup target  : {final_cup_temp_C:.1f} °C")
        print(f"  Vessel equiv.     : {vessel_equivalent_ml:.1f} mL")
        print(f"  Predicted cup temp: {mixed_temp_C:.1f} °C")
        print(f"  Cup volume        : {sim['v_out_ml'][-1]:.1f} mL")
        print(f"  Brew / drain      : {sim['brew_time']:.1f} s / {sim['drain_time']:.1f} s")

    return params_fit, protocol, info


def save_fit_summary_csv(output_path: str | Path, info: dict) -> None:
    """
    將擬合摘要寫入 CSV。

    What: 以單列表格輸出此次擬合的核心結果。
    Why:  方便後續做版本比對、繪圖、或與其他實測批次拼接分析。
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "csv_path",
        "roast",
        "brew_time_s",
        "drain_time_s",
        "cup_volume_ml",
        "ambient_temp_C",
        "final_cup_temp_target_C",
        "mixed_cup_temp_C",
        "vessel_equivalent_ml",
        "h_bed_cm",
        "rho_bulk_dry_g_ml",
        "T_out_end_C",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({k: info[k] for k in fieldnames})


def fit_k_kbeta_from_flow_profile(
    csv_path: str | Path,
    params_init: V60Params | None = None,
    min_pour_ml: float = 1.0,
    weights: dict | None = None,
    vessel_equivalent_ml: float | None = MEASURED_VESSEL_EQUIV_ML,
    tau_lag_init_s: float = 2.0,
    fit_preferential_flow: bool = False,
    pref_open_rate_fixed: float = DEFAULT_PREF_FLOW_OPEN_RATE_FIXED,
    pref_tau_decay_fixed: float = DEFAULT_PREF_FLOW_TAU_DECAY_FIXED,
    fit_server_cooling: bool = True,
    fit_liquid_dripper_lambda: bool = True,
    verbose: bool = True,
) -> tuple[V60Params, dict]:
    """
    由 `V_in(t)` / `V_out(t)` 同步擬合滲透率 `k`、細粉堵塞 `k_beta`，
    並可選擇追加雙路徑快支路與兩條熱端 λ 的後段校準。

    What:
      1. 由觀測的累積注水曲線重建等效注水協議
      2. 固定其餘參數，最小化模型與實測的 `V_out(t)` 誤差
      3. 若啟用 `fit_preferential_flow`，固定
         `pref_flow_open_rate / pref_flow_tau_decay`，
         只對 `pref_flow_coeff` 做第三階段校準
      4. 若啟用 `fit_server_cooling`，在流量參數固定後，
         只對 `lambda_server_ambient` 做杯端散熱校準（stage 5）
      5. 若啟用 `fit_liquid_dripper_lambda`，在 stage 5 之後再對
         `lambda_liquid_dripper` 做液體 → 濾杯介面熱導校準（stage 6）。
         identifiability scan 顯示此 λ 是熱端最強自由度，先前被當量測
         常數凍結為 `0.02`，是個 hidden DOF；現升為正式 fit 自由度，
         以小幅 prior reg 約束在 `MEASURED_LIQUID_DRIPPER_LAMBDA` 附近
      6. 回傳 fitted params 與擬合資訊

    Why:
    `k` 主導早期通量量級，`k_beta` 主導後期衰減；
    `tau_lag` 代表濾床出口到壺內量測之間的小暫存體積。
    這組資料正好提供三者的可識別訊號。
    `pref_flow_*` 則代表每一注中心沖擊打開的快路徑，專門補「快響應 + 慢拖尾」
    這個單一路徑 Darcy 難以表達的時間尺度；identifiability 顯示
    `open_rate / tau_decay` 不應再與 `coeff` 一起自由漂移，因此正式流程固定它們。
    容器熱容預設採量測給定的 `42.4 mL water equivalent`；
    只有顯式傳入 `None` 時，才改用最終杯溫反推。
    NOTE: P0/P1 重構後，χ 結構態 (`wetbed_struct_*`) 已被移除——其物理敘事
    與 `f_irr` 重複，identifiability log 顯示其自由度為平 ridge。
    bloom 後濕床效應現以 `wetbed_postbloom_factor` 內的 `f_rev × f_irr`
    加性進 `R_total` 表達，不再有獨立的 stage 3 wetbed 校準。
    loss 會同時考慮：
      - `V_out(t)` 曲線誤差
      - 區間平均流出速度誤差
      - 停止流動時間
      - 最終杯溫（若 CSV 有提供）
    """
    prof = load_flow_profile_csv(csv_path)
    meta = prof["meta"]
    t_obs = prof["t_s"]
    v_in_obs = np.maximum.accumulate(prof["v_in_ml"])
    v_out_obs = np.asarray(prof["v_out_ml"], dtype=float)
    fit_mask = np.asarray(prof["use_for_fit"], dtype=bool)
    final_cup_temp_C = prof["final_cup_temp_C"]
    final_tds_gl_obs = prof.get("final_tds_gl")  # 量測 Brix→TDS [g/L]，未量測為 None
    stop_flow_time_s = float(prof["stop_flow_time_s"])
    if weights is None:
        weights = {
            "volume": 1.0,
            "velocity": 0.8,
            "drain_time": 0.5,
            "temperature": 0.35,
            "tds": 0.6,
            "regularization": 0.02,
        }

    roast_map = {
        "light": RoastProfile.LIGHT,
        "medium": RoastProfile.MEDIUM,
        "dark": RoastProfile.DARK,
    }
    roast_key = meta["roast"].strip().lower()
    profile = roast_map.get(roast_key)
    if profile is None:
        raise ValueError(f"未知烘焙度：{meta['roast']}")

    if params_init is None:
        params_init = V60Params.for_roast(profile)
    else:
        params_init = V60Params.for_roast(profile, base=params_init)

    params_base = dataclasses.replace(
        params_init,
        dose_g=_meta_float(meta, "dose_g"),
        h_bed=_meta_float(meta, "bed_height_cm", MEASURED_BED_HEIGHT_CM) / 100.0,
        T_brew=_meta_float(meta, "brew_temp_C") + 273.15,
        **_measured_setup_overrides(meta, flow_csv_path=csv_path),
    )
    if min_pour_ml <= 0:
        protocol = PourProtocol.from_cumulative_profile(list(zip(t_obs, v_in_obs)))
    else:
        # 目前標準做法仍建議直接使用累積注水曲線，以免人工切段丟失節奏資訊。
        # 保留 min_pour_ml 參數只是為了向後相容。
        protocol = PourProtocol.from_cumulative_profile(list(zip(t_obs, v_in_obs)))

    obs_interval_mask = fit_mask[1:] & fit_mask[:-1]
    dt_obs = np.diff(t_obs)
    q_obs_mlps = np.diff(v_out_obs) / np.maximum(dt_obs, 1e-12)

    if vessel_equivalent_ml is None and final_cup_temp_C is not None:
        # 用基準參數先反推一次量測端熱容，之後在多目標 loss 中固定使用。
        sim_ref = simulate_brew(params_base, protocol, t_end=max(float(t_obs[-1]) + 30.0, 180.0), n_eval=1600)
        obs_ref = apply_outflow_lag(sim_ref, tau_lag_init_s, ambient_temp_C=params_base.T_amb - 273.15)
        sim_ref = {
            **sim_ref,
            "q_out_mlps": obs_ref["q_cup_mlps"],
            "T_C": obs_ref["T_cup_C"],
        }
        vessel_equivalent_ml = fit_vessel_equivalent_ml(
            sim_ref, final_cup_temp_C=final_cup_temp_C, ambient_temp_C=params_base.T_amb - 273.15
        )

    fit_n_eval_coarse = 720
    fit_n_eval_final = 1800
    fit_rtol_coarse = 3e-5
    fit_atol_coarse = 1e-7
    fit_max_step_coarse = 1.0

    def _simulate_observed(
        params_try: V60Params,
        tau_try: float,
        n_eval: int = fit_n_eval_coarse,
        rtol: float = fit_rtol_coarse,
        atol: float = fit_atol_coarse,
        max_step: float = fit_max_step_coarse,
    ):
        sim = simulate_brew(
            params_try, protocol,
            t_end=max(float(t_obs[-1]) + 30.0, 180.0),
            n_eval=n_eval,
            rtol=rtol,
            atol=atol,
            max_step=max_step,
        )
        obs_layer = apply_outflow_lag(
            sim,
            tau_try,
            ambient_temp_C=params_base.T_amb - 273.15,
            vessel_equivalent_ml=0.0 if vessel_equivalent_ml is None else vessel_equivalent_ml,
            lambda_server_ambient=float(getattr(params_try, "lambda_server_ambient", 0.0)),
        )
        interp = interp1d(
            sim["t"], obs_layer["v_cup_ml"], kind="linear",
            bounds_error=False, fill_value="extrapolate",
        )
        v_pred_obs = interp(t_obs)
        q_pred_mlps = np.diff(v_pred_obs) / np.maximum(dt_obs, 1e-12)
        stop_model_s = observed_stop_time_from_layer(obs_layer, np.asarray(sim["t"], dtype=float), protocol)
        return sim, obs_layer, v_pred_obs, q_pred_mlps, stop_model_s

    loss_cache: dict[tuple, tuple[float, dict]] = {}

    def _evaluate_loss(
        params_try: V60Params,
        tau_try: float,
        *,
        coarse: bool = True,
    ) -> tuple[float, dict]:
        if coarse:
            cache_key = (
                round(float(params_try.k), 15),
                round(float(params_try.k_beta), 8),
                round(float(tau_try), 4),
                round(float(getattr(params_try, "pref_flow_coeff", 0.0)), 9),
                round(float(getattr(params_try, "pref_flow_open_rate", 0.0)), 6),
                round(float(getattr(params_try, "pref_flow_tau_decay", 0.0)), 6),
                round(float(getattr(params_try, "lambda_server_ambient", 0.0)), 7),
                round(float(getattr(params_try, "lambda_liquid_dripper", 0.0)), 6),
                round(float(getattr(params_try, "k_ext_slow_coef", 0.0)), 12),
                round(float(getattr(params_try, "k_ext_fast_coef", 0.0)), 12),
                round(float(getattr(params_try, "max_EY", 0.0)), 6),
            )
            if cache_key in loss_cache:
                return loss_cache[cache_key]
            sim, obs_layer, v_pred_obs, q_pred_mlps, stop_model_s = _simulate_observed(params_try, tau_try)
        else:
            sim, obs_layer, v_pred_obs, q_pred_mlps, stop_model_s = _simulate_observed(
                params_try,
                tau_try,
                n_eval=fit_n_eval_final,
                rtol=1e-6,
                atol=1e-8,
                max_step=0.5,
            )

        volume_rmse = float(np.sqrt(np.mean((v_pred_obs[fit_mask] - v_out_obs[fit_mask]) ** 2)))
        velocity_rmse = float(np.sqrt(np.mean((q_pred_mlps[obs_interval_mask] - q_obs_mlps[obs_interval_mask]) ** 2)))
        drain_dt = abs(stop_model_s - stop_flow_time_s)

        temp_rmse = 0.0
        mixed_temp = None
        if final_cup_temp_C is not None and vessel_equivalent_ml is not None:
            mixed_temp = mixed_cup_temperature_C(
                {
                    **sim,
                    "q_out_mlps": obs_layer["q_cup_mlps"],
                    "T_C": obs_layer["T_cup_C"],
                    "T_server_C": obs_layer["T_server_C"],
                },
                ambient_temp_C=params_base.T_amb - 273.15,
                vessel_equivalent_ml=vessel_equivalent_ml,
            )
            temp_rmse = abs(mixed_temp - final_cup_temp_C)

        # TDS 量測（Brix×0.85×10）vs 模型最終 TDS [g/L]
        tds_pred = float(sim["TDS_gl"][-1]) if "TDS_gl" in sim else None
        tds_rmse = (
            abs(tds_pred - final_tds_gl_obs)
            if (tds_pred is not None and final_tds_gl_obs is not None)
            else 0.0
        )

        # 物理合理性懲罰：避免為了壓誤差，把參數拉到不合理量級。
        phys_penalty = 0.0
        if params_try.k < 2.0e-11 or params_try.k > 1.5e-10:
            phys_penalty += 3.0 * abs(np.log10(params_try.k / np.clip(params_try.k, 2.0e-11, 1.5e-10)))
        if params_try.k_beta < 5.0e2 or params_try.k_beta > 6.0e3:
            phys_penalty += 2.0 * abs(np.log10(params_try.k_beta / np.clip(params_try.k_beta, 5.0e2, 6.0e3)))
        if tau_try < 0.5 or tau_try > 5.0:
            phys_penalty += 1.5 * abs(np.log10(tau_try / np.clip(tau_try, 0.5, 5.0)))

        loss = (
            weights["volume"] * volume_rmse +
            weights["velocity"] * velocity_rmse +
            weights["drain_time"] * drain_dt +
            weights["temperature"] * temp_rmse +
            weights.get("tds", 0.0) * tds_rmse +
            phys_penalty
        )
        metrics = {
            "sim": sim,
            "obs_layer": obs_layer,
            "v_pred_obs": v_pred_obs,
            "q_pred_mlps": q_pred_mlps,
            "stop_model_s": stop_model_s,
            "volume_rmse": volume_rmse,
            "velocity_rmse": velocity_rmse,
            "drain_dt": drain_dt,
            "mixed_temp": mixed_temp,
            "temp_rmse": temp_rmse,
            "tds_pred": tds_pred,
            "tds_rmse": tds_rmse,
            "phys_penalty": phys_penalty,
        }
        out = (float(loss), metrics)
        if coarse:
            loss_cache[cache_key] = out
        return out

    def _flow_loss(log_x: np.ndarray, tau_try: float) -> float:
        k_try = 10.0 ** log_x[0]
        beta_try = 10.0 ** log_x[1]
        p = dataclasses.replace(params_base, k=k_try, k_beta=beta_try)
        loss, metrics = _evaluate_loss(p, tau_try, coarse=True)
        k_beta_prior = float(getattr(params_base, "k_beta_prior_psd", params_base.k_beta))
        reg = weights["regularization"] * (
            (log_x[0] - np.log10(params_base.k)) ** 2 +
            (log_x[1] - np.log10(k_beta_prior)) ** 2
        )
        return float(loss + reg)

    x0 = np.array([np.log10(params_base.k), np.log10(params_base.k_beta)])
    bounds = [(np.log10(2.0e-11), np.log10(1.5e-10)), (np.log10(5.0e2), np.log10(6.0e3))]

    # 監控 timer：wall_clock vs process_time + per-stage nfev/elapsed
    # 若 wall ≫ process_time，表示外部 IO/thermal/scheduler 干擾（如原 4 hr outlier）
    stage_timings: list[dict] = []
    fit_t0_wall = time.perf_counter()
    fit_t0_proc = time.process_time()

    def _stage_start():
        return time.perf_counter(), time.process_time()

    def _stage_end(name: str, t0: tuple[float, float], nfev: int | None = None):
        wall = time.perf_counter() - t0[0]
        proc = time.process_time() - t0[1]
        stage_timings.append({
            "stage": name,
            "wall_s": float(wall),
            "process_s": float(proc),
            "wall_over_proc": float(wall / max(proc, 1e-9)),
            "nfev": int(nfev) if nfev is not None else None,
        })
        if verbose:
            nfev_str = f", nfev={nfev}" if nfev is not None else ""
            scale = wall / max(proc, 1e-9)
            stall = " ⚠" if scale > 1.5 else ""
            print(f"  [timer] {name}: wall={wall:.1f}s proc={proc:.1f}s ratio={scale:.2f}{nfev_str}{stall}")

    t0 = _stage_start()
    res_stage1 = minimize(
        lambda x: _flow_loss(x, tau_lag_init_s),
        x0,
        method="Powell",
        bounds=bounds,
        options={"xtol": 1e-2, "ftol": 1e-2, "maxiter": 90, "disp": False},
    )
    _stage_end("stage1_kkbeta", t0, nfev=getattr(res_stage1, "nfev", None))

    params_stage1 = dataclasses.replace(
        params_base,
        k=10.0 ** res_stage1.x[0],
        k_beta=10.0 ** res_stage1.x[1],
    )

    t0 = _stage_start()
    tau_grid = np.array([0.5, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0])
    best_tau = tau_lag_init_s
    best_tau_loss = float("inf")
    for tau_try in tau_grid:
        loss_tau, _ = _evaluate_loss(params_stage1, float(tau_try), coarse=True)
        if loss_tau < best_tau_loss:
            best_tau_loss = loss_tau
            best_tau = float(tau_try)
    _stage_end("tau_grid", t0, nfev=len(tau_grid))

    t0 = _stage_start()
    res_stage2 = minimize(
        lambda x: _flow_loss(x, best_tau),
        np.array([np.log10(params_stage1.k), np.log10(params_stage1.k_beta)]),
        method="Powell",
        bounds=bounds,
        options={"xtol": 1e-2, "ftol": 1e-2, "maxiter": 90, "disp": False},
    )
    _stage_end("stage2_kkbeta", t0, nfev=getattr(res_stage2, "nfev", None))

    params_fit = dataclasses.replace(
        params_base,
        k=10.0 ** res_stage2.x[0],
        k_beta=10.0 ** res_stage2.x[1],
    )
    tau_lag_fit = best_tau
    # NOTE: 舊 stage3_wetbed 已隨 P0/P1 重構移除（χ 結構態合併進 f_post）。
    res_stage4 = None
    res_stage5 = None

    if fit_preferential_flow:
        t_pref_start = _stage_start()
        pref_off_loss, _ = _evaluate_loss(params_fit, tau_lag_fit, coarse=True)
        seed_specs = [2.5e-5, 5.0e-5, 8.0e-5, 1.2e-4, 2.0e-4]
        seed_loss = pref_off_loss
        seed_coeff = None
        for coeff_try in seed_specs:
            params_try = dataclasses.replace(
                params_fit,
                pref_flow_coeff=float(coeff_try),
                pref_flow_open_rate=float(pref_open_rate_fixed),
                pref_flow_tau_decay=float(pref_tau_decay_fixed),
            )
            loss_try, _ = _evaluate_loss(params_try, tau_lag_fit, coarse=True)
            if loss_try < seed_loss:
                seed_loss = loss_try
                seed_coeff = float(coeff_try)

        if seed_coeff is not None:

            def _pref_loss(log_x: np.ndarray) -> float:
                coeff_try = 10.0 ** log_x[0]
                params_try = dataclasses.replace(
                    params_fit,
                    pref_flow_coeff=float(coeff_try),
                    pref_flow_open_rate=float(pref_open_rate_fixed),
                    pref_flow_tau_decay=float(pref_tau_decay_fixed),
                )
                loss_try, _ = _evaluate_loss(params_try, tau_lag_fit, coarse=True)
                reg = 0.35 * weights["regularization"] * (
                    (log_x[0] - np.log10(seed_coeff)) ** 2
                )
                return float(loss_try + reg)

            res_stage4 = minimize(
                _pref_loss,
                np.array([np.log10(seed_coeff)], dtype=float),
                method="Powell",
                bounds=[
                    (np.log10(5.0e-6), np.log10(5.0e-4)),
                ],
                options={"xtol": 8e-3, "ftol": 1e-2, "maxiter": 110, "disp": False},
            )
            params_pref = dataclasses.replace(
                params_fit,
                pref_flow_coeff=float(10.0 ** res_stage4.x[0]),
                pref_flow_open_rate=float(pref_open_rate_fixed),
                pref_flow_tau_decay=float(pref_tau_decay_fixed),
            )
            pref_obj = _pref_loss(np.asarray(res_stage4.x, dtype=float))
            _, pref_off_metrics_final = _evaluate_loss(params_fit, tau_lag_fit, coarse=False)
            _, pref_metrics_final = _evaluate_loss(params_pref, tau_lag_fit, coarse=False)
            volume_guard_ok = pref_metrics_final["volume_rmse"] <= (pref_off_metrics_final["volume_rmse"] + 0.15)
            if pref_obj < pref_off_loss and volume_guard_ok:
                params_fit = params_pref
            else:
                res_stage4 = None
        _stage_end("stage4_pref", t_pref_start, nfev=getattr(res_stage4, "nfev", None))

    # ── Stage 5+6：熱端 (lambda_server_ambient, lambda_liquid_dripper) joint fit ──
    # Why: thermal identifiability 顯示兩者沿對角線存在 mild ridge
    #      （cup_temp_error 在對角守恆，沿 ridge Δloss span ~0.16）。
    #      sequential 1D fit 會在初始點 (0.02, 0) 收斂於局部 (1.0×, 1.0×)，
    #      無法穿過 ridge 抵達真正的 2D 最小值。改採 joint Powell 在 log-space。
    # Implementation note: stage 6 變數仍保留以維持 stage_res schema 相容性，
    #      但實作上是同一輪 minimize 的 result alias。
    res_stage6 = None
    if (
        fit_server_cooling
        and final_cup_temp_C is not None
        and vessel_equivalent_ml is not None
    ):
        t_thermal_start = _stage_start()
        thermal_off_loss, thermal_off_metrics = _evaluate_loss(params_fit, tau_lag_fit, coarse=True)
        liq_prior = float(np.log10(MEASURED_LIQUID_DRIPPER_LAMBDA))
        liq_baseline = max(float(getattr(params_fit, "lambda_liquid_dripper", MEASURED_LIQUID_DRIPPER_LAMBDA)), 1e-6)
        if verbose:
            cup_err_off = thermal_off_metrics.get("mixed_temp")
            cup_err_str = (
                f"{float(cup_err_off - final_cup_temp_C):+.2f}"
                if cup_err_off is not None and final_cup_temp_C is not None
                else "n/a"
            )
            print(f"  [stage5] thermal_off_loss={thermal_off_loss:.4f} "
                  f"(V_RMSE={thermal_off_metrics['volume_rmse']:.3f}, "
                  f"cup_err={cup_err_str} °C)")

        # Server seed search (1D)：先抓出大致的 lambda_server 量級
        server_seed_grid = [0.0, 2.0e-4, 5.0e-4, 1.0e-3, 2.0e-3, 4.0e-3]
        seed_loss = thermal_off_loss
        seed_server = 0.0
        for lambda_try in server_seed_grid:
            params_try = dataclasses.replace(
                params_fit,
                lambda_server_ambient=float(lambda_try),
            )
            loss_try, _ = _evaluate_loss(params_try, tau_lag_fit, coarse=True)
            improved = loss_try < seed_loss
            if verbose:
                tag = " <-- update" if improved else ""
                print(f"  [stage5 seed] λ_srv={lambda_try:.1e}  loss={loss_try:.4f}{tag}")
            if improved:
                seed_loss = loss_try
                seed_server = float(lambda_try)

        # 永遠嘗試 joint Powell（即使 seed 沒找到改善）：
        # 觀察到原 4 小時 fit 在 7-bin baseline 下 stage 5/6 沒觸發；推測為
        # seed search 因浮點精度 / cache hit 導致 `loss_try < seed_loss` 嚴格 `<`
        # 比較失敗，雖然 Powell 從合理起點實際可找到 0.5+ 的改善。
        # 改為：seed search 只用來決定起點 λ_srv，joint Powell 一律啟動；
        # 由結尾的 `improvement_ok and volume_guard_ok` 把關「真的有改善才接受」。
        attempt_joint = fit_liquid_dripper_lambda
        if verbose:
            print(f"  [stage5] seed_server={seed_server:.1e}, seed_loss={seed_loss:.4f}, "
                  f"attempt_joint_powell={attempt_joint}")
        if attempt_joint:
            # 若 seed 沒找到改善，從 1e-4 出發（量級對 V60 baseline 是合理小默認值）
            seed_for_powell = seed_server if seed_server > 0.0 else 1.0e-4
            seed_server_clamped = float(np.clip(seed_for_powell, 1.0e-5, 1.0e-2))

            def _thermal_loss(log_x: np.ndarray) -> float:
                liq_try = 10.0 ** log_x[0]
                server_try = 10.0 ** log_x[1]
                params_try = dataclasses.replace(
                    params_fit,
                    lambda_liquid_dripper=float(liq_try),
                    lambda_server_ambient=float(server_try),
                )
                loss_try, _ = _evaluate_loss(params_try, tau_lag_fit, coarse=True)
                # 弱 prior reg on lambda_liq_drip toward MEASURED initial guess
                reg = 0.30 * weights["regularization"] * ((log_x[0] - liq_prior) ** 2)
                return float(loss_try + reg)

            x0 = np.array([
                np.log10(liq_baseline),
                np.log10(seed_server_clamped),
            ], dtype=float)
            res_thermal = minimize(
                _thermal_loss,
                x0,
                method="Powell",
                bounds=[
                    (np.log10(5.0e-3), np.log10(1.0e-1)),  # lambda_liq_drip
                    (np.log10(1.0e-5), np.log10(1.0e-2)),  # lambda_server
                ],
                options={"xtol": 8e-3, "ftol": 1e-2, "maxiter": 150, "disp": False},
            )
            params_thermal = dataclasses.replace(
                params_fit,
                lambda_liquid_dripper=float(10.0 ** res_thermal.x[0]),
                lambda_server_ambient=float(10.0 ** res_thermal.x[1]),
            )
            # Volume guard：禁止熱端 fit 為了杯溫犧牲體積擬合
            # IMPORTANT: 與 thermal_off 比較必須用同一 coarse mode（apples-to-apples）。
            # FINE / COARSE V_RMSE 存在 ~0.15 mL 系統性差（不同 n_eval 的數值積分差），
            # 若這裡用 FINE 對比 stage entry 的 COARSE，會誤殺合理的 Powell 改善
            # （原 4 小時 fit 的 stage 5/6 沒觸發即此 bug：FINE 13.917 vs COARSE+0.2=13.888 by 0.029）。
            _, thermal_metrics_coarse = _evaluate_loss(params_thermal, tau_lag_fit, coarse=True)
            volume_guard_ok = thermal_metrics_coarse["volume_rmse"] <= (thermal_off_metrics["volume_rmse"] + 0.20)
            final_loss_with_reg = _thermal_loss(np.asarray(res_thermal.x, dtype=float))
            improvement_ok = final_loss_with_reg < thermal_off_loss
            if verbose:
                print(f"  [stage5 powell] λ_liq={10.0**res_thermal.x[0]:.3e}, "
                      f"λ_srv={10.0**res_thermal.x[1]:.3e}, "
                      f"loss+reg={final_loss_with_reg:.4f}, "
                      f"V_RMSE={thermal_metrics_coarse['volume_rmse']:.3f} "
                      f"(off+0.2={thermal_off_metrics['volume_rmse']+0.20:.3f}, both coarse), "
                      f"vol_guard={'OK' if volume_guard_ok else 'FAIL'}, "
                      f"improved={'YES' if improvement_ok else 'NO'}")
            if improvement_ok and volume_guard_ok:
                params_fit = params_thermal
                res_stage5 = res_thermal  # 沿用 stage_res schema
                res_stage6 = res_thermal  # alias：兩個 λ 由同一輪 minimize 產出
        else:
            # Fall-back：fit_liquid_dripper_lambda 關閉時，做 server-only 1D fit。
            # 同樣 unconditional：seed 沒找到改善也跑 Powell，由結尾 strict `<`
            # 比較把關。
            seed_for_server_powell = seed_server if seed_server > 0.0 else 1.0e-4
            seed_server_anchor = float(np.clip(seed_for_server_powell, 1.0e-5, 1.0e-2))

            def _server_loss(log_x: np.ndarray) -> float:
                lambda_try = 10.0 ** log_x[0]
                params_try = dataclasses.replace(
                    params_fit,
                    lambda_server_ambient=float(lambda_try),
                )
                loss_try, _ = _evaluate_loss(params_try, tau_lag_fit, coarse=True)
                reg = 0.20 * weights["regularization"] * (
                    (log_x[0] - np.log10(seed_server_anchor)) ** 2
                )
                return float(loss_try + reg)

            res_server = minimize(
                _server_loss,
                np.array([np.log10(seed_server_anchor)], dtype=float),
                method="Powell",
                bounds=[(np.log10(1.0e-5), np.log10(1.0e-2))],
                options={"xtol": 8e-3, "ftol": 1e-2, "maxiter": 90, "disp": False},
            )
            params_server = dataclasses.replace(
                params_fit,
                lambda_server_ambient=float(10.0 ** res_server.x[0]),
            )
            if _server_loss(np.asarray(res_server.x, dtype=float)) < thermal_off_loss:
                params_fit = params_server
                res_stage5 = res_server
        _stage_end("stage5_thermal", t_thermal_start, nfev=getattr(res_stage5, "nfev", None) if res_stage5 else None)

    # ── Stage 7：萃取 joint fit (k_ext_slow_coef, max_EY) ────────────────────
    # Why: 量測 Brix→TDS 解鎖萃取端 fit。Forward sweep 顯示 k_ext_slow 單獨變化在
    #      500× 仍只能達 TDS 8.4 g/L（M_slow 在 reduced-order 0D + Fickian path²
    #      下時間有限），需要同時提升 max_EY 把 M_sol_0 cap 撐高。Joint Powell 2D：
    #      log10(k_ext_slow_coef) × max_EY，以 prior reg 約束在 roast envelope。
    #      AGENTS.md §4.C：max_EY 為 roast-driven prior，允許小範圍 fit 校準。
    res_stage7 = None
    if final_tds_gl_obs is not None:
        t_ext_start = _stage_start()
        ext_off_loss, ext_off_metrics = _evaluate_loss(params_fit, tau_lag_fit, coarse=True)
        slow_baseline = max(float(getattr(params_fit, "k_ext_slow_coef", 1e-7)), 1e-12)
        slow_log_baseline = float(np.log10(slow_baseline))
        max_ey_baseline = float(getattr(params_fit, "max_EY", 0.22))
        if verbose:
            print(f"  [stage7] ext_off_loss={ext_off_loss:.4f} (V_RMSE={ext_off_metrics['volume_rmse']:.3f}, "
                  f"TDS_pred={ext_off_metrics.get('tds_pred', 0):.2f} g/L, target {final_tds_gl_obs:.2f}, "
                  f"max_EY_init={max_ey_baseline:.3f})")

        def _ext_loss(x: np.ndarray) -> float:
            slow_try = float(10.0 ** x[0])
            max_ey_try = float(np.clip(x[1], 0.15, 0.40))
            params_try = dataclasses.replace(
                params_fit, k_ext_slow_coef=slow_try, max_EY=max_ey_try
            )
            loss_try, _ = _evaluate_loss(params_try, tau_lag_fit, coarse=True)
            # Prior reg：log10 k_ext_slow 偏離 baseline 與 max_EY 偏離 roast prior
            reg = 0.20 * weights["regularization"] * (x[0] - slow_log_baseline) ** 2
            reg += 0.50 * weights["regularization"] * ((x[1] - max_ey_baseline) / 0.05) ** 2
            return float(loss_try + reg)

        # Powell 2D: (log10 k_ext_slow, max_EY)
        # Bounds: k_ext_slow 0.3-100× baseline; max_EY 0.18-0.40（延伸自 0.35）
        # 2026-05-01 update: kinu29/4:11 canonical fit 收於 max_EY=0.349（clip=0.35），
        # Powell 還想往上推。延伸 bound 到 0.40 看能不能再降 TDS error。
        # 0.40 對 light roast 仍超 SCA 22% 範圍，但 model max_EY 是 closure 級的
        # M_sol cap，與 actual brew EY 不需直接對應；prior reg 會把它拉回。
        x0 = np.array([slow_log_baseline, max_ey_baseline], dtype=float)
        res_stage7 = minimize(
            _ext_loss,
            x0,
            method="Powell",
            bounds=[
                (slow_log_baseline - 0.5, slow_log_baseline + 2.0),  # 0.3× ~ 100×
                (0.18, 0.40),                                          # extended envelope
            ],
            options={"xtol": 5e-3, "ftol": 5e-3, "maxiter": 100, "disp": False},
        )
        slow_fit = float(10.0 ** res_stage7.x[0])
        max_ey_fit = float(np.clip(res_stage7.x[1], 0.18, 0.40))
        params_ext = dataclasses.replace(
            params_fit, k_ext_slow_coef=slow_fit, max_EY=max_ey_fit
        )
        ext_loss_final, ext_metrics_final = _evaluate_loss(params_ext, tau_lag_fit, coarse=True)
        # vol_guard 用 relative%-pt 制（與 benchmark gate 7% 一致）：
        # 允許 stage 7 把 V_RMSE 上推 0.5 percentage point（對 270 mL V_out 約 1.35 mL）
        # 只要最終仍在 benchmark gate 內就 OK；之前 absolute +0.20/+0.50 mL 對短 brew
        # 過嚴導致 kinu28 stage 7 reject by 0.026 mL（5.45%→5.65% 完全在 gate 內）。
        v_out_final = max(float(ext_off_metrics["sim"]["v_out_ml"][-1]), 1.0)
        v_off_pct = ext_off_metrics["volume_rmse"] / v_out_final
        v_new_pct = ext_metrics_final["volume_rmse"] / v_out_final
        volume_guard_ok = v_new_pct <= v_off_pct + 0.005  # +0.5 percentage point
        improvement_ok = ext_loss_final < ext_off_loss
        if verbose:
            print(f"  [stage7 powell] k_ext_slow={slow_fit:.3e} ({slow_fit/slow_baseline:.2f}× prior), "
                  f"max_EY={max_ey_fit:.3f}, loss={ext_loss_final:.4f}, "
                  f"V_RMSE%={v_new_pct*100:.2f} (off={v_off_pct*100:.2f}, gate +0.5pt={v_off_pct*100+0.5:.2f}), "
                  f"TDS_pred={ext_metrics_final.get('tds_pred', 0):.2f} g/L, "
                  f"vol_guard={'OK' if volume_guard_ok else 'FAIL'}, "
                  f"improved={'YES' if improvement_ok else 'NO'}")
        if improvement_ok and volume_guard_ok:
            params_fit = params_ext
        else:
            res_stage7 = None
        _stage_end("stage7_extraction", t_ext_start, nfev=getattr(res_stage7, "nfev", None) if res_stage7 else None)

    t_final = _stage_start()
    loss_final, metrics_final = _evaluate_loss(params_fit, tau_lag_fit, coarse=False)
    _stage_end("final_eval", t_final, nfev=1)
    fit_wall = time.perf_counter() - fit_t0_wall
    fit_proc = time.process_time() - fit_t0_proc
    if verbose:
        print(f"  [timer] TOTAL: wall={fit_wall:.1f}s proc={fit_proc:.1f}s "
              f"ratio={fit_wall/max(fit_proc,1e-9):.2f}"
              + (" ⚠ external stall detected" if fit_wall/max(fit_proc,1e-9) > 1.5 else ""))
    sim_final = metrics_final["sim"]
    obs_final = metrics_final["obs_layer"]
    v_pred_final = metrics_final["v_pred_obs"]
    q_pred_final = metrics_final["q_pred_mlps"]
    rmse_final = metrics_final["volume_rmse"]
    velocity_rmse_final = metrics_final["velocity_rmse"]
    mixed_temp_final = metrics_final["mixed_temp"]
    temp_err_final = None if mixed_temp_final is None or final_cup_temp_C is None else float(mixed_temp_final - final_cup_temp_C)
    pref_flow_active = bool(fit_preferential_flow and getattr(params_fit, "pref_flow_coeff", 0.0) > 0.0)

    info = {
        "csv_path": str(csv_path),
        "roast": roast_key,
        "protocol": protocol,
        "bloom_end_s": float(protocol.bloom_end_time()),
        "stage_res": {
            "stage1": res_stage1,
            "stage2": res_stage2,
            "stage4_pref": res_stage4,
            "stage5_server": res_stage5,
            "stage6_liq_dripper": res_stage6,
        },
        "sim_final": sim_final,
        "obs_layer": obs_final,
        "rmse_ml": rmse_final,
        "k_fit": float(params_fit.k),
        "k_beta_fit": float(params_fit.k_beta),
        "k_beta_prior_psd": float(getattr(params_base, "k_beta_prior_psd", params_base.k_beta)),
        "k_beta_throat_fit": float(getattr(params_fit, "k_beta_throat_coeff", np.nan)),
        "k_beta_deposition_fit": float(getattr(params_fit, "k_beta_deposition_coeff", np.nan)),
        "k_beta_throat_prior": float(getattr(params_base, "k_beta_throat_prior", np.nan)),
        "k_beta_deposition_prior": float(getattr(params_base, "k_beta_deposition_prior", np.nan)),
        "tau_lag_s": tau_lag_fit,
        "fit_preferential_flow": pref_flow_active,
        "pref_flow_coeff_fit": float(getattr(params_fit, "pref_flow_coeff", 0.0)),
        "pref_flow_open_rate_fit": float(getattr(params_fit, "pref_flow_open_rate", 0.0)),
        "pref_flow_tau_decay_fit": float(getattr(params_fit, "pref_flow_tau_decay", 0.0)),
        "pref_flow_open_rate_fixed": float(pref_open_rate_fixed),
        "pref_flow_tau_decay_fixed": float(pref_tau_decay_fixed),
        "t_obs_s": t_obs,
        "v_in_obs_ml": v_in_obs,
        "v_out_obs_ml": v_out_obs,
        "model_v_out_ml": obs_final["v_cup_ml"],
        "fit_mask": fit_mask,
        "q_obs_mlps": q_obs_mlps,
        "q_pred_obs_mlps": q_pred_final,
        "model_q_out_mlps": obs_final["q_cup_mlps"],
        "model_T_out_C": obs_final["T_cup_C"],
        "velocity_rmse_mlps": velocity_rmse_final,
        "stop_flow_time_s": stop_flow_time_s,
        "drain_time_error_s": float(metrics_final["stop_model_s"] - stop_flow_time_s),
        "cup_stop_time_s": float(metrics_final["stop_model_s"]),
        "final_cup_temp_C": final_cup_temp_C,
        "vessel_equivalent_ml": vessel_equivalent_ml,
        "fit_server_cooling": bool(fit_server_cooling and final_cup_temp_C is not None and vessel_equivalent_ml is not None),
        "server_cooling_lambda_fit": float(getattr(params_fit, "lambda_server_ambient", 0.0)),
        "fit_liquid_dripper_lambda": bool(res_stage6 is not None),
        "lambda_liquid_dripper_fit": float(getattr(params_fit, "lambda_liquid_dripper", MEASURED_LIQUID_DRIPPER_LAMBDA)),
        "lambda_liquid_dripper_prior": float(MEASURED_LIQUID_DRIPPER_LAMBDA),
        "mixed_cup_temp_C": mixed_temp_final,
        "cup_temp_error_C": temp_err_final,
        # TDS / extraction outputs
        "final_tds_gl_obs": final_tds_gl_obs,
        "final_tds_gl_pred": metrics_final.get("tds_pred"),
        "tds_error_gl": (
            float(metrics_final["tds_pred"] - final_tds_gl_obs)
            if metrics_final.get("tds_pred") is not None and final_tds_gl_obs is not None
            else None
        ),
        "fit_extraction": bool(res_stage7 is not None),
        "k_ext_slow_coef_fit": float(getattr(params_fit, "k_ext_slow_coef", 0.0)),
        "k_ext_fast_coef_fit": float(getattr(params_fit, "k_ext_fast_coef", 0.0)),
        "max_EY_fit": float(getattr(params_fit, "max_EY", 0.0)),
        "h_bed_cm": float(params_fit.h_bed * 100.0),
        "rho_bulk_dry_g_ml": float(params_fit.rho_bulk_dry_g_ml),
        "axial_node_count": int(getattr(params_fit, "axial_node_count", 1)),
        "sat_rel_perm_residual_fit": float(getattr(params_fit, "sat_rel_perm_residual", np.nan)),
        "sat_rel_perm_exp_fit": float(getattr(params_fit, "sat_rel_perm_exp", np.nan)),
        "weights": weights,
        "total_loss": float(loss_final),
        "stage_timings": stage_timings,
        "fit_wall_s": float(fit_wall),
        "fit_process_s": float(fit_proc),
    }

    if verbose:
        print("=== 多目標流動標定：k / k_beta / pref / thermal (server + liq_drip) ===")
        print(f"  CSV         : {csv_path}")
        print(f"  Roast       : {roast_key}")
        print(f"  Bed height  : {params_fit.h_bed*100:.1f} cm")
        print(f"  Dry bulk    : {params_fit.rho_bulk_dry_g_ml:.3f} g/mL")
        print(f"  k_fit       : {params_fit.k:.3e} m²")
        print(f"  k_beta_fit  : {params_fit.k_beta:.3e} m⁻³")
        print(f"  k_beta prior: {getattr(params_base, 'k_beta_prior_psd', params_base.k_beta):.3e} m⁻³")
        print(f"    throat / deposition = {getattr(params_fit, 'k_beta_throat_coeff', np.nan):.3e} / {getattr(params_fit, 'k_beta_deposition_coeff', np.nan):.3e}")
        print(f"  tau_lag     : {tau_lag_fit:.2f} s")
        if pref_flow_active:
            print(f"  pref coeff  : {params_fit.pref_flow_coeff:.3e} m²/s")
            print(f"  pref open   : fixed {params_fit.pref_flow_open_rate:.3f} 1/s")
            print(f"  pref tau    : fixed {params_fit.pref_flow_tau_decay:.2f} s")
        print(f"  V_out RMSE  : {rmse_final:.2f} mL")
        print(f"  q_out RMSE  : {velocity_rmse_final:.2f} mL/s")
        print(f"  Drain error : {metrics_final['stop_model_s']-stop_flow_time_s:+.1f} s")
        if final_cup_temp_C is not None and mixed_temp_final is not None:
            print(f"  Cup temp    : {mixed_temp_final:.1f} °C  (target {final_cup_temp_C:.1f} °C)")
            print(f"  λ_server    : {getattr(params_fit, 'lambda_server_ambient', 0.0):.3e} 1/s")
            print(f"  λ_liq_drip  : {getattr(params_fit, 'lambda_liquid_dripper', 0.0):.3e} 1/s "
                  f"(prior {MEASURED_LIQUID_DRIPPER_LAMBDA:.2e})")
        print(f"  Brew / drain: {sim_final['brew_time']:.1f} s / {sim_final['drain_time']:.1f} s")

    return params_fit, info


def save_flow_fit_summary_csv(output_path: str | Path, info: dict) -> None:
    """
    將流動標定摘要寫入 CSV。

    What: 輸出 `k`, `k_beta`, RMSE 與模擬的關鍵終值。
    Why:  流動標定通常會反覆迭代，摘要 CSV 比 console log 更適合版本管理。
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "csv_path",
        "roast",
        "k_fit",
        "k_beta_fit",
        "k_beta_prior_psd",
        "k_beta_throat_fit",
        "k_beta_deposition_fit",
        "k_beta_throat_prior",
        "k_beta_deposition_prior",
        "tau_lag_s",
        "rmse_ml",
        "velocity_rmse_mlps",
        "brew_time_s",
        "drain_time_s",
        "stop_flow_time_s",
        "drain_time_error_s",
        "v_out_final_ml",
        "h_bed_cm",
        "rho_bulk_dry_g_ml",
        "axial_node_count",
        "sat_rel_perm_residual_fit",
        "sat_rel_perm_exp_fit",
        "final_cup_temp_C",
        "mixed_cup_temp_C",
        "cup_temp_error_C",
        "vessel_equivalent_ml",
        "fit_server_cooling",
        "server_cooling_lambda_fit",
        "fit_liquid_dripper_lambda",
        "lambda_liquid_dripper_fit",
        "lambda_liquid_dripper_prior",
        "fit_preferential_flow",
        "pref_flow_coeff_fit",
        "pref_flow_open_rate_fit",
        "pref_flow_tau_decay_fit",
        "pref_flow_open_rate_fixed",
        "pref_flow_tau_decay_fixed",
        # Extraction fit (stage 7)
        "fit_extraction",
        "k_ext_slow_coef_fit",
        "k_ext_fast_coef_fit",
        "max_EY_fit",
        "final_tds_gl_obs",
        "final_tds_gl_pred",
        "tds_error_gl",
    ]
    row = {
        "csv_path": info["csv_path"],
        "roast": info["roast"],
        "k_fit": info["k_fit"],
        "k_beta_fit": info["k_beta_fit"],
        "k_beta_prior_psd": info.get("k_beta_prior_psd"),
        "k_beta_throat_fit": info.get("k_beta_throat_fit"),
        "k_beta_deposition_fit": info.get("k_beta_deposition_fit"),
        "k_beta_throat_prior": info.get("k_beta_throat_prior"),
        "k_beta_deposition_prior": info.get("k_beta_deposition_prior"),
        "tau_lag_s": info.get("tau_lag_s"),
        "rmse_ml": info["rmse_ml"],
        "velocity_rmse_mlps": info.get("velocity_rmse_mlps"),
        "brew_time_s": float(info["sim_final"]["brew_time"]),
        "drain_time_s": float(info["sim_final"]["drain_time"]),
        "stop_flow_time_s": info.get("stop_flow_time_s"),
        "drain_time_error_s": info.get("drain_time_error_s"),
        "v_out_final_ml": float(info.get("model_v_out_ml", info["sim_final"]["v_out_ml"])[-1]),
        "h_bed_cm": info.get("h_bed_cm"),
        "rho_bulk_dry_g_ml": info.get("rho_bulk_dry_g_ml"),
        "axial_node_count": info.get("axial_node_count", info["sim_final"].get("axial_node_count")),
        "sat_rel_perm_residual_fit": info.get("sat_rel_perm_residual_fit"),
        "sat_rel_perm_exp_fit": info.get("sat_rel_perm_exp_fit"),
        "final_cup_temp_C": info.get("final_cup_temp_C"),
        "mixed_cup_temp_C": info.get("mixed_cup_temp_C"),
        "cup_temp_error_C": info.get("cup_temp_error_C"),
        "vessel_equivalent_ml": info.get("vessel_equivalent_ml"),
        "fit_server_cooling": info.get("fit_server_cooling"),
        "server_cooling_lambda_fit": info.get("server_cooling_lambda_fit"),
        "fit_liquid_dripper_lambda": info.get("fit_liquid_dripper_lambda"),
        "lambda_liquid_dripper_fit": info.get("lambda_liquid_dripper_fit"),
        "lambda_liquid_dripper_prior": info.get("lambda_liquid_dripper_prior"),
        "fit_preferential_flow": info.get("fit_preferential_flow"),
        "pref_flow_coeff_fit": info.get("pref_flow_coeff_fit"),
        "pref_flow_open_rate_fit": info.get("pref_flow_open_rate_fit"),
        "pref_flow_tau_decay_fit": info.get("pref_flow_tau_decay_fit"),
        "pref_flow_open_rate_fixed": info.get("pref_flow_open_rate_fixed"),
        "pref_flow_tau_decay_fixed": info.get("pref_flow_tau_decay_fixed"),
        "fit_extraction": info.get("fit_extraction"),
        "k_ext_slow_coef_fit": info.get("k_ext_slow_coef_fit"),
        "k_ext_fast_coef_fit": info.get("k_ext_fast_coef_fit"),
        "max_EY_fit": info.get("max_EY_fit"),
        "final_tds_gl_obs": info.get("final_tds_gl_obs"),
        "final_tds_gl_pred": info.get("final_tds_gl_pred"),
        "tds_error_gl": info.get("tds_error_gl"),
    }
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def plot_flow_fit_comparison(
    info: dict,
    save_as: str = "kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png",
) -> None:
    """
    繪製實測 `V_out(t)` 與擬合模型的對照圖。

    What:
        上圖   — 累積注水 / 累積出液
        中圖   — 區間平均流出速度
        下圖   — 各量測點的體積殘差

    Why:
        現在的 loss 是多目標：不只要對總量，也要對節奏、停流時間與杯溫。
        圖也必須把這三種訊號同時展示出來。
    """
    _setup_style()

    sim = info["sim_final"]
    model_v_out = np.asarray(info.get("model_v_out_ml", sim["v_out_ml"]), dtype=float)
    model_q_out = np.asarray(info.get("model_q_out_mlps", sim["q_out_mlps"]), dtype=float)
    t_obs = np.asarray(info["t_obs_s"], dtype=float)
    v_in_obs = np.asarray(info["v_in_obs_ml"], dtype=float)
    v_out_obs = np.asarray(info["v_out_obs_ml"], dtype=float)
    fit_mask = np.asarray(info["fit_mask"], dtype=bool)
    q_obs_mlps = np.asarray(info.get("q_obs_mlps"), dtype=float)
    q_pred_obs_mlps = np.asarray(info.get("q_pred_obs_mlps"), dtype=float)
    stop_flow_time_s = float(info.get("stop_flow_time_s", sim["drain_time"]))
    bloom_end_s = float(info.get("bloom_end_s", np.nan))
    interp = interp1d(
        sim["t"], model_v_out, kind="linear",
        bounds_error=False, fill_value="extrapolate",
    )
    v_out_pred_obs = interp(t_obs)
    residual = v_out_pred_obs - v_out_obs

    fig, axes = plt.subplots(
        3, 1, figsize=(11.5, 10.2),
        gridspec_kw={"height_ratios": [3.2, 1.7, 1.5]},
    )
    pref_coeff = float(info.get("pref_flow_coeff_fit", 0.0))
    pref_open = float(info.get("pref_flow_open_rate_fixed", info.get("pref_flow_open_rate_fit", 0.0)))
    pref_tau = float(info.get("pref_flow_tau_decay_fixed", info.get("pref_flow_tau_decay_fit", 0.0)))
    _summary_band(fig, "Measured vs Fitted Outflow", [
        ("k", f"{info['k_fit']:.2e} m^2"),
        ("k_beta", f"{info['k_beta_fit']:.0f} m^-3"),
        ("tau_lag", f"{info.get('tau_lag_s', np.nan):.2f} s"),
        ("pref", f"{pref_coeff:.1e}/{pref_open:.2f}f/{pref_tau:.1f}f" if info.get("fit_preferential_flow") else "off"),
        ("V RMSE", f"{info['rmse_ml']:.1f} mL"),
        ("q RMSE", f"{info.get('velocity_rmse_mlps', np.nan):.2f} mL/s"),
        ("Cup", f"{model_v_out[-1]:.1f} mL"),
    ])

    ax = axes[0]
    ax.plot(t_obs, v_in_obs, color=PALETTE["gold"], lw=2.4, ls="--", label="Measured poured volume")
    ax.scatter(t_obs[fit_mask], v_out_obs[fit_mask], s=40, color=PALETTE["orange"],
               edgecolor="white", linewidth=0.8, zorder=4, label="Measured drained volume")
    ax.scatter(t_obs[~fit_mask], v_out_obs[~fit_mask], s=40, color=PALETTE["muted"],
               edgecolor="white", linewidth=0.8, zorder=4, label="Held-out point")
    ax.plot(sim["t"], model_v_out, color=PALETTE["blue"], lw=2.6, label="Fitted model outflow")
    _style_ax(ax, "Cumulative volume trajectories", "Volume [mL]")
    if np.isfinite(bloom_end_s):
        ax.axvline(bloom_end_s, color=PALETTE["purple"], lw=1.0, ls="--")
        ax.text(bloom_end_s, ax.get_ylim()[1], " bloom end", color=PALETTE["purple"],
                fontsize=8.2, va="top", ha="left")
    ax.axvline(stop_flow_time_s, color=PALETTE["muted"], lw=1.0, ls=":")
    ax.text(stop_flow_time_s, ax.get_ylim()[1], " visual stop", color=PALETTE["muted"],
            fontsize=8.2, va="top", ha="left")
    ax.legend(loc="upper left", ncol=2, fontsize=9)
    ax.set_xlim(left=0.0)
    ax.set_ylim(bottom=0.0)

    ax = axes[1]
    t_mid = 0.5 * (t_obs[1:] + t_obs[:-1])
    interval_fit_mask = fit_mask[1:] & fit_mask[:-1]
    ax.plot(
        sim["t"], sim["q_out_mlps"],
        color=PALETTE["blue"], lw=1.2, alpha=0.28,
        label="Model instantaneous q_out",
    )
    ax.plot(
        t_mid, q_pred_obs_mlps,
        color=PALETTE["blue"], lw=2.4,
        label="Model interval mean q_out",
    )
    ax.scatter(t_mid[interval_fit_mask], q_obs_mlps[interval_fit_mask], s=38, color=PALETTE["teal"],
               edgecolor="white", linewidth=0.8, zorder=4, label="Observed interval mean q_out")
    ax.scatter(t_mid[~interval_fit_mask], q_obs_mlps[~interval_fit_mask], s=38, color=PALETTE["muted"],
               edgecolor="white", linewidth=0.8, zorder=4, label="Held-out interval")
    _style_ax(ax, "Interval outflow-rate comparison", "Flow Rate [mL/s]")
    if np.isfinite(bloom_end_s):
        ax.axvline(bloom_end_s, color=PALETTE["purple"], lw=1.0, ls="--")
    ax.axvline(stop_flow_time_s, color=PALETTE["muted"], lw=1.0, ls=":")
    ax.legend(loc="upper left", ncol=2, fontsize=8.8)
    ax.set_xlim(left=0.0)
    ax.set_ylim(bottom=0.0)

    ax = axes[2]
    colors = np.where(fit_mask, PALETTE["red"], PALETTE["muted"])
    ax.axhline(0.0, color=PALETTE["grid"], lw=1.2)
    ax.bar(t_obs, residual, width=4.8, color=colors, alpha=0.9)
    _style_ax(ax, "Residual at observed drained-volume points", "Model - Measured [mL]")
    if np.isfinite(bloom_end_s):
        ax.axvline(bloom_end_s, color=PALETTE["purple"], lw=1.0, ls="--")
    ax.set_xlim(left=0.0)

    temp_txt = "Cup temp n/a"
    if info.get("final_cup_temp_C") is not None and info.get("mixed_cup_temp_C") is not None:
        temp_txt = (
            f"Cup temp {info['mixed_cup_temp_C']:.1f}°C"
            f" vs {info['final_cup_temp_C']:.1f}°C"
        )
    axes[2].text(
        0.995, 0.92,
        f"Drain error {info.get('drain_time_error_s', np.nan):+.2f} s\n{temp_txt}",
        transform=axes[2].transAxes,
        ha="right", va="top", fontsize=8.6, color=PALETTE["ink"],
        bbox=dict(boxstyle="round,pad=0.25", fc=PALETTE["panel"], ec=PALETTE["grid"], lw=0.8),
    )

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    _save_fig(fig, save_as, f"流動擬合對照圖已儲存至 {save_as}")


def fit_with_multi_start(
    csv_path: str | Path,
    starts: list[V60Params] | None = None,
    fit_preferential_flow: bool = True,
    pref_open_rate_fixed: float = DEFAULT_PREF_FLOW_OPEN_RATE_FIXED,
    pref_tau_decay_fixed: float = DEFAULT_PREF_FLOW_TAU_DECAY_FIXED,
    verbose: bool = True,
) -> tuple[V60Params, dict]:
    """
    Multi-start wrapper：對 N 個起點各跑一次 `fit_k_kbeta_from_flow_profile`，
    取 lowest total_loss 的結果作為 canonical fit。

    What:
        以 3 個起點（V60Params 預設、PSD-prior 起點、上次 calibrated artifact）跑
        full fit，比較 final loss，回傳最低者；info dict 多附 `multi_start_results` 欄。

    Why:
        2026-05-01 subagent (c) 審查發現 stages 1/2 loss surface 沿 ridge 因
        drain_dt 量化（已修為 sub-grid 線性插補）與其他殘餘非光滑性，依然
        對 Powell 起點敏感（k_beta basin 漂 40%）。所有 basin 的 V_RMSE 在
        量測解析度內等價，但「同一 csv 不同 caller 不同結果」會在 debug 與
        EXPERIMENT_LOG 比對時造成混淆。multi-start 以 ~3× 成本（單跑 1-3 min →
        multi 3-9 min）提供 deterministic 收斂結果。
    """
    if starts is None:
        # 預設三個起點
        starts = [V60Params()]  # V60Params 物理預設
        # 嘗試讀上一次 calibrated artifact 作 warm-start
        try:
            with Path(DEFAULT_MEASURED_FLOW_FIT_SUMMARY).open(encoding="utf-8") as f:
                last = next(csv.DictReader(f), None)
            if last is not None:
                starts.append(V60Params(
                    k=float(last.get("k_fit", V60Params().k)),
                    k_beta=float(last.get("k_beta_fit", V60Params().k_beta)),
                ))
        except (FileNotFoundError, StopIteration, ValueError):
            pass
        # PSD-prior 起點：以 V60Params() 預設、k 中位、k_beta 取 PSD prior（在 fit 中算）
        # fit_k_kbeta_from_flow_profile 會自動從 V60Params.for_roast(profile) 起；這裡用 k 中位作差異化
        starts.append(V60Params(k=5.0e-11, k_beta=2000.0))

    multi_results: list[dict] = []
    for i, p_init in enumerate(starts):
        if verbose:
            print(f"=== Multi-start fit {i+1}/{len(starts)} (k_init={p_init.k:.2e}, k_beta_init={p_init.k_beta:.0f}) ===")
        p_fit, info = fit_k_kbeta_from_flow_profile(
            csv_path=csv_path,
            params_init=p_init,
            fit_preferential_flow=fit_preferential_flow,
            pref_open_rate_fixed=pref_open_rate_fixed,
            pref_tau_decay_fixed=pref_tau_decay_fixed,
            verbose=verbose,
        )
        multi_results.append({
            "start_idx": i,
            "k_init": float(p_init.k),
            "k_beta_init": float(p_init.k_beta),
            "k_fit": float(info["k_fit"]),
            "k_beta_fit": float(info["k_beta_fit"]),
            "rmse_ml": float(info["rmse_ml"]),
            "total_loss": float(info["total_loss"]),
            "params_fit": p_fit,
            "info": info,
        })

    best = min(multi_results, key=lambda r: r["total_loss"])
    if verbose:
        print(f"\n=== Multi-start summary ===")
        for r in multi_results:
            tag = " ← winner" if r["start_idx"] == best["start_idx"] else ""
            print(f"  start {r['start_idx']}: k={r['k_fit']:.3e}, k_beta={r['k_beta_fit']:.0f}, "
                  f"V_RMSE={r['rmse_ml']:.3f}, loss={r['total_loss']:.3f}{tag}")
        ks = [r["k_fit"] for r in multi_results]
        kbs = [r["k_beta_fit"] for r in multi_results]
        print(f"  k spread: {(max(ks)/min(ks)-1)*100:.1f}%, k_beta spread: {(max(kbs)/min(kbs)-1)*100:.1f}%")

    best_info = best["info"]
    best_info["multi_start_results"] = [
        {k: v for k, v in r.items() if k not in ("params_fit", "info")}
        for r in multi_results
    ]
    best_info["multi_start_winner_idx"] = int(best["start_idx"])
    return best["params_fit"], best_info


def generate_measured_flow_fit_artifacts(
    csv_path: str | Path = DEFAULT_MEASURED_FLOW_CSV,
    plot_path: str | Path = DEFAULT_MEASURED_FLOW_FIT_PLOT,
    summary_path: str | Path = DEFAULT_MEASURED_FLOW_FIT_SUMMARY,
    fit_preferential_flow: bool = True,
    pref_open_rate_fixed: float = DEFAULT_PREF_FLOW_OPEN_RATE_FIXED,
    pref_tau_decay_fixed: float = DEFAULT_PREF_FLOW_TAU_DECAY_FIXED,
    use_multi_start: bool = True,
    verbose: bool = True,
) -> tuple[V60Params, dict]:
    """
    產生專案展示用的量測流動擬合產物（summary CSV + comparison plot）。

    What:
      1. 對量測 `V_in(t)` / `V_out(t)` 執行 `fit_k_kbeta_from_flow_profile`
         （或 `fit_with_multi_start` 若 `use_multi_start=True`）
      2. 將結果寫成 showcase 使用的 summary CSV
      3. 輸出 measured-vs-model 對照圖

    Why:
      展示頁的 lead figure 與校準摘要應和目前的正式擬合流程保持同一套參數，
      避免 code path、圖檔名稱與 README 各自漂移。
      `use_multi_start=True`（預設）以 3× 成本換取 deterministic basin 選擇
      （參見 `fit_with_multi_start` docstring）。
    """
    if use_multi_start:
        params_fit, info = fit_with_multi_start(
            csv_path=csv_path,
            fit_preferential_flow=fit_preferential_flow,
            pref_open_rate_fixed=pref_open_rate_fixed,
            pref_tau_decay_fixed=pref_tau_decay_fixed,
            verbose=verbose,
        )
    else:
        params_fit, info = fit_k_kbeta_from_flow_profile(
            csv_path=csv_path,
            fit_preferential_flow=fit_preferential_flow,
            pref_open_rate_fixed=pref_open_rate_fixed,
            pref_tau_decay_fixed=pref_tau_decay_fixed,
            verbose=verbose,
        )
    save_flow_fit_summary_csv(summary_path, info)
    plot_flow_fit_comparison(info, save_as=str(plot_path))
    return params_fit, info


def fit_measured_benchmark(
    csv_path: str | Path = DEFAULT_MEASURED_FLOW_CSV,
    plot_path: str | Path = DEFAULT_MEASURED_FLOW_FIT_PLOT,
    summary_path: str | Path = DEFAULT_MEASURED_FLOW_FIT_SUMMARY,
    fit_preferential_flow: bool = True,
    pref_open_rate_fixed: float = DEFAULT_PREF_FLOW_OPEN_RATE_FIXED,
    pref_tau_decay_fixed: float = DEFAULT_PREF_FLOW_TAU_DECAY_FIXED,
    verbose: bool = True,
) -> tuple[V60Params, dict]:
    """
    對專案的 measured benchmark case 執行正式校準並輸出展示產物。

    What:
        固定使用 `kinu29_light_20g_flow_profile.csv` 作為 benchmark case，
        跑 `k / k_beta / tau_lag + pref-flow(coeff) + server cooling` 校準，
        並輸出對應的 summary CSV 與 comparison plot。

    Why:
        需要一個穩定、可直接重跑的正式入口，讓 benchmark / regression /
        showcase 三者都引用同一套 calibrated artifact，而不是各自手動組命令。
    """
    return generate_measured_flow_fit_artifacts(
        csv_path=csv_path,
        plot_path=plot_path,
        summary_path=summary_path,
        fit_preferential_flow=fit_preferential_flow,
        pref_open_rate_fixed=pref_open_rate_fixed,
        pref_tau_decay_fixed=pref_tau_decay_fixed,
        verbose=verbose,
    )

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
    res_true = simulate_brew(true_params, protocol, t_end=180, n_eval=1000)
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
