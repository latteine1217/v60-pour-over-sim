"""
calibration_state.py — frozen calibrated closure 常量

What:
    提供目前主模型在「kinu29 light、20 g、h_bed = 5.3 cm、measured PSD =
    data/kinu29_psd_bins.csv、ceramic V60 dripper」這組標準展示基準下，
    經由 ``fit_k_kbeta_from_flow_profile`` 同時開啟
    ``fit_wetbed_structure=True`` 與 ``fit_preferential_flow=True``
    擬合得到的 closure 參數。常量名稱沿用 ``DEFAULT_*_FIXED``，
    以維持 ``pour_over.fitting`` 對外的 API 不破壞。

來源 artifact:
    data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv
    （欄位 ``wetbed_struct_rate_fixed`` / ``pref_flow_open_rate_fixed`` /
    ``pref_flow_tau_decay_fixed``）。

Why:
    這些值在物理上與特定 PSD、dose、bed height、硬體配置綁定，
    並非通用常數；若直接把 15+ 位有效數字的 optimizer raw output
    黏進原始碼，會把擬合 noise 當成模型的一部分，
    並讓「何時必須重算」這件事對新使用者完全不可見。
    把它們集中在獨立檔案、保留 6 位有效數字並附原值與重算指引，
    才能在維持 reproducibility 的同時暴露其 frozen 屬性。

重算指引:
    當下列任一條件改變，必須在乾淨的 measured flow case 上重新跑
    ``fit_k_kbeta_from_flow_profile``（``fit_wetbed_structure=True``、
    ``fit_preferential_flow=True``），並把新值同步更新回此檔；
    不要在 ``fitting.py`` 內就地覆寫常量：

    1. measured PSD（``psd_bins_csv_path`` 或 bin 結構）
    2. dose（``dose_g``）
    3. bed height（``h_bed``）
    4. dripper 硬體（質量、材質、幾何）
    5. ambient / brew 溫度顯著偏離 23 / 92 degC
"""

# 6 位有效數字 round 後的值（原始 full precision 在註釋中保留）
DEFAULT_WETBED_STRUCT_RATE_FIXED = 0.0606837   # 原值 0.06068366147200567
DEFAULT_PREF_FLOW_OPEN_RATE_FIXED = 0.254075   # 原值 0.254074546131474
DEFAULT_PREF_FLOW_TAU_DECAY_FIXED = 3.14014    # 原值 3.1401416403754285
