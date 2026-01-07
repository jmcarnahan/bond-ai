import logging
LOGGER = logging.getLogger(__name__)

from bondable.bond.builder import AgentBuilder, AgentDefinition
from bondable.bond.config import Config
from bondable.bond.functions import Functions
from bondable.bond.cache import bond_cache_clear
import os
import sys
import pytest
import pandas as pd
import base64
import hashlib
import tempfile


class TestBuilder:

  @pytest.fixture
  def setup(self):
      bond_cache_clear()
      config = Config.config()
      builder = AgentBuilder()

      data = {
        'Customer_ID': [1, 2, 3],
        'First_Name': ['Jack', 'Jane', 'Doe'],
        'Last_Name': ['Doe', 'Smith', 'Johnson'],
        'Email': ['john.doe@example.com', 'jane.smith@example.com', 'doe.johnson@example.com'],
        'Phone_Number': ['123-456-7890', '234-567-8901', '345-678-9012'],
        'Region': ['North', 'South', 'East'],
        'Salesperson': ['Alice', 'Bob', 'Charlie'],
        'Address': ['123 Elm St', '456 Oak St', '789 Pine St'],
        'ZIP_Code': ['12345', '23456', '34567'],
        'Last_Purchase_Amount': [100.50, 200.75, 150.00]
      }
      df = pd.DataFrame(data)
      data_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=True)
      df.to_csv(data_file.name, index=False)
      html_file = tempfile.NamedTemporaryFile(suffix=".html", delete=True)
      df.to_html(html_file.name, index=False)

      yield builder, config, data_file, html_file

      builder.cleanup()
      os.remove(data_file.name)
      os.remove(html_file.name)

  def test_get_agent_1(self, setup):
    builder, config, data_file, html_file = setup
    assert len(builder.get_context()['agents']) == 0
    agent_def = AgentDefinition(
      name='Simple Agent',
      description='You are a helpful assistant that answers questions in a single sentence',
      instructions='You are a helpful assistant that answers questions in a single sentence',
    )
    agent = builder.get_agent(agent_def)
    assert agent is not None
    assert agent.get_name() == 'Simple Agent'
    assert agent.get_description() == 'You are a helpful assistant that answers questions in a single sentence'
    assert len(builder.get_context()['agents']) == 1
    assert builder.get_context()['agents']['Simple Agent'].get_name() == 'Simple Agent'

  def test_get_agent_2(self, setup):
    builder, config, data_file, html_file = setup

    # create the agent
    agent_def = AgentDefinition(
      name='Simple Agent',
      description='You are a helpful assistant that answers questions in a single sentence',
      instructions='Help users by answering questions in a single sentence',
    )
    agent = builder.get_agent(agent_def)
    assert agent is not None
    assistant = config.get_openai_client().beta.assistants.retrieve(agent.get_assistant_id())
    assert assistant is not None
    assert assistant.name == agent_def.name
    assert assistant.description == agent_def.description
    assert assistant.instructions == agent_def.instructions

    # update the agent get it again
    agent_def.instructions='Answer questions like a pirate'
    agent = builder.get_agent(agent_def)
    assert agent is not None
    assistant = config.get_openai_client().beta.assistants.retrieve(agent.get_assistant_id())
    assert assistant is not None
    assert assistant.name == agent_def.name
    assert assistant.description == agent_def.description
    assert assistant.instructions == agent_def.instructions

  def test_get_agent_3(self, setup):
    builder, config, data_file, html_file = setup

    agent_def = AgentDefinition(
        name="File Agent",
        description="An agent that will load data about people and answer questions",
        instructions="""
        Answer questions about user data in the attached CSV file. The first row contains the
        names of the columns.
        """,
        tools=[{"type": "code_interpreter"}],
        tool_resources={
          "code_interpreter": {
            "files": [data_file.name]
          }
        }
    )

    agent = builder.get_agent(agent_def)
    assert agent is not None
    assistant = config.get_openai_client().beta.assistants.retrieve(agent.get_assistant_id())
    assert assistant is not None
    assert assistant.name == agent_def.name
    assert assistant.description == agent_def.description
    assert assistant.instructions == agent_def.instructions
    tool_resources = AgentDefinition.to_dict(assistant.tool_resources)
    assert len(tool_resources['code_interpreter']['file_ids']) == 1

    # update the agent get it again
    agent_def = AgentDefinition(
        name="File Agent",
        description="An agent that will load data about people and answer questions",
        instructions="""
        Answer questions like a pirate
        """,
        tools=[{"type": "code_interpreter"}],
        tool_resources={
          "code_interpreter": {
            "files": [data_file.name]
          }
        }
    )

    agent = builder.get_agent(agent_def)
    assert agent is not None
    assistant = config.get_openai_client().beta.assistants.retrieve(agent.get_assistant_id())
    assert assistant is not None
    assert assistant.name == agent_def.name
    assert assistant.description == agent_def.description
    assert assistant.instructions == agent_def.instructions
    tool_resources = AgentDefinition.to_dict(assistant.tool_resources)
    assert len(tool_resources['code_interpreter']['file_ids']) == 1

  def test_file_hash_1(self, setup):
    builder, config, data_file, html_file = setup
    file_record = builder._get_file_record(data_file.name)
    assert file_record is not None
    assert file_record['content'] is not None
    assert file_record['path'] == data_file.name
    assert file_record['file_hash'] is not None
    file_hash = hashlib.sha256(file_record['content']).hexdigest()
    assert file_hash == file_record['file_hash']

  def test_vector_store_1(self, setup):
    builder, config, data_file, html_file = setup
    vector_store_id = builder._get_or_create_vector_store('test_vector_store')
    assert vector_store_id is not None
    new_vector_store_id = builder._get_or_create_vector_store('test_vector_store')
    assert new_vector_store_id == vector_store_id

  def test_vector_store_2(self, setup):
    builder, config, data_file, html_file = setup

    vector_store_id = builder.get_vector_store(name='test_vector_store', files=[html_file.name])
    assert vector_store_id is not None
    file_id = builder.get_file_id(html_file.name)
    assert file_id is not None
    vector_store_file = config.get_openai_client().vector_stores.files.retrieve(
      vector_store_id=vector_store_id,
      file_id=file_id
    )
    assert vector_store_file is not None
    vector_store_file = vector_store_file.to_dict()
    assert vector_store_file['id'] == file_id

    new_vector_store_id = builder.get_vector_store(name='test_vector_store', files=[html_file.name])
    assert new_vector_store_id is not None
    assert new_vector_store_id == vector_store_id

    new_file_id = builder.get_file_id(html_file.name)
    assert new_file_id is not None
    assert new_file_id == file_id

    new_vector_store_file = config.get_openai_client().vector_stores.files.retrieve(
      vector_store_id=new_vector_store_id,
      file_id=new_file_id
    )
    assert new_vector_store_file is not None
    new_vector_store_file = new_vector_store_file.to_dict()
    assert new_vector_store_file['id'] == file_id

  def test_get_agent_4(self, setup):
    builder, config, data_file, html_file = setup

    agent_def = AgentDefinition(
        name="HTML File Agent",
        description="An agent that uses file search to help people answer questions",
        instructions="""
        Use file search to help people answer questions
        """,
        tools=[{"type": "file_search"}],
        tool_resources={
          "file_search": {
            "files": [html_file.name]
          }
        }
    )

    agent = builder.get_agent(agent_def)
    assert agent is not None
    assistant = config.get_openai_client().beta.assistants.retrieve(agent.get_assistant_id())
    assert assistant is not None
    assert assistant.name == agent_def.name
    assert assistant.description == agent_def.description
    assert assistant.instructions == agent_def.instructions
    tool_resources = AgentDefinition.to_dict(assistant.tool_resources)
    assert len(tool_resources['file_search']['vector_store_ids']) == 1
    file_id = builder.get_file_id(html_file.name)
    assert file_id is not None
    vector_store_file = config.get_openai_client().vector_stores.files.retrieve(
      vector_store_id=tool_resources['file_search']['vector_store_ids'][0],
      file_id=file_id
    )
    assert vector_store_file is not None
    vector_store_file = vector_store_file.to_dict()
    assert vector_store_file['id'] == file_id

    agent_def = AgentDefinition(
        name="HTML File Agent",
        description="An agent that uses file search to help people answer questions",
        instructions="""
        Use file search to help people answer questions
        """,
        tools=[{"type": "file_search"}],
        tool_resources={
          "file_search": {
            "files": [html_file.name]
          }
        }
    )

    agent = builder.get_agent(agent_def)
    assert agent is not None
    assistant = config.get_openai_client().beta.assistants.retrieve(agent.get_assistant_id())
    assert assistant is not None
    new_tool_resources = AgentDefinition.to_dict(assistant.tool_resources)
    assert len(new_tool_resources['file_search']['vector_store_ids']) == 1
    new_file_id = builder.get_file_id(html_file.name)
    assert new_file_id is not None
    assert new_file_id == file_id

    new_vector_store_file = config.get_openai_client().vector_stores.files.retrieve(
      vector_store_id=new_tool_resources['file_search']['vector_store_ids'][0],
      file_id=new_file_id
    )
    assert new_vector_store_file is not None
    new_vector_store_file = new_vector_store_file.to_dict()
    assert new_vector_store_file['id'] == file_id



  def test_get_agent_5(self, setup):
    builder, config, data_file, html_file = setup
    functions = Functions.functions()
    agent_def = AgentDefinition(
        name="Function Agent",
        description="Say hello to the user.",
        instructions="Call the simple method 'hello' with the name provided by the user. If no name is provided, ask the user to provide a name.",
        metadata={'visible': 'True'},
        tools=[functions.hello],
    )
    agent = builder.get_agent(agent_def)
