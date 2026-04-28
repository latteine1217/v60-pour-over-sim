"""
observation.py — 模型觀測層與量測對應

What:
    將粉床出口的模擬量轉成使用者真正量到的壺內 / 杯中觀測量，
    包含 outflow lag、server 熱節點與可觀測停流時間。

Why:
    fitting、benchmark、identifiability 都應共享同一套觀測層；
    否則每個工具其實在比較不同訊號，結論無法對齊。
"""

import numpy as np

from .params import PourProtocol


def _contact_path_temperature_C(
    t: np.ndarray,
    T_effluent_C: np.ndarray,
    T_dripper_C: np.ndarray,
    *,
    tau_s: float,
    contact_weight: float,
) -> np.ndarray:
    """
    What: 建立側邊慢滲 / apex contact path 的熱歷史。
    Why:  慢滲路徑會沿濾紙與錐底接觸區匯流，T2 不應只看瞬時 fast effluent。
    """
    tau = max(float(tau_s), 1e-6)
    w_contact = float(np.clip(contact_weight, 0.0, 1.0))
    target = (1.0 - w_contact) * T_effluent_C + w_contact * T_dripper_C
    contact = np.empty_like(target)
    if target.size == 0:
        return contact
    contact[0] = target[0]
    for idx in range(1, len(target)):
        dt = max(float(t[idx] - t[idx - 1]), 0.0)
        alpha = 1.0 - np.exp(-dt / tau)
        contact[idx] = contact[idx - 1] + alpha * (target[idx] - contact[idx - 1])
    return contact


def apex_mixed_temperature_C(results: dict) -> dict[str, np.ndarray]:
    """
    What: 用核心水力通道權重計算 T2 apex mixed temperature。
    Why:  通道效應同時屬於流與熱；observation layer 必須使用 flow model 暴露的同一個權重。
    """
    t = np.asarray(results["t"], dtype=float)
    T_effluent = np.asarray(results.get("T_effluent_C", results["T_C"]), dtype=float)
    T_dripper = np.asarray(results.get("T_dripper_C", T_effluent), dtype=float)
    if T_dripper.shape != T_effluent.shape:
        raise ValueError("T_dripper_C 與 T_effluent_C shape 不一致，無法計算 apex mixed temperature")
    fast_weight = np.asarray(results.get("apex_fast_weight", np.ones_like(T_effluent)), dtype=float)
    if fast_weight.shape != T_effluent.shape:
        raise ValueError("apex_fast_weight 與 T_effluent_C shape 不一致，無法計算 apex mixed temperature")

    contact = _contact_path_temperature_C(
        t,
        T_effluent,
        T_dripper,
        tau_s=float(results.get("apex_contact_tau_s", 6.0)),
        contact_weight=float(results.get("apex_contact_weight", 0.35)),
    )
    fast_weight = np.clip(fast_weight, 0.0, 1.0)
    mixed = fast_weight * T_effluent + (1.0 - fast_weight) * contact
    return {
        "T_contact_path_C": contact,
        "T_apex_mixed_C": mixed,
        "apex_fast_weight": fast_weight,
    }


def mixed_cup_temperature_C(
    results: dict,
    ambient_temp_C: float,
    vessel_equivalent_ml: float = 0.0,
) -> float:
    """
    以能量守恆計算杯中混合後溫度。

    What:
        將流出液的時間序列溫度積分為最終杯中混合溫度。

    Why:
        使用者量到的是 server / cup 中的最終飲用溫度，不是濾杯床層瞬時溫度；
        需額外考慮容器的熱容吸熱。
    """
    if "T_server_C" in results:
        T_server = np.asarray(results["T_server_C"], dtype=float)
        if T_server.size:
            return float(T_server[-1])
    t = np.asarray(results["t"], dtype=float)
    q_out_mlps = np.asarray(results["q_out_mlps"], dtype=float)
    T_out_C = np.asarray(results.get("T_apex_mixed_C", results.get("T_effluent_C", results["T_C"])), dtype=float)
    dt = np.diff(t, prepend=t[0])
    cup_volume_ml = float(np.sum(q_out_mlps * dt))
    if cup_volume_ml <= 0:
        return ambient_temp_C
    cup_energy = float(np.sum(q_out_mlps * T_out_C * dt))
    total_heat_capacity_ml = cup_volume_ml + max(vessel_equivalent_ml, 0.0)
    return (cup_energy + max(vessel_equivalent_ml, 0.0) * ambient_temp_C) / total_heat_capacity_ml


