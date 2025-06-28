

import io
from PIL import Image
from bondable.bond.functions import Functions
from bondable.bond.definition import AgentDefinition
from bondable.bond.cache import bond_cache
from bondable.bond.providers.metadata import Metadata
from bondable.bond.providers.agent import Agent, AgentProvider
from bondable.bond.providers.openai.OAIAMetadata import OAIAMetadata
from bondable.bond.mcp_client import MCPClient
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
import os


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

    def _handle_mcp_call(self, function_name: str, arguments: Dict) -> str:
        """Handle MCP tool or resource calls using synchronous methods."""
        try:
            mcp_client = MCPClient.client()
            
            if function_name.startswith("mcp_resource_"):
                # Handle MCP resource read
                encoded_uri = function_name[13:]  # Remove "mcp_resource_" prefix
                
                # Decode the base64 encoded URI
                try:
                    padded = encoded_uri + '=' * (4 - len(encoded_uri) % 4)
                    resource_uri = base64.urlsafe_b64decode(padded).decode()
                    LOGGER.debug(f"Reading MCP resource with URI: {resource_uri}")
                    
                    # Read the resource using the decoded URI
                    return mcp_client.read_resource_sync(resource_uri)
                except Exception as e:
                    LOGGER.error(f"Failed to decode resource URI: {e}")
                    return f"Error: Failed to decode resource URI: {str(e)}"
                
            elif function_name.startswith("mcp_"):
                # Handle MCP tool call
                tool_name = function_name[4:]  # Remove "mcp_" prefix
                LOGGER.info(f"Calling MCP tool: {tool_name} with arguments: {arguments}")
                
                return mcp_client.call_tool_sync(tool_name, arguments)
            else:
                return f"Error: Unknown MCP function type: {function_name}"
                
        except Exception as e:
            LOGGER.error(f"Error in MCP call: {e}", exc_info=True)
            return f"Error calling MCP: {str(e)}"

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
                        function_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments) if hasattr(tool_call.function, 'arguments') else {}
                        
                        try:
                            # Determine handler and execute
                            if function_name.startswith("mcp_"):
                                result = self._handle_mcp_call(function_name, arguments)
                            else:
                                # Handle bondable functions
                                function_to_call = getattr(self.functions, function_name, None)
                                if not function_to_call:
                                    raise AttributeError(f"Function {function_name} not found")
                                LOGGER.debug(f"Calling function {function_name}")
                                result = function_to_call(**arguments)
                            
                            tool_call_outputs.append({
                                "tool_call_id": tool_call.id,
                                "output": result
                            })
                        except Exception as e:
                            LOGGER.error(f"Error calling {function_name}: {e}")
                            tool_call_outputs.append({
                                "tool_call_id": tool_call.id,
                                "output": f"Error: {str(e)}"
                            })
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
    def stream_response(self, prompt=None, thread_id=None, attachments=None, override_role="user") -> Generator[str, None, None]:
        LOGGER.debug(f"Agent streaming response using assistant id: {self.assistant_id}")

        if prompt is not None:
            LOGGER.info(f"stream_response called with override_role='{override_role}', prompt length={len(prompt)}")
            if override_role == "system":
                LOGGER.debug(f"System message (introduction) content: {prompt[:200]}...")
            user_message_id = self.create_user_message(prompt=prompt, thread_id=thread_id, attachments=attachments, override_role=override_role)
            LOGGER.debug(f"Created new message with role '{override_role}': {user_message_id}")
        message_queue = Queue()

        # Use reminder as additional_instructions
        additional_instructions = self.agent_def.reminder or ""
        if additional_instructions:
            LOGGER.info(f"Agent [{self.agent_def.name}] using reminder as additional_instructions: \"{additional_instructions}\"")

        with self.openai_client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
            additional_instructions=additional_instructions,
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
        # Extract MCP tools/resources by examining tool names
        mcp_tools = []
        mcp_resources = []
        
        for tool in assistant.tools:
            if hasattr(tool, 'function') and hasattr(tool.function, 'name'):
                function_name = tool.function.name
                if function_name.startswith('mcp_resource_'):
                    # Extract encoded URI and decode it back
                    encoded_uri = function_name[13:]  # Remove "mcp_resource_"
                    try:
                        # Add padding if needed and decode
                        padded = encoded_uri + '=' * (4 - len(encoded_uri) % 4)
                        resource_uri = base64.urlsafe_b64decode(padded).decode()
                        mcp_resources.append(resource_uri)
                    except Exception as e:
                        LOGGER.warning(f"Could not decode resource URI from function name {function_name}: {e}")
                        # Fallback to using the encoded string
                        mcp_resources.append(encoded_uri)
                elif function_name.startswith('mcp_'):
                    # Extract tool name by removing prefix
                    tool_name = function_name[4:]  # Remove "mcp_"
                    mcp_tools.append(tool_name)
        
        LOGGER.debug(f"Detected {len(mcp_tools)} MCP tools from assistant: {mcp_tools}")
        LOGGER.debug(f"Detected {len(mcp_resources)} MCP resources from assistant: {mcp_resources}")
        
        if assistant.metadata is None or 'user_id' not in assistant.metadata or not assistant.metadata['user_id']:
            raise ValueError("Assistant metadata must contain a 'user_id' field.")

        # Get introduction and reminder from AgentRecord if available
        introduction = ""
        reminder = ""
        try:
            agent_record = self.get_agent_record(agent_id=assistant.id)
            if agent_record:
                introduction = agent_record.introduction or ""
                reminder = agent_record.reminder or ""
                LOGGER.debug(f"Retrieved introduction and reminder from AgentRecord for agent {assistant.id}")
        except Exception as e:
            LOGGER.warning(f"Could not retrieve AgentRecord for agent {assistant.id}: {e}")

        agent_def = AgentDefinition(
            id=assistant.id,
            name=assistant.name,
            description=assistant.description,
            instructions=assistant.instructions,
            introduction=introduction,
            reminder=reminder,
            tools=assistant.tools,
            tool_resources=assistant.tool_resources,
            metadata=assistant.metadata,
            model=assistant.model,
            user_id=assistant.metadata.get('user_id', None) if assistant.metadata else None,
            mcp_tools=mcp_tools,
            mcp_resources=mcp_resources,
        )
        return agent_def

    def _fetch_and_convert_mcp_tools(self, mcp_tool_names: List[str]) -> List[Dict]:
        """Fetch MCP tools and convert them to OpenAI function calling format."""
        if not mcp_tool_names:
            LOGGER.debug("No MCP tools to convert")
            return []
            
        LOGGER.debug(f"Starting MCP tool conversion for tools: {mcp_tool_names}")
        try:
            mcp_client = MCPClient.client()
            available_tools = mcp_client.list_tools_sync()
            LOGGER.debug(f"Retrieved {len(available_tools)} available MCP tools from server")
            
            # Map available tools by name
            tool_map = {getattr(tool, "name", ""): tool for tool in available_tools}
            LOGGER.debug(f"Available MCP tool names: {list(tool_map.keys())}")
            
            # Convert requested tools
            openai_tools = []
            for tool_name in mcp_tool_names:
                if tool_name not in tool_map:
                    LOGGER.warning(f"MCP tool '{tool_name}' not found")
                    continue
                    
                mcp_tool = tool_map[tool_name]
                params = getattr(mcp_tool, "inputSchema", {})
                
                # Ensure params have required structure
                params.setdefault("type", "object")
                params.setdefault("properties", {})
                params.setdefault("required", [])
                
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": f"mcp_{tool_name}",
                        "description": getattr(mcp_tool, "description", ""),
                        "strict": False,
                        "parameters": params
                    }
                })
                LOGGER.info(f"Converted MCP tool '{tool_name}' to OpenAI format")
                
            LOGGER.info(f"Successfully converted {len(openai_tools)} MCP tools to OpenAI format")
            return openai_tools
            
        except Exception as e:
            LOGGER.error(f"Error fetching/converting MCP tools: {e}", exc_info=True)
            return []  # Continue without MCP tools
    
    def _fetch_and_convert_mcp_resources(self, mcp_resource_names: List[str]) -> List[Dict]:
        """Fetch MCP resources and convert them to OpenAI function calling format."""
        if not mcp_resource_names:
            LOGGER.debug("No MCP resources to convert")
            return []
            
        LOGGER.debug(f"Starting MCP resource conversion for resources: {mcp_resource_names}")
        try:
            mcp_client = MCPClient.client()
            available_resources = mcp_client.list_resources_sync()
            LOGGER.debug(f"Retrieved {len(available_resources)} available MCP resources from server")
            
            # Map available resources by both name and URI for flexible lookup
            resource_map_by_name = {getattr(r, "name", ""): r for r in available_resources}
            resource_map_by_uri = {str(getattr(r, "uri", "")): r for r in available_resources}  # Convert URI to string
            
            # Convert requested resources
            openai_tools = []
            for resource_identifier in mcp_resource_names:
                # Try to find resource by name first, then by URI (with string conversion)
                mcp_resource = resource_map_by_name.get(resource_identifier) or resource_map_by_uri.get(str(resource_identifier))
                
                if not mcp_resource:
                    LOGGER.warning(f"MCP resource '{resource_identifier}' not found (searched by name and URI)")
                    continue
                    
                resource_uri = str(getattr(mcp_resource, "uri", resource_identifier))
                resource_name = getattr(mcp_resource, "name", resource_uri)
                # Base64 encode the URI to create a valid function name
                encoded_uri = base64.urlsafe_b64encode(resource_uri.encode()).decode().rstrip('=')
                
                # Get resource description and include name for clarity
                resource_desc = getattr(mcp_resource, 'description', '')
                full_description = f"Read resource [{resource_name}]"
                if resource_desc:
                    full_description += f": {resource_desc}"
                
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": f"mcp_resource_{encoded_uri}",
                        "description": full_description,
                        "strict": False,
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                })
                LOGGER.info(f"Converted MCP resource '{resource_uri}' to OpenAI format with encoded name 'mcp_resource_{encoded_uri}'")
                
            LOGGER.info(f"Successfully converted {len(openai_tools)} MCP resources to OpenAI format")
            return openai_tools
            
        except Exception as e:
            LOGGER.error(f"Error fetching/converting MCP resources: {e}", exc_info=True)
            return []  # Continue without MCP resources


    @override
    def create_or_update_agent_resource(self, agent_def: AgentDefinition, owner_user_id: str) -> Agent:
        """
        Creates a new agent. This method should be implemented by subclasses.
        Returns the created agent.
        """
        openai_assistant_obj = None # Holds the final OpenAI assistant object

        if agent_def.metadata is None:
            agent_def.metadata = {}
        agent_def.metadata['user_id'] = owner_user_id  # ensure the owner is set in metadata

        # Remove any existing MCP tools/resources from the tools list to avoid duplicates
        # This ensures we only have the MCP tools that are currently requested
        filtered_tools = []
        for tool in agent_def.tools:
            if isinstance(tool, dict) and 'function' in tool:
                func_name = tool.get('function', {}).get('name', '')
                # Keep non-MCP tools
                if not func_name.startswith('mcp_'):
                    filtered_tools.append(tool)
                else:
                    LOGGER.debug(f"Removing existing MCP tool from tools list: {func_name}")
            else:
                # Keep non-function tools (like code_interpreter, file_search)
                filtered_tools.append(tool)
        
        agent_def.tools = filtered_tools
        
        # Log initial tool state after filtering
        LOGGER.debug(f"Initial tools count (after filtering MCP): {len(agent_def.tools)}")
        LOGGER.debug(f"Initial tools: {[t.get('function', {}).get('name', 'unknown') if isinstance(t, dict) else str(t) for t in agent_def.tools]}")
        
        # Process MCP tools if specified
        if agent_def.mcp_tools:
            LOGGER.debug(f"Processing {len(agent_def.mcp_tools)} MCP tools: {agent_def.mcp_tools}")
            try:
                mcp_tools_converted = self._fetch_and_convert_mcp_tools(agent_def.mcp_tools)
                # Merge MCP tools with existing tools
                agent_def.tools.extend(mcp_tools_converted)
                LOGGER.info(f"Added {len(mcp_tools_converted)} MCP tools to agent definition")
                LOGGER.debug(f"Tools after MCP tool addition: {len(agent_def.tools)}")
            except Exception as e:
                LOGGER.error(f"Failed to process MCP tools: {e}", exc_info=True)
                # Continue without MCP tools rather than failing the entire operation
        else:
            LOGGER.debug("No MCP tools specified in agent definition")
        
        # Process MCP resources if specified
        if agent_def.mcp_resources:
            LOGGER.debug(f"Processing {len(agent_def.mcp_resources)} MCP resources: {agent_def.mcp_resources}")
            try:
                mcp_resources_converted = self._fetch_and_convert_mcp_resources(agent_def.mcp_resources)
                # Merge MCP resources with existing tools
                agent_def.tools.extend(mcp_resources_converted)
                LOGGER.info(f"Added {len(mcp_resources_converted)} MCP resources to agent definition")
                LOGGER.debug(f"Tools after MCP resource addition: {len(agent_def.tools)}")
            except Exception as e:
                LOGGER.error(f"Failed to process MCP resources: {e}", exc_info=True)
                # Continue without MCP resources rather than failing the entire operation
        else:
            LOGGER.debug("No MCP resources specified in agent definition")
        
        # Log final tool state
        LOGGER.info(f"Final tools count before assistant create/update: {len(agent_def.tools)}")
        LOGGER.debug(f"Final tool names: {[t.get('function', {}).get('name', 'unknown') if isinstance(t, dict) else str(t) for t in agent_def.tools]}")

        if agent_def.id:  # ID is provided: implies update an existing agent
            LOGGER.debug(f"Agent ID '{agent_def.id}' provided. Attempting to retrieve/update.")
            try:
                # Retrieve from OpenAI first - this is the source of truth for existence by ID
                openai_assistant_obj = self.openai_client.beta.assistants.retrieve(assistant_id=agent_def.id)
                LOGGER.debug(f"Retrieved OpenAI assistant with ID: {agent_def.id}")

                # Compare definitions to see if OpenAI assistant needs an update
                current_definition_from_openai = self.get_definition(assistant=openai_assistant_obj)
                agent_def.name = agent_def.name if agent_def.name is not None else openai_assistant_obj.name
                agent_def.model = agent_def.model if agent_def.model else current_definition_from_openai.model

                # Log hash comparison details
                LOGGER.debug(f"Current definition hash: {current_definition_from_openai.get_hash()}")
                LOGGER.debug(f"New definition hash: {agent_def.get_hash()}")
                LOGGER.debug(f"Current tools count: {len(current_definition_from_openai.tools)}")
                LOGGER.debug(f"New tools count: {len(agent_def.tools)}")
                
                if current_definition_from_openai.get_hash() != agent_def.get_hash():
                    LOGGER.debug(f"Definition changed for agent ID {agent_def.id}. Updating OpenAI assistant.")
                    LOGGER.debug(f"Updating assistant with {len(agent_def.tools)} tools")
                    LOGGER.debug(f"Tools being sent to OpenAI for update: {json.dumps(agent_def.tools, indent=2)}")
                    openai_assistant_obj = self.openai_client.beta.assistants.update(
                        assistant_id=agent_def.id,
                        name=agent_def.name,
                        description=agent_def.description,
                        instructions=agent_def.instructions,
                        model=agent_def.model,
                        tools=agent_def.tools,
                        tool_resources=agent_def.tool_resources,
                        metadata=agent_def.metadata, 
                        temperature=agent_def.temperature,
                        top_p=agent_def.top_p
                    )
                    LOGGER.info(f"Successfully updated OpenAI assistant for ID: {agent_def.id}")
                    LOGGER.info(f"Updated assistant has {len(openai_assistant_obj.tools)} tools")
                    LOGGER.debug(f"Assistant tools after update: {[t.model_dump() if hasattr(t, 'model_dump') else t for t in openai_assistant_obj.tools]}")
                else:
                    LOGGER.info(f"No definition changes detected for agent ID {agent_def.id}. OpenAI assistant not updated.")

            except Exception as e: # Catches openai.NotFoundError and other issues
                LOGGER.error(f"Error processing agent with ID {agent_def.id}: {e}", exc_info=True)
                raise Exception(f"Failed to retrieve or update agent with ID {agent_def.id}. Original error: {str(e)}")

        else:  # No agent_def.id provided: this is a create new agent scenario
            if not agent_def.name:
                raise ValueError("Agent name must be provided for creation.")
            LOGGER.info(f"No ID provided. Attempting to create new agent named '{agent_def.name}'")

            LOGGER.debug(f"Creating new OpenAI assistant: {agent_def.name}")
            LOGGER.debug(f"Creating new assistant with {len(agent_def.tools)} tools")
            LOGGER.debug(f"Tools being sent to OpenAI: {json.dumps(agent_def.tools, indent=2)}")
            openai_assistant_obj = self.openai_client.beta.assistants.create(
                name=agent_def.name,
                description=agent_def.description,
                instructions=agent_def.instructions,
                model=agent_def.model, 
                tools=agent_def.tools,
                tool_resources=agent_def.tool_resources,
                metadata=agent_def.metadata, 
                temperature=agent_def.temperature,
                top_p=agent_def.top_p
            )
            agent_def.id = openai_assistant_obj.id # Update the input agent_def with the new ID

            LOGGER.info(f"Successfully created new agent '{agent_def.name}' with ID '{agent_def.id}'.")
            LOGGER.info(f"Created assistant has {len(openai_assistant_obj.tools)} tools")
            LOGGER.debug(f"Assistant tools: {[t.model_dump() if hasattr(t, 'model_dump') else t for t in openai_assistant_obj.tools]}")

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
    
    @override
    def get_available_models(self) -> List[Dict[str, any]]:
        """
        Get a list of available models that can be used by agents.
        
        Returns:
            List[Dict[str, any]]: A list of dictionaries containing model information.
        """
        models = []
        
        # Read models from environment variables
        # Format: OPENAI_MODELS=model1:description1,model2:description2
        # Default model: OPENAI_DEFAULT_MODEL=model1
        models_config = os.getenv('OPENAI_MODELS', 'gpt-4o:Most capable GPT-4 Omni model for complex tasks')
        default_model = os.getenv('OPENAI_DEFAULT_MODEL', 'gpt-4o').strip()
        
        # Parse the models configuration
        for model_entry in models_config.split(','):
            model_entry = model_entry.strip()
            if ':' in model_entry:
                name, description = model_entry.split(':', 1)
                models.append({
                    'name': name.strip(),
                    'description': description.strip(),
                    'is_default': name.strip() == default_model
                })
            else:
                # Handle case where only model name is provided
                models.append({
                    'name': model_entry,
                    'description': f'{model_entry} model',
                    'is_default': model_entry == default_model
                })
        
        # Ensure at least one model is marked as default
        if models and not any(m['is_default'] for m in models):
            LOGGER.warning(f"Default model '{default_model}' not found in available models, marking first model as default")
            models[0]['is_default'] = True
        
        return models
    
    
    # @override
    # def get_agent_resource(self, agent_id: str) -> dict:
    #     """
    #     Retrieves an agent by its ID. This method should be implemented by subclasses.
    #     Returns a dictionary containing the agent's details.
    #     """
    #     pass