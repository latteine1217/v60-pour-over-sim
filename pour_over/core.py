"""
V60 手沖咖啡 ODE 模擬引擎
==========================
此模組為核心數值積分引擎，實作 V60 8D ODE 系統的求解與結果後處理。

核心狀態向量：
    state = [h, V_out, V_poured, C_fast, M_fast, C_slow, M_slow, T]

主要函式：
    simulate_brew()  — 數值積分 ODE，回傳完整時序結果 dict
    print_summary()  — 格式化輸出沖煮摘要至 stdout
"""

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d

from .params import V60Params, PourProtocol, RHO, G, H_MIN, R_GAS


def simulate_brew(
    params: V60Params,
    protocol: PourProtocol,
    t_end: float = 300.0,
    n_eval: int = 3000,
) -> dict:
    """
    數值積分 V60 8D ODE 系統（v7 多組分萃取）。

    What: 狀態向量 [h, V_out, V_poured, C_fast, M_fast, C_slow, M_slow, T]
          h        → 水位 [m]
          V_out    → 累積出液量 [m³]，動態計算 k_eff
          V_poured → 累積注水量 [m³]，計算吸水飽和度 sat
          C_fast   → Fast 組分粉層濃度 [g/L]（酸/甜）
          M_fast   → Fast 組分剩餘固相質量 [g]
          C_slow   → Slow 組分粉層濃度 [g/L]（苦/澀）
          M_slow   → Slow 組分剩餘固相質量 [g]
          T        → 水溫 [K]，驅動 μ(T)、k_ext_i(T)、C_sat_i(T)

    Why:  八維狀態讓流體力學、多組分化學萃取、熱力學三者完全耦合。
    """
    def rhs(t, state):
        h, V_out, V_poured, C_fast, M_fast, C_slow, M_slow, T = state
        h      = max(h, H_MIN)
        C_fast = max(C_fast, 0.0)
        M_fast = max(M_fast, 0.0)
        C_slow = max(C_slow, 0.0)
        M_slow = max(M_slow, 0.0)
        T      = float(np.clip(T, params.T_amb, params.T_brew + 5.0))

        sat     = params.saturation(V_poured)   # 必須先算 sat，k_eff 需要它
        k_val   = params.k_eff(V_out, sat)      # [修正 8] 溶脹修正需要 sat
        psi_val = params.psi_eff(V_out)

        Q_in  = protocol.pour_rate(t)
        Q_ext = params.q_extract(h, k_val, T, t)   # t 傳入修正 [14] CO₂ 背壓
        Q_bp  = params.q_bypass(h, psi_val, T)
        Q_out = Q_ext + Q_bp
        area  = params.area(h)

        Q_in_free = Q_in * sat
        dh = (Q_in_free - Q_out) / area
        if h <= H_MIN and dh < 0:
            dh = 0.0

        # 修正 [7][11] 多組分萃取（Fast + Slow，Arrhenius 動力學 + 可及性冪次律）
        # 可及性修正：C_eff = C_sat(T) × (M/M₀)^β
        # β=1: 線性（原模型）；β>1: 超線性，末期 C_eff 更快趨零（細胞壁困住深層溶質）
        # 等效於：速率 ∝ k_ext × M^β / M₀^β × (C_sat - C)，β=1.5 時更快收斂
        β = params.beta_access
        if params.M_fast_0 > 0 and M_fast > 0:
            acc_fast = (M_fast / params.M_fast_0) ** β
            C_eff_fast = params.C_sat_fast_T(T) * acc_fast
        else:
            C_eff_fast = 0.0
        dis_fast = params.k_ext_fast_T(T) * max(0.0, C_eff_fast - C_fast)

        if params.M_slow_0 > 0 and M_slow > 0:
            acc_slow = (M_slow / params.M_slow_0) ** β
            C_eff_slow = params.C_sat_slow_T(T) * acc_slow
        else:
            C_eff_slow = 0.0
        dis_slow = params.k_ext_slow_T(T) * max(0.0, C_eff_slow - C_slow)

        # 粉床孔隙 CSTR 濃度更新（修正 [5][7][11] 組合）
        # dC/dt = (dis - Q_ext × C) / V_liq
        # 物理解釋：Q_ext 是「真正穿過粉層」的 Darcy 流速（≈1-3 mL/s），
        #           NOT 注水速率 Q_in（≈7.5 mL/s）。兩者差 4-7 倍，代表大部分注水
        #           先積在自由液面（產生靜水壓），再靠 Darcy 滲透進粉床孔隙。
        # 多段注水效益的捕捉機制：
        #   注水間隙 → Q_ext 排走高濃縮液 → C 下降
        #   下一段注水 → h 升 → Q_ext 增大 → 驅動力(C_eff-C)大 → 更多溶解
        # 此 CSTR 模型忽略粉床縱向濃度梯度（PFR 效應），稍低估多段注水效益；
        # 完整修正需要 PDE 空間模型（未來工作）。
        V_liq = params.V_liquid
        dC_fast = (dis_fast - Q_ext * C_fast) / V_liq
        dM_fast = -dis_fast * 1e3
        dC_slow = (dis_slow - Q_ext * C_slow) / V_liq
        dM_slow = -dis_slow * 1e3

        # 熱動方程（修正 [6]）—— CSTR 焓平衡推導
        # 完整焓平衡：d(V_eff·T)/dt = Q_in·T_brew - Q_out·T - λ·V_eff·(T-T_amb)
        # 展開左側：V_eff·dT/dt + T·dV_eff/dt = Q_in·T_brew - Q_out·T - λ·V_eff·(T-T_amb)
        # 代入 dV_eff/dt = Q_in - Q_out（質量守恆）：
        # → V_eff·dT/dt = Q_in·T_brew - Q_out·T - T·(Q_in-Q_out) - λ·V_eff·(T-T_amb)
        #               = Q_in·(T_brew-T) - λ·V_eff·(T-T_amb)
        # 結論：dm/dt 項在展開後「自然相消」，現有簡化公式完全等價於完整焓平衡。
        V_liq_t = max(params.phi * (np.pi / 3) * params._tan2 * h**3,
                      params.V_liquid * 0.05)
        # 修正 Bug [熱慣性]：咖啡粉固體熱容為常駐項，不隨 sat 消失。
        # 舊版 V_equiv_coffee × (1-sat) 在 sat→1 時錯誤移除粉體熱容，
        # 導致第一注完成瞬間分母縮小，引發虛假溫度跳變並低估後段降溫效果。
        # 修正：V_equiv_coffee 無論 sat 為何，始終計入熱動方程分母。
        V_eff_T = V_liq_t + params.V_equiv_coffee
        dT = (Q_in / V_eff_T) * (params.T_brew - T) \
             - params.lambda_cool * (T - params.T_amb)

        return [dh, Q_out, Q_in, dC_fast, dM_fast, dC_slow, dM_slow, dT]

    t_eval = np.linspace(0, t_end, n_eval)
    # 初始熱衝擊溫度
    V_bloom   = protocol.pours[0][1] * 1e-6
    m_w_bloom = V_bloom * RHO
    m_coffee  = params.dose_g * 1e-3
    CP_W      = 4180.0
    T_shock   = (m_w_bloom * CP_W * params.T_brew + m_coffee * params.Cp_coffee * params.T_amb) \
                / (m_w_bloom * CP_W + m_coffee * params.Cp_coffee)

    sol = solve_ivp(
        rhs,
        t_span=(0, t_end),
        y0=[H_MIN, 0.0, 0.0, 0.0, params.M_fast_0, 0.0, params.M_slow_0, T_shock],
        t_eval=t_eval,
        # RK45 + 加密步長（max_step=0.5）
        # 選用 RK45 而非 LSODA/Radau 的理由：
        # - 模型含 max()、clamp 等非光滑項，LSODA/BDF 的雅可比估算容易失敗
        # - h_cap 附近 sigmoid 梯度 ~1/(h_cap×0.25)=800 m⁻¹，以 max_step=0.5s 足以解析
        # - 批量靈敏度掃描（225 runs）需要快速非剛性求解器
        method="RK45",
        rtol=1e-6,
        atol=1e-8,
        max_step=0.5,  # 從 1.0 縮短至 0.5，改善 sigmoid 截止區域的數值精度
    )

    t        = sol.t
    h        = np.maximum(sol.y[0], 0.0)
    V_out    = sol.y[1]
    V_poured = sol.y[2]
    C_fast   = np.maximum(sol.y[3], 0.0)   # [g/L] Fast 組分粉層濃度
    M_fast   = np.maximum(sol.y[4], 0.0)   # [g]   Fast 組分剩餘固相
    C_slow   = np.maximum(sol.y[5], 0.0)   # [g/L] Slow 組分粉層濃度
    M_slow   = np.maximum(sol.y[6], 0.0)   # [g]   Slow 組分剩餘固相
    T_K      = np.clip(sol.y[7], params.T_amb, params.T_brew + 5.0)  # [K]
    M_sol    = M_fast + M_slow             # 向後相容：總剩餘固相

    sat      = np.vectorize(params.saturation)(V_poured)
    q_in_raw = np.array([protocol.pour_rate(ti) for ti in t])
    q_in_eff = q_in_raw * sat

    # 重新計算各流量分量（用於繪圖，帶入衰減後的 k、Ψ 與溫度）
    k_vals   = params.k_eff(V_out, sat)   # [修正 8] 後處理時同步加入溶脹修正
    psi_vals = params.psi_eff(V_out)
    q_ext  = params.q_extract(h, k_vals, T_K)
    q_bp   = params.q_bypass(h, psi_vals, T_K)
    q_out  = q_ext + q_bp

    dt           = np.diff(t, prepend=t[0])
    v_in_ml      = np.cumsum(dt * q_in_raw) * 1e6
    v_in_eff_ml  = np.cumsum(dt * q_in_eff) * 1e6
    v_out_ml     = V_out * 1e6
    v_extract_ml = np.cumsum(dt * q_ext)  * 1e6

    _q_out_safe  = np.where(q_out > 1e-12, q_out, 1.0)  # 防止零除（h < h_cap 時 q_out=0）
    bypass_ratio = np.where(q_out > 1e-12, q_bp / _q_out_safe, 0.0)

    # ── TDS 後處理（多組分）──────────────────────────────────────────────────
    C_bed = C_fast + C_slow    # 總粉層濃度（用於向後相容 plot_tds/compare_corrections）

    # 各組分有效 C_sat（後處理向量化）
    _mf_safe = params.M_fast_0 if params.M_fast_0 > 0 else 1e-10
    _ms_safe = params.M_slow_0 if params.M_slow_0 > 0 else 1e-10
    C_sat_fast_arr = params.C_sat_fast * (1.0 + params.alpha_C_fast * (T_K - params.T_ref))
    C_sat_slow_arr = params.C_sat_slow * (1.0 + params.alpha_C_slow * (T_K - params.T_ref))
    C_sat_eff = (C_sat_fast_arr / _mf_safe * M_fast * float(params.M_fast_0 > 0)
               + C_sat_slow_arr / _ms_safe * M_slow * float(params.M_slow_0 > 0))

    # 下壺瞬時濃度（旁路稀釋後）
    C_out = np.where(q_out > 1e-12, q_ext * C_bed / _q_out_safe, 0.0)

    # 累積萃取質量（各組分 + 總計）
    M_fast_ext_g  = np.cumsum(dt * q_ext * C_fast) * 1e3
    M_slow_ext_g  = np.cumsum(dt * q_ext * C_slow) * 1e3
    M_extracted_g = M_fast_ext_g + M_slow_ext_g

    # 累積 TDS
    v_out_L = np.maximum(v_out_ml * 1e-3, 1e-9)
    TDS_gl       = M_extracted_g / v_out_L
    TDS_fast_gl  = M_fast_ext_g  / v_out_L
    TDS_slow_gl  = M_slow_ext_g  / v_out_L

    # EY（入壺）
    _dose_safe = params.dose_g if params.dose_g > 0 else 1.0
    _ey_scale  = 100.0 / _dose_safe if params.dose_g > 0 else 0.0
    EY_cup_pct      = M_extracted_g * _ey_scale
    EY_fast_cup_pct = M_fast_ext_g  * _ey_scale
    EY_slow_cup_pct = M_slow_ext_g  * _ey_scale

    # EY（已溶出）
    M_dissolved_g    = params.M_sol_0 - M_sol
    EY_dissolved_pct = M_dissolved_g * _ey_scale
    EY_pct           = EY_cup_pct

    # 最終沖煮時間（最後一注結束後，h 降至毛細管門檻 + 1mm 的時刻）
    # h_cap > 0 時：水位不會低於 h_cap，門檻調整為 h_cap + 1mm
    # h_cap = 0 時：使用舊版 2mm 門檻（向後相容）
    t_last_pour = protocol.last_pour_end()
    mask_after  = t > t_last_pour
    drain_threshold = max(0.002, params.h_cap + 0.001)  # [m]
    drain_time  = t_end
    if mask_after.any():
        below_thresh = np.where(mask_after & (h < drain_threshold))[0]
        if below_thresh.size:
            drain_time = t[below_thresh[0]]

    return dict(
        t            = t,
        h_mm         = h * 1e3,
        q_in_mlps    = q_in_raw * 1e6,
        q_in_eff_mlps= q_in_eff * 1e6,
        q_ext_mlps   = q_ext    * 1e6,
        q_bp_mlps    = q_bp     * 1e6,
        q_out_mlps   = q_out    * 1e6,
        k_vals       = k_vals,
        psi_vals     = psi_vals,
        v_in_ml      = v_in_ml,
        v_in_eff_ml  = v_in_eff_ml,
        v_out_ml     = v_out_ml,
        v_extract_ml = v_extract_ml,
        bypass_ratio = bypass_ratio,
        sat          = sat,
        drain_time   = drain_time,
        # TDS + 固相耗盡（v7 多組分）
        C_bed_gl         = C_bed,
        C_fast_gl        = C_fast,
        C_slow_gl        = C_slow,
        C_sat_eff_gl     = C_sat_eff,
        C_out_gl         = C_out,
        M_sol_g          = M_sol,
        M_fast_g         = M_fast,
        M_slow_g         = M_slow,
        M_extracted_g    = M_extracted_g,
        M_dissolved_g    = M_dissolved_g,
        TDS_gl           = TDS_gl,
        TDS_fast_gl      = TDS_fast_gl,
        TDS_slow_gl      = TDS_slow_gl,
        EY_pct           = EY_pct,
        EY_cup_pct       = EY_cup_pct,
        EY_fast_cup_pct  = EY_fast_cup_pct,
        EY_slow_cup_pct  = EY_slow_cup_pct,
        EY_dissolved_pct = EY_dissolved_pct,
        # 熱力學（修正 [6]）
        T_K              = T_K,
        T_C              = T_K - 273.15,
    )


