import unittest
from upbm.factory import DomainFactory
from upbm.domains.replenish import ReplenishGenerator

class TestReplenishGenerator(unittest.TestCase):
    def setUp(self):
        self.factory = DomainFactory()
        self.domain_name = "replenish"

    def test_registration(self):
        self.assertIn(self.domain_name, self.factory.get_registered_domains())
        self.assertEqual(self.factory[self.domain_name], ReplenishGenerator)

    def test_parameter_spaces(self):
        dom_space = self.factory.get_domain_parameter_space(self.domain_name)
        self.assertIn("max_cardboard_types", dom_space)
        self.assertIn("max_drawers", dom_space)
        self.assertIn("max_goal_sequence_length", dom_space)

        domain_params = self.factory.parse_configuration({"max_cardboard_types": 3, "max_drawers": 5, "max_goal_sequence_length": 10}, dom_space)
        inst_space = self.factory.get_instance_parameter_space(self.domain_name, domain_params)
        self.assertIn("n_cardboard_types", inst_space)
        self.assertIn("n_drawers", inst_space)
        self.assertIn("goal_sequence_length", inst_space)
        self.assertIn("sequence_seed", inst_space)

    def test_instance_generation(self):
        dom_space = self.factory.get_domain_parameter_space(self.domain_name)
        domain_params = self.factory.parse_configuration({"max_cardboard_types": 3, "max_drawers": 5, "max_goal_sequence_length": 10}, dom_space)

        inst_space = self.factory.get_instance_parameter_space(self.domain_name, domain_params)
        instance_params = self.factory.parse_configuration({"n_cardboard_types": 2, "n_drawers": 2, "goal_sequence_length": 3, "sequence_seed": 42}, inst_space)

        problem = self.factory.generate_instance(self.domain_name, domain_params, instance_params)
        self.assertEqual(len(problem.goals), 1) # Equals(goal_progress, Int(3))

        # Check objects
        cardboard_type = problem.user_type("CardboardType")
        cardboard_names = [o.name for o in problem.objects(cardboard_type)]
        # no_type (from base domain) + cardboard_type_1, cardboard_type_2 (from get_objects)
        self.assertEqual(len(cardboard_names), 3)
        self.assertIn("no_type", cardboard_names)
        self.assertIn("cardboard_type_1", cardboard_names)
        self.assertIn("cardboard_type_2", cardboard_names)

        drawer_type = problem.user_type("Drawer")
        drawer_names = [o.name for o in problem.objects(drawer_type)]
        self.assertEqual(len(drawer_names), 2)
        self.assertIn("drawer_0", drawer_names)
        self.assertIn("drawer_1", drawer_names)

if __name__ == "__main__":
    unittest.main()
