# 實驗紀錄

本文件整理目前專案中已落地的實驗結果，作為後續模型迭代的 human-readable narrative。

- canonical state backend：`docs/experiment_log.md`
- 本檔定位：敘事版摘要與脈絡說明
- 同步原則：當 `docs/experiment_log.md` 新增 active 結論時，本檔應同步更新對應摘要

- 時區：`Asia/Taipei`（`+0800`）
- 時間來源：
  - 有產物者：使用 artifact 檔案修改時間
  - 無獨立產物者：使用本次整理時的對話內結論
- 原則：只記錄「有明確改動」與「有明確結果」的項目

---

## 2026-04-28 16:30:57 +0800

- 改動：
  - 將 H4c 從 diagnostic counterfactual 升級為正式 reduced-order channeling closure
  - `core.py` 將 `q_bed_transport` 守恆拆成 `q_fast_apex_mlps` 與 `q_side_seepage_mlps`
  - `observation.py` 用同一個 `apex_fast_weight` 混合 fast effluent 與 contact-cooled side path，新增 `T_apex_mixed_C`
  - `fitting.py` 的 T2 evaluation / plot 改以 mixed apex 對應量測 T2，同時保留 raw `T_effluent_C`
- 實驗：
  - `uv run python -m unittest tests.test_core_mass_balance.CoreMassBalanceTests.test_simulate_brew_reports_channel_flow_split_conservation`
  - `uv run python -m unittest tests.test_measured_case_registry.MeasuredCaseRegistryTests.test_thermal_profile_uses_channel_mixed_apex_for_t2 tests.test_measured_case_registry.MeasuredCaseRegistryTests.test_thermal_plot_uses_channel_mixed_apex_curve_for_t2_panel`
  - `uv run python -m compileall pour_over`
  - `uv run python -m unittest tests.test_measured_case_registry`
  - `uv run python -m unittest tests.test_bloom_diagnostics`
- 結果：
  - `kinu28 4:20`: `T2 RMSE 7.70 °C`, `T1 RMSE 5.95 °C`, `0-40 s fast weight mean 0.743`
  - `kinu29 4:12`: `T2 RMSE 7.00 °C`, `T1 RMSE 7.49 °C`, `0-40 s fast weight mean 0.810`
  - `kinu29 4:11`: `T2 RMSE 4.89 °C`, `T1 RMSE 3.40 °C`, `0-40 s fast weight mean 0.824`
  - flow split residual 最大值維持在 `~1e-15 ml/s`，表示通道拆分不破壞 `q_bed_transport` 守恆
- 判讀：
  - 通道效應現在已被 flow 與 thermal 兩個模型共同引用，而不是只在 bloom diagnostics 裡做事後 counterfactual
  - Flow 端：保留總出流與萃取帳，只新增 fast/side path decomposition
  - Thermal 端：T2 改為 dual-path mixed apex；這比把 T2 硬等於瞬時 `T_effluent` 更符合手沖時向下穿透通道與側邊慢滲匯流並存的機制
  - 下一步不應再新增補償 multiplier；若要繼續改善，應做 `apex_contact_weight/tau` 的跨 case identifiability

---

## 2026-04-28 15:49:30 +0800

- 改動：
  - 在 `analyze_h4_dual_path_apex_mixing()` 新增 recipe/flow event-based release modes：
    - `liq_transport_release_on_pour`
    - `liq_transport_release_between_pours`
  - `release_on_pour`：第二段注水開始後觸發 fast-path 回升
  - `release_between_pours`：偵測第一段注水結束與第二段注水開始，取兩者中點作為 release center；若找不到兩段注水，退回 flow recovery event
  - 本輪仍是 diagnostic-layer counterfactual，不改正式 `core.py`
- 實驗：
  - `uv run python -m unittest tests.test_bloom_diagnostics.BloomDiagnosticsTests.test_analyze_h4_dual_path_apex_mixing_reports_recipe_event_release_mode`
  - `uv run python -m unittest tests.test_bloom_diagnostics.BloomDiagnosticsTests.test_analyze_h4_dual_path_apex_mixing_reports_between_pours_release_mode`
  - `uv run python -m pour_over.bloom_diagnostics`
  - artifact：`data/bloom_h4_dual_path_apex_summary.csv`
- 結果：
  - `release_on_pour` 太晚觸發，結果幾乎等同 `liq_transport_gate`
  - `release_between_pours`：
    - `kinu28 4:20` early Δ `-1.90 °C`，late Δ `+0.64 °C`，`supported`
    - `kinu29 4:12` early Δ `-2.01 °C`，late Δ `+1.15 °C`，`partial`
    - `kinu29 4:11` early Δ `-0.33 °C`，late Δ `+0.42 °C`，`not_supported`
  - overall H4c：`partial`
- 判讀：
  - `release_between_pours` 是目前最合理的 event-based trigger：不硬編碼固定秒數，且比 `release_on_pour` 更早讓 contact path 退場
  - 相較固定 `after25`，`between_pours` 進一步降低 late penalty：
    - `4:20`: `+0.97 -> +0.64 °C`
    - `4:12`: `+1.48 -> +1.15 °C`
    - `4:11`: `+0.87 -> +0.42 °C`
  - `4:12` late penalty 仍略高於 `+1 °C`，因此 H4c 仍是 partial，不能直接宣告正式 closure 已成立
  - 若要往正式模型前進，下一步應把 between-pours trigger 寫成 observation-layer 候選 API，並加入更嚴格的 cross-case acceptance gate

---

## 2026-04-25 14:52:11 +0800

- 改動：
  - 在 `analyze_h4_dual_path_apex_mixing()` 新增 `liq_transport_release_after25`
  - early 沿用 `liq_transport_gate`，保留 contact-cooled side path
  - `25 s` 後用固定 logistic release 讓 fast path 權重回升，使 contact path 退場
  - 本輪仍是 diagnostic-layer counterfactual，不改正式 `core.py`
- 實驗：
  - `uv run python -m unittest tests.test_bloom_diagnostics.BloomDiagnosticsTests.test_analyze_h4_dual_path_apex_mixing_reports_release_mode`
  - `uv run python -m pour_over.bloom_diagnostics`
  - artifact：`data/bloom_h4_dual_path_apex_summary.csv`
- 結果：
  - `kinu28 4:20 release_after25`：early Δ `-1.90 °C`，late Δ `+0.97 °C`，`supported`
  - `kinu29 4:12 release_after25`：early Δ `-2.01 °C`，late Δ `+1.48 °C`，`partial`
  - `kinu29 4:11 release_after25`：early Δ `-0.33 °C`，late Δ `+0.87 °C`，`not_supported`
  - overall H4b：`partial`
- 判讀：
  - `release_after25` 保留 H4 對 `4:20` / `4:12` early 的改善，且明顯降低 late penalty
  - `4:20` 已達 supported；`4:12` late 仍略超過 `+1 °C`，因此不能直接升正式 closure
  - `4:11` 沒有明顯打壞，支持 dual-path 權重應以 `liq_transport_gate` 為基底，而不是 `head_gate` 或 `q_bed_transport_norm`
  - 下一步若要轉成正式模型，應先把 release trigger 從固定 `25 s` 改成由 recipe event / second pour / flow-regime 自動決定，避免硬編碼時間

---

## 2026-04-25 14:28:42 +0800

- 改動：
  - 在 `pour_over/bloom_diagnostics.py` 新增 `analyze_h4_dual_path_apex_mixing()`
  - 不改 `core.py`，只做 observation-layer counterfactual
  - fast path 使用目前 `T_effluent`
  - contact-cooled path 使用 H3 的 `contact_tau6_w35`
  - mixing weight 只用現有水力狀態：
    - `liq_transport_gate`
    - `head_gate`
    - `q_bed_transport_norm`
  - 輸出 `data/bloom_h4_dual_path_apex_summary.csv`
- 實驗：
  - `uv run python -m unittest tests.test_bloom_diagnostics.BloomDiagnosticsTests.test_analyze_h4_dual_path_apex_mixing_reports_weight_modes`
  - `uv run python -m pour_over.bloom_diagnostics`
- 結果：
  - `kinu28 4:20`：
    - `liq_transport_gate` early Δ `-1.90 °C`，late Δ `+1.89 °C`
    - `head_gate` early Δ `-2.48 °C`，late Δ `+8.50 °C`
  - `kinu29 4:12`：
    - `liq_transport_gate` early Δ `-2.01 °C`，late Δ `+2.02 °C`
    - `head_gate` early Δ `+0.89 °C`，late Δ `+6.90 °C`
  - `kinu29 4:11`：
    - `liq_transport_gate` early Δ `-0.33 °C`，late Δ `+0.97 °C`
  - overall H4：`partial`
- 判讀：
  - H4 比 H3 更符合使用者描述的物理圖像：fast penetration 與 side/contact seepage 同時存在
  - `liq_transport_gate` 是目前最有希望的權重：改善 `4:20` / `4:12` early，且 `4:11` 沒被明顯打壞
  - 但 late T2 仍惡化約 `+2 °C`，表示單純用 `liq_transport_gate` 混合還不足以成為正式 closure；下一步應讓 contact path 在 bloom 後段釋放/退場，或讓 fast-path 權重在第二段注水後回升

---

## 2026-04-25 13:58:10 +0800

- 改動：
  - 在 `pour_over/bloom_diagnostics.py` 新增 `analyze_h3_apex_contact_history()`
  - 不改 `core.py`，只做 observation/contact-history counterfactual
  - 測試模式：
    - `effluent`
    - `contact_tau6_w35`
    - `contact_tau12_w45`
    - `contact_tau20_w55`
  - 輸出 `data/bloom_h3_apex_contact_summary.csv`
- 實驗：
  - `uv run python -m unittest tests.test_bloom_diagnostics.BloomDiagnosticsTests.test_analyze_h3_apex_contact_history_reports_observation_modes`
  - `uv run python -m pour_over.bloom_diagnostics`
- 結果：
  - `kinu28 4:20 contact_tau6_w35`：
    - early T2 RMSE `20.53 -> 11.19 °C`
    - late T2 RMSE `6.62 -> 17.50 °C`
    - H3 `partial`
  - `kinu28 4:20 contact_tau12_w45 / contact_tau20_w55`：early 與 late 都惡化
  - `kinu29 4:12`：所有 contact modes 都不支持；`contact_tau6_w35` early `+0.31 °C`、late `+11.79 °C`
  - `kinu29 4:11`：所有 contact modes 都不支持；`contact_tau6_w35` early `+16.88 °C`、late `+6.85 °C`
  - overall H3：`partial`
