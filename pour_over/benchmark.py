"""
benchmark.py — measured benchmark 載入與回歸檢查

What:
    提供 measured benchmark 的 state loader 與 regression gate suite。

Why:
    benchmark 是獨立於一般 sensitivity / grind analysis 的正式驗收流程，
    應有自己的模組邊界，而不是與其他分析工具混在同一檔。
"""

import csv
import dataclasses
from pathlib import Path

from .fitting import (
    DEFAULT_MEASURED_FLOW_CSV,
    DEFAULT_MEASURED_FLOW_FIT_PLOT,
    DEFAULT_MEASURED_FLOW_FIT_SUMMARY,
    evaluate_measured_flow_fit,
    fit_measured_benchmark,
)
from .measured_io import load_flow_profile_csv, _measured_setup_overrides, measured_case_psd_bins_path
from .params import V60Params, RoastProfile


def _load_measured_benchmark_state(
    csv_path: str | Path,
    summary_path: str | Path,
    *,
    refit: bool,
    verbose: bool,
) -> tuple[V60Params, dict]:
    """
    取得 measured benchmark 的目前校準狀態。

    What:
        讀取正式 measured benchmark 的 calibrated summary；若指定 `refit=True`，
        則直接重跑正式 measured benchmark fitting。

    Why:
        benchmark / identifiability 必須共用同一組 calibrated baseline，
        且不允許在 summary 缺失時默默回退到別的 code path。
    """
    flow_path = Path(csv_path) if csv_path is not None else Path(DEFAULT_MEASURED_FLOW_CSV)
    summary_csv = Path(summary_path) if summary_path is not None else Path(DEFAULT_MEASURED_FLOW_FIT_SUMMARY)

    if refit:
        return fit_measured_benchmark(
            csv_path=flow_path,
            plot_path=DEFAULT_MEASURED_FLOW_FIT_PLOT,
            summary_path=summary_csv,
            verbose=verbose,
        )
    if not summary_csv.exists():
        raise FileNotFoundError(f"缺少 calibrated summary CSV：{summary_csv}")

    prof = load_flow_profile_csv(flow_path)
    meta = prof["meta"]
    with summary_csv.open("r", encoding="utf-8", newline="") as f:
        summary = next(csv.DictReader(f))

    roast_map = {
        "light": RoastProfile.LIGHT,
        "medium": RoastProfile.MEDIUM,
        "dark": RoastProfile.DARK,
    }
    roast_key = meta["roast"].strip().lower()
    profile = roast_map.get(roast_key)
    if profile is None:
        raise ValueError(f"未知烘焙度：{meta['roast']}")

    params_base = V60Params.for_roast(profile)
    measured_overrides = _measured_setup_overrides(meta)
    measured_overrides["lambda_server_ambient"] = float(summary["server_cooling_lambda_fit"])
    bins_csv = measured_case_psd_bins_path(flow_path)
    params_fit = dataclasses.replace(
        params_base,
        dose_g=float(meta["dose_g"]),
        h_bed=float(meta["bed_height_cm"]) / 100.0,
        T_brew=float(meta["brew_temp_C"]) + 273.15,
        psd_bins_csv_path=str(bins_csv),
        k=float(summary["k_fit"]),
        k_beta=float(summary["k_beta_fit"]),
        wetbed_struct_gain=float(summary["wetbed_struct_gain_fit"]),
        wetbed_struct_rate=float(summary["wetbed_struct_rate_fixed"]),
        wetbed_impact_release_rate=float(summary["wetbed_impact_release_rate_fixed"]),
        pref_flow_coeff=float(summary["pref_flow_coeff_fit"]),
        pref_flow_open_rate=float(summary["pref_flow_open_rate_fixed"]),
        pref_flow_tau_decay=float(summary["pref_flow_tau_decay_fixed"]),
        sat_rel_perm_residual=float(summary["sat_rel_perm_residual_fit"]),
        sat_rel_perm_exp=float(summary["sat_rel_perm_exp_fit"]),
        **measured_overrides,
    )
    tau_lag_s = float(summary["tau_lag_s"])
    eval_info = evaluate_measured_flow_fit(flow_path, params_fit, tau_lag_s=tau_lag_s)
    info = {
        "csv_path": str(flow_path),
        "roast": roast_key,
        "sim_final": eval_info["sim"],
        "obs_layer": eval_info["obs_layer"],
        "rmse_ml": eval_info["volume_rmse"],
        "velocity_rmse_mlps": eval_info["velocity_rmse"],
        "drain_time_error_s": eval_info["drain_time_error_s"],
        "cup_temp_error_C": eval_info["cup_temp_error_C"],
        "final_cup_temp_C": eval_info["final_cup_temp_C"],
        "mixed_cup_temp_C": eval_info["mixed_cup_temp_C"],
        "stop_flow_time_s": eval_info["stop_flow_time_s"],
        "tau_lag_s": tau_lag_s,
        "axial_node_count": int(params_fit.axial_node_count),
        "sat_rel_perm_residual_fit": float(params_fit.sat_rel_perm_residual),
        "sat_rel_perm_exp_fit": float(params_fit.sat_rel_perm_exp),
        "k_fit": float(params_fit.k),
        "k_beta_fit": float(params_fit.k_beta),
        "wetbed_struct_gain_fit": float(params_fit.wetbed_struct_gain),
        "wetbed_struct_rate_fit": float(params_fit.wetbed_struct_rate),
        "wetbed_struct_rate_fixed": float(summary["wetbed_struct_rate_fixed"]),
        "wetbed_impact_release_rate_fixed": float(params_fit.wetbed_impact_release_rate),
        "fit_wetbed_structure": True,
        "fit_preferential_flow": summary["fit_preferential_flow"] in ("True", "true", True),
        "pref_flow_coeff_fit": float(params_fit.pref_flow_coeff),
        "pref_flow_open_rate_fit": float(params_fit.pref_flow_open_rate),
        "pref_flow_tau_decay_fit": float(params_fit.pref_flow_tau_decay),
        "pref_flow_open_rate_fixed": float(summary["pref_flow_open_rate_fixed"]),
        "pref_flow_tau_decay_fixed": float(summary["pref_flow_tau_decay_fixed"]),
        "fit_server_cooling": summary["fit_server_cooling"] in ("True", "true", True),
        "server_cooling_lambda_fit": float(summary["server_cooling_lambda_fit"]),
        "total_loss": eval_info["total_loss"],
    }
    return params_fit, info


