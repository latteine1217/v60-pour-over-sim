# Experiment Record

本檔是本專案的 canonical state backend，用於：
- 讓 agent 先讀 index 再讀細節
- 把 active baseline 與 archived exploration 分開
- 讓 artifact 路徑可被快速檢索

`EXPERIMENT_LOG.md` 保留為 human-readable narrative companion。

---

## [SCHEMA]

每筆 entry 固定包含：
- `entry_id`
- `timestamp`
- `status`
- `theme`
- `change`
- `artifacts`
- `results`
- `interpretation`

狀態定義：
- `active`：仍直接支撐目前正式 baseline 或當前行為規則
- `archived`：歷史探索，保留證據，但不作當前主敘事

---

## [INDEX] Active

| Entry ID | Timestamp | Theme | Why Active | Key Artifacts |
|---|---|---|---|---|
| `EXP-20260330-041106` | `2026-03-30 04:11:06 +0800` | formal benchmark + hydraulic identifiability | 定義了正式 benchmark 與 `k/k_beta/wetbed` 的可識別性排序 | `data/kinu29_fit_identifiability_slices.csv`, `data/kinu29_fit_identifiability_heatmap.png` |
| `EXP-20260330-051222` | `2026-03-30 05:12:22 +0800` | pref-flow policy | 定義了 `pref_flow` 只保留單自由度且預設不強行啟用的正式策略 | `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`, `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`, `data/benchmark_suite_summary.csv` |
| `EXP-20260330-124820` | `2026-03-30 12:48:20 +0800` | axial extraction + server cooling | 兩層軸向床與壺端自然對流仍在正式 baseline 內 | `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`, `data/kinu29_calibrated_flow_diagnostics_180s.png`, `data/kinu29_calibrated_extraction_quality_180s.png` |
| `EXP-20260330-145202` | `2026-03-30 14:52:02 +0800` | explicit `kr(sat)` | 顯式 unsaturated Darcy 已成為主模型正式 closure | `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`, `data/benchmark_suite_summary.csv`, `data/kinu29_calibrated_flow_diagnostics_180s.png` |
| `EXP-20260330-151548` | `2026-03-30 15:15:48 +0800` | bloom choke diagnostics | 定義目前 bloom 前 choke 的正式判讀：`head_gate` 主導，`kr(sat)` 次之 | `data/kinu29_calibrated_flow_diagnostics_180s.png`, `data/kinu29_fit_identifiability_slices.csv`, `data/kinu29_fit_identifiability_heatmap.png`, `data/benchmark_suite_summary.csv` |
| `EXP-20260407-165556` | `2026-04-07 16:55:56 +0800` | PSD raw ingestion | 將 `data/kinu_29_light/` raw export 轉為正式 measured-PSD artifact，補齊主模型 ingest 路徑 | `data/kinu29_psd_summary.csv`, `data/kinu29_psd_bins.csv`, `data/kinu_29_light/kinu29_PSD_export_data.csv`, `data/kinu_29_light/kinu29_PSD_export_data_stats.csv` |

---

## [INDEX] Archived

| Entry ID | Timestamp | Theme | Why Archived | Key Artifacts |
|---|---|---|---|---|
| `EXP-20260328-183519` | `2026-03-28 18:35:19 +0800` | wetbed coarse scan | 首輪探索，已被後續正式掃描與正式 fit 取代 | `data/archive/2026-03-exploration/kinu29_wetbed_struct_scan.csv`, `data/archive/2026-03-exploration/kinu29_wetbed_struct_scan_heatmap.png` |
| `EXP-20260328-184144` | `2026-03-28 18:41:44 +0800` | wetbed formal scan | 支撐過 `wetbed χ` 的保留判斷，但已不是直接 baseline artifact | `data/archive/2026-03-exploration/kinu29_wetbed_struct_scan_formal.csv`, `data/archive/2026-03-exploration/kinu29_wetbed_struct_scan_formal_heatmap.png` |
| `EXP-20260328-185212` | `2026-03-28 18:52:12 +0800` | early wetbedchi fit | 早期 measured fit，已被正式 baseline summary 取代 | `data/archive/2026-03-exploration/kinu29_light_20g_flow_fit_with_wetbedchi_summary.csv` |
| `EXP-20260330-044713` | `2026-03-30 04:47:13 +0800` | pref-flow exploratory identifiability | 探索性結果仍保留，但正式策略已降級為固定 shape + optional coeff | `data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_slices_fast.csv`, `data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_heatmap_fast.png`, `data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_slices.csv`, `data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_heatmap.png` |

