class OpenBaoKMSAgent:
    """A class to handle Openbao KMS operations."""

    def __init__(self, address: str, token: str, transit_mount: str = "transit"):
        """Initializes the Openbao client."""
        self.address = address
        self.token = token
        self.transit_mount = transit_mount
