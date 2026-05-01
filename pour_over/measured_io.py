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
# `MEASURED_LIQUID_DRIPPER_LAMBDA` 自 2026-04-30 起改為「fit initial guess」，
# 不再是 hard-coded 量測常數：thermal identifiability scan 顯示這條 λ 是熱端
# 最強自由度（cup ΔT swing 0.77 °C），由 `fit_k_kbeta_from_flow_profile`
# stage 6 校準，並以此值作為弱 prior reg 的中心。
MEASURED_LIQUID_DRIPPER_LAMBDA = 0.02
MEASURED_DRIPPER_AMBIENT_LAMBDA = 0.004
MEASURED_SERVER_AMBIENT_LAMBDA = 0.0

# Measured PSD baseline（kinu29 light）
# What: 主量測 baseline 使用的 PSD bins artifact 與其 D10 摘要
# Why:  AGENTS.md §3.2 / §5 要求「有 measured PSD 必須優先使用」；先前
#       fitting 與 benchmark 路徑沒有 ingest 這條，等同退回 single-bin fallback。
#       集中於本檔，與其他 measured 常數同處，方便日後切換不同 PSD baseline。
MEASURED_PSD_BINS_CSV = "data/kinu29_psd_bins.csv"
MEASURED_D10_M = 374.2e-6
MEASURED_PSD_DIAMETER_SCALE = 1.0

# Canonical baseline override (Option C, 2026-05-02)：
# kinu29/4:11 為 calibrated baseline，使用 worktree 頂層的高解析度 PSD
# (17.24 μm/px → D10=374 μm)；其他 cross-validation cases 走 sibling per-case PSD
# (35 μm/px → D10≈517 μm，systematic under-count of fines)。
# Why: per-case PSDs 的低解析度顯微鏡是已知量測限制；high-res baseline 維持作為
#      「best-case demonstration」，per-case 為 honest cross-validation reference
#      但 TDS gate 預期會 relaxed。AGENTS.md §3.2 仍對齊：每個 case 用其 measured PSD，
#      只是 canonical baseline 顯式指定哪一個版本的量測作為 baseline。
CANONICAL_HIGH_RES_PSD_OVERRIDES: dict[str, str] = {
    "data/kinu_29_light/4:11/kinu29_light_20g_flow_profile.csv": MEASURED_PSD_BINS_CSV,
}

# Brix → TDS 經驗轉換（VST 折光儀校正因子，specialty coffee 慣例）
# - 折光儀讀值（°Bx，蔗糖等效百分比）需以 0.85 校正成實際咖啡可溶物 % w/w
# - TDS_g/L ≈ TDS_pct × 10 × ρ_brew （ρ ≈ 1.005，簡化為 ×10）
# 來源：VST CoffeeTools 折光儀手冊；T. Lingle "Coffee Brewing Handbook" 章節
BRIX_TO_TDS_PCT_FACTOR = 0.85
BREW_DENSITY_G_PER_ML = 1.0  # 簡化；實際稀薄咖啡液 ρ ≈ 1.005


def brix_to_tds_gl(brix_pct: float) -> float:
    """
    把折光儀 Brix 讀值（°Bx，% w/w 蔗糖等效）轉為 TDS [g/L]。

    What:
        TDS_pct  = Brix × 0.85
        TDS_g/L  = TDS_pct × 10 × ρ_brew  (ρ ≈ 1.0)

    Why:
        實驗室量測通常用 VST / Atago refractometer，讀值是 sucrose-equiv Brix。
        coffee 可溶物的折射率 ~ 0.85 × sucrose（specialty coffee 慣例校正因子）。
    """
    return float(brix_pct) * BRIX_TO_TDS_PCT_FACTOR * 10.0 * BREW_DENSITY_G_PER_ML


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


def _project_root() -> Path:
    """Project root（與 `data/` 同層）。"""
    return Path(__file__).resolve().parents[1]


