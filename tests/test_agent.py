from bond_ai.bond.agent import Agent

def test_list_agents():
  agents = Agent.list_agents()
  assert len(agents) > 0
  [print(agent) for agent in agents]