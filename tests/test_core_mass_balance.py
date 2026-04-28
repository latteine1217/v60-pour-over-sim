import unittest
from dataclasses import replace
from pathlib import Path

from pour_over.benchmark import _load_measured_benchmark_state
from pour_over.core import simulate_brew
from pour_over.fitting import evaluate_measured_thermal_profile
from pour_over.params import PourProtocol, V60Params


class CoreMassBalanceTests(unittest.TestCase):
    def test_simulate_brew_reports_mass_balance_diagnostics(self) -> None:
        params = V60Params()
        protocol = PourProtocol.standard_v60()

        results = simulate_brew(params, protocol, t_end=180.0, n_eval=600)

        self.assertIn("M_liquid_inventory_g", results)
        self.assertIn("M_balance_residual_g", results)
        self.assertEqual(results["M_liquid_inventory_g"].shape, results["t"].shape)
        self.assertEqual(results["M_balance_residual_g"].shape, results["t"].shape)

    def test_simulate_brew_reports_effluent_temperature_series(self) -> None:
        params = V60Params()
        protocol = PourProtocol.standard_v60()

        results = simulate_brew(params, protocol, t_end=180.0, n_eval=600)

        self.assertIn("T_effluent_C", results)
        self.assertEqual(results["T_effluent_C"].shape, results["t"].shape)

    def test_simulate_brew_reports_channel_flow_split_conservation(self) -> None:
        params = V60Params()
        protocol = PourProtocol.standard_v60()

        results = simulate_brew(params, protocol, t_end=180.0, n_eval=600)

        self.assertIn("q_fast_apex_mlps", results)
        self.assertIn("q_side_seepage_mlps", results)
        residual = (
            results["q_fast_apex_mlps"]
            + results["q_side_seepage_mlps"]
            - results["q_bed_transport_mlps"]
        )
        self.assertLess(float(abs(residual).max()), 1e-9)
        self.assertTrue(((results["apex_fast_weight"] >= 0.0) & (results["apex_fast_weight"] <= 1.0)).all())

    def test_effluent_temperature_starts_from_cold_apex_state(self) -> None:
        params = V60Params()
        protocol = PourProtocol.standard_v60()

        results = simulate_brew(params, protocol, t_end=180.0, n_eval=600)

        self.assertAlmostEqual(float(results["T_effluent_C"][0]), params.T_amb - 273.15, places=3)

    def test_bulk_temperature_starts_from_ambient_state(self) -> None:
        params = V60Params()
        protocol = PourProtocol.standard_v60()

        results = simulate_brew(params, protocol, t_end=180.0, n_eval=600)

        self.assertAlmostEqual(float(results["T_C"][0]), params.T_amb - 273.15, places=3)

    def test_default_effluent_coupling_gate_preserves_baseline_temperature(self) -> None:
        protocol = PourProtocol.standard_v60()
        base = simulate_brew(V60Params(), protocol, t_end=60.0, n_eval=240)
        explicit = simulate_brew(
            replace(V60Params(), effluent_coupling_gate_mode="constant"),
            protocol,
            t_end=60.0,
            n_eval=240,
        )

        self.assertAlmostEqual(float(base["T_effluent_C"][-1]), float(explicit["T_effluent_C"][-1]), places=9)

    def test_unknown_effluent_coupling_gate_mode_fails_fast(self) -> None:
        protocol = PourProtocol.standard_v60()
        params = replace(V60Params(), effluent_coupling_gate_mode="unknown")

        with self.assertRaisesRegex(ValueError, "effluent_coupling_gate_mode"):
            simulate_brew(params, protocol, t_end=10.0, n_eval=20)

    def test_solute_mass_balance_residual_stays_small_for_standard_protocol(self) -> None:
        params = V60Params()
        protocol = PourProtocol.standard_v60()

        results = simulate_brew(params, protocol, t_end=180.0, n_eval=600)

        self.assertLess(abs(float(results["M_balance_residual_g"][-1])), 0.05)
        self.assertLess(float(results["M_balance_residual_g"].max()), 0.08)
        self.assertGreater(float(results["M_balance_residual_g"].min()), -0.08)

    def test_measured_4_12_case_does_not_accumulate_large_negative_balance_error(self) -> None:
        flow_csv = Path("data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv")
        thermal_csv = Path("data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile.csv")
        summary_csv = Path(
            "data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"
        )
        params_fit, info = _load_measured_benchmark_state(flow_csv, summary_csv, refit=False, verbose=False)
        thermal = evaluate_measured_thermal_profile(
            thermal_csv,
            params_fit,
            tau_lag_s=float(info["tau_lag_s"]),
            n_eval=1600,
        )

        residual = thermal["sim"]["M_balance_residual_g"]

        self.assertGreater(float(residual.min()), -0.10)


if __name__ == "__main__":
    unittest.main()
