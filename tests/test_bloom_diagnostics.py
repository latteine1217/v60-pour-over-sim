import tempfile
import unittest
from pathlib import Path

from pour_over.bloom_diagnostics import (
    analyze_h1_flow_timing,
    analyze_h2_effluent_coupling,
    analyze_h3_apex_contact_history,
    analyze_h4_dual_path_apex_mixing,
    build_bloom_diagnostic,
    save_bloom_diagnostics_csv,
)


class BloomDiagnosticsTests(unittest.TestCase):
    def test_build_bloom_diagnostic_reports_thermal_and_flow_residuals(self) -> None:
        report = build_bloom_diagnostic(
            "kinu28 4:20",
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
            bloom_end_s=40.0,
        )

        self.assertEqual(report["label"], "kinu28 4:20")
        self.assertGreater(len(report["rows"]), 0)
        self.assertLessEqual(max(row["time_s"] for row in report["rows"]), 40.0)
        required = {
            "time_s",
            "v_in_obs_ml",
            "server_volume_residual_ml",
            "T1_residual_C",
            "T2_residual_C",
            "q_bed_transport_mlps",
            "q_out_mlps",
            "head_gate",
            "liq_transport_gate",
            "T_bulk_C",
            "T_effluent_C",
            "T_dripper_C",
        }
        self.assertTrue(required.issubset(report["rows"][0]))

    def test_save_bloom_diagnostics_csv_writes_structured_rows(self) -> None:
        report = build_bloom_diagnostic(
            "kinu28 4:20",
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
            bloom_end_s=10.0,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "bloom.csv"
            save_bloom_diagnostics_csv(report, out)
            text = out.read_text(encoding="utf-8")

        self.assertIn("case_label,time_s", text)
        self.assertIn("kinu28 4:20", text)

    def test_analyze_h1_flow_timing_reports_decision_metrics(self) -> None:
        report = build_bloom_diagnostic(
            "kinu28 4:20",
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
            bloom_end_s=40.0,
        )
        summary = analyze_h1_flow_timing([report])

        self.assertEqual(len(summary["case_results"]), 1)
        row = summary["case_results"][0]
        self.assertEqual(row["case_label"], "kinu28 4:20")
        self.assertIn(row["h1_status"], {"supported", "partial", "not_supported"})
        self.assertIn("volume_t2_corr", row)
        self.assertIn("same_sign_fraction", row)
        self.assertIn("early_volume_residual_mean_ml", row)
        self.assertIn("late_t2_residual_mean_C", row)
        self.assertIn(summary["overall_status"], {"supported", "partial", "not_supported"})

    def test_analyze_h2_effluent_coupling_reports_gate_modes(self) -> None:
        summary = analyze_h2_effluent_coupling(
            cases=[(
                "kinu28 4:20",
                Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
                Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
                Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
            )],
            gate_modes=("constant", "liq_transport_gate"),
        )

        self.assertEqual(len(summary["case_results"]), 2)
        modes = {row["gate_mode"] for row in summary["case_results"]}
        self.assertEqual(modes, {"constant", "liq_transport_gate"})
        for row in summary["case_results"]:
            self.assertIn("early_t2_rmse_C", row)
            self.assertIn("late_t2_rmse_C", row)
            self.assertIn("h2_status", row)
        self.assertIn(summary["overall_status"], {"supported", "partial", "not_supported"})

    def test_analyze_h3_apex_contact_history_reports_observation_modes(self) -> None:
        report = build_bloom_diagnostic(
            "kinu28 4:20",
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
            bloom_end_s=40.0,
        )
        summary = analyze_h3_apex_contact_history(
            [report],
            contact_modes=("effluent", "contact_tau12_w45"),
        )

        self.assertEqual(len(summary["case_results"]), 2)
        modes = {row["contact_mode"] for row in summary["case_results"]}
        self.assertEqual(modes, {"effluent", "contact_tau12_w45"})
        for row in summary["case_results"]:
            self.assertIn("early_t2_rmse_C", row)
            self.assertIn("late_t2_rmse_C", row)
            self.assertIn("early_delta_vs_effluent_C", row)
            self.assertIn("h3_status", row)
        self.assertIn(summary["overall_status"], {"supported", "partial", "not_supported"})

    def test_analyze_h4_dual_path_apex_mixing_reports_weight_modes(self) -> None:
        report = build_bloom_diagnostic(
            "kinu28 4:20",
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
            bloom_end_s=40.0,
        )
        summary = analyze_h4_dual_path_apex_mixing(
            [report],
            weight_modes=("effluent", "liq_transport_gate"),
        )

        self.assertEqual(len(summary["case_results"]), 2)
        modes = {row["weight_mode"] for row in summary["case_results"]}
        self.assertEqual(modes, {"effluent", "liq_transport_gate"})
        for row in summary["case_results"]:
            self.assertIn("early_t2_rmse_C", row)
            self.assertIn("late_t2_rmse_C", row)
            self.assertIn("early_delta_vs_effluent_C", row)
            self.assertIn("h4_status", row)
        self.assertIn(summary["overall_status"], {"supported", "partial", "not_supported"})

    def test_analyze_h4_dual_path_apex_mixing_reports_release_mode(self) -> None:
        report = build_bloom_diagnostic(
            "kinu28 4:20",
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
            bloom_end_s=40.0,
        )
        summary = analyze_h4_dual_path_apex_mixing(
            [report],
            weight_modes=("effluent", "liq_transport_release_after25"),
        )

        self.assertEqual(len(summary["case_results"]), 2)
        row = [r for r in summary["case_results"] if r["weight_mode"] == "liq_transport_release_after25"][0]
        self.assertIn("early_t2_rmse_C", row)
        self.assertIn("late_t2_rmse_C", row)
        self.assertIn(row["h4_status"], {"supported", "partial", "not_supported"})

    def test_analyze_h4_dual_path_apex_mixing_reports_recipe_event_release_mode(self) -> None:
        report = build_bloom_diagnostic(
            "kinu28 4:20",
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
            bloom_end_s=40.0,
        )
        summary = analyze_h4_dual_path_apex_mixing(
            [report],
            weight_modes=("effluent", "liq_transport_release_on_pour"),
        )

        self.assertEqual(len(summary["case_results"]), 2)
        row = [r for r in summary["case_results"] if r["weight_mode"] == "liq_transport_release_on_pour"][0]
        self.assertIn("early_t2_rmse_C", row)
        self.assertIn("late_t2_rmse_C", row)
        self.assertIn(row["h4_status"], {"supported", "partial", "not_supported"})

    def test_analyze_h4_dual_path_apex_mixing_reports_between_pours_release_mode(self) -> None:
        report = build_bloom_diagnostic(
            "kinu28 4:20",
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"),
            Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv"),
            bloom_end_s=40.0,
        )
        summary = analyze_h4_dual_path_apex_mixing(
            [report],
            weight_modes=("effluent", "liq_transport_release_between_pours"),
        )

        self.assertEqual(len(summary["case_results"]), 2)
        row = [r for r in summary["case_results"] if r["weight_mode"] == "liq_transport_release_between_pours"][0]
        self.assertIn("early_t2_rmse_C", row)
        self.assertIn("late_t2_rmse_C", row)
        self.assertIn(row["h4_status"], {"supported", "partial", "not_supported"})


if __name__ == "__main__":
    unittest.main()
