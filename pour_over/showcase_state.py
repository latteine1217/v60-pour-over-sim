"""
showcase_state.py — 展示頁與 compare_* 的基準狀態載入

What:
    集中管理 showcase / compare 圖使用的 calibrated baseline、
    預設量測注水曲線，以及由 baseline 衍生出的 grind / correction scenario。

Why:
    這些邏輯屬於「展示狀態選擇」，不是視覺化本身。
    把它們從 viz.py 抽離後，畫圖函式就能回到純輸入 -> 純輸出。
"""

from dataclasses import replace
from pathlib import Path

from .measured_io import load_flow_profile_csv
from .params import PourProtocol, V60Params


def data_dir() -> Path:
    """回傳專案內 data 目錄。"""
    return Path(__file__).resolve().parents[1] / "data"


def measured_case_dir(case_id: str = "4:12") -> Path:
    """回傳 measured case 目錄；預設仍指向正式 benchmark case。"""
    case_dir = data_dir() / "kinu_29_light" / case_id
    if not case_dir.exists():
        raise FileNotFoundError(f"缺少 measured case 目錄：{case_dir}")
    return case_dir


def latest_protocol(protocol: PourProtocol | None = None) -> PourProtocol:
    """
    回傳展示頁預設使用的注水協議。

    What:
        使用正式 measured `V_in(t)` 作為展示頁預設協議。

    Why:
        compare 圖必須圍繞正式 benchmark case，不允許缺檔時默默回退到別的 recipe。
    """
    if protocol is not None:
        return protocol
    flow_csv = measured_case_dir() / "kinu29_light_20g_flow_profile.csv"
    obs = load_flow_profile_csv(flow_csv)
    return PourProtocol.from_cumulative_profile(list(zip(obs["t_s"], obs["v_in_ml"])))


def latest_calibrated_params() -> V60Params:
    """
    回傳目前專案展示用的 calibrated baseline。

    What:
        由正式 calibrated summary 載入目前首頁使用的主模型參數。

    Why:
        compare_*、README 與首頁必須引用同一組展示基準，不允許缺檔時默默回退到舊 baseline。
    """
    case_dir = measured_case_dir()
    flow_csv = case_dir / "kinu29_light_20g_flow_profile.csv"
    summary_csv = case_dir / "kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"
    from .benchmark import _load_measured_benchmark_state

    params_fit, _ = _load_measured_benchmark_state(
        flow_csv,
        summary_csv,
        refit=False,
        verbose=False,
    )
    return params_fit


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