- 判讀：
  - 單一 contact-memory observation 只能解釋 `4:20` 的 early overheating，且會讓 late T2 大幅偏冷
  - `4:12` 與 `4:11` 不支持單節點 contact-memory 假說；尤其 `4:11` 原本 early 已接近，contact memory 會直接打壞
  - 下一步不應把單一 contact-memory 升級為正式模型；較合理的是 dual-path apex mixing：一條 fast effluent path + 一條 contact-cooled path，混合權重由 bloom flow regime 決定

---

## 2026-04-25 13:30:24 +0800

- 改動：
  - 在 `V60Params` 新增 `effluent_coupling_gate_mode`，預設 `constant`
  - 在 `core.py` 將 `bulk_effluent_exchange` 包成可切換 gate：
    - `constant`
    - `liq_transport_gate`
    - `head_gate`
  - 在 `pour_over/bloom_diagnostics.py` 新增 `analyze_h2_effluent_coupling()`，固定 fitted params 只替換 gate mode
  - 本輪是 counterfactual closure test，不是正式 rebaseline
- 實驗：
  - `uv run python -m unittest tests.test_core_mass_balance.CoreMassBalanceTests.test_unknown_effluent_coupling_gate_mode_fails_fast tests.test_core_mass_balance.CoreMassBalanceTests.test_default_effluent_coupling_gate_preserves_baseline_temperature`
  - `uv run python -m unittest tests.test_bloom_diagnostics.BloomDiagnosticsTests.test_analyze_h2_effluent_coupling_reports_gate_modes`
  - `uv run python -m pour_over.bloom_diagnostics`
  - artifact：`data/bloom_h2_effluent_coupling_summary.csv`
- 結果：
  - `kinu28 4:20`：
    - `liq_transport_gate` early Δ `+0.00 °C`，late Δ `-0.12 °C`
    - `head_gate` early Δ `+0.77 °C`，late Δ `-0.74 °C`
  - `kinu29 4:12`：
    - `liq_transport_gate` early Δ `+0.14 °C`，late Δ `-0.10 °C`
    - `head_gate` early Δ `+1.03 °C`，late Δ `-0.69 °C`
  - `kinu29 4:11`：
    - `liq_transport_gate` early Δ `+0.10 °C`，late Δ `-0.03 °C`
    - `head_gate` early Δ `+1.60 °C`，late Δ `-0.15 °C`
  - overall H2：`not_supported`
- 判讀：
  - H2 不成立：降低 low-connectivity 狀態下的 bulk-effluent exchange 並沒有降低 `10-20 s` early T2 RMSE
  - `head_gate` 反而讓 early T2 更差，表示 early overheating 不是單純來自 bulk-effluent 常開耦合過強
  - late T2 RMSE 有小幅下降，但幅度小且不對應 H2 的主要症狀；下一步應進入 H3，檢查 apex/filter contact-history 或獨立 contact node

---

## 2026-04-25 13:08:12 +0800

- 改動：
  - 在 `pour_over/bloom_diagnostics.py` 新增 `analyze_h1_flow_timing()`
  - 對三案 `0-40 s` bloom diagnostic 進行 H1 檢定：server-volume residual 是否能解釋 T2 residual
  - 輸出 `data/bloom_h1_flow_timing_summary.csv`
- 實驗：
  - `uv run python -m unittest tests.test_bloom_diagnostics.BloomDiagnosticsTests.test_analyze_h1_flow_timing_reports_decision_metrics`
  - `uv run python -m pour_over.bloom_diagnostics`
- 結果：
  - `kinu28 4:20`：corr `-0.83`，same-sign `0.29`，H1 `not_supported`
  - `kinu29 4:12`：corr `-0.49`，same-sign `0.57`，H1 `partial`
  - `kinu29 4:11`：corr `+0.02`，same-sign `0.43`，H1 `not_supported`
  - overall H1：`partial`
- 判讀：
  - H1 不是全域主因；`4:20` 與 `4:11` 的 volume residual 與 T2 residual 不同步
  - `4:12` 只能標為 partial，因為同號率略高但相關性仍為負，且 early/late T2 residual 變號
  - 下一步應進入 H2：檢查 `bulk_effluent_exchange` 常開耦合是否主導 early apex overheating，同時監控 late bias 是否惡化

---

## 2026-04-24 15:20:21 +0800

- 改動：
  - 新增 `pour_over/bloom_diagnostics.py`，將 `0-40 s` 悶蒸期作為 thermal-flow coupled diagnostic 視窗
  - 對三個 measured thermal case 輸出 bloom 診斷 CSV，欄位包含體積殘差、`T1/T2` 殘差、`q_bed_transport`、`q_out`、`head_gate`、`liq_transport_gate` 與三個熱節點
  - 產生跨 case 的 `bloom_thermal_flow_diagnostics.png`
  - 不改主熱方程、不改 fitted summary、不改 extraction 參數
- 實驗：
  - `uv run python -m unittest tests.test_bloom_diagnostics`
  - `uv run python -m pour_over.bloom_diagnostics`
  - artifact：
    - `data/bloom_thermal_flow_diagnostics.png`
    - `data/kinu_28_light/4:20/kinu28_light_20g_bloom_thermal_flow_diagnostics.csv`
    - `data/kinu_29_light/4:12/kinu29_light_20g_bloom_thermal_flow_diagnostics.csv`
    - `data/kinu_29_light/4:11/kinu29_light_20g_bloom_thermal_flow_diagnostics.csv`
- 結果：
  - `kinu28 4:20`：volume residual `-10.80 to +0.42 mL`，T2 residual `-10.63 to +32.85 °C`
  - `kinu29 4:12`：volume residual `-16.66 to +0.00 mL`，T2 residual `-10.33 to +24.39 °C`
  - `kinu29 4:11`：volume residual `-33.91 to +0.00 mL`，T2 residual `-39.22 to +8.91 °C`
  - bloom diagnostic regression：`PASS`
- 判讀：
  - 悶蒸期應視為 coupled thermal-flow regime；只看 `10-20 s` 的 T2 過熱會漏掉 `20-35 s` 偏冷與 volume timing mismatch
  - 下一步應用此 diagnostic 先判斷 flow/observation timing 是否主導，再決定是否 gated `bulk_effluent_exchange`
  - 目前不應直接新增熱參數或調小 `lambda_liquid_effluent`，因為可能改善早段過熱但惡化後段偏冷

---

## 2026-04-12 15:06:01 +0800

- 改動：
  - 將 slow pool 的有效反應面積從 `A_total` 改為受 `shell_accessibility` 約束的 `A_total × (1 - shell_acc)^gamma`
  - 新增 `gamma_slow_area`，讓 slow pool 不再同時擁有 full external area 與 deep-core diffusion path
  - 重跑 formal measured fit 與 benchmark suite，重生 summary、diagnostics 與 thermal comparison
- 實驗：
  - 原始碼：`pour_over/params.py`
  - flow summary：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - benchmark：`data/benchmark_suite_summary.csv`
  - flow diagnostics：`data/kinu29_calibrated_flow_diagnostics_180s.png`
  - extraction quality：`data/kinu29_calibrated_extraction_quality_180s.png`
  - thermal comparison：`data/kinu29_light_20g_thermal_profile_comparison.png`
- 結果：
  - `k_fit = 8.215e-11`
  - `k_beta_fit = 1.205e3`
  - `tau_lag = 2.0 s`
  - `wetbed_struct_gain_fit = 0.2946`
  - `server_cooling_lambda_fit = 5.348e-4`
  - `V_out RMSE = 13.51 mL`
  - `q_out RMSE = 1.24 mL/s`
  - `drain_time_error = +1.46 s`
  - `cup_temp_error = +0.04 °C`
  - `benchmark status = PASS`
  - thermal validation：`T1 RMSE = 2.36 °C`、`T2 RMSE = 7.92 °C`
  - thermal validation：model `TDS = 0.716%`，相對目標 `1.36% TDS` 尚有 `-0.64 %-pt` 缺口
- 判讀：
  - 在改成 `TDS-first` 驗證後，slow effective interface 修正只帶來小幅改善：model `TDS` 從前一版約 `0.708%` 升到 `0.716%`
  - 但 `T2 RMSE` 幾乎沒有改善，代表剩餘缺口不只是總量或有效界面，仍包含更深的 transfer-history / thermal-history closure 問題

---

## 2026-04-12 01:45:10 +0800

- 改動：
  - 將 bin-level `M_fast_0_bins / M_slow_0_bins` 的分配從反應面積權重改為固體體積權重
  - 將總可萃量固定為 `dose_g × max_EY`，只讓 measured PSD / shell 幾何改變 fast-slow split，不再同時放大總庫存
- 實驗：
  - 原始碼：`pour_over/params.py`
  - 語法驗證：`uv run python -m compileall pour_over`
  - 守恆檢查：以 `shell_thickness = 100 / 200 / 400 μm` 重建參數並檢查 `M_sol_0`
- 結果：
  - 三組 shell 厚度下皆有 `M_sol_0 = dose × max_EY = 4.4 g`
  - `sum(M_fast_0_bins) = M_fast_0`
  - `sum(M_slow_0_bins) = M_slow_0`
  - shell 增加時，`M_fast_0` 單調上升、`M_slow_0` 單調下降
- 判讀：
  - 第一優先級的質量守恆語義已修正：shell 幾何不再同時改變總可萃量與庫存 split
  - 這一筆先只修正 closure 語義；formal rebaseline 仍在執行中，尚未在本 entry 宣告新的 benchmark 數字

---

## 2026-04-12 01:49:43 +0800

- 改動：
  - 在 inventory conservation rewrite 之後重跑 formal measured fit
  - 重生 summary、benchmark summary、flow diagnostics、extraction quality 與 thermal comparison
- 實驗：
  - flow summary：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - benchmark：`data/benchmark_suite_summary.csv`
  - flow diagnostics：`data/kinu29_calibrated_flow_diagnostics_180s.png`
  - extraction quality：`data/kinu29_calibrated_extraction_quality_180s.png`
  - thermal comparison：`data/kinu29_light_20g_thermal_profile_comparison.png`