---

## [BASELINE] Current

- `baseline_id`: `BL-20260330-151548`
- `case`: `kinu29_light_20g_measured`
- `status`: `PASS`
- `grinder`: `Kinu 29`
- `roast`: `light`
- `dose`: `20 g`
- `bed_height`: `5.3 cm`
- `ambient`: `23 degC`
- `dripper`: `ceramic V60, 123.5 g`
- `axial_node_count`: `2`
- `summary_csv`: `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `psd_summary_csv`: `data/kinu29_psd_summary.csv`
- `psd_bins_csv`: `data/kinu29_psd_bins.csv`
- `benchmark_csv`: `data/benchmark_suite_summary.csv`
- `flow_diagnostics`: `data/kinu29_calibrated_flow_diagnostics_180s.png`
- `extraction_quality`: `data/kinu29_calibrated_extraction_quality_180s.png`
- `identifiability_slices`: `data/kinu29_fit_identifiability_slices.csv`
- `identifiability_heatmap`: `data/kinu29_fit_identifiability_heatmap.png`

Current benchmark metrics:

| Metric | Value |
|---|---|
| `k_fit` | `8.441e-11` |
| `k_beta_fit` | `1.972e3` |
| `tau_lag` | `1.6 s` |
| `wetbed_struct_gain_fit` | `0.1892` |
| `pref_flow_coeff_fit` | `0.0` |
| `server_cooling_lambda_fit` | `5.273e-4` |
| `V_out RMSE` | `13.39 mL` |
| `q_out RMSE` | `1.24 mL/s` |
| `drain_time_error` | `+1.46 s` |
| `cup_temp_error` | `+0.05 degC` |

Current diagnostic conclusion:

| Item | Observation | Implication |
|---|---|---|
| bloom choke driver | `head_gate (h_cap/h_gas)` | 當前未飽和段主導限制不是 `sat_flow` |
| secondary choke | `kr(sat)` | 顯式 unsaturated Darcy 有必要保留 |
| identifiability | `sat_rel_perm_*` 近 flat ridge | 不宜把 `kr(sat)` 參數升級成主擬合自由度 |
| thermal closure | `server-side natural convection` | 杯溫誤差應先由壺端散熱解釋 |
| measured PSD ingress | raw export 已轉成 `psd_summary` / `psd_bins` | baseline measured PSD 已有可重跑 artifact，不再只靠敘事 |

---

## [ENTRY] EXP-20260328-183519

- `timestamp`: `2026-03-28 18:35:19 +0800`
- `status`: `archived`
- `theme`: `wetbed coarse scan`

### Change
- 將 `chi_struct` 正式接入 `k_eff`
- 對 `wetbed_struct_gain / rate / release` 做首輪粗掃描

### Artifacts
- `data/archive/2026-03-exploration/kinu29_wetbed_struct_scan.csv`
- `data/archive/2026-03-exploration/kinu29_wetbed_struct_scan_heatmap.png`

### Results

| Metric | Value |
|---|---|
| best gain | `0.30` |
| best rate | `0.16` |
| best release | `0.60` |
| `V_out RMSE` | `13.32 mL` |
| `q_out RMSE` | `1.19 mL/s` |
| `drain_time_error` | `+0.39 s` |

### Interpretation
- `chi_struct` 有可辨識訊號
- 改善主要來自累積出液與停流時間，不是瞬時流速 RMSE

---

## [ENTRY] EXP-20260328-184144

- `timestamp`: `2026-03-28 18:41:44 +0800`
- `status`: `archived`
- `theme`: `wetbed formal scan`

### Change
- 擴大 `wetbed_struct_*` 掃描範圍，做正式掃描

### Artifacts
- `data/archive/2026-03-exploration/kinu29_wetbed_struct_scan_formal.csv`
- `data/archive/2026-03-exploration/kinu29_wetbed_struct_scan_formal_heatmap.png`

### Results

| Metric | Value |
|---|---|
| best gain | `1.00` |
| best rate | `0.03` |
| best release | `0.30` |
| `V_out RMSE` | `13.27 mL` |
| `q_out RMSE` | `1.18 mL/s` |
| `drain_time_error` | `+0.55 s` |

### Interpretation
- `release≈0.30` 相對穩定
- `gain` 與 `rate` 之間存在 ridge，不適合三個自由度同時正式擬合

---

## [ENTRY] EXP-20260328-185212

- `timestamp`: `2026-03-28 18:52:12 +0800`
- `status`: `archived`
- `theme`: `early wetbedchi fit`

### Change
- measured fitting 流程加入 `wetbed χ`
- 固定 `wetbed_struct_rate = 0.06068366147200567`
- 固定 `wetbed_impact_release_rate = 0.30`
- 只擬合 `wetbed_struct_gain`

### Artifacts
- `data/archive/2026-03-exploration/kinu29_light_20g_flow_fit_with_wetbedchi_summary.csv`

### Results

| Metric | Value |
|---|---|
| `k_fit` | `9.076e-11` |
| `k_beta_fit` | `3.005e3` |
| `tau_lag` | `1.6 s` |
| `wetbed_struct_gain_fit` | `0.1082` |
| `V_out RMSE` | `13.46 mL` |
| `q_out RMSE` | `1.25 mL/s` |
| `drain_time_error` | `+1.38 s` |

### Interpretation
- `wetbed χ` 應保留，但只宜保留單一自由度 `gain`

---

## [ENTRY] EXP-20260330-041106

- `timestamp`: `2026-03-30 04:11:06 +0800`
- `status`: `active`
- `theme`: `formal benchmark + hydraulic identifiability`

### Change
- 建立 formal benchmark 流程
- 新增 measured fit 的局部可識別性分析

### Artifacts
- `data/kinu29_fit_identifiability_slices.csv`
- `data/kinu29_fit_identifiability_heatmap.png`

### Results

| Item | Observation | Implication |
|---|---|---|
| `k` | 對 loss 很敏感 | 硬參數 |
| `k_beta` | 弱可識別 | 可保留，但需搭配 PSD prior |
| `wetbed_struct_gain / rate` | 幾乎是平 ridge | `wetbed_struct_rate` 不應再自由漂移 |

---

## [ENTRY] EXP-20260330-044713

- `timestamp`: `2026-03-30 04:47:13 +0800`
- `status`: `archived`
- `theme`: `pref-flow exploratory identifiability`

### Change
- 新增 `pref_flow_*` 專用 identifiability 分析
- 對 `pref_flow_coeff / open_rate / tau_decay` 做局部掃描

### Artifacts
- `data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_slices_fast.csv`
- `data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_heatmap_fast.png`
- `data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_slices.csv`
- `data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_heatmap.png`

### Results

| Item | Observation | Implication |
|---|---|---|
| `pref_flow_coeff` | `medium` | 非硬參數 |
| `pref_flow_open_rate` | `medium` | 不值得與 `tau_decay` 同時放開 |
| `pref_flow_tau_decay` | `medium` | 適合固定化 |

### Interpretation
- 正式策略應為固定 `pref_flow_open_rate / tau_decay`
- 只保留 `pref_flow_coeff` 為候選自由度

---

## [ENTRY] EXP-20260330-051222

- `timestamp`: `2026-03-30 05:12:22 +0800`
- `status`: `active`
- `theme`: `pref-flow formal policy`

### Change
- 將 `pref_flow` 第四階段改為正式單自由度版本
- 只擬合 `pref_flow_coeff`
- `pref_flow_open_rate`、`pref_flow_tau_decay` 改為 fixed
- 加入 final-resolution 守門

### Artifacts
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `data/benchmark_suite_summary.csv`

### Results

| Metric | Value |
|---|---|
| `k_fit` | `8.478e-11` |
| `k_beta_fit` | `1.528e3` |
| `tau_lag` | `2.0 s` |
| `wetbed_struct_gain_fit` | `0.1809` |
| `pref_flow_coeff_fit` | `0.0` |
| `pref_flow_open_rate_fixed` | `0.254074546131474` |
| `pref_flow_tau_decay_fixed` | `3.1401416403754285` |
| `fit_preferential_flow` | `False` |
| `V_out RMSE` | `13.53 mL` |
| `q_out RMSE` | `1.25 mL/s` |
| `drain_time_error` | `+1.16 s` |
| `cup_temp_error` | `+3.10 degC` |

### Interpretation
- 正式流程允許 `pref_flow` 存在，但不會強行啟用

---

## [ENTRY] EXP-20260330-124820

- `timestamp`: `2026-03-30 12:48:20 +0800`
- `status`: `active`
- `theme`: `axial extraction + server cooling`

### Change
- 將床內萃取由單一 CSTR 升級為兩層軸向串接模型
- 在 lag layer 後加入顯式 `server-side natural convection`
- 讓 measured fit 額外標定 `lambda_server_ambient`

### Artifacts
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `data/benchmark_suite_summary.csv`
- `data/kinu29_calibrated_flow_diagnostics_180s.png`
- `data/kinu29_calibrated_extraction_quality_180s.png`

### Results

| Metric | Value |
|---|---|
| `axial_node_count` | `2` |
| `k_fit` | `9.056e-11` |
| `k_beta_fit` | `2.362e3` |
| `tau_lag` | `2.0 s` |
| `wetbed_struct_gain_fit` | `0.1308` |
| `pref_flow_coeff_fit` | `2.774e-5` |
| `server_cooling_lambda_fit` | `5.556e-4` |
| `V_out RMSE` | `13.77 mL` |
| `q_out RMSE` | `1.25 mL/s` |
| `drain_time_error` | `+0.71 s` |
| `cup_temp_error` | `+0.07 degC` |

### Interpretation
- 兩層軸向床已足以保留上下層濃度差
- 杯溫主誤差來自壺端散熱

---

## [ENTRY] EXP-20260330-145202

- `timestamp`: `2026-03-30 14:52:02 +0800`
- `status`: `active`
- `theme`: `explicit kr(sat)`

### Change
- 在主 Darcy 路徑加入顯式 `kr(sat)`
- `q_preferential()` 同步吃進 `kr(sat)`
- 重跑 calibrated fit / benchmark / calibrated figures

### Artifacts
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `data/benchmark_suite_summary.csv`
- `data/kinu29_calibrated_flow_diagnostics_180s.png`
- `data/kinu29_calibrated_extraction_quality_180s.png`

### Results

| Metric | Value |
|---|---|
| `k_fit` | `8.441e-11` |
| `k_beta_fit` | `1.972e3` |
| `tau_lag` | `1.6 s` |
| `wetbed_struct_gain_fit` | `0.1892` |
| `pref_flow_coeff_fit` | `0.0` |
| `server_cooling_lambda_fit` | `5.273e-4` |
| `V_out RMSE` | `13.39 mL` |
| `q_out RMSE` | `1.24 mL/s` |
| `drain_time_error` | `+1.46 s` |
| `cup_temp_error` | `+0.05 degC` |

### Interpretation
- 顯式 `kr(sat)` 讓未飽和水力 closure 更乾淨
- `pref_flow` 再次退回不必要

---

## [ENTRY] EXP-20260330-151548

- `timestamp`: `2026-03-30 15:15:48 +0800`
- `status`: `active`
- `theme`: `bloom choke diagnostics`

### Change
- 將 `kr(sat)` 納入主 diagnostics panel
- 新增 bloom 視窗內的 `sat_flow / kr(sat) / head_gate` 分解
- 將 `sat_rel_perm_residual`、`sat_rel_perm_exp` 納入 identifiability slices 與 hydraulic heatmap

### Artifacts
- `data/kinu29_calibrated_flow_diagnostics_180s.png`
- `data/kinu29_calibrated_extraction_quality_180s.png`
- `data/kinu29_fit_identifiability_slices.csv`
- `data/kinu29_fit_identifiability_heatmap.png`
- `data/benchmark_suite_summary.csv`

### Results

| Item | Observation | Implication |
|---|---|---|
| benchmark | `PASS` | 正式 baseline 維持有效 |
| `V_out RMSE` | `13.39 mL` | 仍在 gate 內 |
| `q_out RMSE` | `1.24 mL/s` | 仍在 gate 內 |
| `drain_time_error` | `+1.46 s` | 仍在 gate 內 |
| `cup_temp_error` | `+0.05 degC` | 熱端 closure 穩定 |
| `h_cap/h_gas` | `0.662` | bloom choke 主導者 |
| `kr(sat)` | `0.380` | 次級限制 |
| `sat_flow` | `0.264` | 更次級 |

### Interpretation
- 目前 measured baseline 的 bloom 前 choke 主導者是 `head_gate`
- `sat_rel_perm_*` 屬弱可識別 closure，不應取代 `k` 或 `h_cap/h_gas`

---

## [ENTRY] EXP-20260407-165556

- `timestamp`: `2026-04-07 16:55:56 +0800`
- `status`: `active`
- `theme`: `PSD raw ingestion`

### Change
- 將 `data/kinu_29_light/kinu29_PSD_export_data.csv` 與對應 stats 檔轉成正式 model-ready artifact
- 生成 `data/kinu29_psd_summary.csv` 與 `data/kinu29_psd_bins.csv`
- 執行 `uv run python -m compileall pour_over` 做最小 smoke check

### Artifacts
- `data/kinu_29_light/kinu29_PSD_export_data.csv`
- `data/kinu_29_light/kinu29_PSD_export_data_stats.csv`
- `data/kinu29_psd_summary.csv`
- `data/kinu29_psd_bins.csv`

### Results

| Metric | Value |
|---|---|
| particle count | `4554` |
| `hist_D10 / D50 / D90` | `0.374 / 0.723 / 1.611 mm` |
| `model_D10 / D50 / D90` | `0.374 / 0.705 / 1.518 mm` |
| `recommended_D10` | `374 μm` |
| `fines_num_lt_0p40mm` | `13.2 %` |
| multi-bin rows | `7` |
| smoke test | `PASS` |

### Interpretation
- raw export 與目前 baseline 內的 `D10 ≈ 374 μm` 一致，measured PSD 主敘事有正式數據支撐
- 這次工作沒有重跑 calibrated fit 或 benchmark，因此新增的是 artifact reproducibility，不是新的性能結論
- 主模型目前仍透過 `data/kinu29_psd_bins.csv` ingest measured PSD；未來若 raw export 更新，應同步重生 bins artifact

---

## [POLICY] Current Working Rules

| Item | Rule |
|---|---|
| `sat_flow` | 維持平滑鬆弛，不回到硬切 |
| `kr(sat)` | 保留在主 Darcy 路徑與 `q_preferential()` |
| bloom diagnostics | 優先檢查 `head_gate -> kr_sat -> sat_flow` |
| `chi_struct` | 正式回饋到 `k_eff` |
| extraction | 正式版本維持 `axial_node_count = 2` |
| `sat_rel_perm_*` | 視為弱可識別 closure，不作主擬合自由度 |
| `wetbed χ` | `gain` 可擬合；`rate = 0.06068366147200567` 固定；`release = 0.30` 固定 |
| `pref_flow` | `coeff` 僅作候選自由度；`open_rate = 0.254074546131474` 固定；`tau_decay = 3.1401416403754285` 固定 |
| thermal | `lambda_server_ambient` 可作單自由度熱端 closure |
