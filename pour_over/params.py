"""
pour_over.params — V60 手沖咖啡物理參數模組
============================================

What: 封裝 V60 模擬所需的所有物理參數與資料結構。
Why:  將參數定義與 ODE 求解器解耦，使參數組合（研磨度、烘焙度、注水協議）
      可獨立測試、複用與擴展，不依賴任何外部模組。

包含：
    - 物理常數（RHO, G, H_MIN, R_GAS）
    - RoastProfile：烘焙度物理係數集（frozen dataclass）
    - V60Params：V60 濾杯幾何與物理參數（dataclass）
    - PourProtocol：分段注水計畫（dataclass）
"""

import dataclasses

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from dataclasses import dataclass, field
from typing import ClassVar, List, Tuple

# ── 物理常數 ──────────────────────────────────────────────────────────────────
RHO   = 1000.0  # 水密度 [kg/m³]
G     = 9.81    # 重力加速度 [m/s²]
H_MIN = 1e-4    # 最低有效水位（避免 A(h)→0 除以零）[m]
R_GAS = 8.314   # 理想氣體常數 [J/(mol·K)]，用於 Arrhenius k_ext(T)


def _setup_cjk_font() -> None:
    """優先選用系統中的 CJK 字型，否則退回英文 label。"""
    candidates = [
        "Heiti TC", "PingFang TC", "Apple LiGothic",
        "Noto Sans CJK TC", "Noto Sans TC",
        "Microsoft JhengHei",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            return

_setup_cjk_font()


# ─────────────────────────────────────────────────────────────────────────────
#  烘焙度物理係數集
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RoastProfile:
    """
    烘焙度對應的化學與物理係數集（不可變）。

    What: 封裝「烘焙度」直接決定的參數差異，與研磨度 k 正交分離。
    Why:  烘焙改變豆子的細胞結構（max_EY）、可溶物組成（fast_fraction）、
          萃取動力學（Ea_slow、k_ext_factor）以及 CO₂ 含量（吸水率）。
          這些參數不應由使用者逐一調整，而應透過語意明確的工廠 for_roast() 管理。

    使用方式：
        p = V60Params.for_roast(RoastProfile.LIGHT)
        p = V60Params.for_roast(RoastProfile.DARK, k_target=1.5e-10)
    """
    name: str

    # ── 溶質可萃取性 ───────────────────────────────────────────────────────
    max_EY: float
    # 最大萃取率；淺焙細胞壁緻密（0.22），深焙焦糖化破壁（0.30）

    alpha_EY: float
    # k-M 聯動靈敏度；淺焙硬豆磨細效益有限（0.10），深焙較高（0.20）

    # ── 萃取動力學 ────────────────────────────────────────────────────────
    k_ext_factor: float
    # k_ext_coef 相對倍率（相對於中焙基準 1.0）
    # Why: 深焙糖類分解增加易溶物 → k_ext↑；淺焙有機酸多但細胞壁阻力大 → k_ext↓

    Ea_slow: float
    # Slow 組分活化能 [J/mol]；深焙苦味物質焦化後活化能降低（更易在高溫萃出）

    # ── 組分比例 ──────────────────────────────────────────────────────────
    fast_fraction: float
    # Fast 組分佔比；淺焙含更多有機酸（0.45），深焙苦味物多（0.25）

    C_sat_slow: float
    # Slow 組分平衡濃度 [g/L]；深焙苦味物量大（100），淺焙少（60）

    # ── 吸水特性（CO₂ 含量影響） ─────────────────────────────────────────
    absorb_dry_ratio: float
    # 零出液吸水率 [mL/g]；淺焙 CO₂ 多→孔隙被佔（0.4），深焙脫氣後（0.7）

    absorb_full_ratio: float
    # 完全飽和吸水率 [mL/g]；淺焙緻密（1.2），深焙疏鬆（1.7）

    # ── CO₂ 背壓（修正 [14]）────────────────────────────────────────────────
    co2_pressure_m: float
    # 悶蒸初始 CO₂ 背壓等效水頭 [m]；映射至 V60Params.h_gas_0
    # Why: 新鮮淺焙豆 CO₂ 殘留多（9mm），深焙脫氣快（4mm）
    #      決定 q_extract 在早期受到的額外反向阻力大小

    # ── 預設配置（class-level constants，型別宣告）────────────────────────
    LIGHT:  ClassVar["RoastProfile"]
    MEDIUM: ClassVar["RoastProfile"]
    DARK:   ClassVar["RoastProfile"]


RoastProfile.LIGHT = RoastProfile(
    name              = "light",
    max_EY            = 0.22,
    alpha_EY          = 0.10,
    k_ext_factor      = 0.80,
    Ea_slow           = 50000.0,
    fast_fraction     = 0.45,
    C_sat_slow        = 60.0,
    absorb_dry_ratio  = 0.40,
    absorb_full_ratio = 1.20,
    co2_pressure_m    = 0.009,   # 9mm：淺焙 CO₂ 多，逸散慢
)

RoastProfile.MEDIUM = RoastProfile(
    name              = "medium",
    max_EY            = 0.28,
    alpha_EY          = 0.15,
    k_ext_factor      = 1.00,
    Ea_slow           = 45000.0,
    fast_fraction     = 0.35,
    C_sat_slow        = 80.0,
    absorb_dry_ratio  = 0.50,
    absorb_full_ratio = 1.30,
    co2_pressure_m    = 0.007,   # 7mm：中焙基準
)

RoastProfile.DARK = RoastProfile(
    name              = "dark",
    max_EY            = 0.30,
    alpha_EY          = 0.20,
    k_ext_factor      = 1.30,
    Ea_slow           = 38000.0,
    fast_fraction     = 0.25,
    C_sat_slow        = 100.0,
    absorb_dry_ratio  = 0.70,
    absorb_full_ratio = 1.70,
    co2_pressure_m    = 0.004,   # 4mm：深焙出油後 CO₂ 已大量散逸
)


# ─────────────────────────────────────────────────────────────────────────────
#  V60 物理參數
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class V60Params:
    """
    V60 濾杯的幾何與物理參數。

    What: 封裝所有可調物理量，包含四項修正後的新增參數
    Why:  讓每個旋鈕都對應真實的物理機制，而非純曲線擬合

    k 參考值（有效滲透率，重新校準使沖煮時間符合真實 V60 ~150s）：
        粗研磨 ≈ 2e-10 m²   中研磨 ≈ 6e-11 m²   細研磨 ≈ 1.5e-11 m²

    h_bed 估算（20g 咖啡，堆積密度約 0.5 g/mL）：
        V_bed = 40 mL → h_bed ≈ 48 mm

    k_beta 估算：
        k_beta = 3e3 m⁻³ → 300mL 出液後 k 降至初值 50%

    V_absorb 估算（修正 [13]）：
        V_dry  = 0.5mL/g × 20g = 10mL（CO₂ 修正後零出液門檻）
        V_full = 1.3mL/g × 20g = 26mL（完全飽和，正常出液）
    """
    # 幾何
    half_angle_deg: float = 30.0

    # 粉層物理
    k: float = 6e-11            # 初始有效滲透率 k0 [m²]（校準至 ~150s 沖煮時間）
    mu: float = 3.0e-4          # 動力黏度 [Pa·s]（93°C）

    # 旁路
    psi: float = 2.0e-6         # 旁路係數 Ψ [m²/s]

    # ── 修正 [1][2] 粉層高度 ──────────────────────────────────────────────────
    h_bed: float = 0.048        # 粉層高度 [m]；20g ≈ 48mm

    # ── 修正 [3] 細粉堵塞 ─────────────────────────────────────────────────────
    k_beta: float = 3e3         # 堵塞係數 β [m⁻³]；k(V) = k0/(1+β·V_out)

    # ── 旁路衰減 ──────────────────────────────────────────────────────────────
    psi_beta: float = 1e3
    # 旁路衰減係數 [m⁻³]；Ψ_eff(V) = Ψ0/(1+psi_beta·V_out)
    # Why: 細粉同樣會沉積在濾紙邊緣，降低肋骨旁路滲透率
    #      psi_beta < k_beta（旁路堵塞比粉層慢，因為流速較低）

    # ── 修正 [4][13] 悶蒸吸水 ────────────────────────────────────────────────
    dose_g: float = 20.0
    # 粉重 [g]。

    absorb_dry_ratio: float = 0.5
    # 零出液吸水率 [mL/g]；V_dry = dose_g × absorb_dry_ratio
    # Why（修正 [13]）：新鮮豆 CO₂ 仍殘留於微孔，有效吸水起點僅 ~0.5mL/g
    #      舊值 1.0mL/g 高估「悶蒸零出液」時長（Rao & Fuller 2018 實測中值 0.4–0.6）

    absorb_full_ratio: float = 1.3
    # 完全飽和吸水率 [mL/g]；V_full = dose_g × absorb_full_ratio
    # Why（修正 [13]）：飽和上限取 1.3mL/g（SCA protocol 中值 1.2–1.5）
    #      深焙/脫氣豆可調高至 ~1.7mL/g（CO₂ 少，微孔更易進水）
    #      舊值 2.0mL/g 高估，使悶蒸過渡段（sat 0→1）拉太長，首滴時間偏晚 5–10s

    # ── TDS 萃取動力學 ─────────────────────────────────────────────────────────
    phi: float = 0.4
    # 粉層孔隙率（porosity）；決定滯留水量 V_liquid = φ·V_bed
    # 參考：緊密堆積粉粒 φ ≈ 0.35–0.45

    C_sat: float = 150.0
    # 平衡濃度 [g/L]；粉層液體能達到的萃取上限濃度
    # 推算：典型 EY_max≈28%，20g粉 → 5.6g 溶質，V_liquid≈15mL → 373 g/L
    # 但實際平衡受細胞壁阻力限制，取 150 g/L 作為有效 C_sat

    k_ext_coef: float = 6.0e-7
    # 萃取速率係數 [m³/s]
    # 校正依據（穩態解析解 + 數值掃描，k=6e-11，Q_ext≈2mL/s）：
    #   η = k_ext / (k_ext + Q_ext)；k_ext_coef=6.0e-7 → η≈23%，EY≈18.8%，TDS≈13.9g/L
    #   目標：SCA Golden Cup EY=18–22%，TDS=11.5–14.5g/L → 取 6.0e-7 作為保守下界

    max_EY: float = 0.28
    # 最大萃取率（可溶物佔粉重的比例）
    # Why: 決定初始固相溶質量 M_sol_0 = dose_g × max_EY [g]
    #      當 M_sol → 0 時 C_sat_eff → 0，自然終止萃取，修正 C_bed 末端暴增

    # ── 修正 [6] 熱力學 ────────────────────────────────────────────────────────
    T_brew: float = 366.15
    # 初始沖煮水溫 [K]（93°C）；決定 ODE 初始條件與混合項的熱源溫度

    T_ref: float = 366.15
    # μ 與 k_ext 的校準參考溫度 [K]（固定 = 93°C）
    # Why: T_brew 可以改變（比較不同水溫），而 T_ref 是參數量測的基準，不隨實驗改變
    #      若 T_ref = T_brew，改變水溫只是平移參考點，物理效果消失

    T_amb: float = 298.15
    # 環境溫度 [K]（25°C）；Newton 冷卻終點

    lambda_cool: float = 3.7e-4
    # Newton 冷卻係數 λ [1/s]
    # 估算：典型手沖冷卻 ~1.5°C/min，ΔT_0 = 68°C → λ ≈ 1.5/(60×68) ≈ 3.7e-4

    mu_gamma: float = 1800.0
    # Andrade 黏度溫度係數 γ [K]
    # μ(T) = μ_ref·exp(γ·(1/T - 1/T_ref))
    # 水在 60–100°C：γ ≈ 1700–1900 K（與實驗數據吻合）

    Ea_ext: float = 25000.0
    # 萃取活化能 Ea [J/mol]（~25 kJ/mol）
    # Why: 符合擴散控制固液萃取典型範圍（10–40 kJ/mol）
    #      80°C vs 93°C：k_ext 降至 ~74%（定性與杯測感受一致）

    Cp_coffee: float = 1800.0
    # 乾咖啡粉比熱容 [J/(kg·K)]；典型植物性固體 1500–2000，取中值 1800
    # Why: 決定悶蒸初始熱衝擊：93°C 熱水 + 25°C 乾粉 → 首注後溫降 ~8-10°C

    alpha_C_sat: float = 0.003
    # C_sat 溫度係數 [1/K]；C_sat(T) = C_sat_ref·(1+α·(T-T_ref))
    # Why: 溶解度為溫度正函數（吸熱）；0.3%/K 對應典型有機物測量值
    #      使 83°C 萃取天花板低於 99°C，復現冷萃化學差異

    # ── 修正 [7] 多組分萃取 ────────────────────────────────────────────────────
    fast_fraction: float = 0.35
    # Fast 組分佔可溶物比例（有機酸、咖啡因、糖類）
    # Why: Fast 在低 T 易萃，決定明亮感與酸度；Slow 需高 T，帶出苦味

    C_sat_fast: float = 220.0
    # Fast 組分平衡濃度 [g/L]；活性物質分子量小，溶解度較高

    C_sat_slow: float = 80.0
    # Slow 組分平衡濃度 [g/L]；大分子苦味物質溶解度低

    Ea_fast: float = 15000.0
    # Fast 活化能 [J/mol]（~15 kJ/mol）；小分子擴散快，低 T 即可萃出

    Ea_slow: float = 45000.0
    # Slow 活化能 [J/mol]（~45 kJ/mol）；苦味物質需突破高熱障礙
    # Why: 99°C 下 k_ext_slow 比 83°C 高 ~7×，復現「高溫焦苦感」

    alpha_C_fast: float = 0.0015
    # Fast C_sat 溫度係數 [1/K]；小分子，對 T 較不靈敏

    alpha_C_slow: float = 0.006
    # Slow C_sat 溫度係數 [1/K]；苦味跳變：高溫大幅提升苦味溶解上限

    # ── k–M 聯動（The k-M Linkage）─────────────────────────────────────────
    k_ref: float = 6e-11
    # 中研磨參考滲透率 [m²]；聯動公式以此為基準
    # Why: k 是研磨度的流體力學代理變數（k ∝ d²，Kozeny-Carman）
    #      改變 k 即代表改變粒徑 d ∝ k^(1/2)，同步牽動 max_EY 和 k_ext_coef

    alpha_EY: float = 0.15
    # 可及溶質冪次指數：max_EY(k) = max_EY_ref × (k_ref/k)^alpha_EY
    # Why: 磨細 → 更多細胞壁破裂 → 更多可萃取溶質
    #      alpha_EY > 0：k↓（研磨越細）→ max_EY↑
    # 校準：粗(5e-11)→細(5e-12) EY 約 22→30%，alpha≈0.12–0.18（取 0.15）
    # 警告：超過 alpha=0.3 會使模型在細研磨端 EY > 100%（物理不合理）

    alpha_ext: float = 0.30
    # 萃取速率冪次指數：k_ext(k) = k_ext_ref × (k_ref/k)^alpha_ext
    # Why: 磨細 → 粒徑縮短 → 擴散路徑縮短 → k_ext↑
    #      alpha_ext > 0：k↓（研磨越細）→ k_ext↑（更快萃出）
    # 物理估算：k_ext ∝ 1/d² ∝ 1/k（alpha≈1），但實測偏弱，取保守值 0.30

    # ── 修正 [11] 可及性冪次律（Shrinking-Core Accessibility）───────────────
    beta_access: float = 1.5
    # 溶質可及性冪次指數（>1 = 超線性衰減）
    # Why: M_sol 下降時，易萃的「地表溶質」先耗盡，剩下被細胞壁困住的「深層溶質」。
    #      驅動力修正：C_eff = C_sat(T) × (M/M₀)^β
    #      β=1：目前線性模型（C_eff ∝ M/M₀）
    #      β=2/3：縮核模型（球形粒子，面積 ∝ r² ∝ M^(2/3)）⟵ 偏高
    #      β=1.5：超線性，對應「末期阻力驟增」的杯測觀察（推薦預設）
    #      量化效果：M=0.5M₀ 時 C_eff/C_sat = 0.5^1.5 = 35%（vs 線性的 50%）

    # ── 修正 [8] 顆粒溶脹（Kozeny-Carman）──────────────────────────────────
    delta_phi: float = 0.02
    # 飽和時孔隙率最大降幅 Δφ；φ(sat) = φ₀ - Δφ·sat
    # Why: 咖啡纖維吸水後膨脹（Swelling），粒子體積約增加 3–5%
    #      等效孔隙率：φ₀=0.40 → 0.38（Δφ≈0.02）
    #      Kozeny-Carman：k ∝ φ³/(1-φ)²，k 在全飽和時降低約 16%
    #      解耦兩種機制：細粉遷移（k_beta·V_out）vs 溶脹（delta_phi·sat）
    #      意義：篩掉細粉後流速仍會變慢 → 這部分由 delta_phi 解釋，k_beta 僅代表細粉
    #      校準備注：原 k=2e-11 已含隱性溶脹效應；若加入本項可能需上調 k_0

    # ── 修正 [9] 毛細管壓門檻（滴濾模式）──────────────────────────────────
    h_cap: float = 0.003

    # ── 修正 [14] CO₂ 背壓（Gas-trapping，新鮮豆悶蒸阻力）─────────────────
    h_gas_0: float = 0.007
    # CO₂ 背壓初始等效水頭 [m]（7mm ≈ 69 Pa）
    # Why: 新鮮豆子（烘焙 7 天內）悶蒸時 CO₂ 分壓 0.5–1.5 bar 對向下達西流施加反向阻力。
    #      等效於水頭修正：h_eff = h - h_cap - h_gas(t)
    #      h_gas(t) = h_gas_0 × exp(−t / τ_CO2)，隨 CO₂ 逸散指數衰減。
    #      此項解釋「新鮮豆水位高但流速慢」的 Gas-trapping 現象。
    #      文獻範圍：5–10mm（Cameron et al. 2020；悶蒸流速反推）

    tau_co2: float = 35.0
    # CO₂ 逸散時間常數 [s]
    # Why: t = τ → h_gas 降至初值 37%；t = 3τ ≈ 105s → 降至 5%（可忽略）
    #      Cameron et al. (2020) 建議 35–45s；取 35s 復現「第二注水位居高不下」現象
    #      舊值 25s 使排氣過快（第二注 t=45s 時 h_gas 已衰至 28%），阻力表現不足
    # 毛細管壓等效水位門檻 [m]（3mm ≈ 29 Pa）
    # 校準說明：原 5mm 使末段流量過早趨零，導致沖煮時間嚴重高估。
    # 真實 V60 在最後 3-5mm 水位仍有明顯滴流，3mm 更符合實際觀測。
    # Why: 當水頭壓力 ρgh < P_c 時，Poiseuille 流無法維持，轉入「滴濾」模式
    #      對應 V60 肋骨縫隙寬度 ~2–3mm 的毛細管壓（P_c ≈ 2σ/w ≈ 50–100 Pa）
    #      驅動水頭修正為 h_eff = max(0, h-h_cap)，h < h_cap 時流量驟降至零
    #      物理後果：粉層底部殘留少量高濃度液體，永遠不會被計入杯測 EY
    #      （這是真實「可量測 EY < 理論萃取率」的一個重要來源）

    def __post_init__(self):
        self._tan  = np.tan(np.radians(self.half_angle_deg))
        self._tan2 = self._tan ** 2
        # 達西係數基值 Φ_ref = π·tan²θ·ρg/μ_ref [m⁻¹s⁻¹]
        # Why: T 相依版本在 q_extract 中按 μ(T)/μ_ref 縮放
        self.phi_darcy = np.pi * self._tan2 * RHO * G / self.mu  # 避免與孔隙率 phi 重名
        # 悶蒸兩階段門檻（修正 [13]：CO₂排氣修正吸水率）
        self._V_dry  = self.dose_g * self.absorb_dry_ratio  * 1e-6  # [m³]
        self._V_full = self.dose_g * self.absorb_full_ratio * 1e-6  # [m³]
        # 粉層滯留水量（孔隙體積）
        self.V_bed    = (np.pi / 3) * self._tan2 * self.h_bed**3  # 粉床幾何體積 [m³]
        self.V_liquid = self.phi * self.V_bed                      # 孔隙水量 [m³]
        # 固相溶質耗盡模型
        self.M_sol_0 = self.dose_g * self.max_EY            # 初始可溶質量 [g]
        # κ = C_sat_0 / M_sol_0 [L⁻¹]；C_sat_eff(t) = κ·M_sol(t)
        # 單位：[g/L] / [g] = [1/L]（與 SI：k_ext[m³/s]×C_sat[kg/m³] 一致）
        # dose_g=0（用於 baseline 對比）時退化為純流體模型，不需萃取
        # 保留舊 kappa（單組分，backward compat）
        self.kappa = (self.C_sat / self.M_sol_0) if self.M_sol_0 > 0 else 0.0
        # 多組分初始質量（修正 [7]）
        self.M_fast_0 = self.M_sol_0 * self.fast_fraction
        self.M_slow_0 = self.M_sol_0 * (1.0 - self.fast_fraction)
        # k_ext_fast/slow 從 k_ext_coef 比例衍生；fitting 只需調 k_ext_coef
        self.k_ext_fast = self.k_ext_coef * 2.0   # Fast：2× 基準速率
        self.k_ext_slow = self.k_ext_coef * 0.5   # Slow：0.5× 基準速率
        # κ for each component（溫度相依，在方法中計算；此處存 ref 值）
        self.kappa_fast = (self.C_sat_fast / self.M_fast_0) if self.M_fast_0 > 0 else 0.0
        self.kappa_slow = (self.C_sat_slow / self.M_slow_0) if self.M_slow_0 > 0 else 0.0
        # 咖啡粉等效熱容體積：V_equiv = m_coffee × Cp_coffee / (ρ_water × Cp_water)
        # Why: 悶蒸時乾粉（常溫）吸收熱水熱量，換算為等效水體積後加入熱動方程分母
        #      Cp_water ≈ 4180 J/(kg·K)；dose_g [g] = dose_g×1e-3 [kg]
        self.V_equiv_coffee = (self.dose_g * 1e-3 * self.Cp_coffee) / (RHO * 4180.0)  # [m³]

    def saturation(self, V_poured: float) -> float:
        """
        悶蒸飽和係數 sat ∈ [0, 1]。C¹ 連續。

        What: cubic Hermite smooth-step：
              x = clamp((V_poured - V_dry) / (V_full - V_dry), 0, 1)
              sat = x² × (3 - 2x)

        Why（修正 [10]）: 原分段線性版本在 V=V_dry 和 V=V_full 有一階不連續（C⁰）。
             這兩個轉折點在 Q_in_free = Q_in×sat 中直接影響 dh/dt，
             造成 ODE 積分器在轉折瞬間遭遇非光滑項，引發數值衝擊（spike）。
             Cubic Hermite 在兩端都有 dsat/dV=0，保持 C¹ 連續。
        """
        if V_poured <= self._V_dry:
            return 0.0
        elif V_poured >= self._V_full:
            return 1.0
        x = (V_poured - self._V_dry) / (self._V_full - self._V_dry)
        return x * x * (3.0 - 2.0 * x)   # cubic Hermite: C¹ at both ends

    def h_gas(self, t_sec: float) -> float:
        """
        CO₂ 背壓等效水頭 [m]（修正 [14]）。

        What: h_gas(t) = h_gas_0 × exp(−t / τ_CO2)

        Why:  新鮮豆子悶蒸時內部 CO₂ 分壓對達西流施加反向阻力。
              隨著 CO₂ 從粉床逸散，背壓指數衰減至零。
              Darcy 有效驅動水頭修正為：h_eff = h − h_cap − h_gas(t)
        """
        return self.h_gas_0 * np.exp(-t_sec / self.tau_co2)

    # ── 幾何 ─────────────────────────────────────────────────────────────────
    def area(self, h):
        """錐形截面積 A(h) = π·(h·tanθ)² [m²]"""
        return np.pi * self._tan2 * h ** 2

    def volume(self, h: float) -> float:
        """錐體體積 V(h) = (π/3)·tan²θ·h³ [m³]"""
        return (np.pi / 3) * self._tan2 * h ** 3

    # ── 修正 [3][8] 有效滲透率（細粉遷移 × 顆粒溶脹）────────────────────────
    def k_eff(self, V_out, sat: float = 1.0):
        """
        綜合有效滲透率：細粉遷移（k_beta）× 顆粒溶脹（Kozeny-Carman）

        What: k_eff(V_out, sat) = k_mig(V_out) × k_kc(sat)
              k_mig = k0 / (1 + β_V·V_out)            [修正 3：細粉堵塞]
              k_kc  = (φ(sat)/φ₀)³·((1-φ₀)/(1-φ(sat)))²  [修正 8：溶脹]

        Why: 兩個機制完全獨立：
             - 細粉遷移：隨累積出液量增加（不可逆）
             - 顆粒溶脹：由飽和度驅動，悶蒸期就啟動
             解耦後，k_beta 只代表「細粉量」，delta_phi 只代表「纖維膨脹度」，
             讓參數的物理意義更純粹，擬合偏差更小。

        TODO: 加入攪動項：dk/dt = -beta_agit·Q_in·k（高 Q_in 時細粉遷移更快）
        """
        k_mig = self.k / (1.0 + self.k_beta * V_out)
        # Kozeny-Carman 溶脹修正
        phi_sw = self.phi - self.delta_phi * sat
        phi_sw = np.maximum(phi_sw, 1e-3 * self.phi)     # 防止數值奇異（φ→0 時 k→∞）
        kc = (phi_sw / self.phi)**3 * ((1.0 - self.phi) / (1.0 - phi_sw))**2
        return k_mig * kc

    def psi_eff(self, V_out) -> float:
        """
        旁路衰減修正：Ψ_eff(V) = Ψ0 / (1 + psi_beta·V_out)

        Why: 細粉同樣沉積於濾紙邊緣，逐漸堵塞肋骨旁路通道
             psi_beta < k_beta：旁路堵塞比粉層慢（流速較低，衝擊力小）
        """
        return self.psi / (1.0 + self.psi_beta * V_out)

    # ── 修正 [6] 熱力學方法 ────────────────────────────────────────────────────
    def mu_water(self, T_K: float) -> float:
        """
        Andrade 黏度模型：μ(T) = μ_ref·exp(γ·(1/T - 1/T_ref)) [Pa·s]

        Why: 溫度降低時黏度上升，Q_ext 變小；
             以固定 T_ref（93°C）作為校準基準，
             讓不同 T_brew 實驗的 μ 值可以相互比較。
        """
        return self.mu * np.exp(self.mu_gamma * (1.0 / T_K - 1.0 / self.T_ref))

    def k_ext_T(self, T_K: float) -> float:
        """
        Arrhenius 萃取速率縮放：k_ext(T) = k_ext_0·exp(Ea/R·(1/T_ref - 1/T))

        Why: 溫度下降 → 分子擴散減弱 → 萃取速率降低；
             以固定 T_ref（93°C）校準，確保不同 T_brew 的對比有物理意義。
             k_ext_coef 代表「93°C 下的標準萃取速率」。
        """
        return self.k_ext_coef * np.exp(
            self.Ea_ext / R_GAS * (1.0 / self.T_ref - 1.0 / T_K)
        )

    # ── 修正 [1][9] 達西萃取（C∞ 平滑過渡 + 毛細管壓門檻） ──────────────────
    def q_extract(self, h, k_val=None, T_K=None, t_sec: float = 0.0):
        """
        平滑達西萃取流量 [m³/s]，含溫度修正、毛細管壓門檻與 CO₂ 背壓。

        What: Q_ext(h,T,t) = Φ(T)·k·h_bed·h·smooth(h)·cap_factor(h,t)
              cap_factor 的截止水位 = h_cap + h_gas(t)  ← 修正 [9][14]
              h_gas(t) = h_gas_0 × exp(−t / τ_CO2)

        Why（修正 [14] CO₂ 背壓）:
             新鮮豆悶蒸時 CO₂ 分壓對達西流施加反向阻力，等效為額外背壓水頭。
             h_back(t) = h_cap + h_gas(t)：隨 CO₂ 逸散從 h_cap+h_gas_0 衰減至 h_cap。
             物理後果：早期（t < 45s）流量顯著受壓，復現「新鮮豆水位高但流速慢」。
        """
        if k_val is None:
            k_val = self.k
        if T_K is None:
            T_K = self.T_brew
        # 毛細管壓 + CO₂ 背壓合併截止：sigmoid 截止函數
        # 過渡寬度 = h_cap × 0.25（~1.25mm）；接近驟降但保持 C¹ 連續
        h_back = self.h_cap + self.h_gas(t_sec)
        cap_factor = 1.0 / (1.0 + np.exp(-(h - h_back) / (self.h_cap * 0.25)))
        phi_T = self.phi_darcy * (self.mu / self.mu_water(T_K))
        hb = self.h_bed
        smooth = hb * (1.0 - np.exp(-h / hb))       # 原始平滑過渡（對全 h）
        return phi_T * k_val * h * smooth * cap_factor

    def C_sat_T(self, T_K: float) -> float:
        """
        溫度相依的飽和濃度：C_sat(T) = C_sat_ref·(1 + α·(T - T_ref)) [g/L]

        Why: 溶解度為溫度正函數（吸熱溶解）；
             83°C 的萃取天花板比 99°C 低，復現冷萃 vs 熱沖的化學差異。
        """
        return self.C_sat * (1.0 + self.alpha_C_sat * (T_K - self.T_ref))

    # ── 修正 [7] 多組分萃取方法 ───────────────────────────────────────────────
    def k_ext_fast_T(self, T_K: float) -> float:
        """Fast 組分 Arrhenius 速率：Ea=15kJ/mol，低溫弱化不明顯"""
        return self.k_ext_fast * np.exp(self.Ea_fast / R_GAS * (1.0 / self.T_ref - 1.0 / T_K))

    def k_ext_slow_T(self, T_K: float) -> float:
        """Slow 組分 Arrhenius 速率：Ea=45kJ/mol，83°C 比 99°C 低 7×"""
        return self.k_ext_slow * np.exp(self.Ea_slow / R_GAS * (1.0 / self.T_ref - 1.0 / T_K))

    def C_sat_fast_T(self, T_K: float) -> float:
        """Fast 組分溫度相依平衡濃度"""
        return self.C_sat_fast * (1.0 + self.alpha_C_fast * (T_K - self.T_ref))

    def C_sat_slow_T(self, T_K: float) -> float:
        """Slow 組分溫度相依平衡濃度；alpha 較大，苦味跳變效應"""
        return self.C_sat_slow * (1.0 + self.alpha_C_slow * (T_K - self.T_ref))

    # ── 修正 [2][9] 旁路（消散型 + V 衰減 + μ(T) + 毛細管門檻） ──────────────
    def q_bypass(self, h, psi_val=None, T_K=None):
        """
        帶消散係數的旁路流量 [m³/s]，含溫度修正與毛細管壓門檻。

        What: Q_bp = Ψ·h_eff·min(h_eff/h_bed, 1)·(μ_ref/μ(T))
              h_eff = max(0, h - h_cap)

        Why（毛細管門檻）: 肋骨通道與濾床同樣受毛細管壓影響，
             低水位時旁路也停止，保持旁路比的物理一致性。
        Why（μ 縮放）: Poiseuille 流 Q ∝ 1/μ；與 Q_ext 同比例縮放，
             旁路「比例」由 h 主導，不被 T 扭曲（修正了 v5 的物理悖論）。
        """
        if psi_val is None:
            psi_val = self.psi
        if T_K is None:
            T_K = self.T_brew
        # 毛細管壓門檻（與 q_extract 一致的 sigmoid 截止，寬度 0.25）
        cap_factor = 1.0 / (1.0 + np.exp(-(h - self.h_cap) / (self.h_cap * 0.25)))
        factor = np.minimum(h / self.h_bed, 1.0)
        mu_scale = self.mu / self.mu_water(T_K)
        return psi_val * h * factor * mu_scale * cap_factor

    def q_total(self, h, k_val=None, psi_val=None, T_K=None, t_sec: float = 0.0):
        """總出水流量 [m³/s]"""
        return self.q_extract(h, k_val, T_K, t_sec) + self.q_bypass(h, psi_val, T_K)

    # ── k–M 聯動：研磨度工廠方法 ───────────────────────────────────────────
    @classmethod
    def for_grind(cls, k_target: float, base: "V60Params | None" = None) -> "V60Params":
        """
        以研磨度 k 為軸，聯動調整 max_EY 與 k_ext_coef。

        What: 返回以 k_target 為滲透率的新 V60Params：
              max_EY(k)     = max_EY_ref     × (k_ref / k)^alpha_EY
              k_ext_coef(k) = k_ext_coef_ref × (k_ref / k)^alpha_ext

        Why（物理耦合）:
              k ∝ d²（Kozeny-Carman）—— k 是粒徑的流體代理變數。
              磨細（k↓）同步帶來：
                1. 更多細胞壁破裂 → max_EY↑（可及溶質增加）
                2. 擴散路徑縮短  → k_ext↑（萃取速率加快）
              三者解耦時無法預測最佳研磨點；聯動後可掃描 k-EY 曲線找極值。

        Args:
            k_target : 目標滲透率 [m²]，代表研磨粗細
            base     : 參考基底（None → 使用預設中研磨參數）

        Returns:
            新的 V60Params，k / max_EY / k_ext_coef 均已按聯動公式修正。
        """
        if base is None:
            base = cls()
        ratio = base.k_ref / k_target
        return dataclasses.replace(
            base,
            k          = k_target,
            max_EY     = base.max_EY     * (ratio ** base.alpha_EY),
            k_ext_coef = base.k_ext_coef * (ratio ** base.alpha_ext),
        )

    @classmethod
    def for_roast(
        cls,
        profile: "RoastProfile",
        k_target: float | None = None,
        base: "V60Params | None" = None,
    ) -> "V60Params":
        """
        以烘焙度 RoastProfile 為軸，調整所有相關物理係數。

        What: 套用 profile 的組成/動力學/吸水特性至 base（或預設中研磨參數）；
              若提供 k_target，則額外套用 k-M 聯動（for_grind）。

        Why:  烘焙度與研磨度是正交的兩個自由度：
              - for_roast() 設定烘焙度的「基準面」（max_EY_ref, k_ext_ref...）
              - for_grind() 在該基準面上沿研磨度軸縮放
              兩者可單獨使用，或串聯使用。

        Args:
            profile  : RoastProfile 實例（推薦使用 RoastProfile.LIGHT/MEDIUM/DARK）
            k_target : 目標研磨滲透率 [m²]（None → 不改變 k，使用 base.k）
            base     : 參考基底（None → 使用預設中研磨參數）

        Returns:
            新的 V60Params，所有烘焙相關參數已更新；
            若 k_target 不為 None，則同時套用 k-M 聯動。
        """
        if base is None:
            base = cls()

        # 1. 套用烘焙度決定的參數（覆蓋 base 中對應欄位）
        roasted = dataclasses.replace(
            base,
            max_EY            = profile.max_EY,
            alpha_EY          = profile.alpha_EY,
            k_ext_coef        = base.k_ext_coef * profile.k_ext_factor,
            Ea_slow           = profile.Ea_slow,
            fast_fraction     = profile.fast_fraction,
            C_sat_slow        = profile.C_sat_slow,
            absorb_dry_ratio  = profile.absorb_dry_ratio,
            absorb_full_ratio = profile.absorb_full_ratio,
            h_gas_0           = profile.co2_pressure_m,   # 修正 [14]
        )

        # 2. 若指定研磨度，在已更新的烘焙基準上套用 k-M 聯動
        if k_target is not None:
            return cls.for_grind(k_target, base=roasted)
        return roasted


# ─────────────────────────────────────────────────────────────────────────────
#  注水協議
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class PourProtocol:
    """
    分段注水計畫。每個事件為 (開始時間[s], 水量[mL], 持續秒數[s])。
    """
    pours: List[Tuple[float, float, float]] = field(default_factory=list)

    @classmethod
    def standard_v60(cls) -> "PourProtocol":
        """標準三段式 V60（300mL，1:15 粉水比，20g 粉）"""
        return cls(pours=[
            (  0,  50,  5),
            ( 45, 150, 20),
            (100, 100, 15),
        ])

    @classmethod
    def single_pour(cls) -> "PourProtocol":
        return cls(pours=[(0, 300, 30)])

    def pour_rate(self, t: float) -> float:
        """瞬時注水流量 [m³/s]"""
        rate = 0.0
        for start, vol_ml, dur in self.pours:
            if start <= t < start + dur:
                rate += vol_ml / dur
        return rate * 1e-6

    def last_pour_end(self) -> float:
        """最後一注結束的時間 [s]"""
        return max(start + dur for start, _, dur in self.pours)