- 結果：
  - `k_fit = 7.827e-11`
  - `k_beta_fit = 1.134e3`
  - `tau_lag = 2.0 s`
  - `wetbed_struct_gain_fit = 0.1659`
  - `server_cooling_lambda_fit = 5.259e-4`
  - `V_out RMSE = 13.48 mL`
  - `q_out RMSE = 1.24 mL/s`
  - `drain_time_error = +2.06 s`
  - `cup_temp_error = +0.06 °C`
  - `benchmark status = PASS`
  - thermal validation：`T1 RMSE = 2.42 °C`、`T2 RMSE = 7.91 °C`
  - thermal validation：model `TDS = 0.708%`，相對目標 `1.36% TDS` 仍有 `-0.65 %-pt` 缺口
  - showcase baseline 重生後的 extraction figure：final `TDS ≈ 0.548%`、`EY ≈ 7.50%`
- 判讀：
  - 在修正庫存守恆後，formal baseline 仍可通過全部 flow / thermal benchmark gate，表示這次 `P0/P1` 修改沒有破壞既有水力主線
  - model `TDS` 從前一版約 `0.56%` 再推高到 `0.71%`，代表「先修總量守恆，再重 fit」確實有實質改善
  - 但主缺口仍然存在，說明下一步應聚焦 slow-pool effective interface / transfer-history，而不是再調整總可萃量

---

## 2026-04-11 16:33:13 +0800

- 改動：
  - 以新的 `data/kinu_29_light/PSD_export_data.csv` / `PSD_export_data_stats.csv` 重生 measured PSD artifact
  - 正式 measured fit 路徑補上 `data/kinu29_psd_bins.csv` ingest，避免只更新檔案卻沒進主模型
- 實驗：
  - PSD 摘要：`data/kinu29_psd_summary.csv`
  - PSD bins：`data/kinu29_psd_bins.csv`
- 結果：
  - `recommended_D10 = 517 μm`
  - `fines_num_lt_0p40mm = 5.8%`
  - `k_beta_prior_psd = 6.19e2 m^-3`
- 判讀：
  - 新 PSD 比舊 baseline 顯著偏粗，主模型預期會把堵塞 prior 與萃取表面積一起往下修
  - 後續 flow / extraction 結果必須用這份新 bins 重跑，舊的 `D10≈374 μm` 敘事不再有效

---

## 2026-04-11 16:47:50 +0800

- 改動：
  - 以新 PSD bins 對 measured benchmark 做 seeded refit，重生 summary、lead figure、benchmark summary 與 calibrated diagnostics
  - 新增 `data/kinu29_light_20g_thermal_profile.csv` 與熱端對照圖，將 `T1/T2/final TDS` 納入獨立驗證線
- 實驗：
  - flow summary：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - benchmark：`data/benchmark_suite_summary.csv`
  - lead figure：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
  - flow diagnostics：`data/kinu29_calibrated_flow_diagnostics_180s.png`
  - extraction quality：`data/kinu29_calibrated_extraction_quality_180s.png`
  - thermal comparison：`data/kinu29_light_20g_thermal_profile_comparison.png`
- 結果：
  - `k_fit = 7.824e-11`
  - `k_beta_fit = 7.185e2`
  - `tau_lag = 2.0 s`
  - `wetbed_struct_gain_fit = 0.1418`
  - `V_out RMSE = 13.62 mL`
  - `q_out RMSE = 1.24 mL/s`
  - `drain_time_error = +0.71 s`
  - `cup_temp_error = -0.05 °C`
  - `benchmark status = PASS`
  - `T1 RMSE = 2.40 °C`
  - `T2 RMSE = 7.92 °C`
  - `final TDS error = -0.88 %-pt`（model `0.48%` vs target `1.36% TDS`，由折射計讀值換算）
- 判讀：
  - 新 PSD 下的水力校準仍可通過 benchmark，但堵塞量級顯著下降，表示舊的高堵塞 baseline 主要來自舊 PSD 假設
  - 熱端 bulk server 溫度已接近可接受，但 cone outflow 溫度與 final TDS 同時嚴重偏低，顯示目前 extraction / thermal coupling 仍缺機制，不能把這組新資料當成單純雜訊

---

## 2026-04-11 17:02:58 +0800

- 改動：
  - 固定新的水力 baseline，不動 `k / k_beta / tau_lag / wetbed / server cooling`
  - 以 `TDS = 1.36%` 為硬目標，對 thermal recipe 單獨掃描 `k_ext_coef`
- 實驗：
  - 掃描檔：`data/kinu29_kext_scan_thermal_recipe.csv`
- 結果：
  - baseline `k_ext_coef = 4.8e-7`
  - 掃到 `64x` 時，`TDS = 1.048%`、`EY = 14.39%`
  - 掃到 `2048x` 時，`TDS = 1.224%`、`EY = 16.82%`
  - 仍無法達到目標 `1.36%`
  - 當前 closure 的 `M_sol_0 = 3.338 g`
  - 目標 `1.36%` 配 `~275 mL` 出杯需要 `~3.74 g` 溶出物
- 判讀：
  - 缺口主要不是傳質倍率不足，而是 closure 結構把可萃總量上限壓得太低
  - 目前最關鍵的限制來自 `max_EY=0.22` 與 measured-PSD 下的 accessibility / soluble-mass budget，而不是單獨的 `k_ext_coef`

---

## 2026-04-11 18:49:49 +0800

- 改動：
  - 延續固定水力 baseline 的策略，單獨掃描 `max_EY`
  - 檢查只放寬可萃總量上限時，是否足以把 thermal recipe 拉到 `TDS = 1.36%`
- 實驗：
  - 掃描檔：`data/kinu29_max_ey_scan_thermal_recipe.csv`
- 結果：
  - baseline `max_EY = 0.22` 時，`TDS = 0.480%`
  - 掃到 `max_EY = 0.40` 時，`TDS = 0.785%`、`EY = 10.79%`
  - 全段都無法接近目標 `1.36%`
- 判讀：
  - 單獨提高 `max_EY` 也不夠，代表缺口不只是 soluble budget 太低
  - 在當前 closure 下，`accessibility / diffusion-path / thermal-history` 與 `max_EY` 一起形成更強的結構限制

---

## 2026-04-11 18:52:26 +0800

- 改動：
  - 固定水力 baseline，單獨掃描 `shell_thickness`
  - 直接測試 accessibility closure 是否為主缺口
- 實驗：
  - 掃描檔：`data/kinu29_shell_thickness_scan_thermal_recipe.csv`
- 結果：
  - baseline `shell_thickness = 200 μm` 時，`TDS = 0.480%`
  - 最佳點約在 `600 μm`，`TDS = 0.794%`、`EY = 10.90%`
  - 同點 `M_sol_0 = 4.176 g`，已高於目標所需的 `~3.74 g`
  - `800–1000 μm` 時 TDS 反而下降
- 判讀：
  - 單獨放寬 accessibility 仍無法達到 `1.36%`
  - 當 soluble budget 已足夠但 TDS 仍偏低，代表主限制已轉移到 diffusion-path / transfer-history，而不是單純可及質量不足
  - `shell_thickness` 出現非單調反轉，表示目前 closure 對 shell 深度的耦合方式本身值得重寫，而不是只調一個更大的數值

---

## 2026-04-11 19:00:16 +0800

- 改動：
  - 固定水力 baseline，直接縮放 fast/slow effective diffusion path
  - 檢查 `L_eff` 是否為單一主限制
- 實驗：
  - 掃描檔：`data/kinu29_diffusion_path_scan_thermal_recipe.csv`
- 結果：
  - baseline fast/slow path 約為 `100 / 396 μm`
  - 將 path 同步縮短到 baseline 的 `5%` 時，`TDS = 1.022%`、`EY = 14.04%`
  - 即便極端縮短路徑，仍無法達到目標 `1.36%`
- 判讀：
  - diffusion-path 不是單一主因；即使顯著縮短 `L_eff`，缺口仍存在
  - 目前 under-extraction 至少同時來自兩個以上 closure：可及質量、路徑/傳質、以及熱歷史之一或多者共同作用

---

## 2026-04-11 19:06:59 +0800

- 改動：
  - 固定水力 baseline，對 `shell_thickness × path_mult` 做 joint scan
  - 檢查 accessibility 與 diffusion-path 是否需要聯合調整，才能回到量測 `TDS = 1.36%`
- 實驗：
  - 掃描檔：`data/kinu29_shell_path_joint_scan_thermal_recipe.csv`
  - 熱圖：`data/kinu29_shell_path_joint_scan_thermal_recipe.png`
- 結果：
  - 共有 `5` 個組合可達 `TDS >= 1.36%`
  - 第一個達標點為 `shell_thickness = 500 μm`、`path_mult = 0.05`
  - 最接近目標的點為 `shell_thickness = 600 μm`、`path_mult = 0.1`
  - 該點 `TDS = 1.373%`、`EY = 18.87%`、`M_extracted = 3.773 g`
  - 但 `T2 RMSE = 7.92 °C` 幾乎未改善
- 判讀：
  - 目標 TDS 並非不可達，但必須同時放寬 shell accessibility 與 effective path，單變數調整無法做到
  - 這說明目前主缺口在 `shell_accessibility + diffusion_path` 的耦合寫法，而不是單一倍率參數
  - 即使把 TDS / EY 拉回量測區間，`T2` 仍然失配，表示熱歷史 closure 也仍有獨立問題，不能把整個偏差都歸因於萃取倍率

---

## 2026-04-11 19:33:03 +0800

- 改動：
  - 直接重寫 `shell_accessibility + diffusion_path` 耦合 closure
  - measured-bin 的 fast/slow area、mass fraction、path 改為共用同一套 shell/core 幾何
  - aggregate slow path 改為真正的 core-weighted 平均，移除舊版把 weighted sum 直接當 path 的結構錯誤
  - `latest_calibrated_params()` 改為從 measured flow metadata 與最新 summary 載入正式 baseline，避免展示 state 繼續吃舊 `D10` 或漏掉熱端校準參數
- 實驗：
  - flow summary：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - benchmark：`data/benchmark_suite_summary.csv`
  - flow diagnostics：`data/kinu29_calibrated_flow_diagnostics_180s.png`
  - extraction quality：`data/kinu29_calibrated_extraction_quality_180s.png`
  - thermal comparison：`data/kinu29_light_20g_thermal_profile_comparison.png`
