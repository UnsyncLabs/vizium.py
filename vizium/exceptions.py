class ViziumError(Exception):
    """Base exception for the Vizium bot client."""


class InvalidToken(ViziumError):
    pass


class InvalidChannel(ViziumError):
    pass


class AlreadyConnected(ViziumError):
    pass


class WebSocketClosure(ViziumError):
    pass


class UnsupportedOperation(ViziumError):
    pass
