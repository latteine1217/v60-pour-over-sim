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
| `EXP-20260407-165556` | `2026-04-07 16:55:56 +0800` | PSD raw ingestion | 將 `data/kinu_29_light/` raw export 轉為正式 measured-PSD artifact，補齊主模型 ingest 路徑 | `data/kinu29_psd_summary.csv`, `data/kinu29_psd_bins.csv`, `data/kinu_29_light/PSD_export_data.csv`, `data/kinu_29_light/PSD_export_data_stats.csv` |
| `EXP-20260411-163313` | `2026-04-11 16:33:13 +0800` | PSD refresh + measured ingest fix | 新 PSD export 已進入正式 measured fit，不再停留在 artifact-only 更新 | `data/kinu29_psd_summary.csv`, `data/kinu29_psd_bins.csv`, `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv` |
| `EXP-20260411-164750` | `2026-04-11 16:47:50 +0800` | thermal validation line | 新增 `T1/T2/final TDS` 驗證線，顯示水力 baseline 通過但熱/萃取仍失配 | `data/kinu29_light_20g_thermal_profile_comparison.png`, `data/kinu29_calibrated_flow_diagnostics_180s.png`, `data/kinu29_calibrated_extraction_quality_180s.png` |
| `EXP-20260411-170258` | `2026-04-11 17:02:58 +0800` | k_ext scan against hard TDS target | 證明目前缺口不是單純 `k_ext_coef`，而是可萃總量 budget / accessibility 結構上限 | `data/kinu29_kext_scan_thermal_recipe.csv` |
| `EXP-20260411-184949` | `2026-04-11 18:49:49 +0800` | max_EY scan against hard TDS target | 證明只放寬 `max_EY` 也不夠，缺口來自更深的萃取結構限制 | `data/kinu29_max_ey_scan_thermal_recipe.csv` |
| `EXP-20260411-185226` | `2026-04-11 18:52:26 +0800` | shell accessibility scan | 證明單獨放寬 shell accessibility 也不夠，限制已轉到 diffusion-path / transfer-history | `data/kinu29_shell_thickness_scan_thermal_recipe.csv` |
| `EXP-20260411-190016` | `2026-04-11 19:00:16 +0800` | direct diffusion-path scan | 證明即使極端縮短 effective path，TDS 仍碰不到量測值 | `data/kinu29_diffusion_path_scan_thermal_recipe.csv` |
| `EXP-20260411-190659` | `2026-04-11 19:06:59 +0800` | joint shell-path scan | 證明量測 TDS 只有在 accessibility 與 path 聯合放寬時才可達，但 `T2` 失配仍存在 | `data/kinu29_shell_path_joint_scan_thermal_recipe.csv`, `data/kinu29_shell_path_joint_scan_thermal_recipe.png` |
| `EXP-20260411-193303` | `2026-04-11 19:33:03 +0800` | shell-path closure rewrite + rebaseline | 修正 measured-bin 幾何不一致後，formal baseline 仍通過 benchmark，但 thermal/TDS 主缺口仍在 | `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`, `data/benchmark_suite_summary.csv`, `data/kinu29_light_20g_thermal_profile_comparison.png` |
| `EXP-20260412-014510` | `2026-04-12 01:45:10 +0800` | inventory conservation rewrite | 修正 bin inventory 與總可萃量守恆語義，讓 shell 幾何只改變 fast-slow split | `pour_over/params.py` |
| `EXP-20260412-014943` | `2026-04-12 01:49:43 +0800` | formal rebaseline after inventory rewrite | 在守恆語義修正後重跑 formal fit；benchmark 仍 PASS，且 thermal TDS 繼續上升 | `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`, `data/benchmark_suite_summary.csv`, `data/kinu29_light_20g_thermal_profile_comparison.png` |
| `EXP-20260412-150601` | `2026-04-12 15:06:01 +0800` | slow interface rewrite + rebaseline | 將 slow pool 有效界面改為受 shell 幾何限制後重跑 formal fit；flow benchmark 維持 PASS，且 thermal TDS 小幅改善 | `pour_over/params.py`, `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`, `data/benchmark_suite_summary.csv`, `data/kinu29_light_20g_thermal_profile_comparison.png` |
| `EXP-20260420-194710` | `2026-04-20 19:47:10 +0800` | apex startup thermal closure | 將 `T2` 明確綁到冷 apex 初始條件與 startup apex hold-up；`4:20` / `4:12` 進一步改善，但 `4:11` 仍顯示快熱啟動 regime mismatch | `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile_comparison.png`, `pour_over/core.py`, `pour_over/fitting.py`, `tests/test_measured_case_registry.py` |
| `EXP-20260424-152021` | `2026-04-24 15:20:21 +0800` | bloom thermal-flow diagnostics | 將 `0-40 s` 悶蒸期改為熱/流耦合診斷視窗，不再只看 `10-20 s` 的局部 T2 殘差 | `data/bloom_thermal_flow_diagnostics.png`, `data/kinu_28_light/4:20/kinu28_light_20g_bloom_thermal_flow_diagnostics.csv`, `data/kinu_29_light/4:12/kinu29_light_20g_bloom_thermal_flow_diagnostics.csv`, `data/kinu_29_light/4:11/kinu29_light_20g_bloom_thermal_flow_diagnostics.csv` |
| `EXP-20260425-130812` | `2026-04-25 13:08:12 +0800` | H1 flow-timing hypothesis test | H1 僅部分成立：`4:12` partial，`4:20` / `4:11` not supported；flow/observation timing 不是全域主因 | `data/bloom_h1_flow_timing_summary.csv`, `pour_over/bloom_diagnostics.py`, `tests/test_bloom_diagnostics.py` |
| `EXP-20260425-133024` | `2026-04-25 13:30:24 +0800` | H2 effluent coupling gate test | H2 不成立：`liq_transport_gate` / `head_gate` 都沒有降低 early T2 RMSE；常開 bulk-effluent 耦合不是 early overheating 主因 | `data/bloom_h2_effluent_coupling_summary.csv`, `pour_over/core.py`, `pour_over/params.py`, `pour_over/bloom_diagnostics.py` |
| `EXP-20260425-135810` | `2026-04-25 13:58:10 +0800` | H3 apex contact-history test | H3 單一 contact-memory observation 僅部分成立：只改善 `4:20` early，但 late 與其他 cases 明顯惡化 | `data/bloom_h3_apex_contact_summary.csv`, `pour_over/bloom_diagnostics.py`, `tests/test_bloom_diagnostics.py` |
| `EXP-20260425-142842` | `2026-04-25 14:28:42 +0800` | H4 dual-path apex mixing test | H4 部分成立：`liq_transport_gate` dual-path 改善 `4:20` / `4:12` early，且未明顯打壞 `4:11`，但 late 仍惡化 | `data/bloom_h4_dual_path_apex_summary.csv`, `pour_over/bloom_diagnostics.py`, `tests/test_bloom_diagnostics.py` |
| `EXP-20260425-145211` | `2026-04-25 14:52:11 +0800` | H4b dual-path release test | H4b 進一步支持 dual-path：`release_after25` 修正 `4:20` late penalty，`4:12` 仍 partial，`4:11` 未明顯打壞 | `data/bloom_h4_dual_path_apex_summary.csv`, `pour_over/bloom_diagnostics.py`, `tests/test_bloom_diagnostics.py` |
| `EXP-20260428-154930` | `2026-04-28 15:49:30 +0800` | H4c event-based dual-path release | 將 release trigger 綁到 recipe event；between-pours trigger 比固定時間更合理，改善 `4:20` / `4:12` early 並降低 late penalty | `data/bloom_h4_dual_path_apex_summary.csv`, `pour_over/bloom_diagnostics.py`, `tests/test_bloom_diagnostics.py` |
| `EXP-20260428-163057` | `2026-04-28 16:30:57 +0800` | formal channeling flow/thermal closure | 將通道效應正式納入主模型：flow 暴露 fast/side split，thermal T2 改用 dual-path mixed apex | `pour_over/core.py`, `pour_over/observation.py`, `pour_over/fitting.py`, `tests/test_core_mass_balance.py`, `tests/test_measured_case_registry.py` |

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

