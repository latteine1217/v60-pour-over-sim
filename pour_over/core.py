"""
V60 手沖咖啡 ODE 模擬引擎
==========================
此模組為核心數值積分引擎，實作 V60 動態 ODE 系統的求解與結果後處理。

核心狀態向量：
    state = [h, V_out, V_bed, V_poured, sat, extraction axial bins..., T, T_dripper, chi_struct, xi_pref]

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
    t_end: float = 180.0,
    n_eval: int = 3000,
    rtol: float = 1e-6,
    atol: float = 1e-8,
    max_step: float = 0.5,
) -> dict:
    """
    數值積分 V60 動態 ODE 系統（bin-resolved 萃取 + 軸向梯度 + 動態潤濕 + 濕床結構記憶 + 濾杯熱節點）。

    What:
          基礎狀態固定為 [h, V_out, V_bed, V_poured, sat]；
          measured PSD bins 啟用時，接著是每個 axial layer × bin 的：
          [C_fast_ij, M_fast_ij, C_slow_ij, M_slow_ij]；
          最後接 [T, T_dripper, chi_struct, xi_pref]。

    Why:
          水力學仍是集總床層模型，但萃取端升級為 bin-resolved，
          讓 measured PSD 的 A_i、L_i、M_i 真正進入 ODE，而不是只作 aggregate closure。
          軸向上則用少量串接 CSTR 保留「上層先被稀釋、下層決定出液濃度」的梯度，
          避免把整個粉床濃度硬壓成單一均勻池。
          `rtol/atol/max_step` 保持預設即可重現既有結果；fitting 可用較鬆設定換取速度。
    """
    t_bloom_end = protocol.bloom_end_time()
    n_bins = int(getattr(params, "extraction_bin_count", 1))
    n_layers = int(getattr(params, "axial_node_count", 1))
    n_axial = n_layers * n_bins
    layer_frac = np.asarray(getattr(params, "axial_layer_volume_fraction", np.full(n_layers, 1.0 / max(n_layers, 1))), dtype=float)
    layer_frac = layer_frac / np.maximum(np.sum(layer_frac), 1e-12)
    layer_frac_col = layer_frac[:, None]
    M_fast_0_layers = layer_frac_col * np.asarray(params.M_fast_0_bins, dtype=float)[None, :]
    M_slow_0_layers = layer_frac_col * np.asarray(params.M_slow_0_bins, dtype=float)[None, :]
    c_fast_slice = slice(5, 5 + n_axial)
    m_fast_slice = slice(5 + n_axial, 5 + 2 * n_axial)
    c_slow_slice = slice(5 + 2 * n_axial, 5 + 3 * n_axial)
    m_slow_slice = slice(5 + 3 * n_axial, 5 + 4 * n_axial)
    T_idx = 5 + 4 * n_axial
    T_dripper_idx = T_idx + 1
    chi_idx = T_idx + 2
    pref_idx = T_idx + 3

    def rhs(t, state):
        h = float(state[0])
        V_out = float(state[1])
        V_bed = float(state[2])
        V_poured = float(state[3])
        sat = float(state[4])
        C_fast_layers = np.maximum(np.asarray(state[c_fast_slice], dtype=float), 0.0).reshape(n_layers, n_bins)
        M_fast_layers = np.maximum(np.asarray(state[m_fast_slice], dtype=float), 0.0).reshape(n_layers, n_bins)
        C_slow_layers = np.maximum(np.asarray(state[c_slow_slice], dtype=float), 0.0).reshape(n_layers, n_bins)
        M_slow_layers = np.maximum(np.asarray(state[m_slow_slice], dtype=float), 0.0).reshape(n_layers, n_bins)
        T = float(state[T_idx])
        T_dripper = float(state[T_dripper_idx])
        chi_struct = float(state[chi_idx])
        xi_pref = float(state[pref_idx])
        h      = max(h, H_MIN)
        sat    = float(np.clip(sat, 0.0, 1.0))
        T      = float(np.clip(T, params.T_amb, params.T_brew + 5.0))
        T_dripper = float(np.clip(T_dripper, params.T_amb - 5.0, params.T_brew + 5.0))
        chi_struct = float(np.clip(chi_struct, 0.0, 1.0))
        xi_pref = float(np.clip(xi_pref, 0.0, 1.0))
        M_fast = float(np.sum(M_fast_layers))
        M_slow = float(np.sum(M_slow_layers))

        bloom_active = t < t_bloom_end
        sat_target = params.saturation(V_poured) if bloom_active else 1.0
        # sat 只追蹤乾粉潤濕前沿；流動方程則在 bloom 後平滑鬆弛到濕床近似。
        sat_flow = params.flow_saturation(sat, t, t_bloom_end)

        area  = params.area(h)
        impact = protocol.pour_start_impact(t, bloom_end_s=t_bloom_end, width_s=params.wetbed_impact_tau)

        # 先估計不含 bloom 後濕床重排的基礎滲透率，再用其對應的孔隙流速當代理量。
        k_base = params.k_eff(
            V_bed, sat_flow, h,
            q_in=0.0, u_pore=0.0, t_sec=t, bloom_end_s=None,
            wetbed_struct_state=chi_struct,
            pour_impact=impact,
        )
        psi_val = params.psi_eff(V_out)

        Q_in  = protocol.pour_rate(t)
        Q_ext_base = params.q_extract(h, k_base, T, t, sat=sat_flow)
        Q_pref_base = params.q_preferential(
            h, xi_pref, T_K=T, t_sec=t, sat=sat_flow, bloom_end_s=t_bloom_end
        )
        phi_eff_now = params.phi_effective(sat_flow, h)
        Q_bed_base = Q_ext_base + Q_pref_base
        u_proxy = max(Q_bed_base, 0.0) / max(area * phi_eff_now, 1e-12)
        k_val = params.k_eff(
            V_bed, sat_flow, h,
            q_in=Q_in, u_pore=u_proxy, t_sec=t, bloom_end_s=t_bloom_end,
            wetbed_struct_state=chi_struct,
            pour_impact=impact,
        )
        Q_ext = params.q_extract(h, k_val, T, t, sat=sat_flow)
        Q_pref = params.q_preferential(
            h, xi_pref, T_K=T, t_sec=t, sat=sat_flow, bloom_end_s=t_bloom_end
        )
        Q_bed = Q_ext + Q_pref
        Q_bp  = params.q_bypass(h, psi_val, T)
        Q_out = Q_bed + Q_bp

        # 修正 [16] 動態潤濕：注水填充 + 毛細潤濕並行
        # d sat / dt = hydraulic_fill + capillary_fill
        # hydraulic_fill : 直接由新注入的水推進
        # capillary_fill : 只在「乾粉浸濕」階段由已滯留液體繼續潤濕粉床
        # 注意：Lucas-Washburn 僅適用於乾粉前沿潤濕；當 V_poured >= V_full 時，
        #       模型視為乾粉浸濕階段已結束，後續不再額外啟用毛細浸潤項。
        sat_gap = max(0.0, sat_target - sat)
        V_absorb = max(params.V_absorb, 1e-12)
        dsat_hyd = (Q_in / V_absorb) * sat_gap if bloom_active else 0.0
        retained_liquid = max(V_poured - V_out, 0.0)
        dry_wetting_active = float(bloom_active and (V_poured < params._V_full))
        cap_gate = np.clip(retained_liquid / max(params._V_full, 1e-12), 0.0, 1.0)
        dsat_cap = dry_wetting_active * cap_gate * sat_gap / params.tau_cap_T(T)
        dsat = dsat_hyd + dsat_cap

        # 只有 bloom 的乾粉潤濕期，注水才會被 sat 節流；之後視為已浸濕床層。
        Q_in_free = Q_in * sat_flow
        dh = (Q_in_free - Q_out) / area
        if h <= H_MIN and dh < 0:
            dh = 0.0

        # 修正 [7][11] 多組分萃取（Fast + Slow，Arrhenius 動力學 + 可及性冪次律）
        # 可及性修正：C_eff = C_sat(T) × (M/M₀)^β
        # β=1: 線性（原模型）；β>1: 超線性，末期 C_eff 更快趨零（細胞壁困住深層溶質）
        # 等效於：速率 ∝ k_ext × M^β / M₀^β × (C_sat - C)，β=1.5 時更快收斂
        β = params.beta_access
        # 修正 [15] 流速依賴傳質係數（邊界層 Sh 效應）
        # flow_factor = k_diff_ratio + (1-k_diff_ratio) × Q_ext/(Q_ext+Q_half)
        # 靜置(Q→0): flow_factor→k_diff_ratio；流動(Q>>Q_half): flow_factor→1
        _kr = params.k_diff_ratio
        flow_factor = _kr + (1.0 - _kr) * Q_bed / (Q_bed + params.Q_half)
        k_ext_fast_bins = params.k_ext_fast_bins_T(T, t_sec=t)
        k_ext_slow_bins = params.k_ext_slow_bins_T(T, t_sec=t)
        V_liq_conc_layers = np.maximum(
            params.V_liquid * layer_frac_col,
            params.V_liquid * 0.05 / max(n_layers, 1),
        )

        if params.M_fast_0 > 0:
            acc_fast_layers = np.where(
                M_fast_0_layers > 1e-12,
                (M_fast_layers / np.maximum(M_fast_0_layers, 1e-12)) ** β,
                0.0,
            )
            C_eff_fast_layers = params.C_sat_fast_T(T) * acc_fast_layers
        else:
            C_eff_fast_layers = np.zeros_like(C_fast_layers)
        dis_fast_layers = k_ext_fast_bins[None, :] * flow_factor * np.maximum(C_eff_fast_layers - C_fast_layers, 0.0)

        if params.M_slow_0 > 0:
            acc_slow_layers = np.where(
                M_slow_0_layers > 1e-12,
                (M_slow_layers / np.maximum(M_slow_0_layers, 1e-12)) ** β,
                0.0,
            )
            C_eff_slow_layers = params.C_sat_slow_T(T) * acc_slow_layers
        else:
            C_eff_slow_layers = np.zeros_like(C_slow_layers)
        dis_slow_layers = k_ext_slow_bins[None, :] * flow_factor * np.maximum(C_eff_slow_layers - C_slow_layers, 0.0)

        # 粉床孔隙串接 CSTR 濃度更新：上層先吃稀釋，下層決定出液濃度。
        # 上游邊界濃度視為 0（注入液進入粉床前不含咖啡溶質），
        # 各層之間只由 Q_bed 單向帶走濃度，保留 reduced-order 的局部可推理性。
        C_fast_upstream = np.vstack([np.zeros((1, n_bins), dtype=float), C_fast_layers[:-1]])
        C_slow_upstream = np.vstack([np.zeros((1, n_bins), dtype=float), C_slow_layers[:-1]])
        dC_fast_layers = (dis_fast_layers + Q_bed * (C_fast_upstream - C_fast_layers)) / V_liq_conc_layers
        dM_fast_layers = -dis_fast_layers * 1e3
        dC_slow_layers = (dis_slow_layers + Q_bed * (C_slow_upstream - C_slow_layers)) / V_liq_conc_layers
        dM_slow_layers = -dis_slow_layers * 1e3

        # 瞬時孔隙液體體積（供熱動方程使用）
        V_liq_t = max(params.phi * (np.pi / 3) * params._tan2 * h**3,
                      params.V_liquid * 0.05)

        # 熱動方程（修正 [6]）—— CSTR 焓平衡推導
        # 完整焓平衡：d(V_eff·T)/dt = Q_in·T_brew - Q_out·T - λ·V_eff·(T-T_amb)
        # 展開左側：V_eff·dT/dt + T·dV_eff/dt = Q_in·T_brew - Q_out·T - λ·V_eff·(T-T_amb)
        # 代入 dV_eff/dt = Q_in - Q_out（質量守恆）：
        # → V_eff·dT/dt = Q_in·T_brew - Q_out·T - T·(Q_in-Q_out) - λ·V_eff·(T-T_amb)
        #               = Q_in·(T_brew-T) - λ·V_eff·(T-T_amb)
        # 結論：dm/dt 項在展開後「自然相消」，現有簡化公式完全等價於完整焓平衡。
        # 修正 Bug [熱慣性]：咖啡粉固體熱容為常駐項，不隨 sat 消失。
        # 舊版 V_equiv_coffee × (1-sat) 在 sat→1 時錯誤移除粉體熱容，
        # 導致第一注完成瞬間分母縮小，引發虛假溫度跳變並低估後段降溫效果。
        # 修正：V_equiv_coffee 無論 sat 為何，始終計入熱動方程分母。
        V_eff_T = V_liq_t + params.V_equiv_coffee
        exchange_liq_dripper = params.lambda_liquid_dripper * (T - T_dripper)
        dT = (Q_in / V_eff_T) * (params.T_brew - T) \
             - params.lambda_cool * (T - params.T_amb) \
             - exchange_liq_dripper

        if params.V_equiv_dripper > 0.0:
            dT_dripper = (
                params.lambda_liquid_dripper
                * (V_eff_T / max(params.V_equiv_dripper, 1e-12))
                * (T - T_dripper)
                - params.lambda_dripper_ambient * (T_dripper - params.T_amb)
            )
        else:
            dT_dripper = 0.0

        dchi_struct = params.d_wetbed_struct_dt(
            chi_struct,
            q_in=Q_in,
            h=h,
            pour_impact=impact,
            t_sec=t,
            bloom_end_s=t_bloom_end,
        )
        dxi_pref = params.d_preferential_flow_dt(
            xi_pref,
            q_in=Q_in,
            pour_impact=impact,
            t_sec=t,
            bloom_end_s=t_bloom_end,
        )

        return np.concatenate((
            np.array([dh, Q_out, Q_bed, Q_in, dsat], dtype=float),
            dC_fast_layers.reshape(-1),
            dM_fast_layers.reshape(-1),
            dC_slow_layers.reshape(-1),
            dM_slow_layers.reshape(-1),
            np.array([dT, dT_dripper, dchi_struct, dxi_pref], dtype=float),
        ))

    t_eval = np.linspace(0, t_end, n_eval)
    # 初始熱衝擊溫度
    V_bloom   = protocol.first_pour_volume_ml() * 1e-6
    m_w_bloom = V_bloom * RHO
    m_coffee  = params.dose_g * 1e-3
    CP_W      = 4180.0
    T_shock   = (m_w_bloom * CP_W * params.T_brew + m_coffee * params.Cp_coffee * params.T_amb) \
                / (m_w_bloom * CP_W + m_coffee * params.Cp_coffee)

    y0 = np.concatenate((
        np.array([H_MIN, 0.0, 0.0, 0.0, 0.0], dtype=float),
        np.zeros(n_axial, dtype=float),
        M_fast_0_layers.reshape(-1),
        np.zeros(n_axial, dtype=float),
        M_slow_0_layers.reshape(-1),
        np.array([T_shock, params.T_amb, 0.0, 0.0], dtype=float),
    ))

    sol = solve_ivp(
        rhs,
        t_span=(0, t_end),
        y0=y0,
        t_eval=t_eval,
        # RK45 + 加密步長（max_step=0.5）
        # 選用 RK45 而非 LSODA/Radau 的理由：
        # - 模型含 max()、clamp 等非光滑項，LSODA/BDF 的雅可比估算容易失敗
        # - h_cap 附近 sigmoid 梯度 ~1/(h_cap×0.25)=800 m⁻¹，以 max_step=0.5s 足以解析
        # - 批量靈敏度掃描（225 runs）需要快速非剛性求解器
        method="RK45",
        rtol=rtol,
        atol=atol,
        max_step=max_step,  # 預設 0.5；fitting 可暫用較粗步長，再以高精度回算 final
    )

    t        = sol.t
    h        = np.maximum(sol.y[0], 0.0)
    V_out    = sol.y[1]
    V_bed    = sol.y[2]
    V_poured = sol.y[3]
    sat_state = np.clip(sol.y[4], 0.0, 1.0)
    sat      = np.where(t < t_bloom_end, sat_state, 1.0)
    C_fast_layers = np.maximum(sol.y[c_fast_slice], 0.0).reshape(n_layers, n_bins, -1)
    M_fast_layers = np.maximum(sol.y[m_fast_slice], 0.0).reshape(n_layers, n_bins, -1)
    C_slow_layers = np.maximum(sol.y[c_slow_slice], 0.0).reshape(n_layers, n_bins, -1)
    M_slow_layers = np.maximum(sol.y[m_slow_slice], 0.0).reshape(n_layers, n_bins, -1)
    C_fast_bins_mean = np.tensordot(layer_frac, C_fast_layers, axes=(0, 0))
    C_slow_bins_mean = np.tensordot(layer_frac, C_slow_layers, axes=(0, 0))
    C_fast   = np.sum(C_fast_bins_mean, axis=0)
    M_fast   = np.sum(M_fast_layers, axis=(0, 1))
    C_slow   = np.sum(C_slow_bins_mean, axis=0)
    M_slow   = np.sum(M_slow_layers, axis=(0, 1))
    C_fast_out = np.sum(C_fast_layers[-1], axis=0)
    C_slow_out = np.sum(C_slow_layers[-1], axis=0)
    C_bed_top = np.sum(C_fast_layers[0] + C_slow_layers[0], axis=0)
    C_bed_bottom = np.sum(C_fast_layers[-1] + C_slow_layers[-1], axis=0)
    T_K      = np.clip(sol.y[T_idx], params.T_amb, params.T_brew + 5.0)  # [K]
    T_dripper_K = np.clip(sol.y[T_dripper_idx], params.T_amb - 5.0, params.T_brew + 5.0)
    chi_struct = np.clip(sol.y[chi_idx], 0.0, 1.0)
    xi_pref = np.clip(sol.y[pref_idx], 0.0, 1.0)
    M_sol    = M_fast + M_slow             # 向後相容：總剩餘固相

    q_in_raw = np.array([protocol.pour_rate(ti) for ti in t])
    sat_flow_arr = np.array([params.flow_saturation(float(si), float(ti), t_bloom_end) for si, ti in zip(sat, t)])
    kr_sat_arr = np.asarray(params.relative_permeability(sat_flow_arr), dtype=float)
    q_in_eff = q_in_raw * sat_flow_arr

    # 重新計算各流量分量（用於繪圖，帶入衰減後的 k、Ψ、濕床 gate 與溫度）
    impact_arr = np.array([protocol.pour_start_impact(float(ti), bloom_end_s=t_bloom_end, width_s=params.wetbed_impact_tau) for ti in t])
    area_arr = np.maximum(params.area(h), 1e-12)
    drive_components = params.bed_drive_components(h, T_K=T_K, t_sec=t, sat=sat_flow_arr)
    h_threshold_arr = np.asarray(drive_components["h_threshold"], dtype=float)
    h_threshold_eff_arr = np.asarray(drive_components["h_threshold_eff"], dtype=float)
    h_cap_wet_arr = np.asarray(drive_components["h_cap_wet"], dtype=float)
    h_eff_arr = np.asarray(drive_components["h_eff"], dtype=float)
    phi_eff_seed = np.array([params.phi_effective(sf, hi) for sf, hi in zip(sat_flow_arr, h)])
    k_base_vals = np.array([
        params.k_eff(
            vb, sf, hi,
            q_in=0.0, u_pore=0.0, t_sec=float(ti), bloom_end_s=None,
            wetbed_struct_state=chi,
            pour_impact=imp,
        )
        for vb, sf, hi, ti, chi, imp in zip(V_bed, sat_flow_arr, h, t, chi_struct, impact_arr)
    ])
    q_ext_seed = np.array([
        params.q_extract(float(hi), float(kv), float(Ti), t_sec=float(ti), sat=float(sf))
        for hi, kv, Ti, ti, sf in zip(h, k_base_vals, T_K, t, sat_flow_arr)
    ])
    q_pref_seed = np.array([
        params.q_preferential(float(hi), float(xi), T_K=float(Ti), t_sec=float(ti), sat=float(sf), bloom_end_s=t_bloom_end)
        for hi, xi, Ti, ti, sf in zip(h, xi_pref, T_K, t, sat_flow_arr)
    ])
    q_bed_seed = q_ext_seed + q_pref_seed
    u_seed = np.where(q_bed_seed > 1e-12, q_bed_seed / np.maximum(area_arr * phi_eff_seed, 1e-12), 0.0)
    k_vals = np.array([
        params.k_eff(
            vb, sf, hi,
            q_in=qin, u_pore=u, t_sec=float(ti), bloom_end_s=t_bloom_end,
            wetbed_struct_state=chi,
            pour_impact=imp,
        )
        for vb, sf, hi, qin, u, ti, chi, imp in zip(V_bed, sat_flow_arr, h, q_in_raw, u_seed, t, chi_struct, impact_arr)
    ])
    psi_vals = params.psi_eff(V_out)
    q_ext  = np.array([
        params.q_extract(float(hi), float(kv), float(Ti), t_sec=float(ti), sat=float(sf))
        for hi, kv, Ti, ti, sf in zip(h, k_vals, T_K, t, sat_flow_arr)
    ])
    q_pref = np.array([
        params.q_preferential(float(hi), float(xi), T_K=float(Ti), t_sec=float(ti), sat=float(sf), bloom_end_s=t_bloom_end)
        for hi, xi, Ti, ti, sf in zip(h, xi_pref, T_K, t, sat_flow_arr)
    ])
    q_bed = q_ext + q_pref
    q_bp   = params.q_bypass(h, psi_vals, T_K)
    q_out  = q_bed + q_bp
    phi_eff_arr = np.array([params.phi_effective(sf, hi) for sf, hi in zip(sat_flow_arr, h)])
    u_pore = np.where(q_bed > 1e-12, q_bed / np.maximum(area_arr * phi_eff_arr, 1e-12), 0.0)
    fine_drag = np.abs(u_pore) * np.array([params.mu_water(Ti) for Ti in T_K]) * params.fine_radius()

    dt           = np.diff(t, prepend=t[0])
    v_in_ml      = np.cumsum(dt * q_in_raw) * 1e6
    v_in_eff_ml  = np.cumsum(dt * q_in_eff) * 1e6
    v_out_ml     = V_out * 1e6
    v_bed_ml     = V_bed * 1e6
    v_extract_ml = np.cumsum(dt * q_bed)  * 1e6

    _q_out_safe  = np.where(q_out > 1e-12, q_out, 1.0)  # 防止零除（h < h_cap 時 q_out=0）
    bypass_ratio = np.where(q_out > 1e-12, q_bp / _q_out_safe, 0.0)
    pref_ratio = np.where(q_out > 1e-12, q_pref / _q_out_safe, 0.0)
    head_gate = np.clip(h_eff_arr / np.maximum(h + h_cap_wet_arr, 1e-12), 0.0, 1.0)
    bloom_mask = t <= t_bloom_end
    if np.any(bloom_mask):
        choke_means = {
            "sat_flow": float(np.mean(1.0 - sat_flow_arr[bloom_mask])),
            "kr_sat": float(np.mean(1.0 - kr_sat_arr[bloom_mask])),
            "h_cap_h_gas": float(np.mean(1.0 - head_gate[bloom_mask])),
        }
        dominant_bloom_choke = max(choke_means, key=choke_means.get)
    else:
        choke_means = {"sat_flow": 0.0, "kr_sat": 0.0, "h_cap_h_gas": 0.0}
        dominant_bloom_choke = "n/a"

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
    C_bed_out = C_fast_out + C_slow_out
    C_out = np.where(q_out > 1e-12, q_bed * C_bed_out / _q_out_safe, 0.0)

    # 累積萃取質量（各組分 + 總計）
    M_fast_ext_g  = np.cumsum(dt * q_bed * C_fast_out) * 1e3
    M_slow_ext_g  = np.cumsum(dt * q_bed * C_slow_out) * 1e3
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

    # 沖煮時間（最後一注結束後，水柱高度 = 粉層高度 的時刻）
    # 在現有集總幾何中，h 直接代表相對濾杯出口的液柱高度；
    # 因此以 h <= h_bed 作為可操作的工程定義。
    # 保留原有 drain_time 作為「滴濾幾乎結束」的次要診斷量，避免破壞既有分析。
    t_last_pour = protocol.last_pour_end()
    mask_after  = t > t_last_pour
    brew_time   = t_end
    brew_threshold = params.h_bed
    if mask_after.any():
        reach_brew_time = np.where(mask_after & (h <= brew_threshold))[0]
        if reach_brew_time.size:
            brew_time = t[reach_brew_time[0]]

    # 最終滴濾結束時間（舊定義）
    drain_threshold = max(0.002, params.h_cap + 0.001)  # [m]
    drain_time  = t_end
    if mask_after.any():
        below_thresh = np.where(mask_after & (h < drain_threshold))[0]
        if below_thresh.size:
            drain_time = t[below_thresh[0]]

    return dict(
        t            = t,
        h_mm         = h * 1e3,
        dose_g       = params.dose_g,          # 粉重（供 LRR 驗算）
        f_abs        = params.absorb_full_ratio,  # 充分浸潤吸水率 [mL/g]
        D10_um       = params.D10 * 1e6,
        shell_ratio  = params.shell_accessibility_ratio,
        area_ratio   = params.surface_area_ratio,
        phi_eff      = phi_eff_arr,
        u_pore_mps   = u_pore,
        fine_drag_N  = fine_drag,
        q_in_mlps    = q_in_raw * 1e6,
        q_in_eff_mlps= q_in_eff * 1e6,
        q_ext_mlps   = q_ext    * 1e6,
        q_pref_mlps  = q_pref   * 1e6,
        q_bed_mlps   = q_bed    * 1e6,
        q_bp_mlps    = q_bp     * 1e6,
        q_out_mlps   = q_out    * 1e6,
        k_vals       = k_vals,
        psi_vals     = psi_vals,
        v_in_ml      = v_in_ml,
        v_in_eff_ml  = v_in_eff_ml,
        v_out_ml     = v_out_ml,
        v_bed_ml     = v_bed_ml,
        v_extract_ml = v_extract_ml,
        bypass_ratio = bypass_ratio,
        pref_ratio   = pref_ratio,
        sat          = sat,
        sat_flow     = sat_flow_arr,
        kr_sat       = kr_sat_arr,
        head_gate    = head_gate,
        h_gas_mm     = np.asarray(params.h_gas(t), dtype=float) * 1e3,
        h_threshold_mm = h_threshold_arr * 1e3,
        h_threshold_eff_mm = h_threshold_eff_arr * 1e3,
        h_cap_wet_mm = h_cap_wet_arr * 1e3,
        h_eff_mm     = h_eff_arr * 1e3,
        bloom_end_s  = float(t_bloom_end),
        bloom_choke_means = choke_means,
        dominant_bloom_choke = dominant_bloom_choke,
        wetbed_struct= chi_struct,
        pref_flow_state = xi_pref,
        extraction_bin_count = n_bins,
        axial_node_count = n_layers,
        C_fast_bins_gl = C_fast_bins_mean,
        C_slow_bins_gl = C_slow_bins_mean,
        C_fast_layers_gl = C_fast_layers,
        C_slow_layers_gl = C_slow_layers,
        M_fast_bins_g = np.sum(M_fast_layers, axis=0),
        M_slow_bins_g = np.sum(M_slow_layers, axis=0),
        M_fast_layers_g = M_fast_layers,
        M_slow_layers_g = M_slow_layers,
        brew_time    = brew_time,
        drain_time   = drain_time,
        # TDS + 固相耗盡（v7 多組分）
        C_bed_gl         = C_bed,
        C_fast_gl        = C_fast,
        C_slow_gl        = C_slow,
        C_bed_top_gl     = C_bed_top,
        C_bed_bottom_gl  = C_bed_bottom,
        C_out_bed_gl     = C_bed_out,
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
        T_dripper_K      = T_dripper_K,
        T_dripper_C      = T_dripper_K - 273.15,
        lambda_server_ambient = float(getattr(params, "lambda_server_ambient", 0.0)),
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
    brew_time = results.get("brew_time", results["drain_time"])
    print(f"  沖煮時間       : {brew_time:.1f} s  (自由水柱 = 粉層高)")
    print(f"  滴濾結束時間   : {results['drain_time']:.1f} s")
    print(f"  總注水量       : {results['v_in_ml'][-1]:.1f} mL")
    print(f"  有效水量（扣吸）: {results['v_in_eff_ml'][-1]:.1f} mL")
    print(f"  總出液量       : {v_out:.1f} mL")
    if v_out > 0:
        print(f"    ├ 萃取液     : {v_ext:.1f} mL  ({v_ext/v_out*100:.1f}%)")
        print(f"    └ 旁路液     : {v_bp:.1f} mL  ({v_bp/v_out*100:.1f}%)")
    if "q_pref_mlps" in results:
        pref_share = float(np.mean(results.get("pref_ratio", np.zeros_like(results["q_out_mlps"])))) * 100.0
        print(f"  平均快路徑占比 : {pref_share:.1f}%")
    print(f"  峰值水位       : {results['h_mm'].max():.1f} mm")
    print(f"  峰值出水速度   : {results['q_out_mlps'].max():.2f} mL/s")
    k0  = results["k_vals"][0]
    k_f = results["k_vals"][-1]
    print(f"  k 衰減比       : {k_f/k0:.2f}  ({k0:.2e} → {k_f:.2e} m²)")
    if "D10_um" in results:
        print(f"  D10 / 殼層比   : {results['D10_um']:.0f} μm  /  {results['shell_ratio']:.2f}×")
    if "u_pore_mps" in results:
        print(f"  峰值孔隙流速   : {results['u_pore_mps'].max():.4f} m/s")
    if "fine_drag_N" in results:
        print(f"  峰值細粉拖曳力 : {results['fine_drag_N'].max():.2e} N")
    print(f"  最終 TDS       : {results['TDS_gl'][-1]:.2f} g/L  ({results['TDS_gl'][-1]/10:.2f}%)")
    print(f"  EY（入壺）     : {results['EY_cup_pct'][-1]:.1f}%")
    print(f"  EY（已溶出）   : {results['EY_dissolved_pct'][-1]:.1f}%")
    print(f"  └ 差值（留杯） : {results['EY_dissolved_pct'][-1]-results['EY_cup_pct'][-1]:.1f}%")
    print(f"  粉層峰值濃度   : {results['C_bed_gl'].max():.1f} g/L")
    print(f"  固相剩餘溶質   : {results['M_sol_g'][-1]:.2f} g / {results['M_sol_g'][0]:.2f} g")
    # ── Gagné LRR 質量守恆驗算 ───────────────────────────────────────────────
    # LRR = (W - B(1-C)) / D；其中 W=注水量, B=出壺量, C=TDS分率, D=粉重
    # 物理意義：每克咖啡粉保留了多少 mL 水（吸水 + 殘留粉層）
    # V60 典型值 ~2.2 mL/g（Gagné）；偏低代表排得較乾淨
    if "dose_g" in results:
        W   = float(results["v_in_ml"][-1])
        B   = float(results["v_out_ml"][-1])
        C   = float(results["TDS_gl"][-1]) / 1000.0   # g/L → 無量綱分率
        D   = results["dose_g"]
        f_a = results["f_abs"]
        lrr = (W - B * (1.0 - C)) / D
        ey_lrr = (C / (1.0 - C)) * (W / D - f_a)
        print(f"  ── Gagné 質量守恆驗算 ────────────────────────")
        print(f"    LRR（留水率）   : {lrr:.2f} mL/g  （V60 典型 ~2.2）")
        print(f"    EY（LRR 公式）  : {ey_lrr*100:.1f}%  （vs 模型 EY {results['EY_cup_pct'][-1]:.1f}%）")
    if "EY_fast_cup_pct" in results:
        ey_fast = results["EY_fast_cup_pct"][-1]
        ey_slow = results["EY_slow_cup_pct"][-1]
        total   = ey_fast + ey_slow
        ratio   = ey_fast / total * 100 if total > 0 else 50.0
        print(f"  風味分解（入壺）:")
        print(f"    ├ Fast（酸/甜）: EY={ey_fast:.1f}%  TDS={results['TDS_fast_gl'][-1]:.1f} g/L")
        print(f"    └ Slow（苦/澀）: EY={ey_slow:.1f}%  TDS={results['TDS_slow_gl'][-1]:.1f} g/L")
        print(f"    風味平衡 Fast% = {ratio:.0f}%  （越高越明亮/酸，越低越苦）")
        # ── 風味診斷標籤（CVA 邏輯，優先級：萃取完整性 > 平衡傾向）──────────
        ey_cup = results["EY_cup_pct"][-1]
        tds    = results["TDS_gl"][-1]
        fast_ratio = ratio / 100.0
        if ey_cup < 17.0:
            flavor_tag = "Under-extracted ⚠  （萃取不足：甜感與酸質均未發展完全）"
        elif ey_cup > 23.0:
            flavor_tag = "Over-extracted  ⚠  （過度萃取：苦澀物質過量釋放）"
        elif fast_ratio > 0.55:
            flavor_tag = "Bright & Acidic    （明亮酸質主導：有機酸/糖類充分，苦韻偏弱）"
        elif fast_ratio < 0.45:
            flavor_tag = "Heavy & Bitter     （厚重苦韻主導：Slow 組分過度發展）"
        else:
            flavor_tag = "Balanced           （均衡發展：Fast/Slow 在 SCA 黃金窗口內）"
        # 並列顯示 TDS 強度標記
        if tds < 11.0:
            flavor_tag += "  [淡薄]"
        elif tds > 14.5:
            flavor_tag += "  [濃烈]"
        print(f"  ── 風味診斷 ──────────────────────────────────")
        print(f"    {flavor_tag}")
    if "T_C" in results:
        T_start = results["T_C"][0]
        T_end   = results["T_C"][-1]
        print(f"  水溫變化       : {T_start:.1f}°C → {T_end:.1f}°C  (Δ{T_start-T_end:.1f}°C)")
    print("=" * 54)
