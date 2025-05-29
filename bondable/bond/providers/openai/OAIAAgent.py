

import io
from PIL import Image
from bondable.bond.functions import Functions
from bondable.bond.definition import AgentDefinition
from bondable.bond.cache import bond_cache
from bondable.bond.providers.metadata import Metadata
from bondable.bond.providers.agent import Agent, AgentProvider
from bondable.bond.providers.openai.OAIAMetadata import OAIAMetadata
from typing_extensions import override
from typing import List, Dict, Optional, Generator
from openai import OpenAI, AssistantEventHandler, NotFoundError
from openai.types.beta.assistant import Assistant
from openai.types.beta.threads import (
    Message,
    ImageFile,
    MessageDelta,
)
from queue import Queue
import threading
import logging
import base64
import abc
import json


LOGGER = logging.getLogger(__name__)


class EventHandler(AssistantEventHandler):  

    def __init__(self, message_queue: Queue, openai_client: OpenAI, functions, thread_id):
        super().__init__()
        self.message_queue = message_queue
        self.openai_client = openai_client
        self.functions = functions
        self.thread_id = thread_id

        self.current_msg = None
        self.message_state = 0
        self.files = {}
        LOGGER.debug("EventHandler initialized")

    @override
    def on_message_created(self, message: Message) -> None:
        # print(f"on_message_created: {message}")
        if self.current_msg is not None:
            LOGGER.error(f"Message created before previous message was done: {self.current_msg}")
        self.current_msg = message


    @override 
    def on_message_delta(self, delta: MessageDelta, snapshot: Message) -> None:
        LOGGER.debug(f"on_message_delta: {delta}")
        for part in delta.content:
            part_id = f"{self.current_msg.id}_{part.index}"
            if part.type == 'image_file':
                if self.message_state > 0:
                    self.message_queue.put('</_bondmessage>')
                    self.message_state = 0
                
                if part.image_file.file_id not in self.files:
                    self.message_queue.put(f"<_bondmessage id=\"{part_id}\" role=\"{self.current_msg.role}\" type=\"error\" thread_id=\"{self.thread_id}\" is_done=\"false\">")
                    self.message_queue.put("No image found.")
                    self.message_queue.put("</_bondmessage>")
                else:
                    self.message_queue.put(f"<_bondmessage id=\"{part_id}\" role=\"{self.current_msg.role}\" type=\"image_file\" thread_id=\"{self.thread_id}\" file=\"{part.image_file.file_id}\" is_done=\"false\">")
                    self.message_queue.put(f"{self.files[part.image_file.file_id]}")
                    self.message_queue.put("</_bondmessage>")
    
            elif part.type == 'text':
                if self.message_state == 0:
                    self.message_queue.put(f"<_bondmessage id=\"{part_id}\" role=\"{self.current_msg.role}\" type=\"text\" thread_id=\"{self.thread_id}\" is_done=\"false\">")
                self.message_queue.put(part.text.value)
                self.message_state += 1
            else:
                LOGGER.warning(f"Delta message of unhandled type: {delta}")


    @override 
    def on_message_done(self, message: Message) -> None:
        if self.message_state > 0:
            self.message_queue.put('</_bondmessage>')
            self.message_state = 0
        self.current_msg = None


    @override
    def on_end(self) -> None:
        self.message_queue.put(f"<_bondmessage id=\"-1\" role=\"system\" type=\"text\" thread_id=\"{self.thread_id}\" is_done=\"true\">")
        self.message_queue.put("Done.")
        self.message_queue.put("</_bondmessage>")
        self.message_queue.put(None)

    @override
    def on_exception(self, exception):
        LOGGER.error(f"Received assistant exception: {exception}")
        self.message_queue.put(f"<_bondmessage id=\"-1\" role=\"system\" type=\"text\" thread_id=\"{self.thread_id}\" is_done=\"false\" is_error=\"true\">")
        self.message_queue.put(f"An error occurred: " + str(exception))
        self.message_queue.put("</_bondmessage>")       

    @override
    def on_image_file_done(self, image_file: ImageFile) -> None:
        response_content = self.openai_client.files.content(image_file.file_id)
        data_in_bytes = response_content.read()
        readable_buffer = io.BytesIO(data_in_bytes)
        img_src = 'data:image/png;base64,' + base64.b64encode(readable_buffer.getvalue()).decode('utf-8')
        self.files[image_file.file_id] = img_src

    @override
    def on_tool_call_done(self, tool_call) -> None:
        # LOGGER.info(f"on_tool_call_done: {tool_call}")
        match self.current_run.status:
            case "completed":
                LOGGER.debug("Completed.")
            case "failed":
                LOGGER.error(f"Run failed: {str(self.current_run.last_error)}")
            case "expired":
                LOGGER.error(f"Run expired")
            case "cancelled":
                LOGGER.error(f"Run cancelled")
            case "in_progress":
                LOGGER.debug(f"In Progress ...")
            case "requires_action":
                LOGGER.debug(f"on_tool_call_done: requires action")
                tool_call_outputs = []
                for tool_call in self.current_event.data.required_action.submit_tool_outputs.tool_calls:
                    if tool_call.type == "function":
                        function_to_call = getattr(self.functions, tool_call.function.name, None)
                        arguments =  json.loads(tool_call.function.arguments) if hasattr(tool_call.function, 'arguments') else {}
                        if function_to_call:
                            try:
                                LOGGER.debug(f"Calling function {tool_call.function.name}")
                                result = function_to_call(**arguments)
                                tool_call_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": result
                                })
                            except Exception as e:
                                LOGGER.error(f"Error calling function {tool_call.function.name}: {e}")
                        else:
                            LOGGER.error(f"No function was defined: {tool_call.function.name}")
                    else:
                        LOGGER.error(f"Unhandled tool call type: {tool_call.type}")
                if tool_call_outputs:
                    try: 
                        with self.openai_client.beta.threads.runs.submit_tool_outputs_stream(
                            thread_id=self.current_run.thread_id,
                            run_id=self.current_run.id,
                            tool_outputs=tool_call_outputs,
                            event_handler=EventHandler(
                                openai_client=self.openai_client,
                                message_queue=self.message_queue,
                                functions=self.functions,
                                thread_id=self.thread_id
                            )
                        ) as stream:
                            stream.until_done() 
                    except Exception as e:
                        LOGGER.error(f"Failed to submit tool outputs {tool_call_outputs}: {e}")
            case _:
                LOGGER.warning(f"Run status is not handled: {self.current_run.status}")


