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

from enum import Enum
from pathlib import Path
from typing import Optional, List

from ConfigSpace import ConfigurationSpace
import unified_planning as up
from unified_planning.model import Problem  # type: ignore[import-untyped]
from unified_planning.plans import Plan
from unified_planning.io import PDDLWriter, ANMLWriter  # type: ignore[import-untyped]
from fractions import Fraction
import re
import warnings


class Format(str, Enum):
    PDDL = "pddl"
    ANML = "anml"


def warn_if_metric_lost(instance: Problem) -> None:
    """Warn that the quality metrics of *instance* are not written to ANML.

    ANML has no syntax for plan quality metrics, so a problem that defines one
    loses it when it is written out in that format. This is only a warning: a
    plan for the resulting problem is still a valid plan, it is just not
    optimised for the metric.
    """
    if instance.quality_metrics:
        metrics = ", ".join(str(m) for m in instance.quality_metrics)
        warnings.warn(
            f"The ANML format cannot express plan quality metrics, so "
            f"[{metrics}] will not appear in the output. The problem is still "
            f"written and remains solvable, but not optimisable.",
            UserWarning,
            stacklevel=2,
        )


def dump_instance(
    instance: Problem,
    format: Format,
    output_prob: Path,
    output_dom: Optional[Path] = None,
) -> None:
    """Write a Problem to disk in the given format.

    For PDDL, both *output_prob* and *output_dom* must be provided.
    For ANML, only *output_prob* is required.
    """
    if format == Format.PDDL:
        if output_dom is None or output_prob is None:
            raise ValueError(
                "Both output domain and problem files must be specified for PDDL format"
            )
        writer = PDDLWriter(instance)
        writer.write_domain(str(output_dom))
        writer.write_problem(str(output_prob))
    elif format == Format.ANML:
        warn_if_metric_lost(instance)
        writer = ANMLWriter(instance)
        writer.write_problem(str(output_prob))
    else:
        raise ValueError(f"Unknown format: {format}")


def print_instance(instance: Problem, format: Format) -> None:
    """Print a Problem to stdout in the given format."""
    if format == Format.PDDL:
        writer = PDDLWriter(instance)
        writer.print_domain()
        writer.print_problem()
    elif format == Format.ANML:
        warn_if_metric_lost(instance)
        writer = ANMLWriter(instance)
        writer.print_problem()
    else:
        raise ValueError(f"Unknown format: {format}")


def print_parameter_space(space: ConfigurationSpace) -> None:
    """Print the parameters in the given ConfigurationSpace in a pretty table."""
    hps = space.get_hyperparameters()
    if not hps:
        print("No parameters found.")
        return

    # Table headers
    headers = ["Parameter", "Type", "Values/Range", "Default"]

    # Process each HP to get its data
    rows = []
    for hp in hps:
        name = hp.name
        hp_type = type(hp).__name__.replace("Hyperparameter", "")

        # Format the values/range
        if hasattr(hp, "choices"):
            # Categorical
            values = "{" + ", ".join(map(str, hp.choices)) + "}"
        elif hasattr(hp, "lower") and hasattr(hp, "upper"):
            # Numerical
            values = f"[{hp.lower}, {hp.upper}]"
        elif hasattr(hp, "value"):
            # Constant
            values = str(hp.value)
        else:
            values = "N/A"

        default = str(hp.default_value) if hasattr(hp, "default_value") else "N/A"

        rows.append([name, hp_type, values, default])

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    # Print the table
    separator = "+" + "+".join(["-" * (w + 2) for w in widths]) + "+"

    print(separator)
    header_row = (
        "|"
        + "|".join([f" {headers[i]:<{widths[i]}} " for i in range(len(headers))])
        + "|"
    )
    print(header_row)
    print(separator)

    for row in rows:
        data_row = (
            "|" + "|".join([f" {row[i]:<{widths[i]}} " for i in range(len(row))]) + "|"
        )
        print(data_row)

    print(separator)


def parse_plan_string(
    problem: Problem,
    plan_str: str,
) -> Plan:
    """
    The format of the string must be:
        ``(action-name param1 param2 ... paramN)`` in each line for SequentialPlans
        ``start-time: (action-name param1 param2 ... paramN) [duration]`` in each line for TimeTriggeredPlans,
        where ``[duration]`` is optional and not specified for InstantaneousActions.
    """
    actions: List = []
    is_tt = False
    for line in plan_str.splitlines():
        if re.match(r"^\s*(;.*)?$", line):
            continue
        s_ai = re.match(r"^\s*\(\s*([\w?-]+)((\s+[\w?-]+)*)\s*\)\s*$", line)
        t_ai = re.match(
            r"^\s*(\d+\.?\d*)\s*:\s*\(\s*([\w?-]+)((\s+[\w?-]+)*)\s*\)\s*(\[\s*(\d+\.?\d*)\s*\])?\s*$",
            line,
        )
        if s_ai:
            assert is_tt == False
            name = s_ai.group(1)
            params_name = s_ai.group(2).split()
        elif t_ai:
            is_tt = True
            start = Fraction(t_ai.group(1))
            name = t_ai.group(2)
            params_name = t_ai.group(3).split()
            dur = None
            if t_ai.group(6) is not None:
                dur = Fraction(t_ai.group(6))
        else:
            raise ValueError(f"Error parsing test plan:\n{plan_str}")

        action = problem.action(name)
        assert isinstance(action, up.model.Action), "Wrong plan or renaming."
        parameters = []
        for p in params_name:
            try:
                obj = problem.object(p)
                assert isinstance(obj, up.model.Object)
                parameters.append(problem.environment.expression_manager.ObjectExp(obj))
            except:
                parameters.append(problem.environment.expression_manager.Int(int(p)))
        act_instance = up.plans.ActionInstance(action, tuple(parameters))
        if is_tt:
            actions.append((start, act_instance, dur))
        else:
            actions.append(act_instance)
    if is_tt:
        return up.plans.TimeTriggeredPlan(actions)
    else:
        return up.plans.SequentialPlan(actions)
