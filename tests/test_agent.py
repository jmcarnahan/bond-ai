from bond_ai.bond.agent import Agent, AgentResponseHandler
from bond_ai.bond.threads import Threads
from bond_ai.bond.config import Config


def test_list_agents():
  agents = Agent.list_agents()
  assert len(agents) > 0

def test_simple_agent():
  pass

class MyFunctionsAgentHandler(AgentResponseHandler):
  def __init__(self):
    self.response = ""

  def on_content(self, content, id, type, role):
    self.response += " " + content

  def on_done(self, success=True, message=None):
    pass


def test_functions_agent():
  openai_client = Config.get_openai_client()
  functions_assistant = openai_client.beta.assistants.create(
      name="Functions Agent",
      instructions="""
      You are a helpful assistant that answers questions about numbers. When the user
      gives you two numbers, you will use them to call the function 'use_numbers'. The use
      the result of that function to answer the question.
      """,
      tools=[{"type": "code_interpreter"},
        {
          "type": "function",
          "function": {
            "name": "use_numbers",
            "description": "use two numbers to generate a result",
            "parameters": {
              "type": "object",
              "properties": {
                "a": {
                  "type": "integer",
                  "description": "first number"
                },
                "b": {
                  "type": "integer",
                  "description": "second number"
                },
              },
              "required": ["a", "b"]
            }
          }
        }],
      model=Config.get_openai_deployment(),
  )
  assert functions_assistant is not None

  threads = Threads(user_id="test")
  thread_id = threads.create_thread()
  assert thread_id is not None

  handler = MyFunctionsAgentHandler()
  agent = Agent.get_agent_by_name("Functions Agent")
  assert agent is not None
  agent.handle_response("The numbers are 3 and 4", thread_id, handler)
  assert len(handler.response) > 0
  assert "-1" in handler.response
  print(handler.response)

  threads.delete_thread(thread_id)

  response = openai_client.beta.assistants.delete(assistant_id=functions_assistant.id)
  assert response is not None
  assert response.deleted == True