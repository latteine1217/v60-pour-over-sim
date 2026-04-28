"""
bloom_diagnostics.py — 悶蒸期熱/流耦合診斷

What:
    將 measured thermal profile 與 calibrated simulation 對齊，輸出 0-40 s
    悶蒸期的流量、體積、熱節點與殘差。

Why:
    悶蒸期的 T1/T2 誤差不能只用單點 RMSE 判斷；必須同時看水力連通、
    apex 熱歷史與 observation layer，才知道下一個 closure 應該改在哪裡。
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np

from .benchmark import _load_measured_benchmark_state
from .fitting import evaluate_measured_thermal_profile
from .viz import PALETTE, _save_fig, _setup_style, _style_ax, _summary_band


BLOOM_DIAGNOSTIC_FIELDS = [
    "case_label",
    "time_s",
    "v_in_obs_ml",
    "server_volume_obs_ml",
    "server_volume_model_ml",
    "server_volume_residual_ml",
    "T1_obs_C",
    "T1_model_C",
    "T1_residual_C",
    "T2_obs_C",
    "T2_model_C",
    "T2_residual_C",
    "T2_used_for_fit",
    "q_in_mlps",
    "q_bed_mlps",
    "q_bed_transport_mlps",
    "q_out_mlps",
    "head_gate",
    "liq_transport_gate",
    "T_bulk_C",
    "T_effluent_C",
    "T_dripper_C",
]

H1_FLOW_TIMING_FIELDS = [
    "case_label",
    "point_count",
    "volume_t2_corr",
    "same_sign_fraction",
    "early_volume_residual_mean_ml",
    "early_t2_residual_mean_C",
    "late_volume_residual_mean_ml",
    "late_t2_residual_mean_C",
    "max_abs_volume_residual_ml",
    "max_abs_t2_residual_C",
    "h1_status",
]

H2_EFFLUENT_COUPLING_FIELDS = [
    "case_label",
    "gate_mode",
    "early_t2_rmse_C",
    "late_t2_rmse_C",
    "early_t2_mean_residual_C",
    "late_t2_mean_residual_C",
    "early_delta_vs_constant_C",
    "late_delta_vs_constant_C",
    "h2_status",
]

H3_APEX_CONTACT_FIELDS = [
    "case_label",
    "contact_mode",
    "early_t2_rmse_C",
    "late_t2_rmse_C",
    "early_t2_mean_residual_C",
    "late_t2_mean_residual_C",
    "early_delta_vs_effluent_C",
    "late_delta_vs_effluent_C",
    "h3_status",
]

H4_DUAL_PATH_FIELDS = [
    "case_label",
    "weight_mode",
    "early_t2_rmse_C",
    "late_t2_rmse_C",
    "early_t2_mean_residual_C",
    "late_t2_mean_residual_C",
    "early_delta_vs_effluent_C",
    "late_delta_vs_effluent_C",
    "h4_status",
]

H3_CONTACT_MODES = {
    "effluent": None,
    "contact_tau6_w35": {"tau_s": 6.0, "contact_weight": 0.35},
    "contact_tau12_w45": {"tau_s": 12.0, "contact_weight": 0.45},
    "contact_tau20_w55": {"tau_s": 20.0, "contact_weight": 0.55},
}


DEFAULT_BLOOM_CASES = (
    (
        "kinu28 4:20",
        Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
        Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
        Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
    ),
    (
        "kinu29 4:12",
        Path("data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv"),
        Path("data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
        Path("data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile.csv"),
    ),
    (
        "kinu29 4:11",
        Path("data/kinu_29_light/4:11/kinu29_light_20g_flow_profile.csv"),
        Path("data/kinu_29_light/4:11/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
        Path("data/kinu_29_light/4:11/kinu29_light_20g_thermal_profile.csv"),
    ),
)


def _interp_at_obs(sim: dict, key: str, t_obs: np.ndarray) -> np.ndarray:
    return np.interp(t_obs, np.asarray(sim["t"], dtype=float), np.asarray(sim[key], dtype=float))


def _finite_residual(model: float, obs: float) -> float:
    if not np.isfinite(obs):
        return float("nan")
    return float(model - obs)


def build_bloom_diagnostic(
    label: str,
    flow_csv: str | Path,
    summary_csv: str | Path,
    thermal_csv: str | Path,
    *,
    bloom_end_s: float = 40.0,
) -> dict:
    """
    建立單一 measured case 的悶蒸期診斷表。

    What:
        以 thermal profile 的觀測時間為索引，對齊 model flow/thermal states。

    Why:
        這讓 bloom 期間的熱殘差可以直接和 `q_bed_transport`、`head_gate`
        等水力連通性指標一起判讀。
    """
    params, state = _load_measured_benchmark_state(
        flow_csv,
        summary_csv,
        refit=False,
        verbose=False,
    )
    thermal = evaluate_measured_thermal_profile(
        thermal_csv,
        params,
        tau_lag_s=float(state["tau_lag_s"]),
    )
    t_obs = np.asarray(thermal["t_obs_s"], dtype=float)
    bloom_mask = t_obs <= float(bloom_end_s)
    sim = thermal["sim"]

    interp = {
        "q_in_mlps": _interp_at_obs(sim, "q_in_mlps", t_obs),
        "q_bed_mlps": _interp_at_obs(sim, "q_bed_mlps", t_obs),
        "q_bed_transport_mlps": _interp_at_obs(sim, "q_bed_transport_mlps", t_obs),
        "q_out_mlps": _interp_at_obs(sim, "q_out_mlps", t_obs),
        "head_gate": _interp_at_obs(sim, "head_gate", t_obs),
        "liq_transport_gate": _interp_at_obs(sim, "liq_transport_gate", t_obs),
        "T_bulk_C": _interp_at_obs(sim, "T_C", t_obs),
        "T_effluent_C": _interp_at_obs(sim, "T_effluent_C", t_obs),
        "T_dripper_C": _interp_at_obs(sim, "T_dripper_C", t_obs),
    }

    rows = []
    for idx in np.where(bloom_mask)[0]:
        server_obs = float(thermal["estimated_server_volume_ml"][idx])
        server_model = float(thermal["model_server_volume_ml"][idx])
        t1_obs = float(thermal["server_temp_obs_C"][idx])
        t1_model = float(thermal["model_server_temp_C"][idx])
        t2_obs = float(thermal["outflow_temp_obs_C"][idx])
        t2_model = float(thermal["model_outflow_temp_C"][idx])
        rows.append({
            "case_label": label,
            "time_s": float(t_obs[idx]),
            "v_in_obs_ml": float(thermal["v_in_obs_ml"][idx]),
            "server_volume_obs_ml": server_obs,
            "server_volume_model_ml": server_model,
            "server_volume_residual_ml": _finite_residual(server_model, server_obs),
            "T1_obs_C": t1_obs,
            "T1_model_C": t1_model,
            "T1_residual_C": _finite_residual(t1_model, t1_obs),
            "T2_obs_C": t2_obs,
            "T2_model_C": t2_model,
            "T2_residual_C": _finite_residual(t2_model, t2_obs),
            "T2_used_for_fit": bool(thermal["outflow_temp_fit_mask"][idx]),
            "q_in_mlps": float(interp["q_in_mlps"][idx]),
            "q_bed_mlps": float(interp["q_bed_mlps"][idx]),
            "q_bed_transport_mlps": float(interp["q_bed_transport_mlps"][idx]),
            "q_out_mlps": float(interp["q_out_mlps"][idx]),
            "head_gate": float(interp["head_gate"][idx]),
            "liq_transport_gate": float(interp["liq_transport_gate"][idx]),
            "T_bulk_C": float(interp["T_bulk_C"][idx]),
            "T_effluent_C": float(interp["T_effluent_C"][idx]),
            "T_dripper_C": float(interp["T_dripper_C"][idx]),
        })

    return {
        "label": label,
        "flow_csv": str(flow_csv),
        "summary_csv": str(summary_csv),
        "thermal_csv": str(thermal_csv),
        "bloom_end_s": float(bloom_end_s),
        "thermal": thermal,
        "rows": rows,
    }


def save_bloom_diagnostics_csv(report: dict, csv_path: str | Path) -> None:
    out = Path(csv_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BLOOM_DIAGNOSTIC_FIELDS)
        writer.writeheader()
        writer.writerows(report["rows"])


def _safe_corr(x: np.ndarray, y: np.ndarray) -> float:
    valid = np.isfinite(x) & np.isfinite(y)
    if int(valid.sum()) < 3:
        return float("nan")
    x_valid = x[valid]
    y_valid = y[valid]
    if float(np.std(x_valid)) <= 1e-12 or float(np.std(y_valid)) <= 1e-12:
        return float("nan")
    return float(np.corrcoef(x_valid, y_valid)[0, 1])


def _same_sign_fraction(x: np.ndarray, y: np.ndarray, *, eps: float = 1e-9) -> float:
    valid = np.isfinite(x) & np.isfinite(y) & (np.abs(x) > eps) & (np.abs(y) > eps)
    if not np.any(valid):
        return float("nan")
    return float(np.mean(np.sign(x[valid]) == np.sign(y[valid])))


def _mean_window(rows: list[dict], key: str, t_min: float, t_max: float) -> float:
    vals = [
        float(row[key])
        for row in rows
        if t_min <= float(row["time_s"]) <= t_max and np.isfinite(float(row[key]))
    ]
    return float(np.mean(vals)) if vals else float("nan")


def _h1_status(corr: float, same_sign: float, early_vol: float, early_t2: float, late_vol: float, late_t2: float) -> str:
    """
    以保守規則判斷 H1 是否成立。

    What:
        H1 主張 flow / observation timing 主導 T2 residual，因此 volume residual
        與 T2 residual 應在悶蒸期呈現一致方向或明確同步。

    Why:
        若 T2 residual 在 volume residual 維持同方向時自行變號，代表熱接觸歷史
        不能被單純 flow timing 解釋，只能標為 partial 或 not_supported。
    """
    early_same = (
        np.isfinite(early_vol)
        and np.isfinite(early_t2)
        and abs(early_vol) > 1.0
        and abs(early_t2) > 2.0
        and np.sign(early_vol) == np.sign(early_t2)
    )
    late_same = (
        np.isfinite(late_vol)
        and np.isfinite(late_t2)
        and abs(late_vol) > 1.0
        and abs(late_t2) > 2.0
        and np.sign(late_vol) == np.sign(late_t2)
    )
    strong_sync = (
        np.isfinite(corr)
        and corr >= 0.60
        and np.isfinite(same_sign)
        and same_sign >= 0.65
    )
    partial_sync = (
        (np.isfinite(corr) and corr >= 0.30)
        or (np.isfinite(same_sign) and same_sign >= 0.45)
        or early_same
        or late_same
    )
    if strong_sync and early_same and late_same:
        return "supported"
    if partial_sync:
        return "partial"
    return "not_supported"


def analyze_h1_flow_timing(reports: Iterable[dict]) -> dict:
    """
    分析 H1：悶蒸期 flow / observation timing 是否主導 T2 residual。

    What:
        對每個 case 計算 server-volume residual 與 T2 residual 的相關性、同號率，
        並拆成早段 `10-20 s` 與後段 `25-40 s` 平均方向。

    Why:
        若 H1 成立，T2 residual 應主要跟 server-volume timing error 同步；
        若不同步，下一步應轉向 apex thermal coupling 或 contact-history closure。
    """
    case_results = []
    for report in reports:
        rows = list(report["rows"])
        used = [row for row in rows if bool(row.get("T2_used_for_fit", False))]
        if not used:
            used = rows
        volume_res = np.asarray([float(row["server_volume_residual_ml"]) for row in used], dtype=float)
        t2_res = np.asarray([float(row["T2_residual_C"]) for row in used], dtype=float)
        corr = _safe_corr(volume_res, t2_res)
        same_sign = _same_sign_fraction(volume_res, t2_res)
        early_vol = _mean_window(used, "server_volume_residual_ml", 10.0, 20.0)
        early_t2 = _mean_window(used, "T2_residual_C", 10.0, 20.0)
        late_vol = _mean_window(used, "server_volume_residual_ml", 25.0, 40.0)
        late_t2 = _mean_window(used, "T2_residual_C", 25.0, 40.0)
        status = _h1_status(corr, same_sign, early_vol, early_t2, late_vol, late_t2)
        case_results.append({
            "case_label": report["label"],
            "point_count": len(used),
            "volume_t2_corr": corr,
            "same_sign_fraction": same_sign,
            "early_volume_residual_mean_ml": early_vol,
            "early_t2_residual_mean_C": early_t2,
            "late_volume_residual_mean_ml": late_vol,
            "late_t2_residual_mean_C": late_t2,
            "max_abs_volume_residual_ml": float(np.nanmax(np.abs(volume_res))) if volume_res.size else float("nan"),
            "max_abs_t2_residual_C": float(np.nanmax(np.abs(t2_res))) if t2_res.size else float("nan"),
            "h1_status": status,
        })

    supported = sum(row["h1_status"] == "supported" for row in case_results)
    partial = sum(row["h1_status"] == "partial" for row in case_results)
    if case_results and supported == len(case_results):
        overall = "supported"
    elif supported or partial:
        overall = "partial"
    else:
        overall = "not_supported"
    return {"overall_status": overall, "case_results": case_results}


def save_h1_flow_timing_summary_csv(summary: dict, csv_path: str | Path) -> None:
    out = Path(csv_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=H1_FLOW_TIMING_FIELDS)
        writer.writeheader()
        writer.writerows(summary["case_results"])


def _rmse_window(rows: list[dict], key: str, t_min: float, t_max: float) -> float:
    vals = [
        float(row[key])
        for row in rows
        if t_min <= float(row["time_s"]) <= t_max
        and bool(row.get("T2_used_for_fit", True))
        and np.isfinite(float(row[key]))
    ]
    return float(np.sqrt(np.mean(np.square(vals)))) if vals else float("nan")


def _build_bloom_diagnostic_with_params(
    label: str,
    thermal_csv: str | Path,
    params,
    tau_lag_s: float,
    *,
    bloom_end_s: float,
) -> dict:
    thermal = evaluate_measured_thermal_profile(
        thermal_csv,
        params,
        tau_lag_s=float(tau_lag_s),
    )
    t_obs = np.asarray(thermal["t_obs_s"], dtype=float)
    bloom_mask = t_obs <= float(bloom_end_s)
    sim = thermal["sim"]
    interp = {
        "q_in_mlps": _interp_at_obs(sim, "q_in_mlps", t_obs),
        "q_bed_mlps": _interp_at_obs(sim, "q_bed_mlps", t_obs),
        "q_bed_transport_mlps": _interp_at_obs(sim, "q_bed_transport_mlps", t_obs),
        "q_out_mlps": _interp_at_obs(sim, "q_out_mlps", t_obs),
        "head_gate": _interp_at_obs(sim, "head_gate", t_obs),
        "liq_transport_gate": _interp_at_obs(sim, "liq_transport_gate", t_obs),
        "T_bulk_C": _interp_at_obs(sim, "T_C", t_obs),
        "T_effluent_C": _interp_at_obs(sim, "T_effluent_C", t_obs),
        "T_dripper_C": _interp_at_obs(sim, "T_dripper_C", t_obs),
    }
    rows = []
    for idx in np.where(bloom_mask)[0]:
        server_obs = float(thermal["estimated_server_volume_ml"][idx])
        server_model = float(thermal["model_server_volume_ml"][idx])
        t1_obs = float(thermal["server_temp_obs_C"][idx])
        t1_model = float(thermal["model_server_temp_C"][idx])
        t2_obs = float(thermal["outflow_temp_obs_C"][idx])
        t2_model = float(thermal["model_outflow_temp_C"][idx])
        rows.append({
            "case_label": label,
            "time_s": float(t_obs[idx]),
            "v_in_obs_ml": float(thermal["v_in_obs_ml"][idx]),
            "server_volume_obs_ml": server_obs,
            "server_volume_model_ml": server_model,
            "server_volume_residual_ml": _finite_residual(server_model, server_obs),
            "T1_obs_C": t1_obs,
            "T1_model_C": t1_model,
            "T1_residual_C": _finite_residual(t1_model, t1_obs),
            "T2_obs_C": t2_obs,
            "T2_model_C": t2_model,
            "T2_residual_C": _finite_residual(t2_model, t2_obs),
            "T2_used_for_fit": bool(thermal["outflow_temp_fit_mask"][idx]),
            "q_in_mlps": float(interp["q_in_mlps"][idx]),
            "q_bed_mlps": float(interp["q_bed_mlps"][idx]),
            "q_bed_transport_mlps": float(interp["q_bed_transport_mlps"][idx]),
            "q_out_mlps": float(interp["q_out_mlps"][idx]),
            "head_gate": float(interp["head_gate"][idx]),
            "liq_transport_gate": float(interp["liq_transport_gate"][idx]),
            "T_bulk_C": float(interp["T_bulk_C"][idx]),
            "T_effluent_C": float(interp["T_effluent_C"][idx]),
            "T_dripper_C": float(interp["T_dripper_C"][idx]),
        })
    return {"label": label, "thermal_csv": str(thermal_csv), "thermal": thermal, "rows": rows}


def _h2_status(early_delta: float, late_delta: float, gate_mode: str) -> str:
    if gate_mode == "constant":
        return "baseline"
    early_better = np.isfinite(early_delta) and early_delta <= -1.0
    late_not_bad = (not np.isfinite(late_delta)) or late_delta <= 1.0
    late_bad = np.isfinite(late_delta) and late_delta > 1.0
    if early_better and late_not_bad:
        return "supported"
    if early_better or late_bad:
        return "partial"
    return "not_supported"


def analyze_h2_effluent_coupling(
    *,
    cases: Iterable[tuple[str, Path, Path, Path]] = DEFAULT_BLOOM_CASES,
    gate_modes: Iterable[str] = ("constant", "liq_transport_gate", "head_gate"),
    bloom_end_s: float = 40.0,
) -> dict:
    """
    分析 H2：bulk-effluent 熱耦合常開是否造成 bloom early apex 過熱。

    What:
        固定 fitted hydraulic/extraction params，只替換 `effluent_coupling_gate_mode`
        做 counterfactual closure test。

    Why:
        若 gated exchange 能降低 `10-20 s` T2 RMSE 且不惡化 `25-40 s`，
        才能說 H2 支持；否則應進一步檢查 H3 apex/contact history。
    """
    case_results = []
    gate_modes = tuple(gate_modes)
    for label, flow_csv, summary_csv, thermal_csv in cases:
        params, state = _load_measured_benchmark_state(flow_csv, summary_csv, refit=False, verbose=False)
        baseline_early = None
        baseline_late = None
        for mode in gate_modes:
            trial_params = dataclasses.replace(params, effluent_coupling_gate_mode=mode)
            report = _build_bloom_diagnostic_with_params(
                label,
                thermal_csv,
                trial_params,
                tau_lag_s=float(state["tau_lag_s"]),
                bloom_end_s=bloom_end_s,
            )
            rows = report["rows"]
            early_rmse = _rmse_window(rows, "T2_residual_C", 10.0, 20.0)
            late_rmse = _rmse_window(rows, "T2_residual_C", 25.0, 40.0)
            early_mean = _mean_window(rows, "T2_residual_C", 10.0, 20.0)
            late_mean = _mean_window(rows, "T2_residual_C", 25.0, 40.0)
            if mode == "constant":
                baseline_early = early_rmse
                baseline_late = late_rmse
            early_delta = float("nan") if baseline_early is None else float(early_rmse - baseline_early)
            late_delta = float("nan") if baseline_late is None else float(late_rmse - baseline_late)
            case_results.append({
                "case_label": label,
                "gate_mode": mode,
                "early_t2_rmse_C": early_rmse,
                "late_t2_rmse_C": late_rmse,
                "early_t2_mean_residual_C": early_mean,
                "late_t2_mean_residual_C": late_mean,
                "early_delta_vs_constant_C": early_delta,
                "late_delta_vs_constant_C": late_delta,
                "h2_status": _h2_status(early_delta, late_delta, mode),
            })
    tested = [row for row in case_results if row["gate_mode"] != "constant"]
    supported = sum(row["h2_status"] == "supported" for row in tested)
    partial = sum(row["h2_status"] == "partial" for row in tested)
    if tested and supported == len(tested):
        overall = "supported"
    elif supported or partial:
        overall = "partial"
    else:
        overall = "not_supported"
    return {"overall_status": overall, "case_results": case_results}


def save_h2_effluent_coupling_summary_csv(summary: dict, csv_path: str | Path) -> None:
    out = Path(csv_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=H2_EFFLUENT_COUPLING_FIELDS)
        writer.writeheader()
        writer.writerows(summary["case_results"])


def _contact_history_t2_model(rows: list[dict], contact_mode: str) -> np.ndarray:
    if contact_mode not in H3_CONTACT_MODES:
        raise ValueError(f"未知 H3 contact_mode：{contact_mode}")
    t = np.asarray([float(row["time_s"]) for row in rows], dtype=float)
    effluent = np.asarray([float(row["T_effluent_C"]) for row in rows], dtype=float)
    if contact_mode == "effluent":
        return effluent.copy()

    spec = H3_CONTACT_MODES[contact_mode]
    assert spec is not None
    dripper = np.asarray([float(row["T_dripper_C"]) for row in rows], dtype=float)
    tau_s = float(spec["tau_s"])
    contact_weight = float(spec["contact_weight"])
    target = (1.0 - contact_weight) * effluent + contact_weight * dripper
    observed = np.empty_like(target)
    observed[0] = target[0]
    for idx in range(1, target.size):
        dt = max(float(t[idx] - t[idx - 1]), 0.0)
        alpha = 1.0 - np.exp(-dt / max(tau_s, 1e-9))
        observed[idx] = observed[idx - 1] + alpha * (target[idx] - observed[idx - 1])
    return observed


def _rows_with_t2_model(rows: list[dict], model_t2: np.ndarray) -> list[dict]:
    out = []
    for row, t2_model in zip(rows, model_t2):
        updated = dict(row)
        obs = float(updated["T2_obs_C"])
        updated["T2_model_C"] = float(t2_model)
        updated["T2_residual_C"] = _finite_residual(float(t2_model), obs)
        out.append(updated)
    return out


def _h3_status(early_delta: float, late_delta: float, contact_mode: str) -> str:
    if contact_mode == "effluent":
        return "baseline"
    early_better = np.isfinite(early_delta) and early_delta <= -1.0
    late_not_bad = (not np.isfinite(late_delta)) or late_delta <= 1.0
    late_bad = np.isfinite(late_delta) and late_delta > 1.0
    if early_better and late_not_bad:
        return "supported"
    if early_better and late_bad:
        return "partial"
    return "not_supported"


def analyze_h3_apex_contact_history(
    reports: Iterable[dict],
    *,
    contact_modes: Iterable[str] = ("effluent", "contact_tau6_w35", "contact_tau12_w45", "contact_tau20_w55"),
) -> dict:
    """
    分析 H3：T2 是否更像 apex/filter contact-history observation。

    What:
        不改主 ODE，只把 `T_effluent` 經過固定 contact-memory observation
        counterfactual 後，再比較 bloom early/late T2 residual。

    Why:
        H1/H2 未能解釋 early overheating 時，下一個最小假說是：
        `T2` 量到的不是瞬時 effluent，而是 apex 濾紙/濾杯接觸區的熱歷史。
    """
    case_results = []
    contact_modes = tuple(contact_modes)
    for report in reports:
        rows = list(report["rows"])
        baseline_early = None
        baseline_late = None
        for mode in contact_modes:
            model_t2 = _contact_history_t2_model(rows, mode)
            trial_rows = _rows_with_t2_model(rows, model_t2)
            early_rmse = _rmse_window(trial_rows, "T2_residual_C", 10.0, 20.0)
            late_rmse = _rmse_window(trial_rows, "T2_residual_C", 25.0, 40.0)
            early_mean = _mean_window(trial_rows, "T2_residual_C", 10.0, 20.0)
            late_mean = _mean_window(trial_rows, "T2_residual_C", 25.0, 40.0)
            if mode == "effluent":
                baseline_early = early_rmse
                baseline_late = late_rmse
            early_delta = float("nan") if baseline_early is None else float(early_rmse - baseline_early)
            late_delta = float("nan") if baseline_late is None else float(late_rmse - baseline_late)
            case_results.append({
                "case_label": report["label"],
                "contact_mode": mode,
                "early_t2_rmse_C": early_rmse,
                "late_t2_rmse_C": late_rmse,
                "early_t2_mean_residual_C": early_mean,
                "late_t2_mean_residual_C": late_mean,
                "early_delta_vs_effluent_C": early_delta,
                "late_delta_vs_effluent_C": late_delta,
                "h3_status": _h3_status(early_delta, late_delta, mode),
            })
    tested = [row for row in case_results if row["contact_mode"] != "effluent"]
    supported = sum(row["h3_status"] == "supported" for row in tested)
    partial = sum(row["h3_status"] == "partial" for row in tested)
    if tested and supported == len(tested):
        overall = "supported"
    elif supported or partial:
        overall = "partial"
    else:
        overall = "not_supported"
    return {"overall_status": overall, "case_results": case_results}


def save_h3_apex_contact_summary_csv(summary: dict, csv_path: str | Path) -> None:
    out = Path(csv_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=H3_APEX_CONTACT_FIELDS)
        writer.writeheader()
        writer.writerows(summary["case_results"])


def _normalized_q_transport_weight(rows: list[dict]) -> np.ndarray:
    q = np.asarray([max(float(row["q_bed_transport_mlps"]), 0.0) for row in rows], dtype=float)
    q_ref = float(np.nanpercentile(q, 90)) if q.size else 0.0
    if q_ref <= 1e-12:
        return np.zeros_like(q)
    return np.clip(q / q_ref, 0.0, 1.0)


def _dual_path_weight(rows: list[dict], weight_mode: str) -> np.ndarray:
    if weight_mode == "effluent":
        return np.ones(len(rows), dtype=float)
    if weight_mode == "liq_transport_gate":
        vals = [float(row["liq_transport_gate"]) for row in rows]
        return np.clip(np.asarray(vals, dtype=float), 0.0, 1.0)
    if weight_mode == "head_gate":
        vals = [float(row["head_gate"]) for row in rows]
        return np.clip(np.asarray(vals, dtype=float), 0.0, 1.0)
    if weight_mode == "q_bed_transport_norm":
        return _normalized_q_transport_weight(rows)
    if weight_mode == "liq_transport_release_after25":
        vals = [float(row["liq_transport_gate"]) for row in rows]
        base = np.clip(np.asarray(vals, dtype=float), 0.0, 1.0)
        t = np.asarray([float(row["time_s"]) for row in rows], dtype=float)
        # bloom 後段或第二段注水前後，側邊 contact-cooled path 應逐步退場。
        release = 1.0 / (1.0 + np.exp(-(t - 25.0) / 3.0))
        return np.maximum(base, release)
    if weight_mode == "liq_transport_release_on_pour":
        vals = [float(row["liq_transport_gate"]) for row in rows]
        base = np.clip(np.asarray(vals, dtype=float), 0.0, 1.0)
        t = np.asarray([float(row["time_s"]) for row in rows], dtype=float)
        release_t = _release_event_time_s(rows)
        release = 1.0 / (1.0 + np.exp(-(t - release_t) / 3.0))
        return np.maximum(base, release)
    if weight_mode == "liq_transport_release_between_pours":
        vals = [float(row["liq_transport_gate"]) for row in rows]
        base = np.clip(np.asarray(vals, dtype=float), 0.0, 1.0)
        t = np.asarray([float(row["time_s"]) for row in rows], dtype=float)
        release_t = _between_pours_release_time_s(rows)
        release = 1.0 / (1.0 + np.exp(-(t - release_t) / 3.0))
        return np.maximum(base, release)
    raise ValueError(f"未知 H4 weight_mode：{weight_mode}")


def _release_event_time_s(rows: list[dict]) -> float:
    """
    以 recipe/flow event 決定 contact path 退場時間。

    What:
        優先找第二段注水開始；若資料解析度下沒有清楚第二段注水，
        改找 `25 s` 後 `q_bed_transport` 回升作為 flow-regime transition。

    Why:
        H4b 的固定 `25 s` 只適合診斷；正式候選必須綁到 recipe/flow event，
        否則不同 recipe 會被硬編碼時間誤導。
    """
    t = np.asarray([float(row["time_s"]) for row in rows], dtype=float)
    q_in = np.asarray([max(float(row["q_in_mlps"]), 0.0) for row in rows], dtype=float)
    if q_in.size:
        q_threshold = max(0.25, 0.10 * float(np.nanmax(q_in)))
        pouring = q_in >= q_threshold
        starts = np.where(pouring & np.concatenate(([True], ~pouring[:-1])))[0]
        if starts.size >= 2:
            return float(t[starts[1]])

    q_transport = np.asarray([max(float(row["q_bed_transport_mlps"]), 0.0) for row in rows], dtype=float)
    late = np.where(t >= 25.0)[0]
    if late.size >= 2:
        q_late = q_transport[late]
        q_threshold = max(0.05, 0.25 * float(np.nanmax(q_late)))
        hits = late[np.where(q_late >= q_threshold)[0]]
        if hits.size:
            return float(t[hits[0]])
    return 25.0


def _pour_segments(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = np.asarray([float(row["time_s"]) for row in rows], dtype=float)
    q_in = np.asarray([max(float(row["q_in_mlps"]), 0.0) for row in rows], dtype=float)
    if q_in.size == 0:
        return t, np.array([], dtype=int), np.array([], dtype=int)
    q_threshold = max(0.25, 0.10 * float(np.nanmax(q_in)))
    pouring = q_in >= q_threshold
    starts = np.where(pouring & np.concatenate(([True], ~pouring[:-1])))[0]
    ends = np.where(pouring & np.concatenate((~pouring[1:], [True])))[0]
    return t, starts, ends


def _between_pours_release_time_s(rows: list[dict]) -> float:
    """
    以 recipe event 決定 bloom contact path 退場中點。

    What:
        偵測第一段注水結束與第二段注水開始，取兩者中點作為 release center。

    Why:
        側邊滲流/接觸冷卻不應等到第二段注水才消失；在兩段注水間的
        drawdown transition，fast path 權重應逐步回升。
    """
    t, starts, ends = _pour_segments(rows)
    if starts.size >= 2 and ends.size >= 1:
        first_end = float(t[ends[0]])
        second_start = float(t[starts[1]])
        if second_start > first_end:
            return 0.5 * (first_end + second_start)
    return _release_event_time_s(rows)


def _h4_status(early_delta: float, late_delta: float, weight_mode: str) -> str:
    if weight_mode == "effluent":
        return "baseline"
    early_better = np.isfinite(early_delta) and early_delta <= -1.0
    late_not_bad = (not np.isfinite(late_delta)) or late_delta <= 1.0
    late_bad = np.isfinite(late_delta) and late_delta > 1.0
    if early_better and late_not_bad:
        return "supported"
    if early_better and late_bad:
        return "partial"
    return "not_supported"


def analyze_h4_dual_path_apex_mixing(
    reports: Iterable[dict],
    *,
    weight_modes: Iterable[str] = (
        "effluent",
        "liq_transport_gate",
        "liq_transport_release_after25",
        "liq_transport_release_on_pour",
        "liq_transport_release_between_pours",
        "head_gate",
        "q_bed_transport_norm",
    ),
) -> dict:
    """
    分析 H4：T2 是否為 fast effluent path 與 contact-cooled path 的混合觀測。

    What:
        fast path 使用目前 `T_effluent`；contact path 使用 H3 中較保守的
        `contact_tau6_w35`。混合權重只取自現有水力狀態，不做 fitting。

    Why:
        使用者描述 bloom 時同時存在向下穿透通道與側邊緩慢滲出；
        單一路徑 contact memory 會打壞 late/fast cases，因此需檢查 dual-path。
    """
    case_results = []
    weight_modes = tuple(weight_modes)
    for report in reports:
        rows = list(report["rows"])
        fast = _contact_history_t2_model(rows, "effluent")
        contact = _contact_history_t2_model(rows, "contact_tau6_w35")
        baseline_early = None
        baseline_late = None
        for mode in weight_modes:
            w_fast = _dual_path_weight(rows, mode)
            model_t2 = w_fast * fast + (1.0 - w_fast) * contact
            trial_rows = _rows_with_t2_model(rows, model_t2)
            early_rmse = _rmse_window(trial_rows, "T2_residual_C", 10.0, 20.0)
            late_rmse = _rmse_window(trial_rows, "T2_residual_C", 25.0, 40.0)
            early_mean = _mean_window(trial_rows, "T2_residual_C", 10.0, 20.0)
            late_mean = _mean_window(trial_rows, "T2_residual_C", 25.0, 40.0)
            if mode == "effluent":
                baseline_early = early_rmse
                baseline_late = late_rmse
            early_delta = float("nan") if baseline_early is None else float(early_rmse - baseline_early)
            late_delta = float("nan") if baseline_late is None else float(late_rmse - baseline_late)
            case_results.append({
                "case_label": report["label"],
                "weight_mode": mode,
                "early_t2_rmse_C": early_rmse,
                "late_t2_rmse_C": late_rmse,
                "early_t2_mean_residual_C": early_mean,
                "late_t2_mean_residual_C": late_mean,
                "early_delta_vs_effluent_C": early_delta,
                "late_delta_vs_effluent_C": late_delta,
                "h4_status": _h4_status(early_delta, late_delta, mode),
            })
    tested = [row for row in case_results if row["weight_mode"] != "effluent"]
    supported = sum(row["h4_status"] == "supported" for row in tested)
    partial = sum(row["h4_status"] == "partial" for row in tested)
    if tested and supported == len(tested):
        overall = "supported"
    elif supported or partial:
        overall = "partial"
    else:
        overall = "not_supported"
    return {"overall_status": overall, "case_results": case_results}


def save_h4_dual_path_summary_csv(summary: dict, csv_path: str | Path) -> None:
    out = Path(csv_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=H4_DUAL_PATH_FIELDS)
        writer.writeheader()
        writer.writerows(summary["case_results"])


def plot_bloom_thermal_flow_diagnostics(
    reports: Iterable[dict],
    save_as: str | Path = "data/bloom_thermal_flow_diagnostics.png",
) -> None:
    """
    繪製跨 case 的悶蒸期 thermal-flow diagnostic。

    What:
        同圖比較 bloom 期間的 server volume residual、T2 residual、水力連通與熱節點。

    Why:
        若 T2 殘差與 volume residual 同步，優先懷疑 flow/observation；
        若 T2 殘差與低連通 gate 同步，才值得改 apex thermal coupling。
    """
    reports = list(reports)
    _setup_style()
    fig, axes = plt.subplots(4, 1, figsize=(11.5, 12.5), sharex=True)
    colors = [PALETTE["teal"], PALETTE["orange"], PALETTE["purple"], PALETTE["blue"]]

    _summary_band(fig, "Bloom Thermal-Flow Diagnostics", [
        ("Window", "0-40 s"),
        ("Cases", str(len(reports))),
        ("Thermal", "T2 apex residual"),
        ("Flow", "server volume residual"),
    ])

    for idx, report in enumerate(reports):
        rows = report["rows"]
        if not rows:
            continue
        color = colors[idx % len(colors)]
        label = report["label"]
        t = np.asarray([row["time_s"] for row in rows], dtype=float)
        vol_res = np.asarray([row["server_volume_residual_ml"] for row in rows], dtype=float)
        t2_res = np.asarray([row["T2_residual_C"] for row in rows], dtype=float)
        q_transport = np.asarray([row["q_bed_transport_mlps"] for row in rows], dtype=float)
        head_gate = np.asarray([row["head_gate"] for row in rows], dtype=float)
        liq_gate = np.asarray([row["liq_transport_gate"] for row in rows], dtype=float)
        t_bulk = np.asarray([row["T_bulk_C"] for row in rows], dtype=float)
        t_eff = np.asarray([row["T_effluent_C"] for row in rows], dtype=float)
        t_drip = np.asarray([row["T_dripper_C"] for row in rows], dtype=float)

        axes[0].plot(t, vol_res, lw=2.0, color=color, label=label)
        axes[1].plot(t, t2_res, lw=2.0, color=color, label=label)
        axes[2].plot(t, q_transport, lw=2.0, color=color, label=f"{label} transport")
        axes[2].plot(t, head_gate, lw=1.1, color=color, alpha=0.55, ls="--")
        axes[2].plot(t, liq_gate, lw=1.1, color=color, alpha=0.55, ls=":")
        axes[3].plot(t, t_bulk, lw=1.6, color=color, alpha=0.55, ls="--")
        axes[3].plot(t, t_eff, lw=2.0, color=color, label=f"{label} effluent")
        axes[3].plot(t, t_drip, lw=1.3, color=color, alpha=0.45, ls=":")

    axes[0].axhline(0.0, color=PALETTE["grid"], lw=1.2)
    _style_ax(axes[0], "Server volume residual", "Model - Measured [mL]")
    axes[0].legend(loc="best", fontsize=8.5, ncol=3)

    axes[1].axhline(0.0, color=PALETTE["grid"], lw=1.2)
    _style_ax(axes[1], "T2 apex temperature residual", "Model - Measured [C]")
    axes[1].legend(loc="best", fontsize=8.5, ncol=3)

    _style_ax(axes[2], "Hydraulic connectivity", "mL/s or gate [-]")
    axes[2].legend(loc="best", fontsize=8.0, ncol=2)

    _style_ax(axes[3], "Thermal states", "Temperature [C]")
    axes[3].set_xlabel("Time [s]")
    axes[3].legend(loc="best", fontsize=8.0, ncol=2)
    axes[3].set_xlim(0.0, 40.0)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    _save_fig(fig, str(save_as), f"悶蒸期熱/流診斷圖已儲存至 {save_as}")


def generate_default_bloom_diagnostics(
    *,
    bloom_end_s: float = 40.0,
    plot_path: str | Path = "data/bloom_thermal_flow_diagnostics.png",
) -> list[dict]:
    reports = [
        build_bloom_diagnostic(label, flow_csv, summary_csv, thermal_csv, bloom_end_s=bloom_end_s)
        for label, flow_csv, summary_csv, thermal_csv in DEFAULT_BLOOM_CASES
    ]
    for report in reports:
        thermal_path = Path(report["thermal_csv"])
        csv_path = thermal_path.with_name(thermal_path.stem.replace("_thermal_profile", "_bloom_thermal_flow_diagnostics") + ".csv")
        save_bloom_diagnostics_csv(report, csv_path)
    h1_summary = analyze_h1_flow_timing(reports)
    save_h1_flow_timing_summary_csv(h1_summary, "data/bloom_h1_flow_timing_summary.csv")
    h2_summary = analyze_h2_effluent_coupling(cases=DEFAULT_BLOOM_CASES, bloom_end_s=bloom_end_s)
    save_h2_effluent_coupling_summary_csv(h2_summary, "data/bloom_h2_effluent_coupling_summary.csv")
    h3_summary = analyze_h3_apex_contact_history(reports)
    save_h3_apex_contact_summary_csv(h3_summary, "data/bloom_h3_apex_contact_summary.csv")
    h4_summary = analyze_h4_dual_path_apex_mixing(reports)
    save_h4_dual_path_summary_csv(h4_summary, "data/bloom_h4_dual_path_apex_summary.csv")
    plot_bloom_thermal_flow_diagnostics(reports, save_as=plot_path)
    return reports


def main() -> None:
    generate_default_bloom_diagnostics()


if __name__ == "__main__":
    main()
