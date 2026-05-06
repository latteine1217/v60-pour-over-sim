# AGENTS.md

本檔提供 agent 進入本專案時的最小完整規範。目標不是堆疊看似合理的 closure，而是維持一套可重現、可驗證、物理上可辯護的 reduced-order V60 simulator。

---

## 1. 專案目標

你應以物理學家與數值建模工程師的角色工作。

本專案是：
- `reduced-order porous-media model`
- `bin-resolved extraction model`
- `multi-node thermal model`

本專案不是：
- full CFD
- full multiphase PDE solver
- 只追求低 loss 的黑箱擬合器

任何新增機制都必須先回答：
- `What:` 它代表什麼物理量？
- `Why:` 現有機制為何不足？

---

## 2. 核心原則

1. 物理合理性優先於較低 loss。
2. 一切以物理正確性優先，不得為了擬合數據而引入缺乏物理意義的調參或 closure。
3. measured data 優先於 proxy。
4. 可直接量測的量不得拿去吸收模型誤差。
5. 維持單一主模型，不保留平行舊分支。
6. `viz.py`、`index.html`、`README.md` 必須與主模型同步。
7. 預設沖煮上限為 `180 s`，除非使用者另有要求。
8. 若新機制只是補償舊錯誤，應重寫 closure，不要再疊 multiplier。

---

## 3. 模型邊界

### 3.1 水力學

允許：
- Darcy 型床層流動
- capillary support / cutoff 的 reduced-order closure
- 顯式 bypass 路徑
- throat clogging 與 deposition clogging 分離
- 注水衝擊造成的短時孔喉 relief
- 必要時有限度的 preferential-flow closure

不允許：
- 把明顯結構重排誤差直接塞進單一 `k`
- 用 bypass 解釋床內堵塞
- 用不可觀測狀態大量補償主方程錯誤

### 3.2 萃取

允許：
- Noyes-Whitney 型 `A_i * D / L_i`
- measured PSD bin-resolved `A_i, L_i, M_i`
- outer-shell accessibility

不允許：
- 有 measured PSD 後退回 fractal PSD 作主敘事
- 只靠 aggregate `fast/slow` closure 謊稱已用 measured PSD

### 3.3 熱模型

允許：
- slurry node
- dripper node
- server / cup observation or mixing layer
- 自然對流與硬體熱容

不允許：
- 把硬體熱容當萬用吸熱黑箱
- 杯溫不對時優先亂調水力或萃取參數

---

## 4. 參數分級

### A. 可直接量測，必須固定

- `dose_g`
- `h_bed`
- `T_brew`
- `T_amb`
- `V_in(t)`
- `V_out(t)`
- dripper / server 質量與材質
- measured PSD bins

### B. 可由量測計算，先算再固定

- `rho_bulk_dry_g_ml`
- `D10 / D50 / D90`
- fines fraction
- vessel equivalent heat capacity
- dripper equivalent heat capacity

### C. 允許少量標定的 closure 參數

- `k`
- `k_beta`
- `tau_lag`
- `h_cap`
- 必要時 `h_gas_0`
- 已被 identifiability 支持的少量附加 closure 參數

### D. 原則上不要先動的次級參數

- `k_ext_coef`
- `k_ext_fast_mult`
- `k_ext_slow_mult`
- `Ea_fast / Ea_slow`
- 已有實測 shape data 後仍想再調的 shape multiplier

---

## 5. PSD 規範

若有 measured PSD：
- 必須優先使用 `psd_bins_csv_path`
- `D10_measured_m` 應由 PSD summary 給定
- 不得再以 idealized fractal PSD 當主流程

PSD 優先直接進主方程的資訊：
- `volume_fraction`
- `num_fraction`
- `surface_to_volume`
- `shell_accessibility`
- `diameter_mid`
- `aspect_ratio`
- `roundness`

PSD 只允許作 prior / regularization 的資訊：
- histogram 摘要
- aggregate span 指標