- 結果：
  - `k_fit = 7.699e-11`
  - `k_beta_fit = 8.899e2`
  - `tau_lag = 1.6 s`
  - `wetbed_struct_gain_fit = 0.0991`
  - `server_cooling_lambda_fit = 5.269e-4`
  - `V_out RMSE = 13.53 mL`
  - `q_out RMSE = 1.23 mL/s`
  - `drain_time_error = +0.26 s`
  - `cup_temp_error = +0.07 °C`
  - `benchmark status = PASS`
  - thermal validation：`T1 RMSE = 2.36 °C`、`T2 RMSE = 7.91 °C`
  - thermal validation：model `TDS = 0.563%`，相對目標 `1.36% TDS` 仍有 `-0.80 %-pt` 缺口
- 判讀：
  - closure rewrite 修正了 measured-bin 幾何不一致與 slow-path 過重懲罰，formal flow baseline 仍可通過 benchmark
  - final `TDS` 只從約 `0.48%` 小幅升到 `0.56%`，表示主缺口已不再是舊的 shell/path wiring bug，而是更深的 transfer-history / thermal-history closure
  - 這次重寫應保留；但若要把 `1.36% TDS` 拉回來，下一步不能只靠再調單一倍率

---

## 2026-03-28 18:35:19 +0800

- 改動：
  - 將 `chi_struct` 正式接入 `k_eff`
  - 對 `wetbed_struct_gain / rate / release` 做首輪粗掃描
- 實驗：
  - 掃描檔：`data/archive/2026-03-exploration/kinu29_wetbed_struct_scan.csv`
  - 熱圖：`data/archive/2026-03-exploration/kinu29_wetbed_struct_scan_heatmap.png`
- 結果：
  - 最佳組合出現在 `gain=0.30, rate=0.16, release=0.60`
  - `V_out RMSE = 13.32 mL`
  - `q_out RMSE = 1.19 mL/s`
  - `drain_time_error = +0.39 s`
- 判讀：
  - `chi_struct` 有可辨識訊號
  - 改善主要來自累積出液與停流時間，不是瞬時流速 RMSE

---

## 2026-03-28 18:41:44 +0800

- 改動：
  - 擴大 `wetbed_struct_*` 掃描範圍，做正式掃描
- 實驗：
  - 掃描檔：`data/archive/2026-03-exploration/kinu29_wetbed_struct_scan_formal.csv`
  - 熱圖：`data/archive/2026-03-exploration/kinu29_wetbed_struct_scan_formal_heatmap.png`
- 結果：
  - 正式最佳組合為 `gain=1.00, rate=0.03, release=0.30`
  - `V_out RMSE = 13.27 mL`
  - `q_out RMSE = 1.18 mL/s`
  - `drain_time_error = +0.55 s`
- 判讀：
  - `release≈0.30` 相對穩定
  - `gain` 與 `rate` 之間存在 ridge，不適合三個自由度同時正式擬合

---

## 2026-03-28 18:52:12 +0800

- 改動：
  - measured fitting 流程加入 `wetbed χ`
  - 固定 `wetbed_struct_rate = 0.06068366147200567`
  - 固定 `wetbed_impact_release_rate = 0.30`
  - 只擬合 `wetbed_struct_gain`
- 實驗：
  - 摘要檔：`data/archive/2026-03-exploration/kinu29_light_20g_flow_fit_with_wetbedchi_summary.csv`
- 結果：
  - `k_fit = 9.076e-11`
  - `k_beta_fit = 3.005e3`
  - `tau_lag = 1.6 s`
  - `wetbed_struct_gain_fit = 0.1082`
  - `V_out RMSE = 13.46 mL`
  - `q_out RMSE = 1.25 mL/s`
  - `drain_time_error = +1.38 s`
- 判讀：
  - `wetbed χ` 應保留，但只宜保留單一自由度 `gain`

---

## 2026-03-30 04:11:06 +0800

- 改動：
  - 建立 formal benchmark 流程
  - 新增 measured fit 的局部可識別性分析
- 實驗：
  - slices：`data/kinu29_fit_identifiability_slices.csv`
  - heatmap：`data/kinu29_fit_identifiability_heatmap.png`
- 結果：
  - `k` 對 loss 很敏感，屬硬參數
  - `k_beta` 屬弱可識別，但仍可保留
  - `wetbed_struct_gain / rate` 幾乎是平 ridge
- 判讀：
  - 正式 fitting 應保留 `k`
  - `k_beta` 應搭配 PSD prior
  - `wetbed_struct_rate` 不應再自由漂移

---

## 2026-03-30 04:47:13 +0800

- 改動：
  - 新增 `pref_flow_*` 專用 identifiability 分析
  - 對 `pref_flow_coeff / open_rate / tau_decay` 做局部掃描
- 實驗：
  - 快速 slices：`data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_slices_fast.csv`
  - 快速 heatmap：`data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_heatmap_fast.png`
  - 完整版產物：`data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_slices.csv`、`data/archive/2026-03-exploration/kinu29_pref_flow_identifiability_heatmap.png`
- 結果：
  - 三個 `pref_flow_*` 都不是硬參數
  - `pref_flow_coeff`：`medium`
  - `pref_flow_open_rate`：`medium`
  - `pref_flow_tau_decay`：`medium`
- 判讀：
  - `open_rate` 與 `tau_decay` 不值得同時放開
  - 正式策略應改成：
    - 只保留 `pref_flow_coeff`
    - 固定 `pref_flow_open_rate = 0.254074546131474`
    - 固定 `pref_flow_tau_decay = 3.1401416403754285`

---

## 2026-03-30 05:12:22 +0800

- 改動：
  - 將 `pref_flow` 第四階段改為正式單自由度版本
  - 只擬合 `pref_flow_coeff`
  - `pref_flow_open_rate`、`pref_flow_tau_decay` 改為 fixed
  - 加入 final-resolution 守門：
    - 若快路徑會明顯惡化 `V_out RMSE`，則拒絕採用
- 實驗：
  - lead figure：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
  - summary：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - benchmark：`data/benchmark_suite_summary.csv`
- 結果：
  - `k_fit = 8.478e-11`
  - `k_beta_fit = 1.528e3`
  - `tau_lag = 2.0 s`
  - `wetbed_struct_gain_fit = 0.1809`
  - `pref_flow_coeff_fit = 0.0`
  - `pref_flow_open_rate_fixed = 0.254074546131474`
  - `pref_flow_tau_decay_fixed = 3.1401416403754285`
  - `fit_preferential_flow = False`
  - `V_out RMSE = 13.53 mL`
  - `q_out RMSE = 1.25 mL/s`
  - `drain_time_error = +1.16 s`
  - `cup_temp_error = +3.10 °C`
  - benchmark 狀態：`PASS`
- 判讀：
  - 在目前 measured case 下，固定 shape 後只放 `coeff` 自由，仍不足以同時改善節奏與守住體積
  - 因此正式流程允許 `pref_flow` 存在，但不會強行啟用

---

## 2026-03-30 12:48:20 +0800

- 改動：
  - 將床內萃取由單一 CSTR 升級為兩層軸向串接模型
  - 在 lag layer 後加入顯式 `server-side natural convection`
  - 讓 measured fit 在固定水力 closure 後，額外標定 `lambda_server_ambient`
  - 重新輸出 calibrated flow / extraction figures
- 實驗：
  - 主摘要：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - benchmark：`data/benchmark_suite_summary.csv`
  - flow diagnostics：`data/kinu29_calibrated_flow_diagnostics_180s.png`
  - extraction quality：`data/kinu29_calibrated_extraction_quality_180s.png`
- 結果：
  - `axial_node_count = 2`
  - `k_fit = 9.056e-11`
  - `k_beta_fit = 2.362e3`
  - `tau_lag = 2.0 s`
  - `wetbed_struct_gain_fit = 0.1308`
  - `pref_flow_coeff_fit = 2.774e-5`
  - `server_cooling_lambda_fit = 5.556e-4`
  - `V_out RMSE = 13.77 mL`
  - `q_out RMSE = 1.25 mL/s`
  - `drain_time_error = +0.71 s`
  - `cup_temp_error = +0.07 °C`
  - benchmark 狀態：`PASS`
- 判讀：
  - 兩層軸向床已足以把「上層先稀釋、下層決定出液濃度」顯式帶進主模型
  - 杯溫主誤差確實來自壺端散熱；加入 `server-side natural convection` 後，不需再扭曲 `vessel_equivalent_ml`
  - `pref_flow` 在新熱/萃取結構下可接受一個小但非零的 `coeff`，且未破壞體積 gate

---

## 2026-03-30 14:52:02 +0800

- 改動：
  - 在主 Darcy 路徑加入顯式 `kr(sat)`
  - `q_preferential()` 同步吃進 `kr(sat)`，避免未飽和期只靠 `wet_gate`
  - 將 `kr_sat` 輸出到 diagnostics，並重跑 calibrated fit / benchmark / calibrated figures
- 實驗：
  - 主摘要：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - benchmark：`data/benchmark_suite_summary.csv`
  - flow diagnostics：`data/kinu29_calibrated_flow_diagnostics_180s.png`
  - extraction quality：`data/kinu29_calibrated_extraction_quality_180s.png`
- 結果：
  - `k_fit = 8.441e-11`
  - `k_beta_fit = 1.972e3`
  - `tau_lag = 1.6 s`
  - `wetbed_struct_gain_fit = 0.1892`
  - `pref_flow_coeff_fit = 0.0`
  - `server_cooling_lambda_fit = 5.273e-4`
  - `V_out RMSE = 13.39 mL`
  - `q_out RMSE = 1.24 mL/s`
  - `drain_time_error = +1.46 s`
  - `cup_temp_error = +0.05 °C`
  - benchmark 狀態：`PASS`
- 判讀：
  - 顯式 `kr(sat)` 讓 bloom 前主流量不再只靠 `h_eff` cutoff，水力 closure 更乾淨
  - 新 closure 讓 `k` 與 `k_beta` 回到更保守的量級，同時維持 benchmark 內通過
  - 在顯式未飽和 Darcy 後，`pref_flow` 再次退回不必要，表示先前的小快路徑需求部分是在替未飽和水力缺項補洞

---

## 2026-03-30 15:15:48 +0800

- 改動：
  - 將 `kr(sat)` 納入主 diagnostics panel，新增 bloom 視窗內的 `sat_flow / kr(sat) / head_gate` 分解
  - 將 `sat_rel_perm_residual`、`sat_rel_perm_exp` 納入 measured-fit identifiability slices 與 hydraulic heatmap
  - calibrated diagnostics / identifiability artifact 重輸出
