"""Entertainment side-game Web runtime for the MITM proxy."""

__all__ = ["EntertainmentRuntime"]


def __getattr__(name):
    # The standalone live viewer has no game/model dependencies.
    if name == "EntertainmentRuntime":
        from pf_entertainment.runtime import EntertainmentRuntime
        return EntertainmentRuntime
    raise AttributeError(name)