堵塞至少拆為：
- `throat_clogging`：偏 number-based fines
- `deposition_clogging`：偏 volume-based fines

不得把所有堵塞效應重新塞回單一不可解釋的 `k_beta`。

---

## 6. 擬合規範

主擬合目標：
- `V_out(t)`
- interval mean `q_out`
- `drain_time`
- `cup temperature`

禁止事項：
- 一次同時亂動水力、萃取、熱三套參數
- 用熱容吸收水力誤差
- 用萃取參數吸收 `V_out(t)` 誤差
- 不得以純粹降低 loss 為理由保留缺乏物理意義的擬合參數

每次 fitting 或重要改模後至少回報：
- `k_fit`
- `k_beta_fit`
- `beta_throat`
- `beta_deposition`
- `tau_lag`
- `V_out RMSE`
- `q_out RMSE`
- `drain_time_error`
- `cup_temp_error`
- 這次改善來自哪條物理線
- 是否引入更不合理的參數

若出現以下情況，先檢查模型，不要繼續調參：
- `k` 明顯偏離合理量級
- `k_beta` 遠離 PSD prior 太多
- 需要極端 `tau_lag`
- 需要不合理熱容

---

## 7. 視覺化與展示

### `viz.py`

- `plot_results()` 與 `plot_tds()` 必須能直接吃最新模型結果
- 所有 `compare_*` 以最新 calibrated baseline 為中心
- 不得繼續展示舊 baseline

### `index.html`

首頁優先展示：
- calibrated flow-fit panel
- calibrated flow diagnostics
- calibrated extraction quality

若圖檔或敘事更新，必須同步修改。

### `README.md`

README 必須與首頁使用同一套：
- 主模型
- 圖檔
- calibration reference

---

## 8. 文件與輸出

### 語言

- 平時回覆與程式註解：中文
- 作圖標題與 label：英文

### 註解規範

重要函式或 closure 前應回答：
- `What`
- `Why`

不要寫逐行解說。

### 輸出格式

重要技術輸出應可直接當報告閱讀：
- 使用 `=== Section ===` 或清楚分段
- 先給可掃描 summary，再附細節

### 實驗紀錄

只要執行了會產生新結論的：
- 實驗
- 掃描
- fitting
- benchmark
- identifiability 分析

就必須同步更新 `EXPERIMENT_LOG.md`。

每筆至少包含：
- 時間
- 改動內容
- 實驗結果
- 判讀或結論
- artifact 路徑（若有）

時間應優先使用 artifact 檔案修改時間。若新實驗推翻舊結論，不得只改程式不改紀錄。

---

## 9. 工程規範

- 優先使用 `uv run python`、`rg`、`fd`
- 手動修改檔案時使用 patch
- 避免 ad-hoc 腳本整檔覆寫，除非必要
- 超過三層巢狀迴圈時，先質疑演算法設計
- 改動主模型時，至少同步檢查 `viz.py`
- 視情況同步 `index.html`、`README.md`

---

## 10. 最低驗收

每次重要改動後至少完成：

1. `uv run python -m compileall pour_over`
2. 一次 calibrated fit
3. 至少輸出：
   - calibrated fit comparison
   - calibrated flow diagnostics
   - calibrated extraction quality
4. 若改動 `viz.py`，需重跑相關 `compare_*`
5. 若改動展示敘事，需同步檢查：
   - `index.html`
   - `README.md`
6. 若有新結論，更新 `EXPERIMENT_LOG.md`

---

## 11. 目前默認展示基準

若無使用者另行指定，展示與比較優先使用：
- grinder：`Kinu 29`
- roast：`light`
- dose：`20 g`
- bed height：`5.3 cm`
- ambient：`23 degC`
- dripper：ceramic V60，`123.5 g`
- measured PSD：`data/kinu29_psd_bins.csv`

目前展示基準應優先從最新 calibrated artifact 讀取；若此基準更新，必須同步更新圖與文件。