- 實驗：
  - flow diagnostics：`data/kinu29_calibrated_flow_diagnostics_180s.png`
  - extraction quality：`data/kinu29_calibrated_extraction_quality_180s.png`
  - identifiability slices：`data/kinu29_fit_identifiability_slices.csv`
  - identifiability heatmap：`data/kinu29_fit_identifiability_heatmap.png`
  - benchmark：`data/benchmark_suite_summary.csv`
- 結果：
  - benchmark 狀態：`PASS`
  - `V_out RMSE = 13.39 mL`
  - `q_out RMSE = 1.24 mL/s`
  - `drain_time_error = +1.46 s`
  - `cup_temp_error = +0.05 °C`
  - bloom 視窗平均 choke 分解：
    - `h_cap/h_gas = 0.662`
    - `kr(sat) = 0.380`
    - `sat_flow = 0.264`
  - bloom 主導 choke：`h_cap_h_gas`
- 判讀：
  - 目前 measured baseline 的 bloom 前 choke 主要不是 `sat_flow`，也不是 `kr(sat)` 本身，而是 `h_cap/h_gas` 對有效驅動頭的抑制
  - `kr(sat)` 確實有次級影響，且方向一致，但量級仍明顯低於 `head_gate`
  - identifiability slices 與 heatmap 都顯示 `sat_rel_perm_residual / sat_rel_perm_exp` 在 calibrated 解附近近乎 flat ridge；它們目前屬弱可識別 closure，不應取代 `k` 或 `h_cap/h_gas` 成為主敘事
  - `k` 仍是硬參數；`k_beta` 次之，但與 `sat_rel_perm_*` 的交互只造成次級 loss 變化
  - 若要再提升未飽和段 closure 的可識別性，下一步應優先補更直接的 bloom 期資料，而不是再放大 `kr(sat)` 的自由度

---

## 2026-04-07 16:55:56 +0800

- 改動：
  - 將 `data/kinu_29_light/` 的 PSD raw export 轉成正式 model-ready artifact
  - 新增 `data/kinu29_psd_summary.csv`
  - 新增 `data/kinu29_psd_bins.csv`
  - 執行 `uv run python -m compileall pour_over` 做最小 smoke check
- 實驗：
  - raw：`data/kinu_29_light/kinu29_PSD_export_data.csv`
  - stats：`data/kinu_29_light/kinu29_PSD_export_data_stats.csv`
  - summary：`data/kinu29_psd_summary.csv`
  - bins：`data/kinu29_psd_bins.csv`
- 結果：
  - `particle_count = 4554`
  - `hist_D10 / D50 / D90 = 0.374 / 0.723 / 1.611 mm`
  - `model_D10 / D50 / D90 = 0.374 / 0.705 / 1.518 mm`
  - `recommended_D10 = 374 μm`
  - `fines_num_lt_0p40mm = 13.2 %`
  - `multi-bin rows = 7`
  - smoke test：`PASS`
- 判讀：
  - 這批 raw export 與目前正式 baseline 使用的 `D10 ≈ 374 μm` 一致，表示 measured PSD 主敘事已有正式數據來源
  - 這次沒有重跑 calibrated fit 或 benchmark，所以新增的是 artifact reproducibility，不是新的擬合優勢結論
  - 未來若 `data/kinu_29_light/` 內容更新，必須同步重生 `data/kinu29_psd_bins.csv`，不能只替換 raw 資料夾

---

## 中間結論（供下次迭代直接使用）

- `sat_flow` 硬切已被平滑鬆弛取代，避免 bloom 結束後的人為不連續
- `kr(sat)` 已正式進入主 Darcy 路徑與 `q_preferential()`
- bloom 前 choke 的正式診斷應優先看：
  - `head_gate`（`h_cap/h_gas`）
  - `kr_sat`
  - `sat_flow`
  - 目前主導者是 `head_gate`
- `chi_struct` 已正式回饋到 `k_eff`
- 萃取端目前正式版本應維持 `axial_node_count = 2`
- `sat_rel_perm_residual` 與 `sat_rel_perm_exp` 目前應視為弱可識別 closure：
  - 可保留於主模型
  - 不宜作主要擬合自由度
- `wetbed χ` 的正式版本應維持：
  - `wetbed_struct_gain` 可擬合
  - `wetbed_struct_rate = 0.06068366147200567` 固定
  - `wetbed_impact_release_rate = 0.30` 固定
- `pref_flow` 的正式版本應維持：
  - `pref_flow_coeff` 可作候選自由度
  - `pref_flow_open_rate = 0.254074546131474` 固定
  - `pref_flow_tau_decay = 3.1401416403754285` 固定
  - 只有在不惡化 `V_out RMSE` 的前提下才採用
- 熱端目前正式版本應維持：
  - `vessel_equivalent_ml` 仍視為量測固定量
  - `lambda_server_ambient` 可作單自由度熱端 closure
  - 杯溫誤差優先由 server-side cooling 解釋，不回頭吸收到 cone 內熱容
- measured PSD ingress 目前正式 artifact 應維持：
  - `data/kinu29_psd_summary.csv`
  - `data/kinu29_psd_bins.csv`
  - 它們由 `data/kinu_29_light/` raw export 重建，不應手改

---

## 目前正式基準

- case：`kinu29_light_20g_measured`
- 主摘要：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- PSD summary：`data/kinu29_psd_summary.csv`
- PSD bins：`data/kinu29_psd_bins.csv`
- benchmark：`data/benchmark_suite_summary.csv`
- 最新狀態：`PASS`

---

## 2026-04-12 17:19:00 +0800

- 改動：
  - 新增 `data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv`
  - 新增 `data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile.csv`
  - 新增 `data/kinu_29_light/4:12/kinu29_psd_summary.csv`
  - 新增 `data/kinu_29_light/4:12/kinu29_psd_bins.csv`
  - `pour_over.measured_io.load_flow_profile_csv()` 改為允許缺少 `final_tds_pct`
  - 新增 `measured_case_psd_bins_path()`，讓 measured case 的 PSD bins 跟著 case 目錄走
  - `pour_over.fitting` / `pour_over.benchmark` 改為使用 case-local PSD artifact，而不是硬編碼 `4:11`
- 實驗：
  - unit test：`uv run python -m unittest tests.test_measured_case_registry -v`
  - smoke check：`uv run python -m compileall pour_over`
  - dual-case load check：驗證 `4:11` 與 `4:12` 都可由 `load_flow_profile_csv()` 成功載入
- 結果：
  - `4:12` flow profile 載入成功：`t_end = 130 s`、`V_out_end = 310 mL`
  - `4:12` thermal profile 載入成功，`estimated_server_volume_ml` / `T1` / `T2` 已結構化
  - `4:12` PSD artifact 重建成功：`D10 = 529 um`、`D50 = 1287 um`、`D90 = 3391 um`
  - `4:12` 的 `final_tds_pct = None` 不再造成 parser 失敗
  - case-local PSD lookup 成功：`4:12` 會解析到 `data/kinu_29_light/4:12/kinu29_psd_bins.csv`
- 判讀：
  - `4:12` 已可作為第二個 measured case 進入現有資料載入與 case-local PSD 管線
  - `4:11` 仍維持正式 showcase / benchmark baseline，這次改動沒有改動 baseline 選擇
  - 由於 `4:12` 缺少 final TDS，這批資料目前較適合 flow / thermal validation，不應直接升級成正式 benchmark

---

## 2026-04-19 23:58:00 +0800

- 改動：
  - 對 `data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv` 執行完整 calibrated flow fit
  - 產生 `4:12` measured case 專屬的 flow fit summary 與 comparison plot artifact
- 實驗：
  - flow input：`data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv`
  - flow summary：`data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - flow comparison：`data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- 結果：
  - `k_fit = 1.241e-10`
  - `k_beta_fit = 1.252e3`
  - `beta_throat = 6.402e2`
  - `beta_deposition = 6.122e2`
  - `tau_lag = 0.50 s`
  - `wetbed_struct_gain_fit = 0.1756`
  - `pref_flow_coeff_fit = 2.643e-4`
  - `V_out RMSE = 16.48 mL`
  - `q_out RMSE = 1.40 mL/s`
  - `drain_time_error = -1.63 s`
  - `v_out_final_ml = 276.13 mL`
- 判讀：
  - `4:12` case 已可完整走過正式 calibrated flow fit 管線，並成功輸出可重用 artifact
  - 相較 `4:11` baseline，`4:12` 顯示更高的有效滲透率與更短的 observation lag，符合其更粗 PSD 與更快排水趨勢
  - 但這組 flow fit 的 `V_out RMSE` 與 `q_out RMSE` 都高於 `4:11` baseline，說明 `4:12` 的量測節奏或當前 closure 仍存在額外差異；目前適合作為第二驗證案例，不應直接取代正式 benchmark

---

## 2026-04-20 00:10:00 +0800

- 改動：
  - 新增 `data/kinu_27_light/4:12/kinu27_light_20g_flow_profile.csv`
  - 新增 `data/kinu_27_light/4:12/kinu27_light_20g_thermal_profile.csv`
  - 新增 `data/kinu_27_light/4:12/kinu27_psd_summary.csv`
  - 新增 `data/kinu_27_light/4:12/kinu27_psd_bins.csv`
  - `measured_case_psd_bins_path()` 改為在 case 目錄內唯一定位 `*_psd_bins.csv`，不再硬編碼 grinder 型號
- 實驗：
  - unit test：`uv run python -m unittest tests.test_measured_case_registry -v`
  - smoke check：`uv run python -m compileall pour_over`
  - load check：直接載入 `data/kinu_27_light/4:12/kinu27_light_20g_flow_profile.csv`
- 結果：
  - `kinu_27 4:12` flow profile 載入成功：`t_end = 135 s`、`V_in_end = 320 mL`、`V_out_end = 280 mL`
  - `stop_flow_time_s = 125 s`
  - `final_tds_pct = None`
  - `kinu27_psd_bins.csv` 可由 case-local lookup 成功解析
  - PSD artifact：`D10 = 517 um`、`D50 = 1246 um`、`D90 = 3116 um`
