"""
measured_io.py — 量測資料與硬體條件輸入

What:
    集中管理 measured benchmark 使用的 CSV parsing、metadata fallback、
    與可直接量測的硬體/環境條件常數。

Why:
    量測資料 I/O 與 optimizer / loss 定義無關；把它們從 fitting 主流程拆開，
    可減少模組耦合，並讓 benchmark、viz、analysis 共用同一套輸入定義。
"""

import csv
from pathlib import Path

import numpy as np

from .params import PourProtocol


MEASURED_BED_HEIGHT_CM = 5.3
MEASURED_VESSEL_EQUIV_ML = 42.4
MEASURED_AMBIENT_TEMP_C = 23.0
MEASURED_DRIPPER_MASS_G = 123.5
MEASURED_DRIPPER_CP_J_GK = 0.88
MEASURED_LIQUID_DRIPPER_LAMBDA = 0.02
MEASURED_DRIPPER_AMBIENT_LAMBDA = 0.004
MEASURED_SERVER_AMBIENT_LAMBDA = 0.0


def _meta_float(meta: dict, key: str, default: float | None = None) -> float:
    """
    從 CSV metadata 取浮點數，必要時回退到預設值。

    What:
        讀取首列 metadata 的數值欄位，空字串或缺值時使用 `default`。

    Why:
        量測資料有時只缺單一欄位；集中處理可避免擬合流程散落隱性 fallback。
    """
    raw = meta.get(key)
    if raw is None or str(raw).strip() == "":
        if default is None:
            raise ValueError(f"CSV metadata 缺少必要欄位：{key}")
        return float(default)
    return float(raw)


def _measured_setup_overrides(meta: dict) -> dict:
    """
    組裝量測可直接給定的環境與硬體參數。

    What:
        回傳 ambient、濾杯質量/比熱與初始熱交換係數的 override dict。

    Why:
        這些量屬於量測條件或硬體條件，不應每次在擬合內隱性漂移。
    """
    ambient_C = _meta_float(meta, "ambient_temp_C", MEASURED_AMBIENT_TEMP_C)
    dripper_mass_g = _meta_float(meta, "dripper_mass_g", MEASURED_DRIPPER_MASS_G)
    dripper_cp_j_gk = _meta_float(meta, "dripper_cp_J_gK", MEASURED_DRIPPER_CP_J_GK)
    liquid_dripper_lambda = _meta_float(meta, "lambda_liquid_dripper", MEASURED_LIQUID_DRIPPER_LAMBDA)
    dripper_ambient_lambda = _meta_float(meta, "lambda_dripper_ambient", MEASURED_DRIPPER_AMBIENT_LAMBDA)
    server_ambient_lambda = _meta_float(meta, "lambda_server_ambient", MEASURED_SERVER_AMBIENT_LAMBDA)
    return {
        "T_amb": ambient_C + 273.15,
        "dripper_mass_g": dripper_mass_g,
        "dripper_cp_J_gK": dripper_cp_j_gk,
        "lambda_liquid_dripper": liquid_dripper_lambda,
        "lambda_dripper_ambient": dripper_ambient_lambda,
        "lambda_server_ambient": server_ambient_lambda,
    }


def load_brew_log_csv(csv_path: str | Path) -> tuple[list[dict], dict]:
    """
    讀取實測沖煮紀錄 CSV。

    What:
        載入使用者手動整理的區段式量測資料，回傳原始列與首列中繼資料。

    Why:
        實驗資料常先以 CSV 留存；將 parsing 與擬合分離，後續更容易重複使用。
    """
    path = Path(csv_path)
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"空的 CSV：{path}")
    return rows, rows[0]


def load_flow_profile_csv(csv_path: str | Path) -> dict:
    """
    讀取 `V_in(t)` / `V_out(t)` 實測剖面。

    What:
        載入逐時刻觀測，回傳 numpy 陣列與首列 metadata。

    Why:
        流動標定需要時間序列，而不是僅靠最終端點。
    """
    rows, meta = load_brew_log_csv(csv_path)
    t_s = np.array([float(r["time_s"]) for r in rows], dtype=float)
    v_in_ml = np.array([float(r["poured_weight_g"]) for r in rows], dtype=float)
    v_out_ml = np.array([float(r["drained_volume_ml"]) for r in rows], dtype=float)
    use_for_fit = np.array([int(r.get("use_for_fit", "1")) for r in rows], dtype=int)
    phases = [r.get("phase", "") for r in rows]
    final_cup_temp_C = float(meta["final_coffee_temp_C"]) if meta.get("final_coffee_temp_C") else None

    stop_flow_time_s = None
    for row in rows:
        if row.get("phase", "").strip().lower() == "flow_stop_visual":
            stop_flow_time_s = float(row["time_s"])
            break
    if stop_flow_time_s is None:
        stop_flow_time_s = float(t_s[-1])

    return {
        "rows": rows,
        "meta": meta,
        "t_s": t_s,
        "v_in_ml": v_in_ml,
        "v_out_ml": v_out_ml,
        "use_for_fit": use_for_fit,
        "phase": phases,
        "final_cup_temp_C": final_cup_temp_C,
        "stop_flow_time_s": stop_flow_time_s,
    }


def protocol_from_brew_log(rows: list[dict]) -> PourProtocol:
    """
    從區段式沖煮紀錄重建 PourProtocol。

    What:
        將每個 `pour_*` 區段轉成 `(start, volume, duration)`。

    Why:
        使用量測得到的累積重量終點，比逐列內差更能抵抗起始讀值的小幅抖動。
    """
    pours: list[tuple[float, float, float]] = []
    prev_end_g = 0.0

    for row in rows:
        end_g = float(row["weight_end_g"])
        phase = row["phase"].strip().lower()
        if phase.startswith("pour"):
            start_s = float(row["time_start_s"])
            end_s = float(row["time_end_s"])
            duration_s = end_s - start_s
            volume_ml = max(end_g - prev_end_g, 0.0)
            if duration_s <= 0:
                raise ValueError(f"無效注水區段：{row}")
            pours.append((start_s, volume_ml, duration_s))
        prev_end_g = end_g

    if not pours:
        raise ValueError("CSV 中沒有可用的注水區段（phase 必須以 pour 開頭）")
    return PourProtocol(pours=pours)


def protocol_from_cumulative_input(
    t_obs_s: np.ndarray,
    v_in_obs_ml: np.ndarray,
    min_pour_ml: float = 1.0,
) -> PourProtocol:
    """
    從累積注水曲線重建等效分段注水協議。

    What:
        將單調化後的 `V_in(t)` 差分為多段等效 constant-rate pours。

    Why:
        使用真實注水曲線重建協議，比人工估段更穩定，也能直接進 simulate_brew。
    """
    t_obs_s = np.asarray(t_obs_s, dtype=float)
    v_in_obs_ml = np.maximum.accumulate(np.asarray(v_in_obs_ml, dtype=float))
    pours: list[tuple[float, float, float]] = []

    for i in range(1, len(t_obs_s)):
        dt = float(t_obs_s[i] - t_obs_s[i - 1])
        dv = float(v_in_obs_ml[i] - v_in_obs_ml[i - 1])
        if dt <= 0:
            continue
        if dv >= min_pour_ml:
            pours.append((float(t_obs_s[i - 1]), dv, dt))

    if not pours:
        raise ValueError("無法從 V_in(t) 重建注水協議：沒有足夠的正增量")
    return PourProtocol(pours=pours)
