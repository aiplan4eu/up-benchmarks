import unittest
from upbm.factory import DomainFactory
from upbm.domains.majsp import MaJSPGenerator


class TestMaJSPGenerator(unittest.TestCase):
    def setUp(self):
        self.factory = DomainFactory()
        self.domain_name = "majsp"

    def test_registration(self):
        self.assertIn(self.domain_name, self.factory.get_registered_domains())
        self.assertEqual(self.factory[self.domain_name], MaJSPGenerator)

    def test_parameter_spaces(self):
        dom_space = self.factory.get_domain_parameter_space(self.domain_name)
        self.assertIn("max_robots", dom_space)
        self.assertIn("max_pallets", dom_space)
        self.assertIn("max_positions", dom_space)

        domain_params = self.factory.parse_configuration(
            {"max_robots": 2, "max_pallets": 2, "max_positions": 5}, dom_space
        )
        inst_space = self.factory.get_instance_parameter_space(
            self.domain_name, domain_params
        )
        self.assertIn("n_robots", inst_space)
        self.assertIn("n_pallets", inst_space)
        self.assertIn("n_positions", inst_space)
        self.assertIn("n_treatments", inst_space)

    def test_instance_generation(self):
        dom_space = self.factory.get_domain_parameter_space(self.domain_name)
        domain_params = self.factory.parse_configuration(
            {"max_robots": 2, "max_pallets": 2, "max_positions": 5}, dom_space
        )

        inst_space = self.factory.get_instance_parameter_space(
            self.domain_name, domain_params
        )
        instance_params = self.factory.parse_configuration(
            {"n_robots": 1, "n_pallets": 1, "n_positions": 3, "n_treatments": 2},
            inst_space,
        )

        problem = self.factory.generate_instance(
            self.domain_name, domain_params, instance_params
        )
        self.assertEqual(
            len(problem.goals), 2
        )  # n_pallets * min(n_treatments, n_positions) = 1 * 2 = 2

        # Check objects
        robot_names = [o.name for o in problem.objects(problem.user_type("Robot"))]
        self.assertEqual(len(robot_names), 1)
        self.assertIn("r0", robot_names)

        pallet_names = [o.name for o in problem.objects(problem.user_type("Pallet"))]
        self.assertEqual(len(pallet_names), 2)  # b0 + NOPALLET
        self.assertIn("b0", pallet_names)
        self.assertIn("NOPALLET", pallet_names)

        pos_names = [o.name for o in problem.objects(problem.user_type("Position"))]
        self.assertEqual(len(pos_names), 5)  # p0, p1, p2 + UNKNOWN, DEPOT
        self.assertIn("p0", pos_names)
        self.assertIn("p1", pos_names)
        self.assertIn("p2", pos_names)
        self.assertIn("UNKNOWN", pos_names)
        self.assertIn("DEPOT", pos_names)


if __name__ == "__main__":
    unittest.main()
