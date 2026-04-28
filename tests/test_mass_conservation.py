import unittest

import numpy as np

from pour_over import PourProtocol, RoastProfile, V60Params, simulate_brew


class MassConservationTests(unittest.TestCase):
    def test_main_model_exposes_bounded_solute_balance_residual(self):
        params = V60Params.for_roast(RoastProfile.LIGHT)
        protocol = PourProtocol.standard_v60()

        results = simulate_brew(params, protocol, t_end=200, max_step=1.0)
        residual = np.asarray(results["M_balance_residual_g"], dtype=float)

        self.assertTrue(np.all(np.isfinite(residual)))
        self.assertLess(float(np.max(np.abs(residual))), 5.0e-2)


if __name__ == "__main__":
    unittest.main()