class OAIAAgent(Agent):

    def __init__(self, assistant: Assistant, agent_def: AgentDefinition, openai_client: OpenAI):
        super().__init__()
        self.assistant_id = assistant.id
        self.agent_def = agent_def
        self.name = assistant.name
        self.description = assistant.description
        self.model = assistant.model
        self.agent_metadata = assistant.metadata if assistant.metadata else {}
        self.openai_client = openai_client
        self.functions = Functions.functions()
        if 'user_id' not in self.agent_metadata:
            self.agent_metadata['user_id'] = agent_def.user_id
        LOGGER.debug(f"Initialized OAIARunner with assistant id: {self.assistant_id}")

    @override
    def get_agent_id(self) -> str:
        return self.assistant_id
    
    @override
    def get_agent_definition(self) -> AgentDefinition:
        return self.agent_def

    @override
    def get_name(self) -> str:
        """
        Returns the name of the agent.
        """
        return self.name

    @override
    def get_description(self) -> str:
        """
        Returns the description of the agent.
        """
        return self.description
    
    @override
    def get_metadata_value(self, key, default_value=None):
        if key in self.agent_metadata:
            return self.agent_metadata[key]
        else:
            return default_value

    @override
    def get_metadata(self) -> Dict[str, str]:
        """
        Returns the metadata of the agent.
        """
        return self.agent_metadata

    @override
    def create_user_message(self, prompt, thread_id, attachments=None, override_role="user") -> str:
        msg = self.openai_client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt,
            attachments=attachments,
            metadata={"override_role": override_role}
        )
        return msg.id

    @override
    def stream_response(self, prompt=None, thread_id=None, attachments=None) -> Generator[str, None, None]:
        LOGGER.debug(f"Agent streaming response using assistant id: {self.assistant_id}")

        if prompt is not None:
            user_message_id = self.create_user_message(prompt=prompt, thread_id=thread_id, attachments=attachments)
            LOGGER.debug(f"Created new user message: {user_message_id}")
        message_queue = Queue()

        with self.openai_client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
            event_handler=EventHandler(
                message_queue=message_queue,
                openai_client=self.openai_client,
                functions=self.functions,
                thread_id=thread_id
            )
        ) as stream:
            stream_thread: threading.Thread = threading.Thread(target=stream.until_done, daemon=True)
            stream_thread.start()
            streaming = True
            while streaming:
                try:
                    message = message_queue.get()
                    if message is not None:
                        yield message
                    else: 
                        streaming = False       
                except EOFError:
                    streaming = False 
            message_queue.task_done()   
            stream_thread.join()
            stream.close()

            # if the functions have any files we need to add them to the thread after the run
            code_file_ids = self.functions.consume_code_file_ids()
            if code_file_ids:
                for file_id in code_file_ids:
                    # attachments = [  
                    #     {"file_id": file_id, "tools": [{"type": "code_interpreter"}]}
                    # ]
                    # message = self.create_user_message(self, "data file from last run", thread_id, attachments=attachments)
                    message = self.openai_client.beta.threads.messages.create(
                        thread_id=thread_id,
                        role="user",
                        content=f"__FILE__{file_id}",
                        attachments=[  
                            {"file_id": file_id, "tools": [{"type": "code_interpreter"}]}
                        ],
                        metadata={"override_role": "system"}
                    )
                LOGGER.info(f"Added code files to thread: {code_file_ids} from functions")
            return
        