def print_summary(results: dict, label: str = "") -> None:
    """
    What: 格式化輸出 simulate_brew() 結果摘要至 stdout。
    Why:  提供一致且可掃描的診斷輸出，便於快速評估沖煮品質。
    """
    tag = f"  [{label}]" if label else ""
    v_out = results["v_out_ml"][-1]
    v_ext = results["v_extract_ml"][-1]
    v_bp  = v_out - v_ext

    print("=" * 54)
    print(f"  V60 手沖模擬摘要{tag}")
    print("=" * 54)
    print(f"  沖煮完成時間   : {results['drain_time']:.1f} s")
    print(f"  總注水量       : {results['v_in_ml'][-1]:.1f} mL")
    print(f"  有效水量（扣吸）: {results['v_in_eff_ml'][-1]:.1f} mL")
    print(f"  總出液量       : {v_out:.1f} mL")
    if v_out > 0:
        print(f"    ├ 萃取液     : {v_ext:.1f} mL  ({v_ext/v_out*100:.1f}%)")
        print(f"    └ 旁路液     : {v_bp:.1f} mL  ({v_bp/v_out*100:.1f}%)")
    print(f"  峰值水位       : {results['h_mm'].max():.1f} mm")
    print(f"  峰值出水速度   : {results['q_out_mlps'].max():.2f} mL/s")
    k0  = results["k_vals"][0]
    k_f = results["k_vals"][-1]
    print(f"  k 衰減比       : {k_f/k0:.2f}  ({k0:.2e} → {k_f:.2e} m²)")
    print(f"  最終 TDS       : {results['TDS_gl'][-1]:.2f} g/L  ({results['TDS_gl'][-1]/10:.2f}%)")
    print(f"  EY（入壺）     : {results['EY_cup_pct'][-1]:.1f}%")
    print(f"  EY（已溶出）   : {results['EY_dissolved_pct'][-1]:.1f}%")
    print(f"  └ 差值（留杯） : {results['EY_dissolved_pct'][-1]-results['EY_cup_pct'][-1]:.1f}%")
    print(f"  粉層峰值濃度   : {results['C_bed_gl'].max():.1f} g/L")
    print(f"  固相剩餘溶質   : {results['M_sol_g'][-1]:.2f} g / {results['M_sol_g'][0]:.2f} g")
    if "EY_fast_cup_pct" in results:
        ey_fast = results["EY_fast_cup_pct"][-1]
        ey_slow = results["EY_slow_cup_pct"][-1]
        total   = ey_fast + ey_slow
        ratio   = ey_fast / total * 100 if total > 0 else 50.0
        print(f"  風味分解（入壺）:")
        print(f"    ├ Fast（酸/甜）: EY={ey_fast:.1f}%  TDS={results['TDS_fast_gl'][-1]:.1f} g/L")
        print(f"    └ Slow（苦/澀）: EY={ey_slow:.1f}%  TDS={results['TDS_slow_gl'][-1]:.1f} g/L")
        print(f"    風味平衡 Fast% = {ratio:.0f}%  （越高越明亮/酸，越低越苦）")
    if "T_C" in results:
        T_start = results["T_C"][0]
        T_end   = results["T_C"][-1]
        print(f"  水溫變化       : {T_start:.1f}°C → {T_end:.1f}°C  (Δ{T_start-T_end:.1f}°C)")
    print("=" * 54)
