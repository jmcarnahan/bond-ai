import logging
LOGGER = logging.getLogger(__name__)

import json
from bondable.bond.config import Config
from bondable.bond.agent import Agent
from bondable.bond.broker import Broker, BrokerConnectionEmpty
from bondable.bond.metadata import Metadata, AgentRecord
from bondable.bond.definition import AgentDefinition
from bondable.bond.cache import bond_cache
from IPython.display import Image, display
import threading
import base64



class AgentBuilder:

    # Using this class so that I dont need to set up and tear down assistants each time
    def __init__(self):
        self.metadata = Metadata.metadata()
        self.openai_client = Config.config().get_openai_client()
        self.context = {"agents": {}}
        # atexit.register(self.cleanup)
        LOGGER.info(f"Created AgentBuilder instance")

    @classmethod
    @bond_cache
    def builder(cls):
        return AgentBuilder()


    def cleanup(self):
        """This will delete all records and remove them from openai"""
        self.metadata.cleanup()

    def get_agent(self, agent_def: AgentDefinition, user_id: str) -> Agent:
        # agent_def.init_resources()
        with self.metadata.get_db_session() as session:
            agent_record = session.query(AgentRecord).filter(AgentRecord.name == agent_def.name).first()
            agent = None

            if agent_record:
                assistant_id = agent_record.assistant_id
                existing_agent_def = AgentDefinition.from_assistant(assistant_id=assistant_id)
                LOGGER.debug(f"Existing Agent Def: {existing_agent_def}")
                LOGGER.debug(f"New Agent Def: {agent_def}")

                if existing_agent_def.get_hash() != agent_def.get_hash():
                    assistant = self.openai_client.beta.assistants.update(
                        assistant_id=assistant_id,
                        name=agent_def.name,
                        description=agent_def.description,
                        instructions=agent_def.instructions,
                        model=agent_def.model,
                        tools=agent_def.tools,
                        tool_resources=agent_def.tool_resources,
                        metadata=agent_def.metadata
                    )
                    LOGGER.debug(f"Tool Resources: {json.dumps(agent_def.tool_resources, sort_keys=True, indent=4)}")
                    LOGGER.info(f"Updated agent [{agent_def.name}] with assistant_id: {assistant_id}")
                else:
                    assistant = self.openai_client.beta.assistants.retrieve(assistant_id=assistant_id)
                    LOGGER.debug(f"Tool Resources: {json.dumps(agent_def.tool_resources, sort_keys=True, indent=4)}")
                    LOGGER.info(f"Reusing agent [{agent_def.name}] with assistant_id: {assistant_id}")
                agent = Agent(assistant=assistant)
            else:
                assistant = self.openai_client.beta.assistants.create(
                    name=agent_def.name,
                    description=agent_def.description,
                    instructions=agent_def.instructions,
                    model=agent_def.model,
                    tools=agent_def.tools,
                    tool_resources=agent_def.tool_resources,
                    metadata=agent_def.metadata
                )
                agent = Agent(assistant=assistant)
                agent_record = self.metadata.create_agent_record(
                    name=agent_def.name,
                    assistant_id=assistant.id,
                    user_id=user_id,
                )
                LOGGER.debug(f"Tool Resources: {json.dumps(agent_def.tool_resources, sort_keys=True, indent=4)}")
                LOGGER.info(f"Created new agent [{agent_def.name}] with assistant_id: {assistant.id}")

            self.context["agents"][agent_def.name] = agent
            return agent

    def get_context(self):
        return self.context

    def display_message (self, message):
        if message.role == 'system':
            LOGGER.debug(f"Received system message, ignoring {message.message_id}")
            return
        if message.type == "text":
            print(f"[{message.message_id}/{message.role}] => {message.clob.get_content()}")
        elif message.type == "image_file":
            print(f"[{message.message_id}/{message.role}] => ")
            content = message.clob.get_content()
            if content.startswith('data:image/png;base64,'):
                base64_image = content[len('data:image/png;base64,'):]
                image_data = base64.b64decode(base64_image)
                display(Image(data=image_data))
            else:
                print(content)
        else:
            LOGGER.error(f"Unknown message type {type}")

    def print_responses (self, user_id, prompts, agent_def: AgentDefinition):
        thread_id = self.metadata.create_thread(user_id=user_id)
        try:
            broker = Broker.broker()
            conn = broker.connect(thread_id=thread_id, subscriber_id=user_id)
            agent = self.get_agent(agent_def, user_id=user_id)
            for prompt in prompts:
            
                message = agent.create_user_message(prompt, thread_id)
                thread = threading.Thread(target=agent.broadcast_response, args=(None, thread_id), daemon=True)
                thread.start()
                while True:
                    try:
                        bond_msg = conn.wait_for_message(timeout=5)
                        if bond_msg is None:
                            break
                        self.display_message(bond_msg)
                        if bond_msg.is_done:
                            break
                    except BrokerConnectionEmpty:
                        continue
                    except Exception as e:
                        LOGGER.error(f"Error: {e}")
                        break
                thread.join()

            conn.close()
        finally:
            self.metadata.delete_thread(thread_id)




