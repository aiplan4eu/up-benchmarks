import unittest
from upbm.factory import DomainFactory
import importlib
import json
import os


class TestGenericGenerator(unittest.TestCase):
    def setUp(self):
        self.factory = DomainFactory()

    def test_generic(self):
        tests_folder = os.path.join(os.path.dirname(__file__), "test_params")
        for testfile_name in os.listdir(tests_folder):
            print(f"\ntesting : {testfile_name}\n")
            testfile_path = os.path.join(tests_folder, testfile_name)
            test_config = {}
            with open(testfile_path) as jsonfile:
                test_config = json.load(jsonfile)

            print(test_config)

            # registration

            self.assertIn(test_config["name"], self.factory.get_registered_domains())
            module = importlib.import_module(test_config["module"])
            problem_generator = getattr(module, test_config["generator"])
            self.assertEqual(self.factory[test_config["name"]], problem_generator)

            # parameter spaces

            dom_space = self.factory.get_domain_parameter_space(test_config["name"])
            for domanin_parameter in test_config["domain_params"].keys():
                self.assertIn(domanin_parameter, dom_space)
            domain_params = self.factory.parse_configuration(
                test_config["domain_params"], dom_space
            )
            inst_space = self.factory.get_instance_parameter_space(
                test_config["name"], domain_params
            )
            for instance_parameter in test_config["instance_params"].keys():
                self.assertIn(instance_parameter, inst_space)

            # instance generation

            instance_params = self.factory.parse_configuration(
                test_config["instance_params"],
                inst_space,
            )

            problem = self.factory.generate_instance(
                test_config["name"], domain_params, instance_params
            )
            self.assertEqual(len(problem.goals), test_config["instance_goals_n"])

            # Check objects
            for obj_type_name in test_config["instance_objects"].keys():
                print(obj_type_name)
                obj_names = [
                    o.name for o in problem.objects(problem.user_type(obj_type_name))
                ]
                print(obj_names)
                print(test_config["instance_objects"][obj_type_name])

                self.assertEqual(
                    len(obj_names), len(test_config["instance_objects"][obj_type_name])
                )
                for obj_name in test_config["instance_objects"][obj_type_name]:
                    self.assertIn(obj_name, obj_names)

            print(f"\n{testfile_name} OK!\n")
