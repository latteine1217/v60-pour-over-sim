"""
identifiability.py — measured benchmark 局部可識別性分析

What:
    提供主水力 closure 與 preferential-flow closure 的 local identifiability 掃描。

Why:
    這些分析直接依賴 measured benchmark baseline，應從一般 analysis 工具中抽離，
    讓 benchmark / identifiability 形成同一條正式驗證線。
"""

import csv
import dataclasses
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .benchmark import _load_measured_benchmark_state
from .fitting import DEFAULT_MEASURED_FLOW_CSV, DEFAULT_MEASURED_FLOW_FIT_SUMMARY, evaluate_measured_flow_fit
from .params import V60Params


def analyze_fit_identifiability(
    csv_path: str | Path | None = None,
    summary_path: str | Path | None = None,
    slices_csv_path: str | Path = "data/kinu29_fit_identifiability_slices.csv",
    heatmap_path: str | Path = "data/kinu29_fit_identifiability_heatmap.png",
    *,
    refit: bool = False,
    verbose: bool = True,
    n_eval: int = 900,
) -> dict:
    """
    分析目前 measured-fit 解附近的局部可識別性。
    """
    flow_path = Path(csv_path) if csv_path is not None else Path(DEFAULT_MEASURED_FLOW_CSV)
    summary_csv = Path(summary_path) if summary_path is not None else Path(DEFAULT_MEASURED_FLOW_FIT_SUMMARY)
    params_fit, info = _load_measured_benchmark_state(
        flow_path,
        summary_csv,
        refit=refit,
        verbose=verbose,
    )
    tau_lag_s = float(info["tau_lag_s"])
    baseline = evaluate_measured_flow_fit(flow_path, params_fit, tau_lag_s=tau_lag_s, n_eval=n_eval)
    baseline_loss = float(baseline["total_loss"])

    def _set_param(p: V60Params, name: str, value: float) -> V60Params:
        return dataclasses.replace(p, **{name: float(value)})

    factor_grid = np.array([0.70, 0.85, 1.00, 1.15, 1.30], dtype=float)
    slice_specs = [
        ("k", float(params_fit.k), 2.0e-11, 1.5e-10),
        ("k_beta", float(params_fit.k_beta), 5.0e2, 6.0e3),
        ("wetbed_struct_gain", float(params_fit.wetbed_struct_gain), 0.0, 1.2),
        ("wetbed_struct_rate", float(params_fit.wetbed_struct_rate), 0.0, 0.25),
        ("sat_rel_perm_residual", float(params_fit.sat_rel_perm_residual), 0.02, 0.40),
        ("sat_rel_perm_exp", float(params_fit.sat_rel_perm_exp), 1.0, 6.0),
    ]

    slice_rows: list[dict] = []
    for param_name, center, low, high in slice_specs:
        for factor in factor_grid:
            trial_value = float(np.clip(center * factor, low, high))
            trial_params = _set_param(params_fit, param_name, trial_value)
            eval_row = evaluate_measured_flow_fit(flow_path, trial_params, tau_lag_s=tau_lag_s, n_eval=n_eval)
            slice_rows.append({
                "param": param_name,
                "factor": float(factor),
                "value": trial_value,
                "delta_loss": float(eval_row["total_loss"] - baseline_loss),
                "rmse_ml": float(eval_row["volume_rmse"]),
                "velocity_rmse_mlps": float(eval_row["velocity_rmse"]),
                "drain_time_error_s": float(eval_row["drain_time_error_s"]),
            })

    slices_path = Path(slices_csv_path)
    slices_path.parent.mkdir(parents=True, exist_ok=True)
    with slices_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(slice_rows[0].keys()))
        writer.writeheader()
        writer.writerows(slice_rows)

    pair_specs = [
        ("k", "k_beta"),
        ("sat_rel_perm_residual", "sat_rel_perm_exp"),
        ("k", "sat_rel_perm_residual"),
        ("k_beta", "sat_rel_perm_exp"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 8.6))
    fig.suptitle("Hydraulic Identifiability Around Measured Fit", fontsize=13, fontweight="bold")

    for ax, (param_x, param_y) in zip(axes.flat, pair_specs):
        spec_x = next(spec for spec in slice_specs if spec[0] == param_x)
        spec_y = next(spec for spec in slice_specs if spec[0] == param_y)
        x_vals = np.clip(spec_x[1] * factor_grid, spec_x[2], spec_x[3])
        y_vals = np.clip(spec_y[1] * factor_grid, spec_y[2], spec_y[3])
        z = np.zeros((len(y_vals), len(x_vals)))
        for iy, yv in enumerate(y_vals):
            for ix, xv in enumerate(x_vals):
                trial_params = _set_param(params_fit, param_x, float(xv))
                trial_params = _set_param(trial_params, param_y, float(yv))
                eval_row = evaluate_measured_flow_fit(flow_path, trial_params, tau_lag_s=tau_lag_s, n_eval=n_eval)
                z[iy, ix] = float(eval_row["total_loss"] - baseline_loss)

        im = ax.imshow(z, origin="lower", aspect="auto", cmap="YlOrRd")
        ax.set_title(f"{param_x} vs {param_y}")
        ax.set_xlabel(param_x)
        ax.set_ylabel(param_y)
        ax.set_xticks(range(len(x_vals)))
        ax.set_xticklabels([f"{v:.3g}" for v in x_vals], rotation=30, ha="right")
        ax.set_yticks(range(len(y_vals)))
        ax.set_yticklabels([f"{v:.3g}" for v in y_vals])
        for iy in range(len(y_vals)):
            for ix in range(len(x_vals)):
                ax.text(ix, iy, f"{z[iy, ix]:.2f}", ha="center", va="center", fontsize=7)
        fig.colorbar(im, ax=ax, label="Δloss")

    for ax in axes.flat[len(pair_specs):]:
        ax.axis("off")

    plt.tight_layout()
    heatmap_out = Path(heatmap_path)
    heatmap_out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(heatmap_out, dpi=160, bbox_inches="tight")
    plt.close(fig)

    print("\n=== Identifiability ===")
    print(f"  baseline loss : {baseline_loss:.3f}")
    print(f"  slices csv    : {slices_path}")
    print(f"  heatmap png   : {heatmap_out}")

    return {
        "params_fit": params_fit,
        "info": info,
        "baseline": baseline,
        "baseline_loss": baseline_loss,
        "slice_rows": slice_rows,
        "slices_csv_path": str(slices_path),
        "heatmap_path": str(heatmap_out),
        "factor_grid": factor_grid,
    }