- 判讀：
  - `kinu_27 4:12` 已完成最小可重跑的 measured case 結構化，可直接進入後續 calibrated flow fit / thermal validation
  - 由於使用者只提供體積與 `T1/T2`，本 case 目前沒有 final TDS 與 final cup temperature；因此現階段較適合 flow / thermal validation，不適合直接做帶終點杯測約束的比較
  - 這次沿用 `20 g / 92°C / 23°C / 5.3 cm / ceramic V60` 的既有 measured-case metadata；若後續有更精確的沖煮設定，應回填 CSV metadata 而不是只改口頭描述

---

## 2026-04-20 00:15:00 +0800

- 改動：
  - 對 `data/kinu_27_light/4:12/kinu27_light_20g_flow_profile.csv` 執行完整 calibrated flow fit
  - 產生 `kinu_27 4:12` measured case 專屬的 flow fit summary 與 comparison plot artifact
- 實驗：
  - flow input：`data/kinu_27_light/4:12/kinu27_light_20g_flow_profile.csv`
  - flow summary：`data/kinu_27_light/4:12/kinu27_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - flow comparison：`data/kinu_27_light/4:12/kinu27_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- 結果：
  - `k_fit = 1.341e-10`
  - `k_beta_fit = 9.450e2`
  - `beta_throat = 4.849e2`
  - `beta_deposition = 4.601e2`
  - `tau_lag = 0.50 s`
  - `wetbed_struct_gain_fit = 0.1288`
  - `pref_flow_coeff_fit = 4.016e-4`
  - `V_out RMSE = 18.00 mL`
  - `q_out RMSE = 1.51 mL/s`
  - `drain_time_error = +10.98 s`
  - `v_out_final_ml = 291.20 mL`
- 判讀：
  - `kinu_27 4:12` 已可完整走過正式 calibrated flow fit 管線，並成功輸出可重用 artifact
  - 相較 `kinu_29` measured cases，這組 fit 需要更高的有效滲透率、更低的堵塞量級與更強的 preferential-flow 項，才能逼近量測曲線
  - 但 `drain_time_error` 仍偏大，表示 `kinu_27 4:12` 的後段排水節奏與當前 closure 仍有顯著落差；它目前適合作為 cross-case stress test，而不是可直接拿來做正式 baseline 的候選

---

## 2026-04-20 00:20:00 +0800

- 改動：
  - 對 `kinu_27 4:12` fitted params 輸出單獨的 thermal comparison artifact
  - 以 `kinu_29 4:11 / 4:12 / kinu_27 4:12` 三案生成並排 comparison artifact
- 實驗：
  - thermal artifact：`data/kinu_27_light/4:12/kinu27_light_20g_thermal_profile_comparison.png`
  - triptych artifact：`data/measured_case_triptych_kinu29_411_412_kinu27_412.png`
- 結果：
  - `kinu_29 4:11`：`Vol RMSE = 51.11 mL`、`T1 RMSE = 2.29 °C`、`T2 RMSE = 7.94 °C`
  - `kinu_29 4:12`：`Vol RMSE = 16.53 mL`、`T1 RMSE = 6.29 °C`、`T2 RMSE = 14.86 °C`
  - `kinu_27 4:12`：`Vol RMSE = 18.04 mL`、`T1 RMSE = 9.93 °C`、`T2 RMSE = 18.21 °C`
  - 三案 model final TDS 皆約 `0.97–1.03%`
- 判讀：
  - 從熱端 validation 看，`kinu_29 4:11` 仍是三案中最接近模型現有熱 closure 的案例，尤其 `T1/T2` 誤差都最低
  - `kinu_29 4:12` 與 `kinu_27 4:12` 的 thermal mismatch 都顯著放大，且 `kinu_27 4:12` 最嚴重，表示跨 case 的主要缺口不只是 flow，而是熱歷史 / observation-layer closure 也沒有一起泛化
  - `kinu_29 4:11` 的 volume RMSE 特別大，反映 thermal profile 的 `estimated_server_volume_ml` 與 flow benchmark 的 `V_out(t)` 並非同一條觀測線，後續比較時不能把它直接當成 flow-fit 失敗

---

## 2026-04-20 00:28:00 +0800

- 改動：
  - 將三份 thermal profile 中 `T1 < 30°C` 的早期冷啟動點改為 `server_temp_use_for_fit = 0`
  - 重跑 `kinu_27 4:12` thermal comparison artifact
  - 重跑三案並排 comparison artifact
- 實驗：
  - unit test：`uv run python -m unittest tests.test_measured_case_registry -v`
  - thermal artifact：`data/kinu_27_light/4:12/kinu27_light_20g_thermal_profile_comparison.png`
  - triptych artifact：`data/measured_case_triptych_kinu29_411_412_kinu27_412.png`
- 結果：
  - `kinu_29 4:11`：`T1 RMSE = 2.29 °C`、`T2 RMSE = 7.94 °C`（不變）
  - `kinu_29 4:12`：`T1 RMSE = 6.41 °C`、`T2 RMSE = 14.86 °C`
  - `kinu_27 4:12`：`T1 RMSE = 10.15 °C`、`T2 RMSE = 18.21 °C`
- 判讀：
  - 把明顯的 cold-start sensor lag 從 `T1` fit mask 排除後，artifact 現在更符合量測語義：保留原始 row，但不讓錯誤早期點污染熱端擬合
  - 這個修正沒有改變跨 case 的主結論：`kinu_29 4:11` 仍是熱端最接近模型的案例，而 `kinu_29 4:12` / `kinu_27 4:12` 的 thermal mismatch 仍顯著偏大

---

## 2026-04-20 00:36:00 +0800

- 改動：
  - 將使用者提供的折射計讀值回填到 `4/12` measured cases
  - 依 Alan Adler relation `TDS = 0.85 × °Brix`，將：
    - `kinu_29 4:12 = 1.6 brix -> 1.36% TDS`
    - `kinu_27 4:12 = 1.4 brix -> 1.19% TDS`
  - 重跑 `kinu_29 4:12` / `kinu_27 4:12` thermal comparison artifact
  - 重跑三案並排 comparison artifact
- 實驗：
  - unit test：`uv run python -m unittest tests.test_measured_case_registry -v`
  - thermal artifacts：
    - `data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile_comparison.png`
    - `data/kinu_27_light/4:12/kinu27_light_20g_thermal_profile_comparison.png`
  - triptych artifact：`data/measured_case_triptych_kinu29_411_412_kinu27_412.png`
- 結果：
  - `kinu_29 4:12`：`final_tds_pct = 1.36%`、model `0.978%`、`final_tds_error = -0.382 %-pt`
  - `kinu_27 4:12`：`final_tds_pct = 1.19%`、model `0.968%`、`final_tds_error = -0.222 %-pt`
  - `kinu_29 4:11`：`final_tds_error = -0.331 %-pt`
- 判讀：
  - 回填終點杯測後，`4/12` cases 終於可以和 `4:11` 在同一個 TDS 指標上直接比較
  - `kinu_29 4:12` 的 TDS 缺口略大於 `4:11`，表示即使把 `4:12` 視為主資料，當前模型在該 case 上也還沒有比 `4:11` 更貼近
  - `kinu_27 4:12` 的 TDS 缺口相對較小，但其 `T1/T2` mismatch 仍然偏大，說明濃度終點較接近不代表整段熱歷史也已被模型正確解釋

---

## 2026-04-20 00:48:00 +0800

- 改動：
  - 將正式 measured baseline 預設從 `data/kinu_29_light/4:11` 切到 `data/kinu_29_light/4:12`
  - 更新 `showcase_state.py` 與 `fitting.py` 的 default measured case
  - 重跑 top-level benchmark summary
  - 重生首頁使用的 calibrated flow / extraction diagnostics
  - 更新 README 與 `index.html`，讓基準敘事與 lead figure 路徑同步到 `4:12`
- 實驗：
  - unit test：`uv run python -m unittest tests.test_measured_case_registry -v`
  - benchmark：`data/benchmark_suite_summary.csv`
  - showcase diagnostics：
    - `data/kinu29_calibrated_flow_diagnostics_180s.png`
    - `data/kinu29_calibrated_extraction_quality_180s.png`
- 結果：
  - default measured case = `data/kinu_29_light/4:12`
  - benchmark status = `FAIL`
  - `V_out RMSE = 16.53 mL`
  - `q_out RMSE = 1.40 mL/s`
  - `drain_time_error = -1.64 s`
- 判讀：
  - `4:12` 已正式升為 repo 的 measured baseline，`4:11` 退為 historical reference
  - 但 baseline 切換後，現行 regression gate 也跟著顯示目前 closure 對 `4:12` 尚未達標；這不是切換失敗，而是更忠實地暴露了模型與你認定較可信量測之間的缺口

---

## 2026-04-20 01:44:00 +0800

- 改動：
  - 將 `kinu_29 4:12` 與 `kinu_27 4:12` 的 glass server 質量 metadata 從 `123.5 g` 改為 `224.1 g`
  - 先保留 `dripper_cp_J_gK = 0.88` 不變
  - 重跑兩組 `4:12` thermal comparison artifact 與三案並排比較
- 實驗：
  - unit test：`uv run python -m unittest tests.test_measured_case_registry -v`
  - thermal artifacts：
    - `data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile_comparison.png`
    - `data/kinu_27_light/4:12/kinu27_light_20g_thermal_profile_comparison.png`
  - triptych artifact：`data/measured_case_triptych_kinu29_411_412_kinu27_412.png`
- 結果：
  - `kinu_29 4:12`：
    - `Vol RMSE = 16.73 mL`
    - `T1 RMSE = 6.17 °C`
    - `T2 RMSE = 15.18 °C`
    - `final_tds_error = -0.394 %-pt`
  - `kinu_27 4:12`：
    - `Vol RMSE = 18.13 mL`
    - `T1 RMSE = 9.73 °C`
    - `T2 RMSE = 17.99 °C`
    - `final_tds_error = -0.232 %-pt`
- 判讀：
  - 單獨修正 glass server 質量後，兩組 `4:12` case 的 `T1 RMSE` 都有小幅改善，表示器材熱容 metadata 確實是熱端誤差來源之一
  - 但 `T2 RMSE` 與 final TDS 誤差沒有一起改善，顯示剩餘主缺口不在 server-side heat capacity，而更可能在 outflow thermal history / observation-layer 或萃取-熱耦合 closure