class OAIAAgentProvider(AgentProvider):
    """
    Abstract base class for agent providers.
    This class should be extended by any specific agent provider implementation.
    """
    def __init__(self, openai_client, metadata):
        super().__init__(metadata=metadata)
        self.openai_client = openai_client

    # @classmethod
    # @bond_cache
    # def provider(cls) -> AgentProvider:
    #     return OAIAAgentProvider()

    @override
    def delete_agent_resource(self, agent_id: str) -> bool:
        """
        Deletes an agent by its ID. This method should be implemented by subclasses.
        Don't throw an exception if it does not exist, just return False.
        """
        try:
            self.openai_client.beta.assistants.delete(agent_id)
            LOGGER.info(f"Successfully deleted agent {agent_id} from provider.")
            return True
        except NotFoundError: 
            LOGGER.warning(f"Agent {agent_id} not found on provider. Considered 'deleted' for provider part.")
            return False
        except Exception as e:
            LOGGER.error(f"Error deleting agent {agent_id} from provider: {e}", exc_info=True)
            raise e
        

    def get_definition(self, assistant: Assistant) -> AgentDefinition:
        """Create an AgentDefinition from an OpenAI Assistant."""
        agent_def = AgentDefinition(
            name=assistant.name,
            description=assistant.description,
            instructions=assistant.instructions,
            tools=assistant.tools,
            tool_resources=assistant.tool_resources,
            metadata=assistant.metadata,
            id=assistant.id,
            model=assistant.model,
            user_id=assistant.metadata.get('user_id', None)
        )
        return agent_def


    @override
    def create_or_update_agent_resource(self, agent_def: AgentDefinition, owner_user_id: str) -> Agent:
        """
        Creates a new agent. This method should be implemented by subclasses.
        Returns the created agent.
        """
        openai_assistant_obj = None # Holds the final OpenAI assistant object

        if agent_def.metadata is None:
            agent_def.metadata = {}
        agent_def.metadata['owner_user_id'] = owner_user_id  # ensure the owner is set in metadata

        if agent_def.id:  # ID is provided: implies update an existing agent
            LOGGER.info(f"Agent ID '{agent_def.id}' provided. Attempting to retrieve/update.")
            try:
                # Retrieve from OpenAI first - this is the source of truth for existence by ID
                openai_assistant_obj = self.openai_client.beta.assistants.retrieve(assistant_id=agent_def.id)
                LOGGER.info(f"Retrieved OpenAI assistant with ID: {agent_def.id}")

                # Compare definitions to see if OpenAI assistant needs an update
                current_definition_from_openai = self.get_definition(assistant=openai_assistant_obj)
                agent_def.name = agent_def.name if agent_def.name is not None else openai_assistant_obj.name
                agent_def.model = agent_def.model if agent_def.model else current_definition_from_openai.model

                
                if current_definition_from_openai.get_hash() != agent_def.get_hash():
                    LOGGER.info(f"Definition changed for agent ID {agent_def.id}. Updating OpenAI assistant.")
                    openai_assistant_obj = self.openai_client.beta.assistants.update(
                        assistant_id=agent_def.id,
                        name=agent_def.name,
                        description=agent_def.description,
                        instructions=agent_def.instructions,
                        model=agent_def.model,
                        tools=agent_def.tools,
                        tool_resources=agent_def.tool_resources,
                        metadata=agent_def.metadata
                    )
                    LOGGER.info(f"Successfully updated OpenAI assistant for ID: {agent_def.id}")
                else:
                    LOGGER.info(f"No definition changes detected for agent ID {agent_def.id}. OpenAI assistant not updated.")

            except Exception as e: # Catches openai.NotFoundError and other issues
                LOGGER.error(f"Error processing agent with ID {agent_def.id}: {e}", exc_info=True)
                raise Exception(f"Failed to retrieve or update agent with ID {agent_def.id}. Original error: {str(e)}")

        else:  # No agent_def.id provided: this is a create new agent scenario
            if not agent_def.name:
                raise ValueError("Agent name must be provided for creation.")
            LOGGER.info(f"No ID provided. Attempting to create new agent named '{agent_def.name}'")

            LOGGER.info(f"Creating new OpenAI assistant: {agent_def.name}")
            openai_assistant_obj = self.openai_client.beta.assistants.create(
                name=agent_def.name,
                description=agent_def.description,
                instructions=agent_def.instructions,
                model=agent_def.model, 
                tools=agent_def.tools,
                tool_resources=agent_def.tool_resources,
                metadata=agent_def.metadata
            )
            agent_def.id = openai_assistant_obj.id # Update the input agent_def with the new ID

            LOGGER.info(f"Successfully created new agent '{agent_def.name}' with ID '{agent_def.id}'.")

        if not openai_assistant_obj:
            # This path should ideally not be hit if logic is correct.
            raise Exception("Critical error: OpenAI assistant object was not set after create/update logic.")

        final_agent_instance = OAIAAgent(assistant=openai_assistant_obj, agent_def=agent_def, openai_client=self.openai_client)
        # TODO: need to add the agent to the context of the user - need to fix this
        #self.context["agents"][final_agent_instance.get_name()] = final_agent_instance # Ensure context is updated
        return final_agent_instance
    

    @override
    def get_agent(self, agent_id) -> Agent:
        assistant = self.openai_client.beta.assistants.retrieve(assistant_id=agent_id)
        agent_def = self.get_definition(assistant=assistant)
        if assistant is None:
            raise Exception(f"Assistant not found: {agent_id}")
        return OAIAAgent(assistant=assistant, agent_def=agent_def, openai_client=self.openai_client)
    
    
    # @override
    # def get_agent_resource(self, agent_id: str) -> dict:
    #     """
    #     Retrieves an agent by its ID. This method should be implemented by subclasses.
    #     Returns a dictionary containing the agent's details.
    #     """
    #     pass