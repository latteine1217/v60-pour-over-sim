import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pour_over.fitting import DEFAULT_MEASURED_CASE_DIR
from pour_over.measured_io import (
    load_flow_profile_csv,
    measured_case_psd_bins_path,
    resolve_measured_ambient_temp_C,
)
from pour_over.showcase_state import measured_case_dir


class MeasuredCaseRegistryTests(unittest.TestCase):
    def test_resolve_measured_ambient_temp_prefers_explicit_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "thermal.csv"
            csv_path.write_text(
                "dose_g,roast,grinder,grinder_setting,bed_height_cm,brew_temp_C,ambient_temp_C,final_coffee_temp_C,final_tds_pct,dripper_mass_g,dripper_cp_J_gK,lambda_liquid_dripper,lambda_dripper_ambient,lambda_server_ambient,time_mmss,time_s,poured_weight_g,drained_volume_ml,estimated_server_volume_ml,server_temp_C,outflow_temp_C,use_for_fit,server_temp_use_for_fit,outflow_temp_use_for_fit,phase\n"
                "20,light,Kinu,29,5.3,92.0,23.0,74.0,,123.5,0.88,0.02,0.004,0.0,00:00,0,0,0,0,24.8,25.1,1,0,0,start\n"
                "20,light,Kinu,29,5.3,92.0,,74.0,,123.5,0.88,0.02,0.004,0.0,00:05,5,30,5,5,35.0,40.0,1,1,1,flow_stop_visual\n",
                encoding="utf-8",
            )

            prof = load_flow_profile_csv(csv_path)

        self.assertAlmostEqual(resolve_measured_ambient_temp_C(prof), 23.0, places=3)

    def test_load_flow_profile_allows_missing_final_tds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "flow.csv"
            csv_path.write_text(
                "dose_g,roast,grinder,grinder_setting,bed_height_cm,brew_temp_C,ambient_temp_C,final_coffee_temp_C,final_tds_pct,dripper_mass_g,dripper_cp_J_gK,lambda_liquid_dripper,lambda_dripper_ambient,lambda_server_ambient,time_mmss,time_s,poured_weight_g,drained_volume_ml,use_for_fit,phase\n"
                "20,light,Kinu,29,5.3,92.0,23.0,74.0,,123.5,0.88,0.02,0.004,0.0,00:00,0,0,0,1,start\n"
                "20,light,Kinu,29,5.3,92.0,23.0,74.0,,123.5,0.88,0.02,0.004,0.0,00:05,5,30,5,1,flow_stop_visual\n",
                encoding="utf-8",
            )

            prof = load_flow_profile_csv(csv_path)

        self.assertIsNone(prof["final_tds_pct"])
        self.assertEqual(prof["stop_flow_time_s"], 5.0)

    def test_resolve_measured_ambient_temp_falls_back_to_t0_server_temperature(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "thermal.csv"
            csv_path.write_text(
                "dose_g,roast,grinder,grinder_setting,bed_height_cm,brew_temp_C,ambient_temp_C,final_coffee_temp_C,final_tds_pct,dripper_mass_g,dripper_cp_J_gK,lambda_liquid_dripper,lambda_dripper_ambient,lambda_server_ambient,time_mmss,time_s,poured_weight_g,drained_volume_ml,estimated_server_volume_ml,server_temp_C,outflow_temp_C,use_for_fit,server_temp_use_for_fit,outflow_temp_use_for_fit,phase\n"
                "20,light,Kinu,29,5.3,92.0,,74.0,,123.5,0.88,0.02,0.004,0.0,00:00,0,0,0,0,23.3,25.0,1,0,0,start\n"
                "20,light,Kinu,29,5.3,92.0,,74.0,,123.5,0.88,0.02,0.004,0.0,00:05,5,30,5,5,30.0,40.0,1,1,1,flow_stop_visual\n",
                encoding="utf-8",
            )

            prof = load_flow_profile_csv(csv_path)

        self.assertAlmostEqual(resolve_measured_ambient_temp_C(prof), 23.3, places=3)

    def test_resolve_measured_ambient_temp_rejects_missing_metadata_and_t0_temperature(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "flow.csv"
            csv_path.write_text(
                "dose_g,roast,grinder,grinder_setting,bed_height_cm,brew_temp_C,ambient_temp_C,final_coffee_temp_C,final_tds_pct,dripper_mass_g,dripper_cp_J_gK,lambda_liquid_dripper,lambda_dripper_ambient,lambda_server_ambient,time_mmss,time_s,poured_weight_g,drained_volume_ml,use_for_fit,phase\n"
                "20,light,Kinu,29,5.3,92.0,,74.0,,123.5,0.88,0.02,0.004,0.0,00:00,0,0,0,1,start\n"
                "20,light,Kinu,29,5.3,92.0,,74.0,,123.5,0.88,0.02,0.004,0.0,00:05,5,30,5,1,flow_stop_visual\n",
                encoding="utf-8",
            )

            prof = load_flow_profile_csv(csv_path)

        with self.assertRaisesRegex(ValueError, "ambient_temp_C"):
            resolve_measured_ambient_temp_C(prof)

    def test_measured_case_dir_accepts_explicit_case_date(self) -> None:
        case_dir = measured_case_dir("4:12")
        self.assertEqual(case_dir.name, "4:12")
        self.assertTrue((case_dir / "PSD_export_data.csv").exists())

    def test_default_measured_baseline_points_to_4_12(self) -> None:
        self.assertEqual(measured_case_dir().name, "4:12")
        self.assertEqual(DEFAULT_MEASURED_CASE_DIR, "data/kinu_29_light/4:12")

    def test_kinu_4_12_structured_case_is_loadable(self) -> None:
        flow_csv = Path("data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv")

        prof = load_flow_profile_csv(flow_csv)

        self.assertEqual(prof["t_s"][-1], 130.0)
        self.assertEqual(prof["v_out_ml"][-1], 310.0)
        self.assertAlmostEqual(prof["final_tds_pct"], 1.36, places=2)

    def test_measured_case_psd_bins_path_uses_case_local_artifact(self) -> None:
        flow_csv = Path("data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv")
        bins_csv = measured_case_psd_bins_path(flow_csv)

        self.assertEqual(bins_csv.name, "kinu29_psd_bins.csv")
        self.assertIn("4:12", str(bins_csv))

    def test_kinu_27_4_12_structured_case_is_loadable(self) -> None:
        flow_csv = Path("data/kinu_27_light/4:12/kinu27_light_20g_flow_profile.csv")

        prof = load_flow_profile_csv(flow_csv)

        self.assertEqual(prof["t_s"][-1], 135.0)
        self.assertEqual(prof["v_out_ml"][-1], 280.0)
        self.assertEqual(prof["v_in_ml"][-1], 320.0)
        self.assertAlmostEqual(prof["final_tds_pct"], 1.19, places=2)

    def test_kinu_28_4_20_structured_case_is_loadable(self) -> None:
        flow_csv = Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv")

        prof = load_flow_profile_csv(flow_csv)

        self.assertEqual(prof["t_s"][-1], 120.0)
        self.assertEqual(prof["v_out_ml"][-1], 265.0)
        self.assertEqual(prof["v_in_ml"][-1], 301.3)
        self.assertAlmostEqual(prof["final_tds_pct"], 1.60, places=2)

    def test_thermal_profile_uses_channel_mixed_apex_for_t2(self) -> None:
        from pour_over.benchmark import _load_measured_benchmark_state
        from pour_over.fitting import evaluate_measured_thermal_profile
        import numpy as np

        flow_csv = Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv")
        thermal_csv = Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv")
        summary_csv = Path(
            "data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"
        )
        params_fit, info = _load_measured_benchmark_state(flow_csv, summary_csv, refit=False, verbose=False)
        thermal = evaluate_measured_thermal_profile(thermal_csv, params_fit, tau_lag_s=float(info["tau_lag_s"]))

        self.assertIn("T_apex_mixed_C", thermal["obs_layer"])
        self.assertIn("model_apex_temp_C", thermal)
        sim_t = thermal["sim"]["t"]
        sim_bulk = thermal["sim"]["T_C"]
        bulk_at_obs = np.interp(thermal["t_obs_s"], sim_t, sim_bulk)
        self.assertFalse(np.allclose(thermal["model_apex_temp_C"], bulk_at_obs))
        apex_at_obs = np.interp(thermal["t_obs_s"], sim_t, thermal["obs_layer"]["T_apex_mixed_C"])
        np.testing.assert_allclose(thermal["model_outflow_temp_C"], apex_at_obs)

    def test_thermal_plot_uses_channel_mixed_apex_curve_for_t2_panel(self) -> None:
        from pour_over.benchmark import _load_measured_benchmark_state
        from pour_over.fitting import evaluate_measured_thermal_profile, plot_measured_thermal_profile_comparison
        import numpy as np

        flow_csv = Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv")
        thermal_csv = Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv")
        summary_csv = Path(
            "data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"
        )
        params_fit, info = _load_measured_benchmark_state(flow_csv, summary_csv, refit=False, verbose=False)
        thermal = evaluate_measured_thermal_profile(thermal_csv, params_fit, tau_lag_s=float(info["tau_lag_s"]))

        captured: dict[str, object] = {}

        def _capture_fig(fig, save_as: str, message: str) -> None:
            captured["fig"] = fig

        with patch("pour_over.fitting._save_fig", _capture_fig):
            plot_measured_thermal_profile_comparison(thermal, save_as="unused.png")

        fig = captured["fig"]
        axes = fig.axes
        t2_line = axes[2].lines[0]
        np.testing.assert_allclose(t2_line.get_ydata(), thermal["obs_layer"]["T_apex_mixed_C"])

    def test_4_20_startup_apex_temperature_does_not_jump_to_near_bulk(self) -> None:
        from pour_over.benchmark import _load_measured_benchmark_state
        from pour_over.fitting import evaluate_measured_thermal_profile

        flow_csv = Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv")
        thermal_csv = Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv")
        summary_csv = Path(
            "data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"
        )
        params_fit, info = _load_measured_benchmark_state(flow_csv, summary_csv, refit=False, verbose=False)
        thermal = evaluate_measured_thermal_profile(thermal_csv, params_fit, tau_lag_s=float(info["tau_lag_s"]))

        t_obs = list(thermal["t_obs_s"])
        t10_idx = t_obs.index(10.0)
        self.assertLess(float(thermal["model_outflow_temp_C"][t10_idx]), 80.0)

    def test_t2_fit_window_holds_out_points_before_10_seconds(self) -> None:
        from pour_over.benchmark import _load_measured_benchmark_state
        from pour_over.fitting import evaluate_measured_thermal_profile

        flow_csv = Path("data/kinu_28_light/4:20/kinu28_light_20g_flow_profile.csv")
        thermal_csv = Path("data/kinu_28_light/4:20/kinu28_light_20g_thermal_profile.csv")
        summary_csv = Path(
            "data/kinu_28_light/4:20/kinu28_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv"
        )
        params_fit, info = _load_measured_benchmark_state(flow_csv, summary_csv, refit=False, verbose=False)
        thermal = evaluate_measured_thermal_profile(thermal_csv, params_fit, tau_lag_s=float(info["tau_lag_s"]))

        t_obs = list(thermal["t_obs_s"])
        t5_idx = t_obs.index(5.0)
        t10_idx = t_obs.index(10.0)
        self.assertFalse(bool(thermal["outflow_temp_fit_mask"][t5_idx]))
        self.assertTrue(bool(thermal["outflow_temp_fit_mask"][t10_idx]))

    def test_t1_fit_window_starts_at_first_drip_plus_5_seconds(self) -> None:
        from pour_over.fitting import _apply_sensor_fit_start_time
        import numpy as np

        t_obs = np.asarray([0.0, 5.0, 10.0, 15.0], dtype=float)
        v_out_obs = np.asarray([0.0, 2.0, 15.0, 15.0], dtype=float)
        raw_mask = np.asarray([0, 1, 1, 1], dtype=bool)

        mask = _apply_sensor_fit_start_time(t_obs, v_out_obs, raw_mask, extra_delay_s=5.0)

        self.assertFalse(bool(mask[1]))
        self.assertTrue(bool(mask[2]))

    def test_measured_case_psd_bins_path_supports_kinu_27_case(self) -> None:
        flow_csv = Path("data/kinu_27_light/4:12/kinu27_light_20g_flow_profile.csv")
        bins_csv = measured_case_psd_bins_path(flow_csv)

        self.assertEqual(bins_csv.name, "kinu27_psd_bins.csv")

    def test_4_12_final_tds_pct_uses_brix_conversion(self) -> None:
        cases = [
            (Path("data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv"), 1.36),
            (Path("data/kinu_27_light/4:12/kinu27_light_20g_flow_profile.csv"), 1.19),
        ]

        for flow_csv, expected_tds_pct in cases:
            prof = load_flow_profile_csv(flow_csv)
            self.assertAlmostEqual(prof["final_tds_pct"], expected_tds_pct, places=2, msg=str(flow_csv))

    def test_4_12_cases_use_new_glass_server_mass(self) -> None:
        cases = [
            Path("data/kinu_29_light/4:12/kinu29_light_20g_flow_profile.csv"),
            Path("data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile.csv"),
            Path("data/kinu_27_light/4:12/kinu27_light_20g_flow_profile.csv"),
            Path("data/kinu_27_light/4:12/kinu27_light_20g_thermal_profile.csv"),
        ]

        for csv_path in cases:
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                first = next(csv.DictReader(f))
            self.assertAlmostEqual(float(first["dripper_mass_g"]), 224.1, places=1, msg=str(csv_path))

    def test_early_cold_server_temperature_points_are_held_out(self) -> None:
        thermal_csvs = [
            Path("data/kinu_29_light/4:11/kinu29_light_20g_thermal_profile.csv"),
            Path("data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile.csv"),
            Path("data/kinu_27_light/4:12/kinu27_light_20g_thermal_profile.csv"),
        ]

        for thermal_csv in thermal_csvs:
            with thermal_csv.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

            cold_rows = [r for r in rows if r.get("server_temp_C", "").strip() and float(r["server_temp_C"]) < 30.0]
            self.assertTrue(cold_rows, msg=str(thermal_csv))
            self.assertTrue(
                all(int(r["server_temp_use_for_fit"]) == 0 for r in cold_rows),
                msg=str(thermal_csv),
            )


if __name__ == "__main__":
    unittest.main()