- `baseline_id`: `BL-20260412-150601`
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
- `thermal_validation`: `data/kinu29_light_20g_thermal_profile_comparison.png`
- `identifiability_slices`: `pending refresh after PSD baseline update`
- `identifiability_heatmap`: `pending refresh after PSD baseline update`

Current benchmark metrics:

| Metric | Value |
|---|---|
| `k_fit` | `8.215e-11` |
| `k_beta_fit` | `1.205e3` |
| `tau_lag` | `2.0 s` |
| `wetbed_struct_gain_fit` | `0.2946` |
| `pref_flow_coeff_fit` | `0.0` |
| `server_cooling_lambda_fit` | `5.348e-4` |
| `V_out RMSE` | `13.51 mL` |
| `q_out RMSE` | `1.24 mL/s` |
| `drain_time_error` | `+1.46 s` |
| `cup_temp_error` | `+0.04 degC` |

Current diagnostic conclusion:

| Item | Observation | Implication |
|---|---|---|
| bloom choke driver | `head_gate (h_cap/h_gas)` | 當前未飽和段主導限制不是 `sat_flow` |
| secondary choke | `kr(sat)` | 顯式 unsaturated Darcy 有必要保留 |
| identifiability | `pending refresh` | 新 PSD baseline 尚未重跑 heatmap，不應直接沿用舊 ridge 結論 |
| thermal closure | `server-side natural convection` | 杯溫誤差應先由壺端散熱解釋 |
| measured PSD ingress | 新 PSD export 已重生並進正式 fit | baseline D10 與 `k_beta` prior 都已切到新量測 |
| thermal validation | `T1 RMSE = 2.36 °C`, `T2 RMSE = 7.92 °C`, `TDS error = -0.64 %-pt` | `TDS-first` 驗證下，slow effective interface 只帶來小幅改善，熱/萃取主缺口仍然存在 |
| extraction budget | `M_sol_0 = dose × max_EY = 4.4 g` | 總可萃量已不再是主限制；剩餘缺口更可能來自 effective interface / transfer-history |
| max_EY scan | `max_EY = 0.40` 時仍僅 `TDS = 0.785%` | 缺口不只 soluble budget，還包含 accessibility / diffusion-path / thermal-history 結構限制 |
| shell scan | `shell_thickness = 600 um` 時 `M_sol_0 > target` 但 `TDS` 仍僅 `0.794%` | accessibility 單獨放寬後，主限制已轉成 diffusion-path / transfer-history |
| path scan | `path_mult = 0.05` 時 `TDS = 1.022%` | diffusion-path 也不是單一主因，缺口來自多個 closure 疊加 |
| joint shell-path scan | `shell = 600 um`, `path_mult = 0.1` 時 `TDS = 1.373%`, `EY = 18.87%`, 但 `T2 RMSE = 7.92 degC` | measured TDS 可由 accessibility 與 path 聯合調整重現，但 thermal-history closure 仍需獨立處理 |
| slow interface rewrite + rebaseline | formal fit 仍 `PASS`，且 `TDS-first` 驗證下 model `TDS` 為 `0.716%` | slow pool 不應保有 full external area；但語義修正後可見其改善幅度有限，主缺口仍指向更深的 transfer-history / thermal-history closure |

---

## [ENTRY] EXP-20260411-163313

- `timestamp`: `2026-04-11 16:33:13 +0800`
- `status`: `active`
- `theme`: `PSD refresh + measured ingest fix`

### Change
- 以新的 `data/kinu_29_light/PSD_export_data.csv` / `PSD_export_data_stats.csv` 重生 measured PSD artifact
- 正式 measured fit 路徑補上 `data/kinu29_psd_bins.csv` ingest