## 2026-04-20 物理實作修復：修正 Phantom Dilution 與 h_eff 面積計算
- **改動內容**：
  1. 修復了 `dC_fast_layers` / `dC_slow_layers` 在 `h < h_bed` 降水期間會因為 `Q_bed` 持續稀釋而產生 Phantom Dilution (幽靈水稀釋) 的質量守恆錯誤，將原本固定的 `V_liq_conc_layers` 升級為動態液體體積 `V_liq_t` 並計算各層真實入流 `Q_in_layers_col`。
  2. 修復了水位 `h` 變化率方程式 `dh = (Q_in_free - Q_out) / area` 在粉床內部沒有乘上 `phi_eff_now` 的問題，避免水位在粉層內下降過慢。引入 sigmoid 平滑以避免 RK45 solver 遇到非連續導數時卡死。
- **實驗結果**：單次模擬 `v60_sim.py` 能順利跑完。多層 CSTR 在 `Q_in_free = 0` 但 `Q_bed > 0` 的 draw-down 階段能完美守恆溶質，不再有不合理的頂層稀釋現象。
- **判讀或結論**：這兩項修復消除了模型在下降階段過度簡化導致的物理悖論，讓後續對萃取動力的標定與擬合能夠基於真實的水動力學體積變化。

## 2026-04-20 16:06:52 +0800

- 改動：
  - 在 `pour_over/core.py` 新增液相溶質庫存與總守恆殘差診斷：
    - `M_liquid_inventory_g`
    - `M_balance_residual_g`
    - `V_liq_inventory_ml`
  - 新增 regression test：`tests/test_core_mass_balance.py`
  - 以新的 `core.py` 重新校準正式 measured baseline `kinu_29 4:12`
  - 重生：
    - `data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
    - `data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
    - `data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile_comparison.png`
    - `data/benchmark_suite_summary.csv`
- 實驗：
  - `uv run python -m unittest tests.test_core_mass_balance -v`
  - `uv run python -m unittest tests.test_measured_case_registry -v`
  - `uv run python -m compileall pour_over`
  - 正式 baseline 重新校準：`data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv`
- 結果：
  - 標準 `PourProtocol.standard_v60()` 的守恆審計：
    - `final_balance_residual_g = +0.0045`
    - `max_balance_residual_g = +0.0251`
    - `min_balance_residual_g = -0.0165`
  - `kinu_29 4:12` 新 calibrated flow fit：
    - `k_fit = 1.184e-10`
    - `k_beta_fit = 1.081e3`
    - `tau_lag = 2.0 s`
    - `V_out RMSE = 15.47 mL`
    - `q_out RMSE = 1.47 mL/s`
    - `drain_time_error = -0.74 s`
  - `kinu_29 4:12` thermal validation：
    - `Vol RMSE = 15.47 mL`
    - `T1 RMSE = 6.19 °C`
    - `T2 RMSE = 14.97 °C`
    - `model final TDS = 0.985%`
    - `final_tds_error = -0.375 %-pt`
  - `benchmark status = FAIL`
  - `kinu_29 4:12` 守恆審計：
    - `final_balance_residual_g = -0.1924`
    - `max_balance_residual_g = +0.0021`
    - `min_balance_residual_g = -0.1924`
    - 代表性時間點：
      - `30 s: -0.0833 g`
      - `60 s: -0.1516 g`
      - `90 s: -0.1522 g`
      - `130 s: -0.1668 g`
      - `180 s: -0.1924 g`
- 判讀：
  - `dh` 的孔隙面積修正方向是對的，且新 flow fit 讓 `V_out RMSE` 與 `drain_time_error` 都比前版略好
  - 但 `q_out RMSE` 變差，正式 benchmark 仍失敗
  - 更重要的是，新的 draw-down closure 並未達成真正的全局溶質守恆；在正式 measured baseline 上，殘差從約 `30 s` 起即持續維持在 `-0.08 ~ -0.19 g`
  - 這顯示目前 `Q_in_layers` 的層內 transport closure 與最終 `q_bed * C_bed_out` 的出口定義仍不一致；phantom dilution 的舊形式雖被移除，但守恆缺口只是轉移到了層間/出口 closure

## 2026-04-20 16:58:48 +0800

- 改動：
  - 將 `core.py` 的床內液相改成顯式 state `V_liq`
  - 不再由 `h` 反推濃度層體積；改由 `dV_liq/dt` 直接驅動 layer storage
  - 新增 `Q_bed_transport` 與 `liq_transport_gate`，把 hydrodynamic tail 與 solute-carrying transport 分開
  - `C_out_gl` 與 `M_extracted_g` 改用 `q_bed_transport`
  - 新增 measured-case 守恆 regression test，要求 `kinu_29 4:12` 的最小殘差不得低於 `-0.10 g`
- 實驗：
  - `uv run python -m unittest tests.test_core_mass_balance tests.test_measured_case_registry -v`
  - `uv run python -m compileall pour_over`
  - 重新校準與重生 artifact：
    - `data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
    - `data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile_comparison.png`
    - `data/benchmark_suite_summary.csv`
- 結果：
  - 守恆 regression：
    - `standard_v60`：PASS
    - `kinu_29 4:12`：PASS（新 gate：`min_balance_residual_g > -0.10`）
  - `kinu_29 4:12` 守恆審計：
    - `final_balance_residual_g = -0.0530`
    - `min_balance_residual_g = -0.0968`
    - 舊版對照：`final = -0.1924`, `min = -0.1924`
  - `kinu_29 4:12` 新 calibrated flow / thermal：
    - `k_fit = 1.184e-10`
    - `k_beta_fit = 1.081e3`
    - `tau_lag = 2.0 s`
    - `V_out RMSE = 15.51 mL`
    - `q_out RMSE = 1.48 mL/s`
    - `drain_time_error = -0.74 s`
    - `T1 RMSE = 6.01 °C`
    - `T2 RMSE = 14.95 °C`
    - `final_tds_error = -0.422 %-pt`
  - `benchmark status = FAIL`
- 判讀：
  - 這次主 closure 修正有效切斷了「液相庫存已接近空，但 hydrodynamic tail 仍以完整 `Q_bed` 繼續帶走溶質」的錯誤路徑
  - 守恆殘差約改善一半以上，從 `-0.19 g` 降到 `-0.05 ~ -0.10 g`
  - 但 flow benchmark 仍未過 gate，且 final TDS 誤差沒有同步改善，表示主模型的下一個缺口已不再是最粗糙的 phantom-tail closure，而更可能落在：
    - 中段 transport / mixing
    - `q_out` observation layer
    - 或 measured-case flow regime 與現有 wet-bed / pref-flow closure 的結構差異

## 2026-04-20 18:04:13 +0800

- 改動：
  - `measured_io.py` 新增 `resolve_measured_ambient_temp_C()`，measured pipeline 不再默認固定 `23.0°C`
  - ambient 解析改為：先讀 `ambient_temp_C`，缺值時退回 `t=0 server_temp_C`，再退到 `t=0 outflow_temp_C`；若仍缺則直接報錯
  - 新增 `data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv`
  - 新增 `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv`
  - 以 `PSD_export_data.csv` / `PSD_export_data_stats.csv` 重生 `kinu28_psd_summary.csv` / `kinu28_psd_bins.csv`
- 實驗：
  - `uv run python -m unittest tests.test_measured_case_registry`
  - `uv run python -m pour_over.psd data/kinu_28_light/4:20/PSD_export_data.csv --stats-csv data/kinu_28_light/4:20/PSD_export_data_stats.csv --output data/kinu_28_light/4:20/kinu28_psd_summary.csv --bin-output data/kinu_28_light/4:20/kinu28_psd_bins.csv`
- 結果：
  - ambient policy：
    - `metadata -> t=0 server_temp_C -> t=0 outflow_temp_C -> fail fast`
  - `kinu_28 4:20` measured case：
    - `ambient_temp_C = 23.3 °C`
    - `final_tds_pct = 1.60 %`
    - `final poured weight = 301.3 g`
    - `final drained volume = 265 mL`
  - `kinu_28 4:20` PSD：
    - `recommended_D10 = 517 μm`
    - `fines_num_lt_0p40mm = 5.7 %`
    - `multi-bin rows = 7`
  - loader regression：`PASS`
- 判讀：
  - 這次完成的是 measured ingest 規則修正與 `4:20` case 結構化，不是新的 calibrated baseline
  - `kinu_28 4:20` 已具備 case-local PSD 與 strict flow/thermal CSV，可進入後續 calibration
  - 由於這輪沒有拿到穩定完成的 flow-fit artifact，暫時不更新 benchmark 或展示頁敘事

## 2026-04-20 18:08:34 +0800

- 改動：
  - 對 `data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv` 完成 case-local flow fit
  - 產生 `kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - 產生 `kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
  - 產生 `kinu28_light_20g_thermal_profile_comparison.png`
- 實驗：
  - 讀取 case-local summary：
    - `data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - 以 `_load_measured_benchmark_state(..., refit=False)` + `evaluate_measured_thermal_profile(...)` 重算熱端指標
- 結果：
  - `kinu_28 4:20` calibrated flow：
    - `k_fit = 1.486e-10`
    - `k_beta_fit = 1.590e3`
    - `tau_lag = 0.5 s`
    - `wetbed_struct_gain_fit = 0.401`
    - `pref_flow_coeff_fit = 4.269e-4`
    - `V_out RMSE = 10.72 mL`
    - `q_out RMSE = 1.49 mL/s`
    - `drain_time_error = -2.45 s`
  - `kinu_28 4:20` thermal validation：
    - `T1 RMSE = 5.92 °C`
    - `T2 RMSE = 15.76 °C`
    - `model final TDS = 0.948 %`
    - `final_tds_error = -0.652 %-pt`
- 判讀：
  - 這筆 `4:20` 標準化沖煮記錄在流量面明顯比 `4:12` 更容易擬合，至少 `V_out RMSE` 已進一步下降
  - 但它同時要求更高滲透率、更強堵塞量級與更強 preferential-flow 項，說明這種沖煮方式的節奏差異確實反映在可識別 closure 上
  - 熱端與 final TDS 仍遠低於量測，表示「讓水位降到粉層以下再移除濾杯」本身並沒有消除目前 thermal / extraction closure 的主缺口

## 2026-04-20 19:05:01 +0800

- 改動：
  - 在 `core.py` 新增最小必要的 `T_effluent` thermal state，將床內 bulk 與即將流出液分離
  - `observation.py` 改用 `T_effluent_C` 作為 outflow / server thermal chain 的熱源
  - `fitting.py` 的 `T2` 對照改從 effluent chain 取值，不再直接取 bulk `T_C`
  - 新增 semantic regression tests，鎖定 `T2` 不再直接等同 bulk thermal state