def analyze_pref_flow_identifiability(
    csv_path: str | Path | None = None,
    summary_path: str | Path | None = None,
    slices_csv_path: str | Path = "data/kinu29_pref_flow_identifiability_slices.csv",
    heatmap_path: str | Path = "data/kinu29_pref_flow_identifiability_heatmap.png",
    *,
    refit: bool = False,
    verbose: bool = True,
    n_eval: int = 900,
) -> dict:
    """
    分析快路徑 `pref_flow_*` 參數在目前 measured fit 附近的局部可識別性。
    """
    flow_path = Path(csv_path) if csv_path is not None else Path(DEFAULT_MEASURED_FLOW_CSV)
    summary_csv = Path(summary_path) if summary_path is not None else Path(DEFAULT_MEASURED_FLOW_FIT_SUMMARY)
    params_fit, info = _load_measured_benchmark_state(
        flow_path,
        summary_csv,
        refit=refit,
        verbose=verbose,
    )
    if float(getattr(params_fit, "pref_flow_coeff", 0.0)) <= 0.0:
        raise ValueError("目前 calibrated baseline 未啟用 pref_flow，無法做 pref_flow identifiability。")

    tau_lag_s = float(info["tau_lag_s"])
    baseline = evaluate_measured_flow_fit(flow_path, params_fit, tau_lag_s=tau_lag_s, n_eval=n_eval)
    baseline_loss = float(baseline["total_loss"])

    def _set_param(p: V60Params, name: str, value: float) -> V60Params:
        return dataclasses.replace(p, **{name: float(value)})

    def _slice_judgement(rows: list[dict], param_name: str) -> dict:
        rows_param = [r for r in rows if r["param"] == param_name]
        near_rows = [r for r in rows_param if abs(float(r["factor"]) - 1.0) > 1e-9]
        local_rows = [r for r in near_rows if abs(float(r["factor"]) - 1.0) <= 0.20 + 1e-9]
        wide_rows = [r for r in near_rows if abs(float(r["factor"]) - 1.0) <= 0.40 + 1e-9]
        local_span = max((abs(float(r["delta_loss"])) for r in local_rows), default=0.0)
        wide_span = max((abs(float(r["delta_loss"])) for r in wide_rows), default=0.0)
        if local_span >= 0.45 or wide_span >= 1.10:
            level = "hard"
            advice = "保留自由度"
        elif local_span >= 0.18 or wide_span >= 0.45:
            level = "medium"
            advice = "可保留，但應搭配另一參數固定"
        else:
            level = "weak"
            advice = "建議固定"
        return {
            "param": param_name,
            "local_span": float(local_span),
            "wide_span": float(wide_span),
            "level": level,
            "advice": advice,
        }

    factor_grid = np.array([0.60, 0.80, 1.00, 1.20, 1.40], dtype=float)
    slice_specs = [
        ("pref_flow_coeff", float(params_fit.pref_flow_coeff), 5.0e-6, 5.0e-4),
        ("pref_flow_open_rate", float(params_fit.pref_flow_open_rate), 0.05, 5.0),
        ("pref_flow_tau_decay", float(params_fit.pref_flow_tau_decay), 1.0, 20.0),
    ]

    slice_rows: list[dict] = []
    for param_name, center, low, high in slice_specs:
        for factor in factor_grid:
            trial_value = float(np.clip(center * factor, low, high))
            trial_params = _set_param(params_fit, param_name, trial_value)
            eval_row = evaluate_measured_flow_fit(flow_path, trial_params, tau_lag_s=tau_lag_s, n_eval=n_eval)
            slice_rows.append({
                "param": param_name,
                "factor": float(factor),
                "value": trial_value,
                "delta_loss": float(eval_row["total_loss"] - baseline_loss),
                "rmse_ml": float(eval_row["volume_rmse"]),
                "velocity_rmse_mlps": float(eval_row["velocity_rmse"]),
                "drain_time_error_s": float(eval_row["drain_time_error_s"]),
            })

    slices_path = Path(slices_csv_path)
    slices_path.parent.mkdir(parents=True, exist_ok=True)
    with slices_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(slice_rows[0].keys()))
        writer.writeheader()
        writer.writerows(slice_rows)

    pair_specs = [
        ("pref_flow_coeff", "pref_flow_open_rate"),
        ("pref_flow_coeff", "pref_flow_tau_decay"),
        ("pref_flow_open_rate", "pref_flow_tau_decay"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    fig.suptitle("Preferential-Flow Identifiability Around Measured Fit", fontsize=13, fontweight="bold")

    for ax, (param_x, param_y) in zip(np.atleast_1d(axes).flat, pair_specs):
        spec_x = next(spec for spec in slice_specs if spec[0] == param_x)
        spec_y = next(spec for spec in slice_specs if spec[0] == param_y)
        x_vals = np.clip(spec_x[1] * factor_grid, spec_x[2], spec_x[3])
        y_vals = np.clip(spec_y[1] * factor_grid, spec_y[2], spec_y[3])
        z = np.zeros((len(y_vals), len(x_vals)))
        for iy, yv in enumerate(y_vals):
            for ix, xv in enumerate(x_vals):
                trial_params = _set_param(params_fit, param_x, float(xv))
                trial_params = _set_param(trial_params, param_y, float(yv))
                eval_row = evaluate_measured_flow_fit(flow_path, trial_params, tau_lag_s=tau_lag_s, n_eval=n_eval)
                z[iy, ix] = float(eval_row["total_loss"] - baseline_loss)

        im = ax.imshow(z, origin="lower", aspect="auto", cmap="YlOrRd")
        ax.set_title(f"{param_x} vs {param_y}")
        ax.set_xlabel(param_x)
        ax.set_ylabel(param_y)
        ax.set_xticks(range(len(x_vals)))
        ax.set_xticklabels([f"{v:.3g}" for v in x_vals], rotation=30, ha="right")
        ax.set_yticks(range(len(y_vals)))
        ax.set_yticklabels([f"{v:.3g}" for v in y_vals])
        for iy in range(len(y_vals)):
            for ix in range(len(x_vals)):
                ax.text(ix, iy, f"{z[iy, ix]:.2f}", ha="center", va="center", fontsize=7)
        fig.colorbar(im, ax=ax, label="Δloss")

    plt.tight_layout()
    heatmap_out = Path(heatmap_path)
    heatmap_out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(heatmap_out, dpi=160, bbox_inches="tight")
    plt.close(fig)

    judgement_rows = [
        _slice_judgement(slice_rows, "pref_flow_coeff"),
        _slice_judgement(slice_rows, "pref_flow_open_rate"),
        _slice_judgement(slice_rows, "pref_flow_tau_decay"),
    ]
    recommendation = {
        "fix_pref_flow_coeff": judgement_rows[0]["level"] == "weak",
        "fix_pref_flow_open_rate": judgement_rows[1]["level"] != "hard",
        "fix_pref_flow_tau_decay": judgement_rows[2]["level"] != "hard",
    }

    print("\n=== Pref-Flow Identifiability ===")
    print(f"  baseline loss : {baseline_loss:.3f}")
    print(f"  slices csv    : {slices_path}")
    print(f"  heatmap png   : {heatmap_out}")
    for row in judgement_rows:
        print(
            f"  {row['param']:<20} : {row['level']:<6} "
            f"(±20% Δloss≈{row['local_span']:.2f}, ±40% Δloss≈{row['wide_span']:.2f})"
            f"  → {row['advice']}"
        )

    return {
        "params_fit": params_fit,
        "info": info,
        "baseline": baseline,
        "baseline_loss": baseline_loss,
        "slice_rows": slice_rows,
        "judgement_rows": judgement_rows,
        "recommendation": recommendation,
        "slices_csv_path": str(slices_path),
        "heatmap_path": str(heatmap_out),
        "factor_grid": factor_grid,
    }