def observed_stop_time_from_layer(
    obs_layer: dict,
    t_sim: np.ndarray,
    protocol: PourProtocol,
    threshold_mlps: float = 0.05,
) -> float:
    """
    由 lag 後杯中出流推估可觀測停流時間。

    What:
        在最後一注之後，尋找 `q_cup <= threshold_mlps` 的第一個時刻。

    Why:
        使用者看到的是壺內液面停止上升，不是濾床出口的瞬時停流；
        benchmark / fitting / identifiability 都應共用同一個觀測層定義。
    """
    q_cup = np.asarray(obs_layer["q_cup_mlps"], dtype=float)
    t_sim = np.asarray(t_sim, dtype=float)
    t_last = protocol.last_pour_end()
    mask = t_sim >= t_last
    below = np.where(mask & (q_cup <= threshold_mlps))[0]
    if below.size:
        return float(t_sim[below[0]])
    return float(t_sim[-1])


def apply_outflow_lag(
    results: dict,
    tau_lag_s: float,
    *,
    ambient_temp_C: float | None = None,
    vessel_equivalent_ml: float = 0.0,
    lambda_server_ambient: float | None = None,
) -> dict:
    """
    將粉床出口流量轉成杯中可觀測出液。

    What:
        用一個小暫存體積 `V_hold` 將模型的床層出口流量 `q_out`
        轉成杯中可觀測流量 `q_cup`，並同步追蹤 hold-up 與 server 熱節點。

    Why:
        使用者量到的是壺內液面上升的區間平均速度，而不是濾床出口的瞬時滴流。
    """
    tau = max(float(tau_lag_s), 1e-6)
    t = np.asarray(results["t"], dtype=float)
    q_src = np.asarray(results["q_out_mlps"], dtype=float)
    apex_mix = apex_mixed_temperature_C(results)
    T_effluent = np.asarray(results.get("T_effluent_C", results["T_C"]), dtype=float)
    T_src = np.asarray(apex_mix["T_apex_mixed_C"], dtype=float)
    if ambient_temp_C is None:
        raw_ambient = results.get("ambient_temp_C")
        if raw_ambient is None:
            raise ValueError("apply_outflow_lag 需要 ambient_temp_C；不再支援固定 23°C 默認值")
        ambient_C = float(raw_ambient)
    else:
        ambient_C = float(ambient_temp_C)
    server_lambda = float(results.get("lambda_server_ambient", 0.0) if lambda_server_ambient is None else lambda_server_ambient)
    vessel_eq = max(float(vessel_equivalent_ml), 0.0)

    q_cup = np.zeros_like(q_src)
    v_cup = np.zeros_like(q_src)
    v_hold = np.zeros_like(q_src)
    T_cup = np.zeros_like(T_src)
    v_server = np.zeros_like(q_src)
    T_server = np.full_like(T_src, ambient_C)

    hold_v = 0.0
    hold_e = 0.0
    server_v = 0.0
    server_T = ambient_C

    for i in range(1, len(t)):
        dt = max(float(t[i] - t[i - 1]), 0.0)
        T_hold_prev = hold_e / hold_v if hold_v > 1e-9 else float(T_src[i - 1])
        q_release = min(hold_v / tau, (hold_v + q_src[i - 1] * dt) / max(dt, 1e-12))

        q_in_i = max(float(q_src[i - 1]), 0.0)
        hold_v = max(hold_v + (q_in_i - q_release) * dt, 0.0)
        hold_e = max(hold_e + (q_in_i * float(T_src[i - 1]) - q_release * T_hold_prev) * dt, 0.0)

        q_cup[i] = q_release
        v_cup[i] = v_cup[i - 1] + q_release * dt
        v_hold[i] = hold_v
        T_cup[i] = T_hold_prev

        inflow_ml = q_release * dt
        total_cap_prev = server_v + vessel_eq
        server_energy = total_cap_prev * server_T
        if total_cap_prev > 1e-9 and server_lambda > 0.0:
            server_energy -= server_lambda * total_cap_prev * (server_T - ambient_C) * dt
        server_energy += inflow_ml * T_hold_prev
        server_v = max(server_v + inflow_ml, 0.0)
        total_cap_next = server_v + vessel_eq
        server_T = server_energy / total_cap_next if total_cap_next > 1e-9 else ambient_C
        v_server[i] = server_v
        T_server[i] = server_T

    if len(T_cup) > 1:
        T_cup[0] = T_cup[1]
    if len(T_server) > 1:
        T_server[0] = ambient_C

    return {
        "tau_lag_s": tau,
        "q_cup_mlps": q_cup,
        "v_cup_ml": v_cup,
        "v_hold_ml": v_hold,
        "T_cup_C": T_cup,
        "T_effluent_C": T_effluent,
        "T_contact_path_C": apex_mix["T_contact_path_C"],
        "T_apex_mixed_C": T_src,
        "apex_fast_weight": apex_mix["apex_fast_weight"],
        "v_server_ml": v_server,
        "T_server_C": T_server,
        "vessel_equivalent_ml": vessel_eq,
        "lambda_server_ambient": server_lambda,
    }
