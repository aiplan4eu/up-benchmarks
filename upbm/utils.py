from ConfigSpace import ConfigurationSpace, Constant, CategoricalHyperparameter, Integer
from typing import Dict, Any


MAX_INT = 2**31 - 1


def is_subspace(small: ConfigurationSpace, big: ConfigurationSpace):
    if len(small.keys()) != len(big.keys()):
        return False
    for key in small.keys():
        if key not in big.keys():
            return False
        small_hyperpar = small[key]
        big_hyperpar = big[key]
        if isinstance(small_hyperpar, Constant):
            # big is either a constant of the same value or a range that contains the value
            if isinstance(big_hyperpar, Constant):
                if type(big_hyperpar.value) != type(small_hyperpar.value):
                    raise TypeError(
                        f"Hyperparameter {small_hyperpar} does not have the same value type as {big_hyperpar}: { type(small_hyperpar.value)}, { type(big_hyperpar.value)}"
                    )
                if big_hyperpar.value != small_hyperpar.value:
                    return False

            else:  # range
                try:
                    big_lower, big_upper = hyperparam_range(big_hyperpar)
                except TypeError as e:
                    raise TypeError(
                        f"Hyperparameter {small_hyperpar} is only compatible with constants or ranges, {big_hyperpar} is neither"
                    )
                if type(big_upper) != type(small_hyperpar.value):
                    raise TypeError(
                        f"Hyperparameter {small_hyperpar} does not have the same value type as {big_hyperpar}: { type(small_hyperpar.value)}, { type(big_upper)}"
                    )
                if (
                    int(small_hyperpar.value) > big_upper
                    or int(small_hyperpar.value) < big_lower
                ):
                    return False
        elif isinstance(small_hyperpar, CategoricalHyperparameter):
            # big is categorical and contains all possible values found in small
            if not isinstance(big_hyperpar, CategoricalHyperparameter):
                return False
            for small_choice in small_hyperpar.choices:
                if small_choice not in big_hyperpar.choices:
                    return False
        else:
            # this should be a range, check min max
            small_lower, small_upper = hyperparam_range(small_hyperpar)
            big_lower, big_upper = hyperparam_range(big_hyperpar)
            if small_lower < big_lower:
                return False
            if small_upper > big_upper:
                return False
    return True


def hyperparam_range(hp):
    if isinstance(hp, Constant):
        return (hp.value, hp.value)
    if not (hasattr(hp, "lower") and hasattr(hp, "upper")):
        raise TypeError(f"Hyperparameter {hp} is not a range")
    return (hp.lower, hp.upper)


def fix_string_integer(p):
    try:
        return int(p)
    except:
        return p


def get_reduced_instance_space(large_space, reduction_dictionary):
    new_dict: Dict[str, Any] = {}
    for k, v in reduction_dictionary.items():
        assert k in large_space
        if isinstance(v, tuple):
            minval, maxval = v
            if minval > maxval:
                raise ValueError
            if minval == maxval:
                new_dict[k] = Constant(k, minval)
            else:
                new_dict[k] = Integer(k, (int(minval), int(maxval)))
        else:
            new_dict[k] = Constant(k, fix_string_integer(v))
    for k, v in large_space.items():
        if k in new_dict:
            continue
        new_dict[k] = v
    new_space = ConfigurationSpace(new_dict)
    assert is_subspace(new_space, large_space)
    return new_space