def _resolve_psd_bins_path(
    meta: dict,
    flow_csv_path: str | Path | None = None,
) -> tuple[str | None, float | None]:
    """
    決定當前 case 應使用的 measured PSD bins 路徑與 D10。

    What:
        優先順序（per-case first，AGENTS.md §3.2 對齊）：
        1. CSV metadata `psd_bins_csv_path` 顯式指定
        2. 與 `flow_csv_path` 同目錄的 sibling `*_psd_bins.csv`（per-case PSD）
        3. fallback：`MEASURED_PSD_BINS_CSV` 全域常數
        若解析後路徑不存在，回傳 (None, None) 讓主模型走 single-bin fallback。

        D10 同理：metadata → sibling PSD summary → 全域常數。

    Why:
        AGENTS.md §3.2：有 measured PSD 必須優先使用 *該 case* 的量測。
        per-case PSD 雖然解析度（35 μm/px）比 worktree 頂層 baseline（17.24 μm/px）
        粗，會 under-count fines（D10 高 38%），但這是 *honest* 量測；模型應暴露其
        結構限制（在粗 PSD 下 TDS 預測偏低）而非靠混用 PSD 假裝校準漂亮。
        2026-05-01 確認：sibling-first priority 是 AGENTS.md 對齊的選擇。
        TDS 預測偏差由 closure 結構（subagent P2 `flow_factor` 拆分等）解決，不靠
        PSD 替代來補償。
    """
    raw_path = meta.get("psd_bins_csv_path")
    bins_path: Path | None = None
    summary_path: Path | None = None

    if raw_path is not None and str(raw_path).strip() != "":
        # 1. CSV metadata 顯式指定（最高優先）
        bins_path = Path(str(raw_path))
    elif flow_csv_path is not None:
        # 2. CANONICAL_HIGH_RES_PSD_OVERRIDES：canonical baseline 用 high-res PSD
        flow_csv_str = str(flow_csv_path)
        # 嘗試匹配絕對路徑或專案相對路徑
        match_key: str | None = None
        for key in CANONICAL_HIGH_RES_PSD_OVERRIDES:
            if flow_csv_str.endswith(key) or flow_csv_str == key:
                match_key = key
                break
        if match_key is not None:
            bins_path = Path(CANONICAL_HIGH_RES_PSD_OVERRIDES[match_key])
        else:
            # 3. sibling per-case PSD
            flow_dir = Path(flow_csv_path).resolve().parent
            siblings = sorted(flow_dir.glob("*_psd_bins.csv"))
            if siblings:
                bins_path = siblings[0]
                summary_candidates = sorted(flow_dir.glob("*_psd_summary.csv"))
                if summary_candidates:
                    summary_path = summary_candidates[0]

    if bins_path is None:
        # 4. fallback：worktree 全域 PSD（kinu29 高解析度 baseline）
        bins_path = Path(MEASURED_PSD_BINS_CSV)

    if not bins_path.is_absolute():
        bins_path = _project_root() / bins_path
    if not bins_path.exists():
        return None, None

    # D10 解析
    d10_raw = meta.get("D10_measured_m")
    d10_value: float | None = None
    if d10_raw is not None and str(d10_raw).strip() != "":
        d10_value = float(d10_raw)
    elif summary_path is not None and summary_path.exists():
        # 從 sibling PSD summary 讀 D10
        try:
            with summary_path.open(encoding="utf-8") as f:
                row = next(csv.DictReader(f), None)
            if row is not None:
                for key in ("recommended_D10_m", "model_D10_m"):
                    if key in row and str(row[key]).strip():
                        d10_value = float(row[key])
                        break
                # 若只有 mm 欄位
                if d10_value is None:
                    for key in ("recommended_D10_mm", "model_D10_mm"):
                        if key in row and str(row[key]).strip():
                            d10_value = float(row[key]) * 1e-3
                            break
        except (StopIteration, ValueError, KeyError):
            pass

    if d10_value is None:
        d10_value = float(MEASURED_D10_M)
    return str(bins_path), d10_value


def _measured_setup_overrides(
    meta: dict,
    flow_csv_path: str | Path | None = None,
) -> dict:
    """
    組裝量測可直接給定的環境、硬體與 PSD ingest 參數。

    What:
        回傳 ambient、濾杯質量/比熱、初始熱交換係數，以及 measured PSD bins
        路徑（若存在）的 override dict。

    Why:
        這些量屬於量測條件或硬體條件，不應每次在擬合內隱性漂移；measured PSD
        ingest 同樣屬於 baseline-level 設定，集中於此處可確保 fitting / benchmark
        / showcase 三條路徑使用同一份 PSD（AGENTS.md §3.2 主敘事必須走 measured PSD）。
    """
    ambient_C = _meta_float(meta, "ambient_temp_C", MEASURED_AMBIENT_TEMP_C)
    dripper_mass_g = _meta_float(meta, "dripper_mass_g", MEASURED_DRIPPER_MASS_G)
    dripper_cp_j_gk = _meta_float(meta, "dripper_cp_J_gK", MEASURED_DRIPPER_CP_J_GK)
    liquid_dripper_lambda = _meta_float(meta, "lambda_liquid_dripper", MEASURED_LIQUID_DRIPPER_LAMBDA)
    dripper_ambient_lambda = _meta_float(meta, "lambda_dripper_ambient", MEASURED_DRIPPER_AMBIENT_LAMBDA)
    server_ambient_lambda = _meta_float(meta, "lambda_server_ambient", MEASURED_SERVER_AMBIENT_LAMBDA)
    overrides: dict = {
        "T_amb": ambient_C + 273.15,
        "dripper_mass_g": dripper_mass_g,
        "dripper_cp_J_gK": dripper_cp_j_gk,
        "lambda_liquid_dripper": liquid_dripper_lambda,
        "lambda_dripper_ambient": dripper_ambient_lambda,
        "lambda_server_ambient": server_ambient_lambda,
    }
    psd_bins_path, d10_value = _resolve_psd_bins_path(meta, flow_csv_path=flow_csv_path)
    if psd_bins_path is not None:
        overrides["psd_bins_csv_path"] = psd_bins_path
        overrides["D10_measured_m"] = d10_value
    return overrides


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

    # 量測 Brix → TDS。CSV 欄位名為 `final_tds_pct`，實際儲存 Brix 讀值（°Bx）；
    # 套用 BRIX_TO_TDS_PCT_FACTOR=0.85 才是實際 TDS_pct。
    # 沒有量測時 final_brix_pct=None，TDS 不進 fit loss。
    final_brix_pct = (
        float(meta["final_tds_pct"]) if meta.get("final_tds_pct") and str(meta["final_tds_pct"]).strip() else None
    )
    final_tds_gl = brix_to_tds_gl(final_brix_pct) if final_brix_pct is not None else None

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
        "final_brix_pct": final_brix_pct,
        "final_tds_gl": final_tds_gl,
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
