from enum import Enum
from pathlib import Path
from typing import Optional

from ConfigSpace import ConfigurationSpace
from unified_planning.model import Problem  # type: ignore[import-untyped]
from unified_planning.io import PDDLWriter, ANMLWriter  # type: ignore[import-untyped]


class Format(str, Enum):
    PDDL = "pddl"
    ANML = "anml"


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