- 實驗：
  - `uv run python -m unittest tests.test_measured_case_registry tests.test_core_mass_balance.CoreMassBalanceTests.test_simulate_brew_reports_effluent_temperature_series`
  - `uv run python -m compileall pour_over`
  - 重生 `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile_comparison.png`
  - 重新評估三案 thermal 指標：
    - `data/kinu_28_light/4:20`
    - `data/kinu_29_light/4:12`
    - `data/kinu_29_light/4:11`
- 結果：
  - semantic regression：`PASS`
  - `4:20`：
    - `T1 RMSE = 5.75 °C`
    - `T2 RMSE = 12.63 °C`
    - `final_tds_error = -0.651 %-pt`
  - `4:12`：
    - `T1 RMSE = 5.92 °C`
    - `T2 RMSE = 13.48 °C`
    - `final_tds_error = -0.433 %-pt`
  - `4:11`：
    - `T1 RMSE = 2.27 °C`
    - `T2 RMSE = 6.14 °C`
    - `final_tds_error = -0.348 %-pt`
- 判讀：
  - 這次 `T2` 改善來自 thermal-history 語義修正，而不是 extraction 參數調整
  - 三個 case 的 `T2 RMSE` 都同步下降，代表「bulk `T` 直接當 `T2`」確實是系統性物理錯位
  - final TDS 幾乎不變，支持這次分階段策略：先修 thermal semantic mismatch，再回頭看 extraction-history 殘差

## 2026-04-20 19:47:10 +0800

- 改動：
  - 將 `core.py` 內 `T_effluent` 初始值改為冷 apex，而不是直接沿用 bulk `T_shock`
  - 將 startup apex 的等效 hold-up 改為受 `gate_h` 調節，使 `gate_h < 1` 時包含額外濕潤濾紙 / apex hold-up，`gate_h -> 1` 時回到較小穩態 effluent 熱容
  - `plot_measured_thermal_profile_comparison()` 的 `T2` panel 改為真正畫 `obs_layer["T_effluent_C"]`
  - 補上三個 targeted regression tests：冷 apex 初始條件、`T2` panel 使用 effluent curve、`4:20` 的 startup apex 溫度不應在 `10 s` 直接跳到近 bulk
- 實驗：
  - `uv run python -m unittest tests.test_measured_case_registry tests.test_core_mass_balance.CoreMassBalanceTests.test_simulate_brew_reports_effluent_temperature_series tests.test_core_mass_balance.CoreMassBalanceTests.test_effluent_temperature_starts_from_cold_apex_state`
  - `uv run python -m compileall pour_over`
  - 重生 `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile_comparison.png`
  - 重新評估三案 thermal 指標：
    - `data/kinu_28_light/4:20`
    - `data/kinu_29_light/4:12`
    - `data/kinu_29_light/4:11`
- 結果：
  - targeted thermal regression：`PASS`
  - `4:20`：
    - `T1 RMSE = 5.75 °C`
    - `T2 RMSE = 8.37 °C`
    - `final_tds_error = -0.651 %-pt`
    - `model T2 @ 0 / 5 / 10 / 15 s = 23.3 / 28.1 / 78.9 / 81.4 °C`
  - `4:12`：
    - `T1 RMSE = 6.94 °C`
    - `T2 RMSE = 8.29 °C`
  - `4:11`：
    - `T1 RMSE = 3.13 °C`
    - `T2 RMSE = 8.94 °C`
- 判讀：
  - `T2` 若量測於濾紙錐形頂點，startup 時不應直接等於熱 bulk outflow；冷 apex 初始條件是必要的物理修正
  - 只改初始條件還不夠，還需要 startup apex hold-up；把 `gate_h` 納入 apex 等效熱容後，`4:20 T2 RMSE` 由 `12.63 °C` 進一步降到 `8.37 °C`
  - `4:12` 也同步改善，表示這不是單一 case 的調參
  - `4:11` 仍比上一輪 semantic-only 修正更差，顯示目前 closure 對「快速熱啟動」regime 還不夠好；下一步應檢查 apex local wall contact / preheated tip history，而不是回頭亂調 extraction

## 2026-04-20 20:03:12 +0800

- 改動：
  - 將 `core.py` 的 bulk thermal node 初始值由預混 `T_shock` 改為 `T_amb`
  - 保持 `T_effluent`、`T_dripper` 與 server observation 都從室溫開始
  - 讓第一注注水由 ODE 自己把 bulk / apex / dripper 從室溫加熱起來
- 實驗：
  - `uv run python -m unittest tests.test_measured_case_registry tests.test_core_mass_balance.CoreMassBalanceTests.test_simulate_brew_reports_effluent_temperature_series tests.test_core_mass_balance.CoreMassBalanceTests.test_effluent_temperature_starts_from_cold_apex_state tests.test_core_mass_balance.CoreMassBalanceTests.test_bulk_temperature_starts_from_ambient_state`
  - `uv run python -m compileall pour_over`
  - 重生 `data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile_comparison.png`
  - 重新評估三案 thermal 指標：
    - `data/kinu_28_light/4:20`
    - `data/kinu_29_light/4:12`
    - `data/kinu_29_light/4:11`
- 結果：
  - ambient-start regression：`PASS`
  - `4:20`：
    - `T1 RMSE = 5.79 °C`
    - `T2 RMSE = 8.15 °C`
    - `final_tds_error = -0.652 %-pt`
    - `model T2 @ 0 / 5 / 10 / 15 s = 23.3 / 26.3 / 77.8 / 80.8 °C`
  - `4:12`：
    - `T1 RMSE = 7.11 °C`
    - `T2 RMSE = 8.06 °C`
  - `4:11`：
    - `T1 RMSE = 3.26 °C`
    - `T2 RMSE = 9.16 °C`
- 判讀：
  - 這個修正讓模型熱敘事更一致：濾杯、下壺、咖啡粉與 bulk 液相都從室溫開始加熱
  - `4:20` 與 `4:12` 的 `T2 RMSE` 再小幅下降，且 `t=0/5 s` 的 apex 溫度更符合「從室溫被第一注拉升」的物理圖像
  - `4:11` 仍未改善，表示剩餘缺口不是單純初始條件，而更像是 fast-start regime 的 apex local contact history

## 2026-04-23 02:39:32 +0800

- 改動：
  - 在 `evaluate_measured_thermal_profile()` 內新增正式規則：`T2` 的主驗證窗從 `10 s` 開始
  - `t < 10 s` 的 `T2` 量測點保留在圖上，但不再進 `outflow_temp_fit_mask`
  - 本輪不改主熱方程、不改 extraction 參數，只修 validation semantics
- 實驗：
  - `uv run python -m unittest tests.test_measured_case_registry tests.test_core_mass_balance.CoreMassBalanceTests.test_simulate_brew_reports_effluent_temperature_series tests.test_core_mass_balance.CoreMassBalanceTests.test_effluent_temperature_starts_from_cold_apex_state tests.test_core_mass_balance.CoreMassBalanceTests.test_bulk_temperature_starts_from_ambient_state`
  - `uv run python -m compileall pour_over`
  - 重新評估三案 thermal 指標：
    - `data/kinu_28_light/4:20`
    - `data/kinu_29_light/4:12`
    - `data/kinu_29_light/4:11`
- 結果：
  - held-out rule regression：`PASS`
  - `4:20`：`T1 RMSE = 5.79 °C`、`T2 RMSE = 8.33 °C`
  - `4:12`：`T1 RMSE = 7.11 °C`、`T2 RMSE = 7.34 °C`
  - `4:11`：`T1 RMSE = 3.26 °C`、`T2 RMSE = 4.83 °C`
  - `used T2 points`：`4:20 = 23`、`4:12 = 25`、`4:11 = 24`
- 判讀：
  - 這次 `T2 RMSE` 的改善應解讀為 validation policy 更合理，而不是熱模型本體突然變好
  - 拿掉 `t < 10 s` 的探針啟動期後，`4:11` 的 `T2 RMSE` 由 `9.16 °C` 明顯降到 `4.83 °C`，支持使用者判讀：前幾秒確實混入溫度計自身響應
  - `4:20` 在新驗證窗下仍維持 `8.33 °C`，表示真正剩餘的主缺口集中在 `10–20 s` 的 apex thermal history，而不是 `5 s` 的 sensor lag

## 2026-04-23 02:45:21 +0800

- 改動：
  - 在 `evaluate_measured_thermal_profile()` 內新增 `T1` 感測器啟動規則：第一滴咖啡液流出時間 + `5 s` 才開始進 `server_temp_fit_mask`
  - 規則由模型端根據 `V_out(t)` 自動計算，不依賴 CSV 是否手動標對
  - 本輪不改主熱方程，只修 `T1` validation semantics
- 實驗：
  - `uv run python -m unittest tests.test_measured_case_registry tests.test_core_mass_balance.CoreMassBalanceTests.test_simulate_brew_reports_effluent_temperature_series tests.test_core_mass_balance.CoreMassBalanceTests.test_effluent_temperature_starts_from_cold_apex_state tests.test_core_mass_balance.CoreMassBalanceTests.test_bulk_temperature_starts_from_ambient_state`
  - `uv run python -m compileall pour_over`
  - 重新評估三案 thermal 指標：
    - `data/kinu_28_light/4:20`
    - `data/kinu_29_light/4:12`
    - `data/kinu_29_light/4:11`
- 結果：
  - T1 startup regression：`PASS`
  - `4:20`：`T1 RMSE = 5.79 °C`、`T2 RMSE = 8.33 °C`、`used T1/T2 = 23/23`
  - `4:12`：`T1 RMSE = 7.11 °C`、`T2 RMSE = 7.34 °C`、`used T1/T2 = 25/25`
  - `4:11`：`T1 RMSE = 3.26 °C`、`T2 RMSE = 4.83 °C`、`used T1/T2 = 14/24`
- 判讀：
  - `4:20` 與 `4:12` 的 `T1 RMSE` 幾乎不變，表示這兩筆 CSV 原本的手動 held-out 已經相當保守
  - `4:11` 的 `used T1 points` 明顯減少，說明壺端溫度計啟動期原本確實混在主驗證窗內
  - 這次仍只是 validation policy 更合理，不應解讀成 server heat model 已經被解決