### Artifacts
- `data/kinu29_psd_summary.csv`
- `data/kinu29_psd_bins.csv`
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`

### Results

| Metric | Value |
|---|---|
| `recommended_D10_m` | `517 um` |
| `fines_num_lt_0p40mm` | `5.8 %` |
| `k_beta_prior_psd` | `6.193e2 m^-3` |

### Interpretation
- 新 PSD 比舊 baseline 顯著偏粗，堵塞 prior 與表面積代理都下降
- measured PSD 現在不只存在於 artifact，已真正進入正式 fit

---

## [ENTRY] EXP-20260411-164750

- `timestamp`: `2026-04-11 16:47:50 +0800`
- `status`: `active`
- `theme`: `thermal validation line`

### Change
- 以新 PSD bins 對 measured benchmark 做 seeded refit，重生 summary、lead figure、benchmark summary 與 calibrated diagnostics
- 新增 `data/kinu29_light_20g_thermal_profile.csv` 與熱端對照圖，將 `T1/T2/final TDS` 納入獨立驗證線

### Artifacts
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `data/benchmark_suite_summary.csv`
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- `data/kinu29_light_20g_thermal_profile_comparison.png`
- `data/kinu29_calibrated_flow_diagnostics_180s.png`
- `data/kinu29_calibrated_extraction_quality_180s.png`

### Results

| Metric | Value |
|---|---|
| `k_fit` | `7.824e-11` |
| `k_beta_fit` | `7.185e2` |
| `tau_lag` | `2.0 s` |
| `V_out RMSE` | `13.62 mL` |
| `q_out RMSE` | `1.24 mL/s` |
| `drain_time_error` | `+0.71 s` |
| `cup_temp_error` | `-0.05 degC` |
| `benchmark status` | `PASS` |
| `T1 RMSE` | `2.40 degC` |
| `T2 RMSE` | `7.92 degC` |
| `final TDS error` | `-0.88 %-pt` |

### Interpretation
- 新 PSD 下的水力 baseline 仍可通過 benchmark，表示主水力 closure 仍成立
- 但 `T2` 與 final TDS 同時偏低，顯示 extraction / thermal coupling 仍缺機制，下一步不該只繼續調 `k` 或 `k_beta`

---

## [ENTRY] EXP-20260411-170258

- `timestamp`: `2026-04-11 17:02:58 +0800`
- `status`: `active`
- `theme`: `k_ext scan against hard TDS target`

### Change
- 固定新的水力 baseline，不動 `k / k_beta / tau_lag / wetbed / server cooling`
- 以 thermal recipe 的 `TDS = 1.36%` 為硬目標，單獨掃描 `k_ext_coef`

### Artifacts
- `data/kinu29_kext_scan_thermal_recipe.csv`

### Results

| Metric | Value |
|---|---|
| baseline `k_ext_coef` | `4.8e-7` |
| `64x` 時 TDS / EY | `1.048% / 14.39%` |
| `2048x` 時 TDS / EY | `1.224% / 16.82%` |
| target TDS | `1.36%` |
| current `M_sol_0` | `3.338 g` |
| target extracted mass | `~3.74 g` |

### Interpretation
- 即使把 `k_ext_coef` 提高到極大倍率，TDS 仍停在 `~1.22%`，顯示系統已接近結構上限
- 主缺口不是單純傳質倍率，而是 `max_EY=0.22` 與 measured-PSD 下的 accessibility / soluble-mass budget 太保守

---

## [ENTRY] EXP-20260411-184949

- `timestamp`: `2026-04-11 18:49:49 +0800`
- `status`: `active`
- `theme`: `max_EY scan against hard TDS target`

### Change
- 延續固定水力 baseline 的策略，單獨掃描 `max_EY`
- 檢查只放寬可萃總量上限時，是否足以將 thermal recipe 拉到 `TDS = 1.36%`

### Artifacts
- `data/kinu29_max_ey_scan_thermal_recipe.csv`

### Results

| Metric | Value |
|---|---|
| baseline `max_EY` | `0.22` |
| baseline TDS | `0.480%` |
| `max_EY = 0.40` 時 TDS / EY | `0.785% / 10.79%` |
| target TDS | `1.36%` |

### Interpretation
- 單獨提高 `max_EY` 也無法把 TDS 拉回量測值，代表缺口不只 soluble budget
- 在目前 measured-PSD closure 下，`accessibility / diffusion-path / thermal-history` 和 `max_EY` 一起形成更強的結構限制

---

## [ENTRY] EXP-20260411-185226

- `timestamp`: `2026-04-11 18:52:26 +0800`
- `status`: `active`
- `theme`: `shell accessibility scan`

### Change
- 固定水力 baseline，單獨掃描 `shell_thickness`
- 直接測試 accessibility closure 是否為主缺口

### Artifacts
- `data/kinu29_shell_thickness_scan_thermal_recipe.csv`

### Results

| Metric | Value |
|---|---|
| baseline `shell_thickness` | `200 um` |
| baseline TDS | `0.480%` |
| 最佳點 `shell_thickness` | `600 um` |
| 最佳點 TDS / EY | `0.794% / 10.90%` |
| 最佳點 `M_sol_0` | `4.176 g` |
| target extracted mass | `~3.74 g` |

### Interpretation
- 單獨放寬 accessibility 仍無法達到 `1.36%`
- 當 soluble budget 已足夠但 TDS 仍偏低，主限制已轉到 diffusion-path / transfer-history
- `shell_thickness` 出現非單調反轉，表示目前 shell-depth closure 值得重寫，而不是只把數值調大

---

## [ENTRY] EXP-20260411-190016

- `timestamp`: `2026-04-11 19:00:16 +0800`
- `status`: `active`
- `theme`: `direct diffusion-path scan`

### Change
- 固定水力 baseline，直接縮放 fast/slow effective diffusion path
- 檢查 `L_eff` 是否為單一主限制

### Artifacts
- `data/kinu29_diffusion_path_scan_thermal_recipe.csv`

### Results

| Metric | Value |
|---|---|
| baseline fast / slow path | `~100 / 396 um` |
| `path_mult = 0.05` 時 TDS / EY | `1.022% / 14.04%` |
| target TDS | `1.36%` |

### Interpretation
- 即使把 effective path 極端縮短，TDS 仍無法達到量測值
- diffusion-path 不是單一主因；目前 under-extraction 至少同時來自兩個以上 closure 疊加

---

## [ENTRY] EXP-20260411-190659

- `timestamp`: `2026-04-11 19:06:59 +0800`
- `status`: `active`
- `theme`: `joint shell-path scan`

### Change
- 固定水力 baseline，對 `shell_thickness × path_mult` 做 2D joint scan
- 檢查 accessibility 與 effective path 是否必須聯合調整，才能回到 measured `TDS = 1.36%`

### Artifacts
- `data/kinu29_shell_path_joint_scan_thermal_recipe.csv`
- `data/kinu29_shell_path_joint_scan_thermal_recipe.png`

### Results

| Metric | Value |
|---|---|
| target TDS | `1.36%` |
| meeting combinations | `5` |
| 第一個達標點 `shell / path_mult` | `500 um / 0.05` |
| 第一個達標點 TDS / EY | `1.390% / 19.10%` |
| 最接近目標點 `shell / path_mult` | `600 um / 0.1` |
| 最接近目標點 TDS / EY | `1.373% / 18.87%` |
| 最接近目標點 `M_extracted` | `3.773 g` |
| 最接近目標點 `T2 RMSE` | `7.92 degC` |

### Interpretation
- 量測 TDS 並非不可達，但只有在 shell accessibility 與 effective path 同時放寬時才會進入可達區
- 這表示目前主缺口在 `shell_accessibility + diffusion_path` 的耦合寫法，而不是某一個單獨倍率旋鈕
- 即使 TDS / EY 已能回到量測區間，`T2 RMSE` 幾乎不變，代表 thermal-history closure 仍有獨立錯誤來源

---

## [ENTRY] EXP-20260411-193303

- `timestamp`: `2026-04-11 19:33:03 +0800`
- `status`: `active`
- `theme`: `shell-path closure rewrite + rebaseline`

### Change
- 直接重寫 `shell_accessibility + diffusion_path` 耦合 closure
- measured-bin 的 fast/slow area、mass fraction、path 改為共用同一套 shell/core 幾何
- aggregate slow path 改為真正的 core-weighted 平均，移除舊版把 weighted sum 直接當 path 的結構錯誤
- `latest_calibrated_params()` 改為從 measured flow metadata 與最新 summary 載入正式 baseline，避免展示 state 繼續吃舊 `D10` 或漏掉熱端校準參數

### Artifacts
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `data/benchmark_suite_summary.csv`
- `data/kinu29_calibrated_flow_diagnostics_180s.png`
- `data/kinu29_calibrated_extraction_quality_180s.png`
- `data/kinu29_light_20g_thermal_profile_comparison.png`

### Results

| Metric | Value |
|---|---|
| `k_fit` | `7.699e-11` |
| `k_beta_fit` | `8.899e2` |
| `tau_lag` | `1.6 s` |
| `wetbed_struct_gain_fit` | `0.0991` |
| `server_cooling_lambda_fit` | `5.269e-4` |
| `V_out RMSE` | `13.53 mL` |
| `q_out RMSE` | `1.23 mL/s` |
| `drain_time_error` | `+0.26 s` |
| `cup_temp_error` | `+0.07 degC` |
| `benchmark status` | `PASS` |
| thermal `T1 / T2 RMSE` | `2.36 / 7.91 degC` |
| thermal model `TDS` | `0.563%` |
| thermal `TDS error` | `-0.80 %-pt` |

### Interpretation
- closure rewrite 修正了 measured-bin 幾何不一致與 slow-path 過重懲罰，formal flow baseline 仍可通過 benchmark
- final `TDS` 只從約 `0.48%` 小幅升到 `0.56%`，表示主缺口已不再是舊的 shell/path wiring bug，而是更深的 transfer-history / thermal-history closure
- 這次重寫應保留；但若要把 `1.36% TDS` 拉回來，下一步不能只靠再調單一倍率

---

## [ENTRY] EXP-20260412-014510

- `timestamp`: `2026-04-12 01:45:10 +0800`
- `status`: `active`
- `theme`: `inventory conservation rewrite`

### Change
- 將 bin-level `M_fast_0_bins / M_slow_0_bins` 的分配從反應面積權重改為固體體積權重
- 將總可萃量固定為 `dose_g × max_EY`
- measured PSD / shell 幾何只負責改變 fast-slow split，不再同時放大總庫存

### Artifacts
- `pour_over/params.py`

### Results

| Metric | Value |
|---|---|
| `M_sol_0` at `shell = 100 / 200 / 400 um` | `4.4 / 4.4 / 4.4 g` |
| target `dose × max_EY` | `4.4 g` |
| `sum(M_fast_0_bins)` | `= M_fast_0` |
| `sum(M_slow_0_bins)` | `= M_slow_0` |
| shell trend | `M_fast_0` 單調上升、`M_slow_0` 單調下降 |

### Interpretation
- 第一優先級的質量守恆語義已修正：shell 幾何不再同時改變總可萃量與庫存 split
- 這一筆先只修正 closure 語義；formal rebaseline 尚未在本 entry 宣告新 benchmark 數字

---

## [ENTRY] EXP-20260412-150601

- `timestamp`: `2026-04-12 15:06:01 +0800`
- `status`: `active`
- `theme`: `slow interface rewrite + rebaseline`

### Change
- 將 slow pool 的有效反應面積從 `A_total` 改為受 `shell_accessibility` 約束的 `A_total × (1 - shell_acc)^gamma`
- 新增 `gamma_slow_area`，讓 slow pool 不再同時擁有 full external area 與 deep-core diffusion path
- 重跑 formal measured fit 與 benchmark suite

### Artifacts
- `pour_over/params.py`
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `data/benchmark_suite_summary.csv`
- `data/kinu29_calibrated_flow_diagnostics_180s.png`
- `data/kinu29_calibrated_extraction_quality_180s.png`
- `data/kinu29_light_20g_thermal_profile_comparison.png`

### Results

| Metric | Value |
|---|---|
| `k_fit` | `8.215e-11` |
| `k_beta_fit` | `1.205e3` |
| `tau_lag` | `2.0 s` |
| `wetbed_struct_gain_fit` | `0.2946` |
| `server_cooling_lambda_fit` | `5.348e-4` |
| `V_out RMSE` | `13.51 mL` |
| `q_out RMSE` | `1.24 mL/s` |
| `drain_time_error` | `+1.46 s` |
| `cup_temp_error` | `+0.04 degC` |
| `benchmark status` | `PASS` |
| thermal `T1 / T2 RMSE` | `2.36 / 7.92 degC` |
| thermal model `TDS` | `0.716%` |
| thermal `TDS error` | `-0.64 %-pt` |

### Interpretation
- 在改成 `TDS-first` 驗證後，slow effective interface 修正只讓 thermal recipe 上的 model `TDS` 從 `0.708%` 小幅升到 `0.716%`
- `T2 RMSE` 幾乎沒有同步改善，表示剩餘缺口不只是總量或有效界面，仍包含 transfer-history / thermal-history closure

---

## [ENTRY] EXP-20260412-014943

- `timestamp`: `2026-04-12 01:49:43 +0800`
- `status`: `active`
- `theme`: `formal rebaseline after inventory rewrite`

### Change
- 在 inventory conservation rewrite 之後重跑 formal measured fit
- 重生 summary、benchmark summary、flow diagnostics、extraction quality 與 thermal comparison

### Artifacts
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `data/benchmark_suite_summary.csv`
- `data/kinu29_calibrated_flow_diagnostics_180s.png`
- `data/kinu29_calibrated_extraction_quality_180s.png`
- `data/kinu29_light_20g_thermal_profile_comparison.png`

### Results

| Metric | Value |
|---|---|
| `k_fit` | `7.827e-11` |
| `k_beta_fit` | `1.134e3` |
| `tau_lag` | `2.0 s` |
| `wetbed_struct_gain_fit` | `0.1659` |
| `server_cooling_lambda_fit` | `5.259e-4` |
| `V_out RMSE` | `13.48 mL` |
| `q_out RMSE` | `1.24 mL/s` |
| `drain_time_error` | `+2.06 s` |
| `cup_temp_error` | `+0.06 degC` |
| `benchmark status` | `PASS` |
| thermal `T1 / T2 RMSE` | `2.42 / 7.91 degC` |
| thermal model `TDS` | `0.708%` |
| thermal `TDS error` | `-0.65 %-pt` |

### Interpretation
- 在修正庫存守恆後，formal baseline 仍可通過全部 flow / thermal benchmark gate，表示這次 `P0/P1` 修改沒有破壞既有水力主線
- model `TDS` 從前一版約 `0.56%` 再推高到 `0.71%`，代表「先修總量守恆，再重 fit」確實有實質改善
- 但主缺口仍然存在，說明下一步應聚焦 slow-pool effective interface / transfer-history，而不是再調整總可萃量

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

## [ENTRY] EXP-20260420-180413

- `timestamp`: `2026-04-20 18:04:13 +0800`
- `status`: `active`
- `theme`: `ambient auto-ingest + kinu28 4:20 measured-case onboarding`

### Change
- measured pipeline 不再默認固定 `23.0°C` 室溫；新增 `resolve_measured_ambient_temp_C()`，改為優先讀 `ambient_temp_C`，缺值時退回 `t=0` 量測溫度
- 新增 `data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv` 與 `kinu28_light_20g_thermal_profile.csv`
- 以 `data/kinu_28_light/4:20/PSD_export_data.csv` 重生 case-local PSD artifact

### Artifacts
- `pour_over/measured_io.py`
- `pour_over/fitting.py`
- `pour_over/observation.py`
- `tests/test_measured_case_registry.py`
- `data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv`
- `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv`
- `data/kinu_28_light/4:20/kinu28_psd_summary.csv`
- `data/kinu_28_light/4:20/kinu28_psd_bins.csv`

### Results

| Metric | Value |
|---|---|
| `ambient source policy` | `metadata -> t=0 server_temp_C -> t=0 outflow_temp_C -> fail fast` |
| `4:20 ambient_temp_C` | `23.3 °C` |
| `4:20 final_tds_pct` | `1.60 %` |
| `4:20 final poured weight` | `301.3 g` |
| `4:20 final drained volume` | `265 mL` |
| `kinu28 PSD recommended D10` | `517 μm` |
| `kinu28 fines_num_lt_0p40mm` | `5.7 %` |
| loader regression | `PASS` (`tests.test_measured_case_registry`) |

### Interpretation
- measured 室溫現在明確綁定當次資料，而不是隱性常數；未來 thermal case 若忘記填 `ambient_temp_C`，仍可由 `t=0` 量測補齊
- `kinu_28_light/4:20` 已完成最小可重跑的 measured case 結構化，可直接進入後續 case-local flow / thermal calibration
- 這次沒有拿到新的 calibrated fit 指標，因此目前新增的是資料面與 ingest 規則，不是新的性能結論

---

## [ENTRY] EXP-20260420-180834

- `timestamp`: `2026-04-20 18:08:34 +0800`
- `status`: `active`
- `theme`: `kinu28 4:20 case-local flow fit + thermal comparison`

### Change
- 對 `data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv` 跑 case-local calibrated flow fit
- 產生 `4:20` measured case 專屬的 flow fit summary / comparison plot / thermal comparison plot
- 保持 `4:12` 為正式 baseline，不改 showcase selector

### Artifacts
- `data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile_comparison.png`

### Results

| Metric | Value |
|---|---|
| `k_fit` | `1.486e-10` |
| `k_beta_fit` | `1.590e3` |
| `tau_lag` | `0.5 s` |
| `wetbed_struct_gain_fit` | `0.401` |
| `pref_flow_coeff_fit` | `4.269e-4` |
| `V_out RMSE` | `10.72 mL` |
| `q_out RMSE` | `1.49 mL/s` |
| `drain_time_error` | `-2.45 s` |
| `T1 RMSE` | `5.92 °C` |
| `T2 RMSE` | `15.76 °C` |
| `model final TDS` | `0.948 %` |
| `final TDS error` | `-0.652 %-pt` |

### Interpretation
- `4:20` 的標準化沖煮紀錄在流量面比目前 `4:12` baseline 更容易擬合，`V_out RMSE` 已降到 `~10.7 mL`
- 但這組 case 需要更高的 `k`、更高的 `k_beta`、更短的 `tau_lag`，以及明顯較強的 `pref_flow_coeff`，表示其流動節奏與目前 baseline 不同
- 熱端與 TDS 仍顯著偏低，說明新的標準化沖煮方式沒有自動解決 thermal-history / extraction-history closure 的主缺口

---

## [ENTRY] EXP-20260420-190501

- `timestamp`: `2026-04-20 19:05:01 +0800`
- `status`: `active`
- `theme`: `effluent thermal state + T2 semantic repair`

### Change
- 在 `core.py` 新增最小必要的 `T_effluent` thermal state，將床內 bulk 熱狀態與即將流出液體熱狀態分離
- `observation.py` 改以 `T_effluent_C` 作為 outflow / server 混合鏈的熱源，而不再默認使用 bulk `T_C`
- `fitting.py` 的 `T2` 對照改從 effluent chain 取值，不再直接以 bulk thermal state 比量測 `T2`
- 本輪不動 `k_ext_coef`、`max_EY`、shell/path closure

### Artifacts
- `pour_over/core.py`
- `pour_over/observation.py`
- `pour_over/fitting.py`
- `tests/test_core_mass_balance.py`
- `tests/test_measured_case_registry.py`
- `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile_comparison.png`

### Results

| Metric | Value |
|---|---|
| `4:20 T1 RMSE` | `5.75 °C` |
| `4:20 T2 RMSE` | `12.63 °C` |
| `4:20 final TDS error` | `-0.651 %-pt` |
| `4:12 T1 / T2 RMSE` | `5.92 / 13.48 °C` |
| `4:12 final TDS error` | `-0.433 %-pt` |
| `4:11 T1 / T2 RMSE` | `2.27 / 6.14 °C` |
| `4:11 final TDS error` | `-0.348 %-pt` |
| semantic regression tests | `PASS` |

### Interpretation
- 這次改善來自 thermal-history 語義修正，而不是萃取參數調整；`4:20` 的 `T2 RMSE` 由 `15.76 °C` 降到 `12.63 °C`
- `4:12` 與 `4:11` 的 `T2 RMSE` 也同步下降，表示原本「直接拿 bulk `T` 當 `T2`」確實是跨 case 的系統性錯位
- final TDS 幾乎不變，反而支持本輪判讀：先前的 `T2` 主缺口包含 thermal semantic mismatch，而不是單純 extraction underfit

---

## [ENTRY] EXP-20260420-194710

- `timestamp`: `2026-04-20 19:47:10 +0800`
- `status`: `active`
- `theme`: `apex startup thermal closure`

### Change
- 將 `T_effluent` 初始值改為冷 apex，而不是直接沿用 bulk `T_shock`
- 將 startup apex 的等效 hold-up 改為受 `gate_h` 調節：
  - `gate_h < 1` 時包含額外濕潤濾紙 / apex hold-up
  - `gate_h -> 1` 時回到較小穩態 effluent 熱容
- `plot_measured_thermal_profile_comparison()` 的 `T2` panel 改為真正畫 `obs_layer["T_effluent_C"]`
- 本輪仍不動 `k_ext_coef`、`max_EY`、shell/path closure

### Artifacts
- `pour_over/core.py`
- `pour_over/fitting.py`
- `tests/test_core_mass_balance.py`
- `tests/test_measured_case_registry.py`
- `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile_comparison.png`

### Results

| Metric | Value |
|---|---|
| `4:20 T1 RMSE` | `5.75 °C` |
| `4:20 T2 RMSE` | `8.37 °C` |
| `4:20 final TDS error` | `-0.651 %-pt` |
| `4:20 model T2 @ 0 / 5 / 10 / 15 s` | `23.3 / 28.1 / 78.9 / 81.4 °C` |
| `4:12 T1 / T2 RMSE` | `6.94 / 8.29 °C` |
| `4:11 T1 / T2 RMSE` | `3.13 / 8.94 °C` |
| targeted thermal regression tests | `PASS` |

### Interpretation
- `T2` 若量測於濾紙錐形頂點，startup 時不應直接等於熱 bulk outflow；冷 apex 初始條件是必要的物理修正
- 只改初始條件還不夠，還需要 startup apex hold-up；把 `gate_h` 納入 apex 等效熱容後，`4:20 T2 RMSE` 由 `12.63 °C` 進一步降到 `8.37 °C`
- `4:12` 也同步改善，表示這不是單一 case 的調參
- `4:11` 仍比上一輪 semantic-only 修正更差，顯示目前 closure 對「快速熱啟動」regime 還不夠好；下一步應檢查 apex local wall contact / preheated tip history，而不是回頭亂調 extraction

---

## [ENTRY] EXP-20260420-200312

- `timestamp`: `2026-04-20 20:03:12 +0800`
- `status`: `active`
- `theme`: `ambient-start bulk thermal initialization`

### Change
- 將 `core.py` 的 bulk thermal node 初始值由預混 `T_shock` 改為 `T_amb`
- 保持 `T_effluent`、`T_dripper` 與 server observation 都從室溫開始
- 讓第一注注水由 ODE 自己把 bulk / apex / dripper 從室溫加熱起來

### Artifacts
- `pour_over/core.py`
- `tests/test_core_mass_balance.py`
- `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile_comparison.png`

### Results

| Metric | Value |
|---|---|
| `4:20 T1 RMSE` | `5.79 °C` |
| `4:20 T2 RMSE` | `8.15 °C` |
| `4:20 final TDS error` | `-0.652 %-pt` |
| `4:20 model T2 @ 0 / 5 / 10 / 15 s` | `23.3 / 26.3 / 77.8 / 80.8 °C` |
| `4:12 T1 / T2 RMSE` | `7.11 / 8.06 °C` |
| `4:11 T1 / T2 RMSE` | `3.26 / 9.16 °C` |
| ambient-start regression tests | `PASS` |

### Interpretation
- 這個修正讓模型熱敘事更一致：濾杯、下壺、咖啡粉與 bulk 液相都從室溫開始加熱
- `4:20` 與 `4:12` 的 `T2 RMSE` 再小幅下降，且 `t=0/5 s` 的 apex 溫度更符合「從室溫被第一注拉升」的物理圖像
- `4:11` 仍未改善，表示剩餘缺口不是單純初始條件，而更像是 fast-start regime 的 apex local contact history

---

## [ENTRY] EXP-20260423-023932

- `timestamp`: `2026-04-23 02:39:32 +0800`
- `status`: `active`
- `theme`: `T2 validation window hardening`

### Change
- 在 `evaluate_measured_thermal_profile()` 內新增正式規則：`T2` 的主驗證窗從 `10 s` 開始
- `t < 10 s` 的 `T2` 量測點保留在圖上，但不再進 `outflow_temp_fit_mask`
- 不改主熱方程、不改 extraction 參數；本輪只修 validation semantics

### Artifacts
- `pour_over/fitting.py`
- `tests/test_measured_case_registry.py`
- `docs/superpowers/specs/2026-04-23-t2-validation-window-and-dual-path-apex-design.md`

### Results

| Metric | Value |
|---|---|
| `4:20 T1 / T2 RMSE` | `5.79 / 8.33 °C` |
| `4:12 T1 / T2 RMSE` | `7.11 / 7.34 °C` |
| `4:11 T1 / T2 RMSE` | `3.26 / 4.83 °C` |
| `used T2 points` | `4:20 = 23`, `4:12 = 25`, `4:11 = 24` |
| held-out rule regression | `PASS` |

### Interpretation
- 這次 `T2 RMSE` 的改善應解讀為 validation policy 更合理，而不是熱模型本體突然變好
- 拿掉 `t < 10 s` 的探針啟動期後，`4:11` 的 `T2 RMSE` 由 `9.16 °C` 明顯降到 `4.83 °C`，支持使用者判讀：前幾秒確實混入溫度計自身響應
- `4:20` 在新驗證窗下仍維持 `8.33 °C`，表示真正剩餘的主缺口集中在 `10–20 s` 的 apex thermal history，而不是 `5 s` 的 sensor lag

---

## [ENTRY] EXP-20260423-024521

- `timestamp`: `2026-04-23 02:45:21 +0800`
- `status`: `active`
- `theme`: `T1 sensor startup window hardening`

### Change
- 在 `evaluate_measured_thermal_profile()` 內新增 `T1` 感測器啟動規則：
  - 第一滴咖啡液流出時間 + `5 s` 才開始進 `server_temp_fit_mask`
- 規則由模型端根據 `V_out(t)` 自動計算，不依賴 CSV 是否手動標對
- 本輪不改主熱方程，只修 `T1` validation semantics

### Artifacts
- `pour_over/fitting.py`
- `tests/test_measured_case_registry.py`

### Results

| Metric | Value |
|---|---|
| `4:20 T1 / T2 RMSE` | `5.79 / 8.33 °C` |
| `4:12 T1 / T2 RMSE` | `7.11 / 7.34 °C` |
| `4:11 T1 / T2 RMSE` | `3.26 / 4.83 °C` |
| `used T1 points` | `4:20 = 23`, `4:12 = 25`, `4:11 = 14` |
| `used T2 points` | `4:20 = 23`, `4:12 = 25`, `4:11 = 24` |
| T1 startup regression | `PASS` |

### Interpretation
- `4:20` 與 `4:12` 的 `T1 RMSE` 幾乎不變，表示這兩筆 CSV 原本的手動 held-out 已經相當保守
- `4:11` 的 `used T1 points` 明顯減少，說明壺端溫度計啟動期原本確實混在主驗證窗內
- 這次仍只是 validation policy 更合理，不應解讀成 server heat model 已經被解決

---

## [ENTRY] EXP-20260424-152021

- `timestamp`: `2026-04-24 15:20:21 +0800`
- `status`: `active`
- `theme`: `bloom thermal-flow diagnostics`

### Change
- 新增 `pour_over/bloom_diagnostics.py`，以 `0-40 s` 悶蒸期為診斷視窗，同時輸出 flow、thermal state 與 observation residual
- 本輪不改 `core.py` 主熱方程、不改 fitted summary、不改 extraction 參數
- 診斷欄位包含 `server_volume_residual_ml`、`T1_residual_C`、`T2_residual_C`、`q_bed_transport_mlps`、`q_out_mlps`、`head_gate`、`liq_transport_gate`、`T_bulk_C`、`T_effluent_C`、`T_dripper_C`

### Artifacts
- `pour_over/bloom_diagnostics.py`
- `tests/test_bloom_diagnostics.py`
- `data/bloom_thermal_flow_diagnostics.png`
- `data/kinu_28_light/4:20/kinu28_light_20g_bloom_thermal_flow_diagnostics.csv`
- `data/kinu_29_light/4:12/kinu29_light_20g_bloom_thermal_flow_diagnostics.csv`
- `data/kinu_29_light/4:11/kinu29_light_20g_bloom_thermal_flow_diagnostics.csv`

### Results

| Metric | Value |
|---|---|
| `kinu28 4:20 volume residual range` | `-10.80 to +0.42 mL` |
| `kinu28 4:20 T2 residual range` | `-10.63 to +32.85 °C` |
| `kinu29 4:12 volume residual range` | `-16.66 to +0.00 mL` |
| `kinu29 4:12 T2 residual range` | `-10.33 to +24.39 °C` |
| `kinu29 4:11 volume residual range` | `-33.91 to +0.00 mL` |
| `kinu29 4:11 T2 residual range` | `-39.22 to +8.91 °C` |
| bloom diagnostic regression | `PASS` |

### Interpretation
- 悶蒸期不是單純 `10-20 s` 的 apex 過熱問題；三案都出現 volume residual 與 T2 residual 在 `0-40 s` 內變號或錯相
- 下一步應先用 bloom diagnostic 判斷 flow/observation timing 是否主導，再決定是否 gated `bulk_effluent_exchange`
- 若直接調小 `lambda_liquid_effluent`，可能改善早段過熱但惡化 `20-35 s` 偏冷，因此目前不應新增自由熱參數

---

## [ENTRY] EXP-20260425-130812

- `timestamp`: `2026-04-25 13:08:12 +0800`
- `status`: `active`
- `theme`: `H1 flow-timing hypothesis test`

### Change
- 在 `pour_over/bloom_diagnostics.py` 新增 `analyze_h1_flow_timing()`
- 對三案 `0-40 s` bloom diagnostic 計算：
  - `volume_t2_corr`
  - `same_sign_fraction`
  - `10-20 s` early residual means
  - `25-40 s` late residual means
  - per-case `h1_status`
- 新增 `data/bloom_h1_flow_timing_summary.csv`

### Artifacts
- `pour_over/bloom_diagnostics.py`
- `tests/test_bloom_diagnostics.py`
- `data/bloom_h1_flow_timing_summary.csv`

### Results

| Case | Corr(`V_res`, `T2_res`) | Same-sign | Early `V/T2` | Late `V/T2` | H1 |
|---|---:|---:|---:|---:|---|
| `kinu28 4:20` | `-0.83` | `0.29` | `-3.36 mL / +16.36 °C` | `-0.48 mL / -4.37 °C` | `not_supported` |
| `kinu29 4:12` | `-0.49` | `0.57` | `-8.32 mL / +9.91 °C` | `-10.11 mL / -4.68 °C` | `partial` |
| `kinu29 4:11` | `+0.02` | `0.43` | `-22.37 mL / +2.61 °C` | `-32.07 mL / +1.44 °C` | `not_supported` |
| overall H1 |  |  |  |  | `partial` |

### Interpretation
- H1 不能作為全域主因：`4:20` 與 `4:11` 的 volume residual 與 T2 residual 不同步
- `4:12` 只能標為 partial，因為同號率略高但相關性仍為負，且 early/late T2 residual 變號
- 下一步應做 H2：不新增自由參數，檢查 `bulk_effluent_exchange` 常開耦合是否能解釋 early apex overheating，但必須同時監控 late bias

---

## [ENTRY] EXP-20260425-133024

- `timestamp`: `2026-04-25 13:30:24 +0800`
- `status`: `active`
- `theme`: `H2 effluent coupling gate test`

### Change
- 在 `V60Params` 新增 `effluent_coupling_gate_mode`，預設 `constant`
- 在 `core.py` 只包住 `bulk_effluent_exchange`：
  - `constant`
  - `liq_transport_gate`
  - `head_gate`
- 在 `pour_over/bloom_diagnostics.py` 新增 `analyze_h2_effluent_coupling()`，固定 fitted params 只替換 gate mode
- 本輪是 counterfactual closure test，不是正式 rebaseline

### Artifacts
- `pour_over/params.py`
- `pour_over/core.py`
- `pour_over/bloom_diagnostics.py`
- `tests/test_core_mass_balance.py`
- `tests/test_bloom_diagnostics.py`
- `data/bloom_h2_effluent_coupling_summary.csv`

### Results

| Case | Gate | Early T2 RMSE | Late T2 RMSE | Early Δ vs constant | Late Δ vs constant | H2 |
|---|---|---:|---:|---:|---:|---|
| `kinu28 4:20` | `liq_transport_gate` | `20.53 °C` | `6.49 °C` | `+0.00 °C` | `-0.12 °C` | `not_supported` |
| `kinu28 4:20` | `head_gate` | `21.29 °C` | `5.88 °C` | `+0.77 °C` | `-0.74 °C` | `not_supported` |
| `kinu29 4:12` | `liq_transport_gate` | `15.15 °C` | `7.75 °C` | `+0.14 °C` | `-0.10 °C` | `not_supported` |
| `kinu29 4:12` | `head_gate` | `16.05 °C` | `7.15 °C` | `+1.03 °C` | `-0.69 °C` | `not_supported` |
| `kinu29 4:11` | `liq_transport_gate` | `4.01 °C` | `6.41 °C` | `+0.10 °C` | `-0.03 °C` | `not_supported` |
| `kinu29 4:11` | `head_gate` | `5.50 °C` | `6.30 °C` | `+1.60 °C` | `-0.15 °C` | `not_supported` |
| overall H2 |  |  |  |  |  | `not_supported` |

### Interpretation
- H2 不成立：降低 low-connectivity 狀態下的 bulk-effluent exchange 並沒有降低 `10-20 s` early T2 RMSE
- `head_gate` 反而讓 early T2 更差，表示 early overheating 不是單純來自 bulk-effluent 常開耦合過強
- late T2 RMSE 有小幅下降，但幅度小且不對應 H2 的主要症狀；下一步應進入 H3，檢查 apex/filter contact-history 或獨立 contact node

---

## [ENTRY] EXP-20260425-135810

- `timestamp`: `2026-04-25 13:58:10 +0800`
- `status`: `active`
- `theme`: `H3 apex contact-history test`

### Change
- 在 `pour_over/bloom_diagnostics.py` 新增 `analyze_h3_apex_contact_history()`
- 本輪不改 `core.py`，只做 observation/contact-history counterfactual：
  - `effluent` baseline
  - `contact_tau6_w35`
  - `contact_tau12_w45`
  - `contact_tau20_w55`
- contact-history 將 `T_effluent` 與 `T_dripper` 以固定接觸權重混合，再經一階 thermal memory；此測試用來判斷 T2 是否像 apex/filter 接觸區熱歷史，而非瞬時 effluent

### Artifacts
- `pour_over/bloom_diagnostics.py`
- `tests/test_bloom_diagnostics.py`
- `data/bloom_h3_apex_contact_summary.csv`

### Results

| Case | Mode | Early T2 RMSE | Late T2 RMSE | Early Δ vs effluent | Late Δ vs effluent | H3 |
|---|---|---:|---:|---:|---:|---|
| `kinu28 4:20` | `contact_tau6_w35` | `11.19 °C` | `17.50 °C` | `-9.34 °C` | `+10.89 °C` | `partial` |
| `kinu28 4:20` | `contact_tau12_w45` | `21.57 °C` | `23.96 °C` | `+1.04 °C` | `+17.35 °C` | `not_supported` |
| `kinu28 4:20` | `contact_tau20_w55` | `28.90 °C` | `31.60 °C` | `+8.37 °C` | `+24.99 °C` | `not_supported` |
| `kinu29 4:12` | `contact_tau6_w35` | `15.33 °C` | `19.63 °C` | `+0.31 °C` | `+11.79 °C` | `not_supported` |
| `kinu29 4:11` | `contact_tau6_w35` | `20.78 °C` | `13.30 °C` | `+16.88 °C` | `+6.85 °C` | `not_supported` |
| overall H3 |  |  |  |  |  | `partial` |

### Interpretation
- 單一 contact-memory observation 只能解釋 `4:20` 的 early overheating，且代價是 late T2 大幅偏冷
- `4:12` 與 `4:11` 不支持這個單節點 contact-memory 假說；尤其 `4:11` early 原本已接近，contact memory 會直接打壞
- 下一步若要繼續 H3，不應把單一 contact-memory 升級為正式模型；較合理的是 dual-path apex mixing：一條 fast effluent path + 一條 contact-cooled path，且混合權重需由 bloom flow regime 決定

---

## [ENTRY] EXP-20260425-142842

- `timestamp`: `2026-04-25 14:28:42 +0800`
- `status`: `active`
- `theme`: `H4 dual-path apex mixing test`

### Change
- 在 `pour_over/bloom_diagnostics.py` 新增 `analyze_h4_dual_path_apex_mixing()`
- 本輪仍不改 `core.py`，只做 observation-layer counterfactual：
  - fast path：目前 `T_effluent`
  - contact-cooled path：H3 的 `contact_tau6_w35`
  - mixing weight：只用現有水力狀態，不做 fitting
- 測試權重：
  - `effluent`
  - `liq_transport_gate`
  - `head_gate`
  - `q_bed_transport_norm`

### Artifacts
- `pour_over/bloom_diagnostics.py`
- `tests/test_bloom_diagnostics.py`
- `data/bloom_h4_dual_path_apex_summary.csv`

### Results

| Case | Weight | Early T2 RMSE | Late T2 RMSE | Early Δ vs effluent | Late Δ vs effluent | H4 |
|---|---|---:|---:|---:|---:|---|
| `kinu28 4:20` | `liq_transport_gate` | `18.63 °C` | `8.51 °C` | `-1.90 °C` | `+1.89 °C` | `partial` |
| `kinu28 4:20` | `head_gate` | `18.05 °C` | `15.12 °C` | `-2.48 °C` | `+8.50 °C` | `partial` |
| `kinu28 4:20` | `q_bed_transport_norm` | `21.99 °C` | `15.32 °C` | `+1.46 °C` | `+8.71 °C` | `not_supported` |
| `kinu29 4:12` | `liq_transport_gate` | `13.00 °C` | `9.86 °C` | `-2.01 °C` | `+2.02 °C` | `partial` |
| `kinu29 4:12` | `head_gate` | `15.91 °C` | `14.74 °C` | `+0.89 °C` | `+6.90 °C` | `not_supported` |
| `kinu29 4:11` | `liq_transport_gate` | `3.58 °C` | `7.42 °C` | `-0.33 °C` | `+0.97 °C` | `not_supported` |
| overall H4 |  |  |  |  |  | `partial` |

### Interpretation
- H4 比 H3 更符合使用者描述的物理圖像：fast penetration 與 side/contact seepage 同時存在
- `liq_transport_gate` 是目前最有希望的權重：改善 `4:20` / `4:12` early，且 `4:11` 沒被明顯打壞
- 但 late T2 仍惡化約 `+2 °C`，表示單純用 `liq_transport_gate` 混合還不足以成為正式 closure；下一步應讓 contact path 在 bloom 後段釋放/退場，或讓 fast-path 權重在第二段注水後回升

---

## [ENTRY] EXP-20260425-145211

- `timestamp`: `2026-04-25 14:52:11 +0800`
- `status`: `active`
- `theme`: `H4b dual-path release test`

### Change
- 在 `analyze_h4_dual_path_apex_mixing()` 新增 `liq_transport_release_after25`
- 權重規則：
  - early：沿用 `liq_transport_gate`，保留 contact-cooled side path
  - after `25 s`：用固定 logistic release 讓 fast path 權重回升，使 contact path 退場
- 本輪仍是 diagnostic-layer counterfactual，不改正式 `core.py`

### Artifacts
- `pour_over/bloom_diagnostics.py`
- `tests/test_bloom_diagnostics.py`
- `data/bloom_h4_dual_path_apex_summary.csv`

### Results

| Case | Weight | Early Δ vs effluent | Late Δ vs effluent | H4b |
|---|---|---:|---:|---|
| `kinu28 4:20` | `liq_transport_release_after25` | `-1.90 °C` | `+0.97 °C` | `supported` |
| `kinu29 4:12` | `liq_transport_release_after25` | `-2.01 °C` | `+1.48 °C` | `partial` |
| `kinu29 4:11` | `liq_transport_release_after25` | `-0.33 °C` | `+0.87 °C` | `not_supported` |
| overall H4b |  |  |  | `partial` |

### Interpretation
- `release_after25` 保留 H4 對 `4:20` / `4:12` early 的改善，且明顯降低 late penalty
- `4:20` 已達 supported；`4:12` late 仍略超過 `+1 °C`，因此不能直接升正式 closure
- `4:11` 沒有明顯打壞，這支持 dual-path 權重應以 `liq_transport_gate` 為基底，而不是 `head_gate` 或 `q_bed_transport_norm`
- 下一步若要轉成正式模型，應先把 release trigger 從固定 `25 s` 改成由 recipe event / second pour / flow-regime 自動決定，避免硬編碼時間

---

## [ENTRY] EXP-20260428-154930

- `timestamp`: `2026-04-28 15:49:30 +0800`
- `status`: `active`
- `theme`: `H4c event-based dual-path release`

### Change
- 在 `analyze_h4_dual_path_apex_mixing()` 新增 recipe/flow event-based release modes：
  - `liq_transport_release_on_pour`
  - `liq_transport_release_between_pours`
- `release_on_pour`：第二段注水開始後觸發 fast-path 回升
- `release_between_pours`：偵測第一段注水結束與第二段注水開始，取兩者中點作為 release center；若找不到兩段注水，退回 flow recovery event
- 本輪仍是 diagnostic-layer counterfactual，不改正式 `core.py`

### Artifacts
- `pour_over/bloom_diagnostics.py`
- `tests/test_bloom_diagnostics.py`
- `data/bloom_h4_dual_path_apex_summary.csv`

### Results

| Case | Weight | Early Δ vs effluent | Late Δ vs effluent | Status |
|---|---|---:|---:|---|
| `kinu28 4:20` | `liq_transport_release_between_pours` | `-1.90 °C` | `+0.64 °C` | `supported` |
| `kinu29 4:12` | `liq_transport_release_between_pours` | `-2.01 °C` | `+1.15 °C` | `partial` |
| `kinu29 4:11` | `liq_transport_release_between_pours` | `-0.33 °C` | `+0.42 °C` | `not_supported` |
| overall H4c |  |  |  | `partial` |

### Interpretation
- `release_between_pours` 是目前最合理的 event-based trigger：不硬編碼固定秒數，且比 `release_on_pour` 更早讓 contact path 退場
- 相較固定 `after25`，`between_pours` 進一步降低 late penalty：
  - `4:20`: `+0.97 -> +0.64 °C`
  - `4:12`: `+1.48 -> +1.15 °C`
  - `4:11`: `+0.87 -> +0.42 °C`
- `4:12` late penalty 仍略高於 `+1 °C`，因此 H4c 仍是 partial，不能直接宣告正式 closure 已成立
- 若要往正式模型前進，下一步應把 between-pours trigger 寫成 observation-layer候選 API，並加入更嚴格的 cross-case acceptance gate

---

## [ENTRY] EXP-20260428-163057

- `timestamp`: `2026-04-28 16:30:57 +0800`
- `status`: `active`
- `theme`: `formal channeling flow/thermal closure`

### Change
- 在 `V60Params` 新增正式通道參數：
  - `apex_channel_mode = "dual_path_between_pours"`
  - `apex_channel_release_tau_s = 3.0`
  - `apex_contact_tau_s = 6.0`
  - `apex_contact_weight = 0.35`
- `simulate_brew()` 以同一個 channel weight 將 `q_bed_transport` 拆成：
  - `q_fast_apex_mlps`
  - `q_side_seepage_mlps`
  - `apex_fast_weight`
- `apply_outflow_lag()` 改用 `T_apex_mixed_C` 作為 outflow/server thermal chain 的熱源，並保留 raw `T_effluent_C` 與 `T_contact_path_C` 供診斷。
- `evaluate_measured_thermal_profile()` 與 T2 plot 改用 mixed apex temperature 對應 T2。

### Artifacts
- `pour_over/core.py`
- `pour_over/observation.py`
- `pour_over/fitting.py`
- `pour_over/params.py`
- `tests/test_core_mass_balance.py`
- `tests/test_measured_case_registry.py`

### Results

| Case | T2 RMSE | T1 RMSE | Bloom fast weight mean | Flow split residual |
|---|---:|---:|---:|---:|
| `kinu28 4:20` | `7.70 °C` | `5.95 °C` | `0.743` | `8.88e-16 ml/s` |
| `kinu29 4:12` | `7.00 °C` | `7.49 °C` | `0.810` | `8.88e-16 ml/s` |
| `kinu29 4:11` | `4.89 °C` | `3.40 °C` | `0.824` | `4.44e-16 ml/s` |

### Verification
- `uv run python -m unittest tests.test_core_mass_balance.CoreMassBalanceTests.test_simulate_brew_reports_channel_flow_split_conservation`
- `uv run python -m unittest tests.test_measured_case_registry.MeasuredCaseRegistryTests.test_thermal_profile_uses_channel_mixed_apex_for_t2 tests.test_measured_case_registry.MeasuredCaseRegistryTests.test_thermal_plot_uses_channel_mixed_apex_curve_for_t2_panel`
- `uv run python -m compileall pour_over`
- `uv run python -m unittest tests.test_measured_case_registry`
- `uv run python -m unittest tests.test_bloom_diagnostics`

### Interpretation
- 通道效應現在已進入正式 flow 與 thermal model，而不是只留在 diagnostic counterfactual。
- Flow 端保持守恆：fast path 與 side seepage 僅分解 `q_bed_transport`，不改總出流或萃取質量帳。
- Thermal 端用同一個 `apex_fast_weight` 混合 fast effluent 與 contact-cooled side path，避免 T2 再被解釋成單一瞬時 effluent。
- 這仍是 reduced-order closure，不是 full multiphase CFD；後續若要提高可信度，應把 `apex_contact_weight/tau` 納入跨 case identifiability，而不是直接用它吸收全部 T2 誤差。

---

## [POLICY] Current Working Rules

| Item | Rule |
|---|---|
| `sat_flow` | 維持平滑鬆弛，不回到硬切 |
| `kr(sat)` | 保留在主 Darcy 路徑與 `q_preferential()` |
| bloom diagnostics | 優先檢查 `0-40 s` 的 volume residual、T2 residual、`head_gate`、`liq_transport_gate` 與 `q_bed_transport` |
| `chi_struct` | 正式回饋到 `k_eff` |
| extraction | 正式版本維持 `axial_node_count = 2` |
| `sat_rel_perm_*` | 視為弱可識別 closure，不作主擬合自由度 |
| `wetbed χ` | `gain` 可擬合；`rate = 0.06068366147200567` 固定；`release = 0.30` 固定 |
| `pref_flow` | `coeff` 僅作候選自由度；`open_rate = 0.254074546131474` 固定；`tau_decay = 3.1401416403754285` 固定 |
| thermal | `lambda_server_ambient` 可作單自由度熱端 closure |
