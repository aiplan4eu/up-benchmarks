# Copyright 2026 Unified Planning library and its maintainers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Constant,
    UniformIntegerHyperparameter,
    CategoricalHyperparameter,
)

from typing import Iterable, Optional, Iterator
from unified_planning.model import Problem, Object, FNode  # type: ignore[import-untyped]
import itertools

from upbm.utils import is_subspace


class Generator(object):
    """Abstract base class for domain-specific problem instance generators.

    Subclasses must implement the abstract methods and properties to define a
    particular planning domain and how instances are constructed from a given
    configuration.
    """

    def __init__(self, domain_params: Configuration):
        """Initialize the generator with domain-level parameters.

        Args:
            domain_params: A ConfigSpace ``Configuration`` object holding the
                hyperparameters that describe the domain (as opposed to
                per-instance parameters).
        """
        self.domain_params = domain_params

    @staticmethod
    def get_domain_parameter_space() -> ConfigurationSpace:
        """Return the configuration space for domain-level parameters.

        This static method must be overridden by subclasses to expose the set
        of hyperparameters that control domain-wide properties (e.g. the number
        of object types, capacity limits, etc.).

        Returns:
            A ``ConfigurationSpace`` describing the domain parameter space.

        Raises:
            NotImplementedError: Always, when called on the base class.
        """
        raise NotImplementedError

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        """Return the configuration space for instance-level parameters.

        Subclasses must override this property to expose the hyperparameters
        that control how individual problem instances are generated (e.g. the
        number of objects, goal conditions, etc.).

        Returns:
            A ``ConfigurationSpace`` describing the instance parameter space.

        Raises:
            NotImplementedError: Always, when called on the base class.
        """
        raise NotImplementedError

    @property
    def name(self) -> str:
        """Return a human-readable name for this generator / domain.

        Returns:
            A string identifier for the domain.

        Raises:
            NotImplementedError: Always, when called on the base class.
        """
        raise NotImplementedError

    @property
    def domain(self) -> Problem:
        """Return the base (skeleton) planning problem for this domain.

        The returned ``Problem`` object typically contains the domain
        definition (types, predicates, actions) but no concrete objects,
        initial state, or goal.  ``get_instance`` clones this skeleton and
        populates it for each configuration.

        Returns:
            A ``unified_planning`` ``Problem`` representing the domain.

        Raises:
            NotImplementedError: Always, when called on the base class.
        """
        raise NotImplementedError

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ) -> Optional[Iterable[Object]]:
        """Return the universe of objects that can be used in instances of this
        domain bounded by the instance_parameters_space, or ``None``.

        When a universe is returned, each generated instance can only use a
        subset of these objects.  Returning ``None`` (the default) means there
        is no pre-defined universe and objects are created fresh for each
        instance.

        Returns:
            An iterable of ``Object`` instances defining the shared object
            pool, or ``None`` if no such pool exists.
        """
        return None

    def get_instance(self, params: Configuration) -> Problem:
        """Build and return a fully specified problem instance.

        Clones the base domain skeleton, assigns a descriptive name, and
        populates the clone with objects, an initial state, and goal conditions
        derived from ``params``.

        Args:
            params: A ``Configuration`` drawn from ``instance_parameter_space``
                that controls the specifics of this instance.

        Returns:
            A ``unified_planning`` ``Problem`` ready for planning.
        """
        res = self.domain.clone()
        res.name = f"{self.name} instance with params {params}"
        res.add_objects(self.get_objects(params))
        for f, v in self.get_initial_state(params).items():
            res.set_initial_value(f, v)
        for g in self.get_goal(params):
            res.add_goal(g)
        return res

    def get_objects(self, params: Configuration) -> Iterable[Object]:
        """Return the objects to include in a problem instance.

        Args:
            params: A ``Configuration`` drawn from ``instance_parameter_space``.

        Returns:
            An iterable of ``Object`` instances to be added to the problem.

        Raises:
            NotImplementedError: Always, when called on the base class.
        """
        raise NotImplementedError

    def get_goal(self, params: Configuration) -> list[FNode]:
        """Return the goal conditions for a problem instance.

        Args:
            params: A ``Configuration`` drawn from ``instance_parameter_space``.

        Returns:
            A list of ``FNode`` expressions that collectively form the goal.

        Raises:
            NotImplementedError: Always, when called on the base class.
        """
        raise NotImplementedError

    def get_initial_state(self, params: Configuration) -> dict[FNode, FNode]:
        """Return the initial state for a problem instance.

        Args:
            params: A ``Configuration`` drawn from ``instance_parameter_space``.

        Returns:
            A mapping from fluent expressions (``FNode``) to their initial
            values (``FNode``).

        Raises:
            NotImplementedError: Always, when called on the base class.
        """
        raise NotImplementedError

    def check_instance_parameters(self, params: Configuration):
        """
        Check if the parameters generate a valid, solvable problem.

        Args:
            params: A ``Configuration`` drawn from ``instance_parameter_space``.

        Returns:
            boolean representing if the parameters are valid - True default for base class / generators that do not implement this
        """
        return True

    def sample(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ) -> Iterator[Configuration]:
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        assert instance_parameters_space is not None
        if not is_subspace(instance_parameters_space, self.instance_parameter_space):
            raise ValueError(
                "The provided parameter space for sampling is not contained in the parameter space for the chosen domain"
            )
        while True:
            instance_params = instance_parameters_space.sample_configuration()
            if not self.check_instance_parameters(instance_params):
                continue
            yield instance_params

    def get_all_instances_configurations(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ) -> Iterator[Configuration]:
        """
        Returns the iterator with all the valid instance configurations that are part of the given instance_parameter_space.
        If instance_parameter_space is None, uses self.instance_parameter_space instead.
        """
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        assert instance_parameters_space is not None
        if not is_subspace(instance_parameters_space, self.instance_parameter_space):
            raise ValueError(
                "The provided parameter space for sampling is not contained in the parameter space for the chosen domain"
            )
        hp_grid = {}
        for name, hp in instance_parameters_space.items():
            if isinstance(hp, Constant):
                hp_grid[name] = [hp.value]
            elif isinstance(hp, UniformIntegerHyperparameter):
                hp_grid[name] = list(range(hp.lower, hp.upper + 1))
            elif isinstance(hp, CategoricalHyperparameter):
                hp_grid[name] = list(hp.choices)
            else:
                raise TypeError("unexpected hyperparam type")

        for combo in itertools.product(*hp_grid.values()):
            values = dict(zip(hp_grid.keys(), combo))
            temp_config = Configuration(instance_parameters_space, values=values)
            if self.check_instance_parameters(temp_config):
                yield temp_config

    @property
    def requires_per_instance_domain(self) -> bool:
        """Return True if the instances produced by this generator require a
        separate domain file in PDDL.

        Returns:
            True if a separate domain file in PDDL is required.
        """
        return False

    @property
    def pddl_expressible(self) -> bool:
        """Return True if the instances produced by this generator can be
        expressed in PDDL.

        Returns:
            True if the instances can be expressed in PDDL.
        """
        return True
