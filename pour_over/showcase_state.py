"""
showcase_state.py — 展示頁與 compare_* 的基準狀態載入

What:
    集中管理 showcase / compare 圖使用的 calibrated baseline、
    預設量測注水曲線，以及由 baseline 衍生出的 grind / correction scenario。

Why:
    這些邏輯屬於「展示狀態選擇」，不是視覺化本身。
    把它們從 viz.py 抽離後，畫圖函式就能回到純輸入 -> 純輸出。
"""

import csv
from dataclasses import replace
from pathlib import Path

from .measured_io import load_flow_profile_csv
from .params import PourProtocol, V60Params


def data_dir() -> Path:
    """回傳專案內 data 目錄。"""
    return Path(__file__).resolve().parents[1] / "data"


def latest_protocol(protocol: PourProtocol | None = None) -> PourProtocol:
    """
    回傳展示頁預設使用的注水協議。

    What:
        優先使用 measured `V_in(t)`；若缺檔則退回標準 V60 recipe。

    Why:
        compare 圖應優先圍繞目前正式 benchmark case，而不是默默退回舊預設。
    """
    if protocol is not None:
        return protocol
    flow_csv = data_dir() / "kinu29_light_20g_flow_profile.csv"
    if flow_csv.exists():
        obs = load_flow_profile_csv(flow_csv)
        return PourProtocol.from_cumulative_profile(list(zip(obs["t_s"], obs["v_in_ml"])))
    return PourProtocol.standard_v60()


def latest_calibrated_params() -> V60Params:
    """
    回傳目前專案展示用的 calibrated baseline。

    What:
        由 calibrated summary 載入目前首頁使用的主模型參數；
        若本地存在 measured PSD bins，則一併接入主模型。

    Why:
        compare_*、README 與首頁必須引用同一組展示基準，避免各自硬編碼。
        repo 目前不保證隨附 measured PSD 檔，因此展示基準必須在缺 bins 時
        仍能安全退回 calibrated D10-only baseline。
    """
    bins_csv = data_dir() / "kinu29_psd_bins.csv"
    summary_csv = data_dir() / "kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"
    if bins_csv.exists():
        summary = {}
        if summary_csv.exists():
            with summary_csv.open("r", encoding="utf-8", newline="") as f:
                summary = next(csv.DictReader(f))
        return V60Params(
            psd_bins_csv_path=str(bins_csv),
            D10_measured_m=374.2e-6,
            h_bed=0.053,
            T_amb=23.0 + 273.15,
            k=float(summary.get("k_fit", 8.122875712025124e-11)),
            k_beta=float(summary.get("k_beta_fit", 1291.7562166952491)),
            wetbed_impact_tau=2.0,
            throat_relief_gain=0.58,
            wetbed_struct_gain=float(summary.get("wetbed_struct_gain_fit", 0.0)),
            wetbed_struct_rate=float(summary.get("wetbed_struct_rate_fixed", summary.get("wetbed_struct_rate_fit", 0.0))),
            wetbed_impact_release_rate=float(summary.get("wetbed_impact_release_rate_fixed", 0.0)),
            pref_flow_coeff=float(summary.get("pref_flow_coeff_fit", 0.0)),
            pref_flow_open_rate=float(summary.get("pref_flow_open_rate_fixed", summary.get("pref_flow_open_rate_fit", 0.0))),
            pref_flow_tau_decay=float(summary.get("pref_flow_tau_decay_fixed", summary.get("pref_flow_tau_decay_fit", 5.0))),
        )
    return V60Params()


def scaled_grind_params(scale: float) -> V60Params:
    """
    用同一份 measured PSD 做等比縮放，生成 coarse / medium / fine。
    """
    base = latest_calibrated_params()
    native_d10 = max(float(base.D10), 1e-9)
    scaled_d10 = native_d10 * max(float(scale), 1e-9)
    scaled_k = float(base.k) * max(float(scale), 1e-9) ** 2
    trial = replace(base, D10_measured_m=scaled_d10, k=scaled_k)
    base_prior = max(float(base.k_beta_prior_from_psd()), 1e-9)
    trial_prior = max(float(trial.k_beta_prior_from_psd()), 1e-9)
    scaled_k_beta = float(base.k_beta) * trial_prior / base_prior
    return replace(trial, k_beta=scaled_k_beta)


def latest_grind_configs() -> dict[str, V60Params]:
    """以 calibrated baseline 為中心建立最新 grind 對比。"""
    return {
        "Coarse": scaled_grind_params(1.35),
        "Medium": scaled_grind_params(1.00),
        "Fine": scaled_grind_params(0.78),
    }


def latest_correction_configs() -> dict[str, V60Params]:
    """用最新模型拆出 correction scenario，而不是回到舊 closure。"""
    base = latest_calibrated_params()
    no_clog = replace(base, k_beta=0.0, throat_relief_gain=0.0)
    clog_only = replace(base, throat_relief_gain=0.0)
    no_bypass = replace(base, psi=0.0, psi_beta=0.0)
    return {
        "No clogging": no_clog,
        "PSD clogging": clog_only,
        "No bypass": no_bypass,
        "Full model": base,
    }
