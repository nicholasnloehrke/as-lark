class UnknownLabelException(Exception):
    closest = None
    token = None


class ImmediateOutOfRangeException(Exception):
    token = None
