from unified_planning.shortcuts import (
    Problem,
    UserType,
    Fluent,
    BoolType,
    DurativeAction,
    RealType,
    StartTiming,
    EndTiming,
    Not,
    ClosedTimeInterval,
)


def get_legacy_domain():
    domain = Problem("MatchCellar")

    Match = UserType("match")
    Fuse = UserType("fuse")

    handfree = Fluent("handfree")
    light = Fluent("light")
    match_used = Fluent("match_used", BoolType(), match=Match)
    fuse_mended = Fluent("fuse_mended", BoolType(), fuse=Fuse)
    mend_fuse_duration = Fluent("mend_fuse_duration", RealType(0, 6))
    domain.add_fluent(handfree, default_initial_value=True)
    domain.add_fluent(light, default_initial_value=False)
    domain.add_fluent(match_used, default_initial_value=False)
    domain.add_fluent(fuse_mended, default_initial_value=False)
    domain.add_fluent(mend_fuse_duration, default_initial_value=6)

    light_match = DurativeAction("light_match", m=Match)
    m = light_match.parameter("m")
    light_match.set_fixed_duration(7)
    light_match.add_condition(StartTiming(), Not(match_used(m)))
    light_match.add_effect(StartTiming(), match_used(m), True)
    light_match.add_effect(StartTiming(), light, True)
    light_match.add_effect(EndTiming(), light, False)
    domain.add_action(light_match)

    mend_fuse = DurativeAction("mend_fuse", f=Fuse)
    f = mend_fuse.parameter("f")
    mend_fuse.set_fixed_duration(mend_fuse_duration)
    mend_fuse.add_condition(StartTiming(), handfree)
    mend_fuse.add_condition(ClosedTimeInterval(StartTiming(), EndTiming()), light)
    mend_fuse.add_effect(StartTiming(), handfree, False)
    mend_fuse.add_effect(EndTiming(), fuse_mended(f), True)
    mend_fuse.add_effect(EndTiming(), handfree, True)
    domain.add_action(mend_fuse)

    return domain
