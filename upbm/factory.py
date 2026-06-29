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

import yaml
import importlib
from pathlib import Path
from typing import Any, Optional, Type, TYPE_CHECKING

from ConfigSpace import Configuration, ConfigurationSpace
from unified_planning.model import Problem  # type: ignore[import-untyped]

from upbm.generator import Generator

if TYPE_CHECKING:
    pass


class DomainFactory:
    """Registry of domain generators plus all high-level operations on domains.

    Built-in domains are registered automatically on construction.
    External plugins (declared in `.upbm` config files) are also loaded during
    construction; call :meth:`load_plugins` (or :meth:`reload_plugins`) at any
    time to pick up newly installed plugins without creating a new instance.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Type[Generator]] = {}
        self._domain_generators: dict[str, Type[Generator]] = {}
        self._initialize_registry()
        self.load_plugins()

    # ── Registry ──────────────────────────────────────────────────────────────

    def _initialize_registry(self) -> None:
        from upbm.domains.matchcellar import MatchCellarGenerator

        self._registry["matchcellar"] = MatchCellarGenerator
        from upbm.domains.majsp import MaJSPGenerator

        self._registry["majsp"] = MaJSPGenerator
        from upbm.domains.kitting.kitting import KittingGenerator

        self._registry["kitting"] = KittingGenerator
        from upbm.domains.replenish import ReplenishGenerator

        self._registry["replenish"] = ReplenishGenerator

    def register(self, name: str, generator_class: Type[Generator]) -> None:
        """Manually register a generator class under *name*."""
        self._registry[name] = generator_class

    def get_registered_domains(self) -> list[str]:
        """Return a sorted list of all registered domain names."""
        return sorted(self._registry.keys())

    def load_plugins(self) -> None:
        """Discover and register external generators from `.upbm` config files.

        Checks ``~/.upbm`` and ``./.upbm``. Each file may declare a ``plugins``
        mapping of the form ``domain_name: "module.path:ClassName"``.
        """
        paths_to_check = [
            Path.home() / ".upbm",
            Path.cwd() / ".upbm",
        ]

        for p in paths_to_check:
            if p.exists() and p.is_file():
                try:
                    with open(p, "r") as f:
                        config = yaml.safe_load(f)

                    if config and isinstance(config, dict) and "plugins" in config:
                        for domain_name, module_path in config["plugins"].items():
                            if ":" in module_path:
                                mod_name, class_name = module_path.split(":", 1)
                            else:
                                print(
                                    f"Warning: Ignoring improperly formatted plugin target {module_path}"
                                )
                                continue

                            mod = importlib.import_module(mod_name)
                            generator_class = getattr(mod, class_name)
                            self.register(domain_name, generator_class)
                except Exception as e:
                    print(f"Warning: Failed to load plugins from {p}: {e}")

    def reload_plugins(self) -> None:
        """Re-run plugin discovery to pick up any newly installed plugins."""
        self.load_plugins()

    def __getitem__(self, key: str) -> Type[Generator]:
        res = self._domain_generators.get(key)
        if res is None:
            res = self._resolve(key)
            self._domain_generators[key] = res
        return res

    def _resolve(self, domain_name: str) -> Type[Generator]:
        if domain_name in self._registry:
            return self._registry[domain_name]
        raise ValueError(f"Unknown domain: {domain_name}")

    # ── Domain operations ─────────────────────────────────────────────────────

    @staticmethod
    def parse_configuration(
        params: dict[str, Any], config_space: ConfigurationSpace
    ) -> Configuration:
        """Convert a plain ``{param: value}`` dict to a typed :class:`Configuration`.

        Unknown keys raise :exc:`ValueError`.  Missing keys are filled from
        hyperparameter defaults where available.
        """
        np: dict[str, Any] = {}
        for k, v in params.items():
            if k not in config_space:
                raise ValueError(
                    f"Unknown parameter '{k}' for configuration space {config_space}"
                )
            hp = config_space[k]
            V = hp.sample_value().__class__
            try:
                np[k] = V(v)
            except Exception as e:
                raise ValueError(
                    f"Invalid value {v!r} for parameter '{k}' of type {V}"
                ) from e
        for k, hp in config_space.items():
            if k not in np:
                if hp.default_value is not None:
                    np[k] = hp.default_value
                else:
                    raise ValueError(f"Missing required parameter '{k}'")
        return Configuration(configuration_space=config_space, values=np)

    def get_domain_parameter_space(self, domain: str) -> ConfigurationSpace:
        """Return the domain-level :class:`ConfigurationSpace` for *domain*."""
        return self[domain].get_domain_parameter_space()

    def get_instance_parameter_space(
        self, domain: str, domain_params: Configuration
    ) -> ConfigurationSpace:
        """Return the instance-level :class:`ConfigurationSpace` for *domain*."""
        return self[domain](domain_params).instance_parameter_space

    def is_pddl_expressible(self, domain: str, domain_params: Configuration) -> bool:
        """Return True if the domain with the given parameters is PDDL expressible."""
        return self[domain](domain_params).pddl_expressible

    def generate_instance(
        self, domain: str, domain_params: Configuration, instance_params: Configuration
    ) -> Problem:
        """Generate and return a single planning :class:`Problem`."""
        return self[domain](domain_params).get_instance(instance_params)

    def sample_instances(
        self,
        domain: str,
        domain_params: Configuration,
        n: int,
        instance_parameter_space: Optional[ConfigurationSpace] = None,
    ) -> list[Problem]:
        """Sample *n* planning problems with randomly drawn instance parameters.

        *fixed_instance_params* pins specific instance parameters to fixed values
        while the rest are sampled at random.
        """
        generator = self[domain](domain_params)
        problems: list[Problem] = []

        instance_params_generator = generator.sample(
            instance_parameters_space=instance_parameter_space
        )
        for _ in range(n):
            instance_params = next(instance_params_generator)
            problems.append(generator.get_instance(instance_params))
        return problems

    def generate_dataset(
        self, dataset_spec: Path
    ) -> tuple[list[tuple[str, Problem]], bool]:
        """Parse a YAML dataset spec file and return ``(name, Problem)`` pairs."""
        with open(dataset_spec, "r") as f:
            spec = yaml.safe_load(f)

        domain = spec.get("domain")
        domain_params_dict = spec.get("params", {})
        instances = spec.get("instances", [])

        dom_space = self.get_domain_parameter_space(domain)
        domain_params = self.parse_configuration(domain_params_dict, dom_space)
        inst_space = self.get_instance_parameter_space(domain, domain_params)

        results: list[tuple[str, Problem]] = []
        for i, inst in enumerate(instances):
            name = inst.get("name", f"instance_{i + 1}")
            instance_params = self.parse_configuration(
                inst.get("params", {}), inst_space
            )
            problem = self.generate_instance(domain, domain_params, instance_params)
            results.append((name, problem))

        pddl_expressible = self.is_pddl_expressible(domain, domain_params)
        return results, pddl_expressible
