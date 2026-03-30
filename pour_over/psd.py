"""
psd.py — 影像量測 PSD 後處理

What:
  將粒子影像匯出的 raw CSV 與 stats CSV 整理成可直接放入模型的摘要欄位，
  並額外輸出 multi-bin PSD 表格。

Why:
  目前模型中的 D10、細粉比例與形狀因子不應再只靠碎形假設；
  一旦有實測 PSD，就應先把影像資料轉成穩定、可重跑的結構化數值。
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

DEFAULT_SHELL_THICKNESS_MM = 0.2
DEFAULT_BIN_EDGES_MM = (0.0, 0.25, 0.40, 0.55, 0.75, 1.00, 1.40, 2.00, 3.00)


def _quantile(values: list[float], prob: float) -> float:
    """線性內插分位數。"""
    xs = sorted(float(v) for v in values)
    if not xs:
        raise ValueError("空的數列無法計算分位數")
    idx = (len(xs) - 1) * float(prob)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return xs[lo]
    w = idx - lo
    return xs[lo] * (1.0 - w) + xs[hi] * w


def _weighted_quantile(values: list[float], weights: list[float], prob: float) -> float:
    """加權分位數；權重需為非負。"""
    pairs = sorted((float(v), max(float(w), 0.0)) for v, w in zip(values, weights))
    total = sum(w for _, w in pairs)
    if total <= 0:
        return _quantile(values, prob)
    target = float(prob) * total
    accum = 0.0
    for value, weight in pairs:
        accum += weight
        if accum >= target:
            return value
    return pairs[-1][0]


def load_psd_raw_csv(raw_csv_path: str | Path) -> list[dict]:
    """
    讀取 PSD raw CSV。

    What: 回傳每顆粒子的幾何量，並換算成 mm / mm² / mm³。
    Why:  下游模型只需要一致的幾何量，不應直接依賴外部軟體的原始欄位縮放。
    """
    path = Path(raw_csv_path)
    particles: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            short_axis = float(row["SHORT_AXIS"])
            long_axis = float(row["LONG_AXIS"])
            surface = float(row["SURFACE"])
            volume = float(row["VOLUME"])
            roundness = float(row["ROUNDNESS"])

            # 由 stats 檔交叉驗證後，匯出軟體的直徑定義可近似為：
            #   diameter_hist_mm ≈ (SHORT_AXIS + LONG_AXIS) / 10
            # 這與使用者看到的 histogram 軸一致。
            diameter_hist_mm = (short_axis + long_axis) / 10.0

            # 對模型更穩定的幾何等效直徑：將長短軸視為橢圓兩直徑，
            # 用面積等效直徑 sqrt(a*b) 作為顆粒尺寸代理。
            diameter_eq_mm = math.sqrt(short_axis * long_axis) / 5.0

            particles.append({
                "diameter_hist_mm": diameter_hist_mm,
                "diameter_eq_mm": diameter_eq_mm,
                "short_axis_mm": short_axis / 5.0,
                "long_axis_mm": long_axis / 5.0,
                "surface_mm2": surface / 100.0,
                "volume_mm3": volume / 1000.0,
                "aspect_ratio": long_axis / max(short_axis, 1e-12),
                "roundness": roundness,
                "surface_to_volume_mm_inv": (surface / 100.0) / max(volume / 1000.0, 1e-12),
            })
    if not particles:
        raise ValueError(f"空的 PSD raw CSV：{path}")
    return particles


def load_psd_stats_csv(stats_csv_path: str | Path) -> dict:
    """
    讀取 PSD stats CSV。

    What: 讀取外部軟體輸出的總表，保留平均直徑與表面積供交叉檢查。
    Why:  raw 欄位單位容易混淆；stats 檔可用來驗證我們的縮放是否正確。
    """
    path = Path(stats_csv_path)
    with path.open("r", encoding="utf-8", newline="") as f:
        row = next(csv.DictReader(f))
    return {
        "stats_avg_diam_mm": float(row["AVG_DIAM"]),
        "stats_std_diam_mm": float(row["STD_DIAM"]),
        "stats_avg_surf_mm2": float(row["AVG_SURF"]),
        "stats_std_surf_mm2": float(row["STD_SURF"]),
        "stats_eff_pct": float(row["EFF"]),
        "stats_quality": float(row["QUAL"]),
    }


def infer_psd_summary(
    raw_csv_path: str | Path,
    stats_csv_path: str | Path | None = None,
) -> dict:
    """
    由 PSD 量測輸出生成模型摘要。

    What:
      1. 讀取 raw 粒子資料
      2. 計算 histogram 一致直徑與模型建議等效直徑
      3. 輸出 D10/D50/D90、細粉比例與形狀統計

    Why:
      模型同時需要「和量測圖一致的直徑」與「幾何上較穩定的等效直徑」；
      兩者應分開保存，避免後續混用。
    """
    particles = load_psd_raw_csv(raw_csv_path)
    stats = load_psd_stats_csv(stats_csv_path) if stats_csv_path else {}

    d_hist = [p["diameter_hist_mm"] for p in particles]
    d_eq = [p["diameter_eq_mm"] for p in particles]
    volumes = [p["volume_mm3"] for p in particles]
    areas = [p["surface_mm2"] for p in particles]
    aspects = [p["aspect_ratio"] for p in particles]
    roundness = [p["roundness"] for p in particles]

    summary = {
        "raw_csv_path": str(Path(raw_csv_path).resolve()),
        "stats_csv_path": str(Path(stats_csv_path).resolve()) if stats_csv_path else "",
        "particle_count": len(particles),
        "diameter_definition_hist": "diameter_hist_mm = (SHORT_AXIS + LONG_AXIS) / 10",
        "diameter_definition_model": "diameter_eq_mm = sqrt(SHORT_AXIS * LONG_AXIS) / 5",
        "hist_avg_diam_mm": statistics.fmean(d_hist),
        "hist_D10_mm": _quantile(d_hist, 0.10),
        "hist_D50_mm": _quantile(d_hist, 0.50),
        "hist_D90_mm": _quantile(d_hist, 0.90),
        "model_avg_diam_mm": statistics.fmean(d_eq),
        "model_D10_mm": _quantile(d_eq, 0.10),
        "model_D50_mm": _quantile(d_eq, 0.50),
        "model_D90_mm": _quantile(d_eq, 0.90),
        "model_Dv10_mm": _weighted_quantile(d_eq, volumes, 0.10),
        "model_Dv50_mm": _weighted_quantile(d_eq, volumes, 0.50),
        "model_Dv90_mm": _weighted_quantile(d_eq, volumes, 0.90),
        "model_Da10_mm": _weighted_quantile(d_eq, areas, 0.10),
        "model_Da50_mm": _weighted_quantile(d_eq, areas, 0.50),
        "model_Da90_mm": _weighted_quantile(d_eq, areas, 0.90),
        "fines_num_lt_0p30mm": sum(d < 0.30 for d in d_eq) / len(d_eq),
        "fines_num_lt_0p40mm": sum(d < 0.40 for d in d_eq) / len(d_eq),
        "fines_num_lt_0p50mm": sum(d < 0.50 for d in d_eq) / len(d_eq),
        "fines_vol_lt_0p30mm": sum(v for d, v in zip(d_eq, volumes) if d < 0.30) / max(sum(volumes), 1e-12),
        "fines_vol_lt_0p40mm": sum(v for d, v in zip(d_eq, volumes) if d < 0.40) / max(sum(volumes), 1e-12),
        "fines_vol_lt_0p50mm": sum(v for d, v in zip(d_eq, volumes) if d < 0.50) / max(sum(volumes), 1e-12),
        "aspect_ratio_mean": statistics.fmean(aspects),
        "aspect_ratio_median": _quantile(aspects, 0.50),
        "aspect_ratio_p90": _quantile(aspects, 0.90),
        "roundness_mean": statistics.fmean(roundness),
        "roundness_median": _quantile(roundness, 0.50),
        "roundness_p10": _quantile(roundness, 0.10),
        # 模型建議欄位：目前優先把面積等效直徑的 number-based D10 鎖進粒子子模型
        "recommended_D10_m": _quantile(d_eq, 0.10) / 1000.0,
        "recommended_D50_m": _quantile(d_eq, 0.50) / 1000.0,
        "recommended_D90_m": _quantile(d_eq, 0.90) / 1000.0,
    }

    if stats:
        summary.update(stats)
        summary["hist_avg_diam_relerr_pct"] = 100.0 * (
            summary["hist_avg_diam_mm"] - stats["stats_avg_diam_mm"]
        ) / max(stats["stats_avg_diam_mm"], 1e-12)
    return summary


def _shell_accessibility_fraction(diameter_mm: float, shell_thickness_mm: float = DEFAULT_SHELL_THICKNESS_MM) -> float:
    """
    估算固定殼層厚度下的可及體積比例。

    What: 將顆粒視為等效球體，回傳最外層 `shell_thickness_mm` 的體積占比。
    Why:  這能把「200 μm 外層可及」直接套到實測 PSD，而不必回退到理想碎形假設。
    """
    radius = 0.5 * max(float(diameter_mm), 1e-12)
    shell = min(max(float(shell_thickness_mm), 0.0), radius)
    core_radius = max(radius - shell, 0.0)
    return 1.0 - (core_radius / radius) ** 3


def infer_psd_bins(
    raw_csv_path: str | Path,
    bin_edges_mm: tuple[float, ...] = DEFAULT_BIN_EDGES_MM,
    shell_thickness_mm: float = DEFAULT_SHELL_THICKNESS_MM,
) -> list[dict]:
    """
    將實測 PSD 彙整為 multi-bin 表。

    What:
      依 `diameter_eq_mm` 將顆粒分桶，輸出各 bin 的：
      - number / area / volume fraction
      - 平均粒徑、aspect ratio、roundness
      - 比表面積代理與 shell accessibility

    Why:
      流動、堵塞與萃取不是由單一 D10 決定；multi-bin 表可以同時保留
      fines、粗顆粒、形狀與外層可及性的粒徑依賴。
    """
    if len(bin_edges_mm) < 2:
        raise ValueError("bin_edges_mm 至少需要兩個邊界")

    particles = load_psd_raw_csv(raw_csv_path)
    total_count = len(particles)
    total_area = sum(p["surface_mm2"] for p in particles)
    total_volume = sum(p["volume_mm3"] for p in particles)

    bins: list[dict] = []
    for idx, (lo, hi) in enumerate(zip(bin_edges_mm[:-1], bin_edges_mm[1:])):
        bucket = [p for p in particles if lo <= p["diameter_eq_mm"] < hi]
        if not bucket:
            continue

        count = len(bucket)
        area_sum = sum(p["surface_mm2"] for p in bucket)
        volume_sum = sum(p["volume_mm3"] for p in bucket)
        eq_diams = [p["diameter_eq_mm"] for p in bucket]
        shell_fracs = [
            _shell_accessibility_fraction(p["diameter_eq_mm"], shell_thickness_mm=shell_thickness_mm)
            for p in bucket
        ]

        bins.append({
            "bin_index": idx,
            "d_lo_mm": lo,
            "d_hi_mm": hi,
            "d_mid_mm": 0.5 * (lo + hi),
            "particle_count": count,
            "num_fraction": count / max(total_count, 1),
            "area_fraction": area_sum / max(total_area, 1e-12),
            "volume_fraction": volume_sum / max(total_volume, 1e-12),
            "diameter_eq_mean_mm": statistics.fmean(eq_diams),
            "diameter_eq_median_mm": _quantile(eq_diams, 0.50),
            "aspect_ratio_mean": statistics.fmean(p["aspect_ratio"] for p in bucket),
            "roundness_mean": statistics.fmean(p["roundness"] for p in bucket),
            "surface_to_volume_mm_inv_mean": statistics.fmean(p["surface_to_volume_mm_inv"] for p in bucket),
            "shell_accessibility_mean": statistics.fmean(shell_fracs),
            "shell_accessibility_volume_weighted": (
                sum(sf * p["volume_mm3"] for sf, p in zip(shell_fracs, bucket)) / max(volume_sum, 1e-12)
            ),
        })

    if not bins:
        raise ValueError("PSD 分桶結果為空，請檢查 bin_edges_mm 是否合理")
    return bins


def psd_overrides_for_model(summary: dict, bins_csv_path: str | Path | None = None) -> dict:
    """
    將 PSD 摘要轉成模型 override。

    What: 回傳目前模型可以直接接收的最小 override 集。
    Why:  現階段先把實測 D10 鎖進粒子子模型；若已有 bins CSV，也一併把分桶路徑傳入，
          讓 params.py 可直接取代理想碎形 PSD。
    """
    overrides = {
        "D10_measured_m": float(summary["recommended_D10_m"]),
    }
    if bins_csv_path is not None:
        overrides["psd_bins_csv_path"] = str(Path(bins_csv_path).resolve())
    return overrides


def save_psd_summary_csv(output_path: str | Path, summary: dict) -> None:
    """將 PSD 摘要寫成單列 CSV。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(summary.keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(summary)


def save_psd_bins_csv(output_path: str | Path, bins: list[dict]) -> None:
    """將 multi-bin PSD 表寫成 CSV。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(bins[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(bins)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Convert PSD CSV exports into model-ready summary values.")
    parser.add_argument("raw_csv", help="Path to raw PSD CSV")
    parser.add_argument("--stats-csv", default=None, help="Optional stats CSV from the same export")
    parser.add_argument(
        "--output",
        default="data/psd_summary.csv",
        help="Output summary CSV path",
    )
    parser.add_argument(
        "--bin-output",
        default="data/psd_bins.csv",
        help="Output multi-bin PSD CSV path",
    )
    parser.add_argument(
        "--shell-thickness-mm",
        type=float,
        default=DEFAULT_SHELL_THICKNESS_MM,
        help="Accessible shell thickness used in multi-bin summary",
    )
    args = parser.parse_args()

    summary = infer_psd_summary(args.raw_csv, args.stats_csv)
    bins = infer_psd_bins(
        args.raw_csv,
        shell_thickness_mm=args.shell_thickness_mm,
    )
    save_psd_summary_csv(args.output, summary)
    save_psd_bins_csv(args.bin_output, bins)

    print("=== PSD Summary ===")
    print(f"  Raw CSV            : {Path(args.raw_csv).resolve()}")
    if args.stats_csv:
        print(f"  Stats CSV          : {Path(args.stats_csv).resolve()}")
    print(f"  Particle count     : {summary['particle_count']}")
    print(f"  Hist D10 / D50 / D90 : {summary['hist_D10_mm']:.3f} / {summary['hist_D50_mm']:.3f} / {summary['hist_D90_mm']:.3f} mm")
    print(f"  Model D10 / D50 / D90: {summary['model_D10_mm']:.3f} / {summary['model_D50_mm']:.3f} / {summary['model_D90_mm']:.3f} mm")
    print(f"  Fines <0.40 mm     : {summary['fines_num_lt_0p40mm']*100:.1f}% (number)")
    print(f"  Aspect median / p90: {summary['aspect_ratio_median']:.2f} / {summary['aspect_ratio_p90']:.2f}")
    print(f"  Roundness median   : {summary['roundness_median']:.3f}")
    print(f"  Recommended D10    : {summary['recommended_D10_m']*1e6:.0f} μm")
    print(f"  Multi-bin rows     : {len(bins)}")
    print(f"  Output             : {Path(args.output).resolve()}")
    print(f"  Bin output         : {Path(args.bin_output).resolve()}")


if __name__ == "__main__":
    _cli()