def run_benchmark_suite(
    csv_path: str | Path | None = None,
    summary_path: str | Path | None = None,
    benchmark_csv_path: str | Path = "data/benchmark_suite_summary.csv",
    *,
    refit: bool = True,
    verbose: bool = True,
    thresholds: dict | None = None,
) -> dict:
    """
    執行專案目前的 benchmark / regression suite。

    What:
        先跑 measured benchmark fitting（或讀取現有 calibrated summary），
        再用固定門檻檢查關鍵指標是否通過，並將結果寫入 summary CSV。

    Why:
        模型越來越複雜後，不能再靠肉眼看圖判斷「這次是否真的比較好」；
        benchmark suite 是每次改物理 closure 後最基本的回歸防線。
    """
    flow_path = Path(csv_path) if csv_path is not None else Path(DEFAULT_MEASURED_FLOW_CSV)
    summary_csv = Path(summary_path) if summary_path is not None else Path(DEFAULT_MEASURED_FLOW_FIT_SUMMARY)
    bench_path = Path(benchmark_csv_path)
    params_fit, info = _load_measured_benchmark_state(
        flow_path,
        summary_csv,
        refit=refit,
        verbose=verbose,
    )

    limits = {
        "volume_rmse_max": 13.8,
        "velocity_rmse_max": 1.30,
        "drain_time_error_abs_max": 3.0,
        "cup_temp_error_abs_max": 3.5,
    }
    if thresholds is not None:
        limits.update(thresholds)

    checks = {
        "volume_rmse_pass": float(info["rmse_ml"]) <= limits["volume_rmse_max"],
        "velocity_rmse_pass": float(info["velocity_rmse_mlps"]) <= limits["velocity_rmse_max"],
        "drain_time_error_pass": abs(float(info["drain_time_error_s"])) <= limits["drain_time_error_abs_max"],
        "cup_temp_error_pass": (
            info.get("cup_temp_error_C") is None
            or abs(float(info["cup_temp_error_C"])) <= limits["cup_temp_error_abs_max"]
        ),
    }
    overall_pass = bool(all(checks.values()))

    row = {
        "case_id": "kinu29_light_20g_measured",
        "status": "PASS" if overall_pass else "FAIL",
        "csv_path": str(flow_path),
        "summary_path": str(summary_csv),
        "k_fit": float(params_fit.k),
        "k_beta_fit": float(params_fit.k_beta),
        "tau_lag_s": float(info["tau_lag_s"]),
        "axial_node_count": int(info.get("axial_node_count", getattr(params_fit, "axial_node_count", 1))),
        "sat_rel_perm_residual_fit": float(info.get("sat_rel_perm_residual_fit", getattr(params_fit, "sat_rel_perm_residual", 0.0))),
        "sat_rel_perm_exp_fit": float(info.get("sat_rel_perm_exp_fit", getattr(params_fit, "sat_rel_perm_exp", 0.0))),
        "wetbed_struct_gain_fit": float(info.get("wetbed_struct_gain_fit", 0.0)),
        "wetbed_struct_rate_fit": float(info.get("wetbed_struct_rate_fit", 0.0)),
        "wetbed_struct_rate_fixed": float(info.get("wetbed_struct_rate_fixed", info.get("wetbed_struct_rate_fit", 0.0))),
        "wetbed_impact_release_rate_fixed": float(info.get("wetbed_impact_release_rate_fixed", 0.0)),
        "fit_preferential_flow": bool(info.get("fit_preferential_flow", False)),
        "pref_flow_coeff_fit": float(info.get("pref_flow_coeff_fit", 0.0)),
        "pref_flow_open_rate_fit": float(info.get("pref_flow_open_rate_fit", 0.0)),
        "pref_flow_tau_decay_fit": float(info.get("pref_flow_tau_decay_fit", 0.0)),
        "pref_flow_open_rate_fixed": float(info.get("pref_flow_open_rate_fixed", info.get("pref_flow_open_rate_fit", 0.0))),
        "pref_flow_tau_decay_fixed": float(info.get("pref_flow_tau_decay_fixed", info.get("pref_flow_tau_decay_fit", 0.0))),
        "fit_server_cooling": bool(info.get("fit_server_cooling", False)),
        "server_cooling_lambda_fit": float(info.get("server_cooling_lambda_fit", 0.0)),
        "rmse_ml": float(info["rmse_ml"]),
        "velocity_rmse_mlps": float(info["velocity_rmse_mlps"]),
        "drain_time_error_s": float(info["drain_time_error_s"]),
        "cup_temp_error_C": info.get("cup_temp_error_C"),
        "volume_rmse_pass": checks["volume_rmse_pass"],
        "velocity_rmse_pass": checks["velocity_rmse_pass"],
        "drain_time_error_pass": checks["drain_time_error_pass"],
        "cup_temp_error_pass": checks["cup_temp_error_pass"],
    }
    bench_path.parent.mkdir(parents=True, exist_ok=True)
    with bench_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    print("\n=== Benchmark Suite ===")
    print(f"  case        : {row['case_id']}")
    print(f"  status      : {row['status']}")
    print(f"  V_out RMSE  : {row['rmse_ml']:.2f} mL   (gate {limits['volume_rmse_max']:.2f})")
    print(f"  q_out RMSE  : {row['velocity_rmse_mlps']:.2f} mL/s (gate {limits['velocity_rmse_max']:.2f})")
    print(f"  Drain error : {row['drain_time_error_s']:+.2f} s  (gate ±{limits['drain_time_error_abs_max']:.2f})")
    if row["cup_temp_error_C"] is not None:
        print(f"  Cup temp err: {row['cup_temp_error_C']:+.2f} °C (gate ±{limits['cup_temp_error_abs_max']:.2f})")
    print(f"  summary csv : {bench_path}")

    return {
        "params_fit": params_fit,
        "info": info,
        "row": row,
        "thresholds": limits,
        "benchmark_csv_path": str(bench_path),
    }
