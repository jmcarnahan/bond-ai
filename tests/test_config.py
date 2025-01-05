from bond_ai.bond.config import Config

def test_openai():
  openai_client = Config.get_openai_client()
  assert openai_client is not None