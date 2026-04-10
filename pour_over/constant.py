"""
pour_over.constant — 可量測固定輸入與物理常數
==============================================

What:
    集中 V60 主模型中「物理上可量測、應固定」的常數與輸入欄位。

Why:
    這些量不應混入 closure / fitting 旋鈕，否則 `params.py` 會同時承擔
    幾何量、量測輸入、物理常數與可標定參數，模組責任會失焦。
    將其獨立後，`V60Params` 可以只保留模型假設與少量可調參數，
    同時又維持既有 dataclass API 相容性。
"""

from dataclasses import dataclass

# ── 物理常數 ──────────────────────────────────────────────────────────────────
RHO = 1000.0  # 水密度 [kg/m³]
G = 9.81  # 重力加速度 [m/s²]
H_MIN = 1e-4  # 最低有效水位（避免 A(h)→0 除以零）[m]
R_GAS = 8.314  # 理想氣體常數 [J/(mol·K)]，用於 Arrhenius k_ext(T)
K_B = 1.380649e-23  # 波茲曼常數 [J/K]


@dataclass
class V60Constant:
    """
    V60 模型的固定物理輸入。

    What:
        定義濾杯幾何、量測環境、硬體熱容與 measured PSD 入口等固定欄位。

    Why:
        這些量應該來自量測、實驗設定或材料性質，而不是交由 optimizer
        當成補償其他 closure 缺項的自由旋鈕。
    """

    half_angle_deg: float = 30.0
    # V60 圓錐半角 [deg]；幾何固定量

    mu: float = 3.0e-4
    # 參考溫度下的水動力黏度 [Pa·s]；供 Darcy 基準縮放使用

    h_bed: float = 0.048
    # 粉層高度 [m]；量測擬合時應以實測覆寫

    dose_g: float = 20.0
    # 粉重 [g]

    T_brew: float = 366.15
    # 初始沖煮水溫 [K]

    T_ref: float = 366.15
    # 黏度與 Arrhenius 校準參考溫度 [K]

    T_amb: float = 298.15
    # 環境溫度 [K]

    dripper_mass_g: float = 0.0
    # 濾杯質量 [g]

    dripper_cp_J_gK: float = 0.88
    # 濾杯材質比熱 [J/(g·K)]

    mu_fit_log_coeffs: tuple[float, float, float, float] = (
        -8.17297841e-07,
        2.32004852e-04,
        -3.36945065e-02,
        5.90898359e-01,
    )
    # 由相對黏滯度 vs 溫度曲線擬合出的 log-cubic 係數

    Cp_coffee: float = 1800.0
    # 乾咖啡粉比熱容 [J/(kg·K)]

    D10_measured_m: float | None = None
    # 若有實測 PSD，優先使用量測 D10 [m]

    psd_bins_csv_path: str | None = None
    # 若有 multi-bin PSD，優先用 bins 直接計算表面積、殼層可及性與擴散路徑
