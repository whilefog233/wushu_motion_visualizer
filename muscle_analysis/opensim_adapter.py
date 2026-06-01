class OpenSimAdapter:
    """
    Reserved adapter for future OpenSim / OpenCap integration.
    Current version does not run real OpenSim simulation.
    """

    def __init__(self):
        pass

    def is_available(self):
        return False

    def run_inverse_dynamics(self, *args, **kwargs):
        raise NotImplementedError("OpenSim integration is reserved for future versions.")
