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
K_B   = 1.380649e-23  # 波茲曼常數 [J/K]


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

    brew_temp_K: float
    # 建議沖煮水溫 [K]；淺焙偏高、深焙偏低，中焙取中間值

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
    brew_temp_K       = 365.15,  # 92°C：淺焙結構緻密，常用較高水溫
    absorb_dry_ratio  = 0.40,
    absorb_full_ratio = 1.20,
    co2_pressure_m    = 0.009,   # 9mm：淺焙 CO₂ 多，逸散慢
)

RoastProfile.MEDIUM = RoastProfile(
    name              = "medium",
    max_EY            = 0.30,   # Gagné: 中焙手沖上限 ~30%（舊值 0.28 偏保守）
    alpha_EY          = 0.15,
    k_ext_factor      = 1.00,
    Ea_slow           = 45000.0,
    fast_fraction     = 0.35,
    C_sat_slow        = 80.0,
    brew_temp_K       = 363.15,  # 90°C：中焙取淺/深焙之間的工程中值
    absorb_dry_ratio  = 0.50,
    absorb_full_ratio = 1.64,
    co2_pressure_m    = 0.001,   # 中焙保留小幅 CO₂ 背壓：較符合一般仍有新鮮度的現實狀況
)

RoastProfile.DARK = RoastProfile(
    name              = "dark",
    max_EY            = 0.32,   # Gagné: 深焙細胞壁破壞嚴重，上限 30–32%；取上界 0.32
    alpha_EY          = 0.20,
    k_ext_factor      = 1.30,
    Ea_slow           = 38000.0,
    fast_fraction     = 0.25,
    C_sat_slow        = 100.0,
    brew_temp_K       = 361.15,  # 88°C：深焙細胞壁破裂、苦味易出，常用較低水溫
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
    psi: float = 2.0e-4         # 旁路係數 Ψ [m²/s]
    # 校準更新：原值使標準配方旁路幾乎為零，不符一般現實 V60；
    # 提高兩個數量級後，中研磨旁路回到 ~1-2%，細研磨也不再過度 choke

    # ── 修正 [1][2] 粉層高度 ──────────────────────────────────────────────────
    h_bed: float = 0.048        # 粉層高度 [m]；20g ≈ 48mm

    # ── 修正 [3] 細粉堵塞 ─────────────────────────────────────────────────────
    k_beta: float = 3e3         # 堵塞係數 β [m⁻³]；k(V) = k0/(1+β·V_out)

    # ── 旁路衰減 ──────────────────────────────────────────────────────────────
    psi_beta: float = 1e3
    # 旁路衰減係數 [m⁻³]；Ψ_eff(V) = Ψ0/(1+psi_beta·V_out)
    # Why: 細粉同樣會沉積在濾紙邊緣，降低肋骨旁路滲透率
    #      psi_beta < k_beta（旁路堵塞比粉層慢，因為流速較低）

    bypass_onset_head: float = 0.003
    # 自由水柱高於粉床頂部後，旁路開始明顯啟動的門檻 [m]
    # Why: 低水位仍近似無旁路，但不把啟動點壓到只剩最高水位末端才出現

    bypass_onset_width: float = 0.008
    # 旁路啟動 sigmoid 的過渡寬度 [m]；控制「低水位近零、高水位漸進打開」

    # ── 修正 [4][13] 悶蒸吸水 ────────────────────────────────────────────────
    dose_g: float = 20.0
    # 粉重 [g]。

    absorb_dry_ratio: float = 0.5
    # 零出液吸水率 [mL/g]；V_dry = dose_g × absorb_dry_ratio
    # Why（修正 [13]）：新鮮豆 CO₂ 仍殘留於微孔，有效吸水起點僅 ~0.5mL/g
    #      舊值 1.0mL/g 高估「悶蒸零出液」時長（Rao & Fuller 2018 實測中值 0.4–0.6）

    absorb_full_ratio: float = 1.64
    # 完全飽和吸水率 [mL/g]；V_full = dose_g × absorb_full_ratio
    # Why（校準更新）：中研磨 V60 要滿足 LRR≈2.2 時，1.3mL/g 偏低；
    #      提高至 1.64mL/g 後，標準 1:17 配方的 LRR 會落在 ~2.2。
    #      深焙/脫氣豆可再調高至 ~1.7mL/g 以上。

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

    max_EY: float = 0.30
    # 最大萃取率（可溶物佔粉重的比例）
    # Why: 決定初始固相溶質量 M_sol_0 = dose_g × max_EY [g]
    #      當 M_sol → 0 時 C_sat_eff → 0，自然終止萃取，修正 C_bed 末端暴增
    # Gagné 實驗依據：手沖可萃取上限 30–32%；中焙取保守值 0.30
    # 舊值 0.28 來自 SCA 測試豆校準，偏保守；修正為物理上限中位估計

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

    mu_fit_log_coeffs: tuple[float, float, float, float] = (
        -8.17297841e-07,
         2.32004852e-04,
        -3.36945065e-02,
         5.90898359e-01,
    )
    # 由使用者提供圖上的「相對黏滯度 vs 溫度」紅線做 log-cubic 擬合：
    #   ln(mu_rel) = c3*T^3 + c2*T^2 + c1*T + c0, T 單位為 °C
    # 節點（肉眼讀圖）約為：
    #   (0,1.80), (10,1.33), (20,1.00), (30,0.79),
    #   (40,0.64), (60,0.47), (80,0.35), (100,0.28)
    # RMSE ≈ 0.006（相對黏滯度）

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

    # ── 修正 [15] 流速依賴傳質係數（邊界層 Sh 效應）────────────────────────────
    k_diff_ratio: float = 0.1
    # 靜置/流動 k_ext 比值；Q_ext=0 時 k_ext_eff = k_diff_ratio × k_ext_T(T)
    # Why: 無流動時邊界層加厚，Sherwood 數降低 ~3-10×；
    #      0.1 = 物理合理估計（靜置僅靠分子擴散，效率約為對流狀態的 10%）
    #      量化影響：60s 悶蒸 EY 貢獻從 +1.31% 降至 ~0.3-0.5%（符合 Gagné 觀測邊界）

    k_ext_fast_mult: float = 2.3
    # Fast 組分萃取速率倍率（相對於 k_ext_coef 的乘數）
    # Why: flow_factor 引入後，整場平均 k_ext 整體被壓低；
    #      Fast（小分子、酸甜）更依賴對流更新，需要較大補償（+15%：2.0 → 2.3）
    #      使標準沖煮 EY 回到 SCA 目標 18–22% 並保持 Fast/Slow 相對動力學比例

    k_ext_slow_mult: float = 0.525
    # Slow 組分萃取速率倍率（相對於 k_ext_coef 的乘數）
    # Why: Slow（苦味大分子）在靜置時仍有緩慢累積；補償幅度保守（+5%：0.5 → 0.525）
    #      避免長悶蒸（>60s）下苦味組分過度萃取，保留 k_diff_ratio 的抑制效果

    Q_half: float = 3e-7
    # Hill 方程半飽和流速 [m³/s]（= 0.3 mL/s）
    # Why: 邊界層過渡的物理臨界點 ≈ Pe=1，即 v_crit = D/d_p ≈ 1.7e-6 m/s
    #      對應體積流量 ~0.005 mL/s；加上注水擾動效應，工程值取 0.3 mL/s
    #      flow_factor = k_diff_ratio + (1-k_diff_ratio) × Q_ext/(Q_ext+Q_half)
    #      Q_ext = 0.3 mL/s 時 flow_factor = 0.55；Q_ext = 1.5 mL/s 時 = 0.85
    #      舊設 Q_half=1 mL/s 錯誤：把正常滴濾（1-2 mL/s）誤判為半靜置狀態

    # ── 修正 [16] Darcy 毛細驅動飽和（Capillary-driven imbibition）────────────
    tau_cap_ref: float = 10.0
    # 毛細驅動飽和特徵時間 [s]，以 T_ref=93°C 為錨點
    # Why: 乾燥粉床在 Darcy 毛細壓力驅動下自主潤濕；物理公式：
    #      κ(T) ∝ γ(T)/μ(T)（Darcy 毛細通量，Gagné 圖實驗驗證）
    #      dsat/dt|cap = (1-sat) / τ_cap(T)；τ_cap(T) = τ_cap_ref / κ_ratio(T)
    #      τ_cap_ref=10s → 93°C 時純毛細驅動 9s 內達到 ~59% 飽和
    #      高溫（93°C）比低溫（20°C）快 2.8×，復現「高溫水入粉快」的物理現象
    #      注：此項與液壓填充（Q_in/V_absorb）疊加，不是取代

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

    delta_phi_pressure: float = 0.012
    # 壓差造成的額外孔隙率降幅；隨自由水頭增大而上升，排水後可逆恢復

    fine_radius_ratio: float = 0.12
    # 細粉代表半徑相對 D10 的比例；供拖曳力診斷使用

    darcy_capillary_c0: float = 0.16663265
    # 已浸濕床層的 Darcy 毛細係數在 0°C 的截距
    # 校準點：a(2°C)=0.18, a(100°C)=0.835

    darcy_capillary_c1: float = 0.00668367
    # 已浸濕床層的 Darcy 毛細係數斜率 [1/°C]
    # 線性式：a(T_C) = 0.16663265 + 0.00668367 * T_C

    darcy_capillary_gain: float = 0.1
    # Darcy 毛細係數對濕床通量的影響強度；作為無因次增益乘子
    # 校準更新：壓力頭收支版 q_extract 下，只保留小幅濕床毛細增益，
    # 避免把通量推得過快而造成 TDS/EY 偏低

    # ── 修正 [9] 毛細管壓門檻（滴濾模式）──────────────────────────────────
    h_cap: float = 0.003

    # ── 修正 [14] CO₂ 背壓（Gas-trapping，新鮮豆悶蒸阻力）─────────────────
    h_gas_0: float = 0.001
    # CO₂ 背壓初始等效水頭 [m]
    # Why: 新鮮豆子（烘焙 7 天內）悶蒸時 CO₂ 分壓 0.5–1.5 bar 對向下達西流施加反向阻力。
    #      等效於水頭修正：h_eff = h - h_cap - h_gas(t)
    #      h_gas(t) = h_gas_0 × exp(−t / τ_CO2)，隨 CO₂ 逸散指數衰減。
    #      此項解釋「新鮮豆水位高但流速慢」的 Gas-trapping 現象。
    #      預設中研磨基準保留 1mm 小幅背壓：對一般仍有新鮮度的豆況更合理；
    #      新鮮豆/淺焙再透過 RoastProfile 額外拉高

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

    # ── 顆粒幾何 / PSD（新增：粒徑、殼層、碎形）──────────────────────────────
    eta_porosity: float = 3.0
    # 空隙率-滲透率指數：k ≈ f_s·D10²·φ^η；典型多孔介質常見值 ~3

    f_sp: float = 0.015
    # 粉床形狀/壓實經驗係數；以中研磨 D10 對應 k≈6e-11 m² 為校準錨點

    fractal_exp: float = 2.5
    # 碎形破碎指數律：N(a)/N(b) = (a/b)^(-2.5)

    particle_d_min: float = 40e-9
    # 最小粒徑下限 [m]；避免碎形分佈在 d→0 發散

    shell_thickness: float = 200e-6
    # 可萃取外層厚度 [m]；可及可溶物質量 ∝ 外層殼層體積

    shape_surface_gain: float = 0.55
    # 大顆粒偏長型時的額外表面積倍率上限；小顆粒接近球形 → 倍率趨近 1

    shape_growth_exp: float = 0.70
    # 粒徑增大時偏離球形的成長冪次；控制表面積增幅的平滑程度

    nu_p_fast: float = 1.1e11
    # Einstein-Smoluchowski mobility：Fast 組分 D = ν_p k_B T

    nu_p_slow: float = 4.5e10
    # Slow 組分 mobility 較低，反映大分子/苦味組分擴散較慢

    def __post_init__(self):
        self._tan  = np.tan(np.radians(self.half_angle_deg))
        self._tan2 = self._tan ** 2
        # 達西係數基值 Φ_ref = π·tan²θ·ρg/μ_ref [m⁻¹s⁻¹]
        # Why: T 相依版本在 q_extract 中按 μ(T)/μ_ref 縮放
        self.phi_darcy = np.pi * self._tan2 * RHO * G / self.mu  # 避免與孔隙率 phi 重名
        # 悶蒸兩階段門檻（修正 [13]：CO₂排氣修正吸水率）
        self._V_dry  = self.dose_g * self.absorb_dry_ratio  * 1e-6  # [m³]
        self._V_full = self.dose_g * self.absorb_full_ratio * 1e-6  # [m³]
        self.V_absorb = self._V_full - self._V_dry  # 可吸收水量 [m³]（毛細飽和 ODE 分母）
        # 粉層滯留水量（孔隙體積）
        self.V_bed    = (np.pi / 3) * self._tan2 * self.h_bed**3  # 粉床幾何體積 [m³]
        self.V_liquid = self.phi * self.V_bed                      # 孔隙水量 [m³]
        # 顆粒子模型：從當前 k 反推 D10，再生成碎形 PSD / 殼層可及性 / 形狀面積倍率
        self.D10 = np.sqrt(max(self.k, 1e-18) / max(self.f_sp * self.phi**self.eta_porosity, 1e-18))
        self.k_from_D10 = self.f_sp * (self.D10 ** 2) * (self.phi ** self.eta_porosity)
        ref_D10 = np.sqrt(max(self.k_ref, 1e-18) / max(self.f_sp * self.phi**self.eta_porosity, 1e-18))
        ref_particle = self._particle_stats(ref_D10)
        particle = self._particle_stats(self.D10)
        self.surface_area_spec = particle["surface_area"]
        self.ref_surface_area_spec = ref_particle["surface_area"]
        self.surface_area_ratio = self.surface_area_spec / max(self.ref_surface_area_spec, 1e-12)
        self.shell_fraction_abs = particle["shell_fraction"]
        self.ref_shell_fraction_abs = ref_particle["shell_fraction"]
        self.shell_accessibility_ratio = self.shell_fraction_abs / max(self.ref_shell_fraction_abs, 1e-12)
        self.diffusion_path_m = particle["diffusion_path_m"]
        self.ref_diffusion_path_m = ref_particle["diffusion_path_m"]
        # 固相溶質耗盡模型
        self.M_sol_0 = self.dose_g * self.max_EY * self.shell_accessibility_ratio
        # shell_accessibility_ratio 已對中研磨參考態做正規化：
        #   >1 代表較多外層殼層體積、可及溶質增加
        #   <1 代表大顆粒占比上升，更多溶質困在核心
        # κ = C_sat_0 / M_sol_0 [L⁻¹]；C_sat_eff(t) = κ·M_sol(t)
        # 單位：[g/L] / [g] = [1/L]（與 SI：k_ext[m³/s]×C_sat[kg/m³] 一致）
        # dose_g=0（用於 baseline 對比）時退化為純流體模型，不需萃取
        # 保留舊 kappa（單組分，backward compat）
        self.kappa = (self.C_sat / self.M_sol_0) if self.M_sol_0 > 0 else 0.0
        # 多組分初始質量（修正 [7]）
        self.M_fast_0 = self.M_sol_0 * self.fast_fraction
        self.M_slow_0 = self.M_sol_0 * (1.0 - self.fast_fraction)
        # Noyes-Whitney 參考校準：以中研磨參考幾何反推無因次效率因子
        # k_NW = η * A_eff * D / L，其中 η 吸收 tortuosity / 未建模阻力 / 單位校準
        A_ref = self.ref_surface_area_spec * (1.0 - self.phi) * self.V_bed * self.ref_shell_fraction_abs
        L_fast_ref = self.noyes_whitney_length(slow=False, use_reference=True)
        L_slow_ref = self.noyes_whitney_length(slow=True,  use_reference=True)
        D_fast_ref = self.diffusion_coeff(self.T_ref, slow=False)
        D_slow_ref = self.diffusion_coeff(self.T_ref, slow=True)
        nw_fast_ref = A_ref * D_fast_ref / max(L_fast_ref, 1e-18)
        nw_slow_ref = A_ref * D_slow_ref / max(L_slow_ref, 1e-18)
        self.nw_eta_fast = (self.k_ext_coef * self.k_ext_fast_mult) / max(nw_fast_ref, 1e-18)
        self.nw_eta_slow = (self.k_ext_coef * self.k_ext_slow_mult) / max(nw_slow_ref, 1e-18)
        # κ for each component（溫度相依，在方法中計算；此處存 ref 值）
        self.kappa_fast = (self.C_sat_fast / self.M_fast_0) if self.M_fast_0 > 0 else 0.0
        self.kappa_slow = (self.C_sat_slow / self.M_slow_0) if self.M_slow_0 > 0 else 0.0
        # 咖啡粉等效熱容體積：V_equiv = m_coffee × Cp_coffee / (ρ_water × Cp_water)
        # Why: 悶蒸時乾粉（常溫）吸收熱水熱量，換算為等效水體積後加入熱動方程分母
        #      Cp_water ≈ 4180 J/(kg·K)；dose_g [g] = dose_g×1e-3 [kg]
        self.V_equiv_coffee = (self.dose_g * 1e-3 * self.Cp_coffee) / (RHO * 4180.0)  # [m³]

    def _particle_stats(self, D10_target: float) -> dict:
        """
        由目標 D10 建立截斷碎形 PSD，回傳殼層可及性與表面積統計。

        What:
          1. 假設體積 D10 約為 d_max 的 21.5%，據此反推 d_max
          2. 生成 N(d) ∝ d^-2.5 的對數粒徑分佈
          3. 小顆粒近球形，大顆粒表面積倍率較大
          4. 以 200 μm 外層殼層估算可及溶質比例

        Why:
          這讓 D10、碎形 PSD、形狀與 200 μm 殼層真正進入模型，
          而不是只停留在註解。
        """
        D10_target = max(D10_target, self.particle_d_min)
        d10_to_dmax = 0.1 ** (2.0 / 3.0)  # 對 volume-weighted d^-2.5 分佈，D10 ≈ 0.215 * d_max
        d_max = max(D10_target / d10_to_dmax, 1.05 * D10_target)
        diam = np.logspace(np.log10(self.particle_d_min), np.log10(d_max), 96)
        counts = (diam / d_max) ** (-self.fractal_exp)
        vol = counts * diam**3
        mass_w = vol / np.sum(vol)

        size_norm = np.clip(diam / max(D10_target, self.particle_d_min), 0.0, None)
        shape_mult = 1.0 + self.shape_surface_gain * (size_norm / (1.0 + size_norm)) ** self.shape_growth_exp
        total_surface = np.sum(counts * np.pi * diam**2 * shape_mult)
        total_volume = np.sum(counts * (np.pi / 6.0) * diam**3)
        surface_area = total_surface / max(total_volume, 1e-18)

        shell_depth = np.minimum(self.shell_thickness, 0.5 * diam)
        core_radius = np.maximum(0.5 * diam - shell_depth, 0.0)
        shell_fraction = 1.0 - (core_radius / np.maximum(0.5 * diam, 1e-12)) ** 3
        shell_fraction = float(np.sum(mass_w * shell_fraction))

        diffusion_path = float(np.sum(mass_w * core_radius))
        return {
            "surface_area": float(surface_area),
            "shell_fraction": shell_fraction,
            "diffusion_path_m": diffusion_path,
        }

    def saturation(self, V_poured: float) -> float:
        """
        累積注水量對飽和目標的平滑上限 sat_target ∈ [0, 1]。C¹ 連續。

        What: cubic Hermite smooth-step：
              x = clamp((V_poured - V_dry) / (V_full - V_dry), 0, 1)
              sat_target = x² × (3 - 2x)

        Why（修正 [10]）: 原分段線性版本在 V=V_dry 和 V=V_full 有一階不連續（C⁰）。
             這兩個轉折點在飽和驅動項中直接影響 dh/dt，
             造成 ODE 積分器在轉折瞬間遭遇非光滑項，引發數值衝擊（spike）。
             Cubic Hermite 在兩端都有 dsat/dV=0，保持 C¹ 連續。
        """
        if V_poured <= self._V_dry:
            return 0.0
        elif V_poured >= self._V_full:
            return 1.0
        x = (V_poured - self._V_dry) / (self._V_full - self._V_dry)
        return x * x * (3.0 - 2.0 * x)   # cubic Hermite: C¹ at both ends

    def sigma_water(self, T_K: float) -> float:
        """
        水的表面張力近似 [N/m]。

        What: 以 93°C 為基準做一階線性近似，避免在 0D 模型中引入過重的物性表。
              σ(T) = σ_ref + a·(T - T_ref)

        Why: Lucas-Washburn / Darcy 毛細潤濕的速度標度與 σ/μ 成正比；
             雖然 σ 對 T 的敏感度小於 μ，但不能完全忽略。
        """
        sigma_ref = 0.060  # 93°C 附近表面張力量級
        slope = -1.5e-4    # dσ/dT < 0：溫度升高時表面張力下降
        return max(1e-3, sigma_ref + slope * (T_K - self.T_ref))

    def tau_cap_T(self, T_K: float) -> float:
        """
        溫度相依的毛細潤濕時間常數 [s]。

        What: τ_cap(T) = τ_ref / κ_ratio，κ_ratio ∝ (σ/μ) / (σ_ref/μ_ref)

        Why: Lucas-Washburn 標度 l ~ sqrt((rσ/μ)t)；
             高溫時 μ 下降的效應大於 σ 下降，因此潤濕加快、τ_cap 變小。
        """
        sigma_ratio = self.sigma_water(T_K) / self.sigma_water(self.T_ref)
        mu_ratio = self.mu_water(T_K) / self.mu
        kappa_ratio = sigma_ratio / max(mu_ratio, 1e-12)
        return self.tau_cap_ref / max(kappa_ratio, 1e-6)

    def darcy_capillary_coeff(self, T_K: float) -> float:
        """
        已浸濕床層的 Darcy 毛細係數（線性溫度關係）。

        What: 依據使用者提供的圖，採線性近似：
              a(T_C) = a0 + a1 * T_C
              0°C  約 0.18，100°C 約 0.80

        Why: 乾粉浸濕前沿可用 Lucas-Washburn；
             但床層一旦完成浸濕，毛細傳輸改以 Darcy 型係數描述，
             並依圖使用線性溫度關係，而不是 sqrt(t) 前沿律。
        """
        T_C = np.clip(T_K - 273.15, 0.0, 100.0)
        return self.darcy_capillary_c0 + self.darcy_capillary_c1 * T_C

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
    def phi_effective(self, sat: float = 1.0, h: float | None = None):
        """
        綜合有效孔隙率：溶脹（與 sat 有關）+ 壓差壓實（與 h 有關，可逆）
        """
        phi_sw = self.phi - self.delta_phi * sat
        if h is not None:
            head_ratio = np.clip(max(h - self.h_bed, 0.0) / max(self.h_bed, 1e-12), 0.0, 1.0)
            phi_sw -= self.delta_phi_pressure * head_ratio
        return max(phi_sw, 1e-3 * self.phi)

    def fine_radius(self) -> float:
        """代表性細粉半徑 [m]。"""
        return 0.5 * self.D10 * self.fine_radius_ratio

    def noyes_whitney_area(self, use_reference: bool = False) -> float:
        """
        顯式 Noyes-Whitney 介面面積 A_eff [m²]。

        What: A_eff = a_s * V_solid * f_shell
              a_s     : PSD/形狀加權後的比表面積 [1/m]
              V_solid : 粉床固體體積
              f_shell : 200 μm 外層殼層可及比例
        """
        a_s = self.ref_surface_area_spec if use_reference else self.surface_area_spec
        f_shell = self.ref_shell_fraction_abs if use_reference else self.shell_fraction_abs
        V_solid = (1.0 - self.phi) * self.V_bed
        return a_s * V_solid * f_shell

    def noyes_whitney_length(self, slow: bool = False, use_reference: bool = False) -> float:
        """
        顯式 Noyes-Whitney 擴散路徑長度 L_eff [m]。

        Why: Fast 受外層殼層控制；Slow 需穿透更深核心，因此路徑較長。
        """
        path = self.ref_diffusion_path_m if use_reference else self.diffusion_path_m
        shell_floor = 0.5 * self.shell_thickness
        if slow:
            return max(self.shell_thickness, 1.35 * path, shell_floor)
        return max(shell_floor, path)

    def k_eff(self, V_out, sat: float = 1.0, h: float | None = None):
        """
        綜合有效滲透率：細粉遷移（k_beta）× 顆粒溶脹（Kozeny-Carman）× 壓差壓實

        What: k_eff(V_out, sat, h) = k_mig(V_out) × k_kc(sat, h)
              k_mig = k0 / (1 + β_V·V_out)            [修正 3：細粉堵塞]
              k_kc  = (φ_eff/φ₀)³·((1-φ₀)/(1-φ_eff))²
              φ_eff = φ₀ - Δφ_sat·sat - Δφ_p·head_ratio

        Why: 兩個機制完全獨立：
             - 細粉遷移：隨累積出液量增加（不可逆）
             - 顆粒溶脹：由飽和度驅動，悶蒸期就啟動
             - 壓差壓實：由床頂/床底壓差驅動，排水後可逆恢復
             解耦後，k_beta 只代表「細粉量」，delta_phi 只代表「纖維膨脹度」，
             讓參數的物理意義更純粹，擬合偏差更小。

        TODO: 加入攪動項：dk/dt = -beta_agit·Q_in·k（高 Q_in 時細粉遷移更快）
        """
        k_mig = self.k / (1.0 + self.k_beta * V_out)
        phi_sw = self.phi_effective(sat, h)
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
        依圖擬合的水黏度曲線：μ(T) = μ_ref × μ_rel(T) / μ_rel(T_ref) [Pa·s]

        What:
          1. 先以圖上紅色相對黏滯度曲線擬合 ln(mu_rel(T_C))
          2. 再用 T_ref 正規化，保證 μ(T_ref) = self.mu

        Why:
          使用者指定要以附圖為準，而不是直接套 Andrade 理論式。
          這讓模型中的流速溫度效應直接對齊圖上的經驗曲線。
        """
        T_C = np.clip(T_K - 273.15, 0.0, 100.0)
        T_ref_C = self.T_ref - 273.15
        mu_rel = np.exp(np.polyval(self.mu_fit_log_coeffs, T_C))
        mu_rel_ref = np.exp(np.polyval(self.mu_fit_log_coeffs, T_ref_C))
        return self.mu * mu_rel / max(mu_rel_ref, 1e-12)

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

    def diffusion_coeff(self, T_K: float, slow: bool = False) -> float:
        """
        Einstein-Smoluchowski 擴散係數：D = ν_p k_B T
        """
        mobility = self.nu_p_slow if slow else self.nu_p_fast
        return mobility * K_B * T_K

    def internal_diffusion_factor(self, t_sec: float, T_K: float, slow: bool = False) -> float:
        """
        顆粒內部擴散近似：c(r,t) ~ exp(-r² / 4Dt)

        What: 以 PSD 加權後的有效殘餘核心半徑作為擴散距離，
              將粒內 diffusion 對可及速率的抑制作為 0–1 乘子。

        Why: 0D 模型無法直接解球坐標 PDE，但仍需要把「核心溶質傳得較慢」
             這件事折進速率方程。
        """
        t_eff = max(t_sec, 0.5)
        D_eff = max(self.diffusion_coeff(T_K, slow=slow), 1e-18)
        path = self.diffusion_path_m * (1.35 if slow else 1.0)
        return float(np.exp(-(path ** 2) / max(4.0 * D_eff * t_eff, 1e-18)))

    # ── 修正 [1][9] 達西萃取（C∞ 平滑過渡 + 毛細管壓門檻） ──────────────────
    def q_extract(self, h, k_val=None, T_K=None, t_sec: float = 0.0, sat=None):
        """
        壓力頭收支版達西萃取流量 [m³/s]。

        What:
            Q_ext = Φ(T) · k · L_bed · h_eff
            h_eff = softplus_like(h - h_cap - h_gas(t) + h_cap,wet)

            其中：
            - h                 : 重力驅動水頭
            - h_cap             : 低水位毛細截止頭
            - h_gas(t)          : CO₂ 背壓等效水頭
            - h_cap,wet         : 已浸濕床層的額外毛細驅動水頭

        Why:
            把所有流動機制都放回「有效壓力頭」的同一語言中，避免：
            1. 用 smooth(h) 和 cap_factor 對低水位重複抑制
            2. 用乘法增益難以判斷各機制究竟是在改變驅動頭，還是改變介質性質

        TODO:
            未飽和期的相對滲透率 kr(sat) 尚未顯式建模；
            目前仍以 h_eff 的壓力頭截止為主，而非完整 unsaturated Darcy。
        """
        if k_val is None:
            k_val = self.k
        if T_K is None:
            T_K = self.T_brew
        phi_T = self.phi_darcy * (self.mu / self.mu_water(T_K))

        # 有效驅動頭 = 重力頭 - 毛細截止 - CO₂ 背壓 + 濕床毛細增益
        h_threshold = self.h_cap + self.h_gas(t_sec)
        if sat is None:
            wet_gate = 0.0
        else:
            wet_gate = np.clip((sat - 0.95) / 0.05, 0.0, 1.0)
        # 已浸濕床層的毛細附加頭不應只用 h_cap（毫米級）量級，
        # 而應對應整段濕床中的平均毛細驅動尺度；工程上取 0.5 * h_bed。
        wet_span = np.clip(h / max(self.h_bed, 1e-12), 0.0, 1.0)
        h_cap_wet = (
            self.darcy_capillary_gain
            * self.darcy_capillary_coeff(T_K)
            * (0.5 * self.h_bed * wet_span)
            * wet_gate
        )
        raw_head = h - h_threshold + h_cap_wet

        # 平滑正部：h_eff = raw_head * sigmoid(raw_head / eps)
        # Why: 保持 head≈threshold 附近可微，避免 solve_ivp 在截止點抖動。
        eps = max(self.h_cap * 0.25, 1e-6)
        gate = 1.0 / (1.0 + np.exp(-raw_head / eps))
        h_eff = raw_head * gate

        return phi_T * k_val * self.h_bed * np.maximum(h_eff, 0.0)

    def C_sat_T(self, T_K: float) -> float:
        """
        溫度相依的飽和濃度：C_sat(T) = C_sat_ref·(1 + α·(T - T_ref)) [g/L]

        Why: 溶解度為溫度正函數（吸熱溶解）；
             83°C 的萃取天花板比 99°C 低，復現冷萃 vs 熱沖的化學差異。
        """
        return self.C_sat * (1.0 + self.alpha_C_sat * (T_K - self.T_ref))

    # ── 修正 [7] 多組分萃取方法 ───────────────────────────────────────────────
    def k_ext_fast_T(self, T_K: float, t_sec: float = 0.0) -> float:
        """
        Fast 組分顯式 Noyes-Whitney 速率：k = η * A_eff * D / L_eff

        Why: 將原本等效的 k_ext 改寫成顯式 A·D/L 形式：
             - A_eff 來自 PSD/形狀/外層殼層
             - D 來自 Einstein-Smoluchowski
             - L_eff 代表外層殼層到核心的平均擴散距離
             另外保留 Arrhenius 與粒內 diffusion 因子，作為咖啡細胞壁阻力修正。
        """
        area = self.noyes_whitney_area()
        length = self.noyes_whitney_length(slow=False)
        D_eff = self.diffusion_coeff(T_K, slow=False)
        arr = np.exp(self.Ea_fast / R_GAS * (1.0 / self.T_ref - 1.0 / T_K))
        return self.nw_eta_fast * area * D_eff / max(length, 1e-18) \
            * arr * self.internal_diffusion_factor(t_sec, T_K, slow=False)

    def k_ext_slow_T(self, T_K: float, t_sec: float = 0.0) -> float:
        """Slow 組分顯式 Noyes-Whitney 速率：k = η * A_eff * D / L_eff"""
        area = self.noyes_whitney_area()
        length = self.noyes_whitney_length(slow=True)
        D_eff = self.diffusion_coeff(T_K, slow=True)
        arr = np.exp(self.Ea_slow / R_GAS * (1.0 / self.T_ref - 1.0 / T_K))
        return self.nw_eta_slow * area * D_eff / max(length, 1e-18) \
            * arr * self.internal_diffusion_factor(t_sec, T_K, slow=True)

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

        What: Q_bp = Ψ·h_free·shape(h_free)·activation(h_free)·(μ_ref/μ(T))
              h_free = max(0, h - h_bed)

        Why（低水位近零）:
             當自由水柱還很低時，水主要穿過粉床而非沿濾紙肋骨形成穩定旁路；
             因此旁路應接近零，而不是只因總水位 > 0 就線性出現。
        Why（高水位打開）:
             當自由水柱高於粉床頂部一段距離後，沿壁面/肋骨的偏流路徑才會快速形成，
             用 sigmoid 啟動函數可平滑表現這個轉折。
        Why（μ 縮放）: Poiseuille 流 Q ∝ 1/μ；與 Q_ext 同比例縮放，
             旁路「比例」由 h 主導，不被 T 扭曲（修正了 v5 的物理悖論）。
        """
        if psi_val is None:
            psi_val = self.psi
        if T_K is None:
            T_K = self.T_brew
        # 毛細管壓門檻（與 q_extract 一致的 sigmoid 截止，寬度 0.25）
        cap_factor = 1.0 / (1.0 + np.exp(-(h - self.h_cap) / (self.h_cap * 0.25)))
        h_free = np.maximum(h - self.h_bed, 0.0)
        activation = 1.0 / (1.0 + np.exp(-(h_free - self.bypass_onset_head) / self.bypass_onset_width))
        shape = np.minimum(h_free / max(0.5 * self.h_bed, 1e-12), 1.0)
        mu_scale = self.mu / self.mu_water(T_K)
        return psi_val * h_free * shape * activation * mu_scale * cap_factor

    def q_total(self, h, k_val=None, psi_val=None, T_K=None, t_sec: float = 0.0, sat=None):
        """總出水流量 [m³/s]"""
        return self.q_extract(h, k_val, T_K, t_sec, sat=sat) + self.q_bypass(h, psi_val, T_K)

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
            T_brew            = profile.brew_temp_K,
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
        """標準三段式 V60（340mL，1:17 粉水比，20g 粉）"""
        return cls(pours=[
            (  0,  60,  6),
            ( 45, 170, 23),
            (100, 110, 16),
        ])

    @classmethod
    def single_pour(cls) -> "PourProtocol":
        return cls(pours=[(0, 300, 30)])

    @classmethod
    def my_recipe(cls) -> "PourProtocol":
        """
        實測五段式 V60（IMG_3244.mov，300mL，20g 粉，93°C）。

        數據來源：影片逐秒電子秤讀數，以秤上計時器為基準。
        注意：注水期間秤重含動能干擾，暫停期間數值才代表靜態液量。

        段次  開始(s)  水量(mL)  持續(s)  流速(mL/s)
        Bloom    0       47       9        5.2
        Pour2   30       75      13        5.8
        Pour3   52       49       8        6.1
        Pour4   71       71       9        7.9
        Pour5   97       62       8        7.8
        合計            304 ≈ 300mL
        """
        return cls(pours=[
            (  0,  47,  9),   # 悶蒸：0–9s，~47mL
            ( 30,  75, 13),   # 第二注：30–43s，~75mL
            ( 52,  49,  8),   # 第三注：52–60s，~49mL
            ( 71,  71,  9),   # 第四注：71–80s，~71mL
            ( 97,  62,  8),   # 第五注：97–105s，~62mL
        ])

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
