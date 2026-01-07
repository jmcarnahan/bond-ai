from bondable.bond.config import Config
from bondable.bond.providers.provider import Provider


def get_bond_provider() -> Provider:
    """FastAPI dependency to get an instance of the Bond Provider."""
    return Config.config().get_provider()
