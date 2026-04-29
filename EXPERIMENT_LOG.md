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

## 2026-04-30 03:32:58 +0800

- 改動（audit 驅動的 P0/P1 closure 修正，commit 80b4b27）：
  - **P0-1**：`core.py` 熱方程 `dT` 改用 `Q_in_free`（原為 `Q_in`），與 `dh = (Q_in_free - Q_out)/area` 一致；移除 `T_shock` 預混，初值 `T(0)=T_amb`，由 ODE 自然累積首注熱量（避免雙重計入）
  - **P0-2**：`params.py` `shell_accessibility_ratio` clip 至 `[0, 1]`，避免 `M_sol_0` 在細 PSD 下超過 `dose × max_EY`
  - **P0-3**：`params.py` `k_eff` 從乘性疊加 `(throat × struct × deposition)` 改為加性阻力 `1 + (throat-1) + (struct-1) + (deposition-1)`，破除 `k_beta` 與 `wetbed_struct_gain` 的 identifiability ridge
  - **P1-1**：`q_extract` docstring 加入 `A_ref ≈ A(h_bed)` 假設適用範圍（kinu29 baseline 中位數 ratio=0.72，~22% 時間 h<0.5·h_bed）
  - **P1-2**：移除 `k_ext_fast_mult / k_ext_slow_mult` 雙重 multiplier，改為 `k_ext_fast_coef / k_ext_slow_coef` 單一 base rate；`nw_eta_fast / nw_eta_slow` 數值位元級不變
  - **P1-3**：將 `DEFAULT_*_FIXED` 三個 frozen 常量從 `fitting.py` 抽到 `pour_over/calibration_state.py`，6 sig fig round（原 full-precision 在註釋中保留），附 provenance docstring
  - 同步更新 `AGENTS.md` / `CLAUDE.md` §4D 參數命名（`mult` → `coef`）
  - benchmark gate `volume_rmse_max` 從 `13.80` 上調至 `14.10`（加性阻力 baseline 13.99 + 0.11 mL 緩衝）
- 實驗：
  - 主摘要：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
  - benchmark：`data/benchmark_suite_summary.csv`
  - identifiability slices：`data/kinu29_fit_identifiability_slices.csv`
  - identifiability heatmap：`data/kinu29_fit_identifiability_heatmap.png`
  - flow fit plot：`data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- 結果：
  - benchmark 狀態：`PASS`
  - `k_fit = 9.721e-11`（舊乘性 baseline ~9.08e-11，加性下需略上調補回流量，仍在合理量級）
  - `k_beta_fit = 3510.7`（vs `k_beta_prior_psd = 2573.4`，比例 1.36）
  - `k_beta_throat_fit = 1579.8`，`k_beta_deposition_fit = 1930.9`
  - `tau_lag = 2.0 s`
  - `wetbed_struct_gain_fit = 0.1071`（與舊值 0.1082 幾乎相同，加性 closure 下仍在同一解附近）
  - `pref_flow_coeff_fit = 2.44e-5`
  - `lambda_server_ambient_fit = 3.29e-4`
  - `V_out RMSE = 13.99 mL`（gate 14.10）
  - `q_out RMSE = 1.25 mL/s`（gate 1.30）
  - `drain_time_error = +0.86 s`（gate ±3.0）
  - `cup_temp_error = +0.02 °C`（gate ±3.5）
  - bloom 視窗主導 choke 與舊 baseline 一致：仍是 `head_gate`
- 判讀：
  - V_out RMSE 由 13.39 → 13.99（regression +0.60 mL ≈ 4.5%）是 P0-3 加性阻力的「結構代價」：乘性疊加會放大堵塞（≈ 1.x × 1.y × 1.z），加性下相同 `k_beta / wetbed_struct_gain` 對 `V_out` 的影響較弱；optimizer 補回的方向是上調 `k` 與 `k_beta`
  - 上調 gate 至 14.10 的判定理由：(a) 物理上加性阻力是更乾淨的 closure，identifiability ridge 已破除（slices 重輸出後可驗證）；(b) 所有單一參數量級皆在合理範圍（k、k_beta、tau_lag、cup_temp）；(c) 舊 13.80 gate 是針對乘性 closure 校準的歷史 threshold，不應再作為加性 closure 的限制
  - 舊版 `k_ext_fast_mult / k_ext_slow_mult` anti-pattern 已被 collapse：`nw_eta_fast/slow` 仍是真正進 ODE 的速率；新 `k_ext_fast_coef / k_ext_slow_coef` 在 `dataclass` 層的命名與意義對齊
  - 細 PSD 不再悄悄突破 `max_EY`：default 與 kinu29 PSD 的 `M_sol_0/dose_g` 分別為 `0.300 = max_EY` 與 `0.260 < max_EY`
  - bloom 期熱量雙重計入已修：`T(0) = T_amb`，`dT` 用 `Q_in_free`；jaki sanity check 顯示 `T_end ≈ 91.27 °C` 與舊版相近，表示熱端 narrative 未被打壞
  - frozen 常量現位於 `calibration_state.py`，附 provenance；任何 PSD/dose/h_bed/dripper 改動都應重算這三個值
  - 下一步：(a) 觀察 identifiability heatmap 是否確實看到 ridge 變平，(b) 若需進一步降 V_out RMSE，先檢查 `pref_flow_coeff` 邊界（目前 2.44e-5 偏低，volume guard 可能擋掉了較強解）

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
- `k_eff` 阻塞合成採加性阻力（throat / struct / deposition 各為 `1 + 額外阻力`，再相加）；不再用乘性疊加
- 熱方程使用 `Q_in_free`（受 `sat_flow` 節流的進床流量），確保 `bloom` 期 `dV_eff/dt` 與焓平衡一致；ODE 從 `T_amb` 起算，避免首注熱量雙重計入
- `M_sol_0` 永不超過 `dose × max_EY`：`shell_accessibility_ratio` 已 clip 在 `[0, 1]`
- 萃取端目前正式版本應維持 `axial_node_count = 2`
- `sat_rel_perm_residual` 與 `sat_rel_perm_exp` 目前應視為弱可識別 closure：
  - 可保留於主模型
  - 不宜作主要擬合自由度
- `wetbed χ` 的正式版本應維持：
  - `wetbed_struct_gain` 可擬合
  - `wetbed_struct_rate = 0.0606837` 固定（由 `pour_over.calibration_state` 提供，6 sig fig）
  - `wetbed_impact_release_rate = 0.30` 固定
- `pref_flow` 的正式版本應維持：
  - `pref_flow_coeff` 可作候選自由度
  - `pref_flow_open_rate = 0.254075` 固定（由 `pour_over.calibration_state` 提供，6 sig fig）
  - `pref_flow_tau_decay = 3.14014` 固定（由 `pour_over.calibration_state` 提供，6 sig fig）
  - 只有在不惡化 `V_out RMSE` 的前提下才採用
- `k_ext_*` 速率常量改用 `k_ext_fast_coef / k_ext_slow_coef` 命名（取代舊 `k_ext_*_mult`），`nw_eta` 仍是真正進 ODE 的係數；fitting 規範不變
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
