import pytest
from upbm.factory import DomainFactory


def test_kitting_generator():
    factory = DomainFactory()
    assert "kitting" in factory.get_registered_domains()

    domain_space = factory.get_domain_parameter_space("kitting")
    domain_params = domain_space.sample_configuration()
    domain_params["max_components"] = 5
    domain_params["max_kit_size"] = 3
    domain_params["max_n_kit"] = 3
    domain_params["max_robots"] = 2
    domain_params["isomorphic_instances"] = True

    assert factory.is_pddl_expressible("kitting", domain_params) is False

    instance_space = factory.get_instance_parameter_space("kitting", domain_params)
    instance_params = instance_space.sample_configuration()
    instance_params["n_components"] = 4
    instance_params["kit_size"] = 2
    instance_params["n_kit"] = 2
    instance_params["n_robots"] = 2
    instance_params["combination_idx"] = 0

    problem = factory.generate_instance("kitting", domain_params, instance_params)
    assert problem is not None
    assert problem.name.startswith("Kitting")

    # Check objects
    objs = list(problem.all_objects)
    assert len(objs) > 0

    # Check goal
    assert len(problem.goals) == 2
