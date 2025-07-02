"""
BedrockAgent - AWS Bedrock implementation of Bond Agent interface

This module implements agents using AWS Bedrock Agents API,
providing conversation management with native session support.
"""

import os
import uuid
import json
import logging
import base64
import hashlib
import boto3
from typing import List, Dict, Optional, Generator, Any
from botocore.exceptions import ClientError
from typing_extensions import override
from bondable.bond.providers.agent import Agent, AgentProvider
from bondable.bond.definition import AgentDefinition
from bondable.bond.config import Config
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.threads import ThreadsProvider
from bondable.bond.providers.files import FilesProvider
from bondable.bond.providers.metadata import AgentRecord
from .BedrockCRUD import create_bedrock_agent, update_bedrock_agent, delete_bedrock_agent, get_bedrock_agent
from .BedrockMCP import execute_mcp_tool_sync
from .BedrockMetadata import BedrockMetadata, BedrockAgentOptions
from .BedrockProvider import BedrockProvider

LOGGER = logging.getLogger(__name__)
DEFAULT_TEMPERATURE = 0.0
# Ensure instructions meet minimum length requirement (40 chars for Bedrock)
MIN_INSTRUCTION_LENGTH = 40
DEFAULT_INSTRUCTION = "You are a helpful AI assistant. Be helpful, accurate, and concise in your responses."


class BedrockAgent(Agent):
    """Bedrock implementation of the Agent interface"""
    
    def __init__(self, agent_id: str, name: str, introduction: str, 
                 reminder: str, owner_user_id: str, bedrock_options: BedrockAgentOptions):
        self.agent_id = agent_id
        self.bedrock_agent_id = bedrock_options.bedrock_agent_id
        self.bedrock_agent_alias_id = bedrock_options.bedrock_agent_alias_id
        self.bond_provider: BedrockProvider = Config.config().get_provider()

        bedrock_agent = self.bond_provider.bedrock_agent_client.get_agent(agentId=self.bedrock_agent_id)
        if 'agent' not in bedrock_agent:
            raise ValueError(f"Bedrock agent response does not have 'agent': {self.agent_id}")
        if 'foundationModel' not in bedrock_agent['agent']:
            raise ValueError(f"Bedrock agent response does not have 'foundationModel': {self.agent_id}")
        if 'instruction' not in bedrock_agent['agent']:
            raise ValueError(f"Bedrock agent response does not have 'instruction': {self.agent_id}")
        
        self.name = name
        self.description = bedrock_agent['agent']['description'] if 'description' in bedrock_agent['agent'] else ''
        self.model = bedrock_agent['agent']['foundationModel']
        self.instructions = bedrock_agent['agent']['instruction']
        self.introduction = introduction
        self.reminder = reminder
        self.owner_user_id = owner_user_id
        self.temperature = bedrock_options.temperature
        self.tools = bedrock_options.tools 
        self.tool_resources = bedrock_options.tool_resources 
        self.mcp_tools = bedrock_options.mcp_tools
        self.mcp_resources = bedrock_options.mcp_resources
        self.metadata = bedrock_options.agent_metadata

        LOGGER.info(f"Initialized BedrockAgent {self.agent_id} with model {self.model}")
        LOGGER.debug(f"  Bedrock Agent ID: {self.bedrock_agent_id}")
        LOGGER.debug(f"  Bedrock Alias ID: {self.bedrock_agent_alias_id}")
    
    def get_agent_id(self) -> str:
        """Get the agent's ID"""
        return self.agent_id
    
    def get_agent_definition(self) -> AgentDefinition:
        agent_def = AgentDefinition(
            id=self.agent_id,
            name=self.name,
            description=self.description,
            instructions=self.instructions,
            introduction=self.introduction,
            reminder=self.reminder,
            tools=self.tools,
            tool_resources=self.tool_resources,
            metadata=self.metadata,
            model=self.model,
            user_id=self.owner_user_id,
            mcp_tools=self.mcp_tools,
            mcp_resources=self.mcp_resources,
        )
        return agent_def
    
    def get_name(self) -> str:
        """Get the agent's name"""
        return self.name
    
    def get_description(self) -> str:
        """Get the agent's description"""
        return self.description
    
    def get_metadata_value(self, key: str, default_value=None):
        return self.metadata.get(key, default_value)
    
    def get_metadata(self) -> Dict[str, str]:
        # Include owner_user_id in metadata for frontend compatibility
        metadata = self.metadata.copy() if self.metadata else {}
        metadata['owner_user_id'] = self.owner_user_id
        return metadata
    
    def _yield_error_message(self, thread_id: str, error_message: str, 
                           error_code: Optional[str] = None) -> Generator[str, None, None]:
        """Helper method to yield error messages in Bond format"""
        error_id = str(uuid.uuid4())
        yield (
            f'<_bondmessage '
            f'id="{error_id}" '
            f'thread_id="{thread_id}" '
            f'agent_id="{self.agent_id}" '
            f'type="error" '
            f'role="system" '
            f'is_error="true" '
            f'is_done="true">'
        )
        if error_code:
            yield f"Bedrock Agent Error ({error_code}): {error_message}"
        else:
            yield f"Error: {error_message}"
        yield '</_bondmessage>'
    
    def _compute_file_hash(self, file_info: Dict[str, Any]) -> Optional[str]:
        """
        Compute MD5 hash of file data for duplicate detection.
        
        Returns None if no bytes data is present.
        """
        if 'bytes' not in file_info:
            return None
            
        file_data = file_info['bytes']
        
        # Convert to bytes if needed
        if isinstance(file_data, str):
            file_data = file_data.encode('utf-8')
        
        # Compute MD5 hash
        return hashlib.md5(file_data).hexdigest()
    
    def _handle_file_event(self, file_info: Dict[str, Any], thread_id: str, 
                           user_id: str) -> Generator[str, None, None]:

        """
        Helper method to handle file events and yield appropriate messages.
        
        Images are returned inline as base64 data URLs.
        Other file types are uploaded to S3 and returned as links.
        """
        if 'bytes' not in file_info:
            return

        # Get file details
        file_data = file_info['bytes']
        file_name = file_info.get('name', 'file')
        file_type = file_info.get('type', 'application/octet-stream')
        
        message_content = ''
        message_type = ''
        message_role = 'assistant'

        # Determine if this is an image based on MIME type
        is_image = file_type.startswith('image/')
        
        if is_image:
            # Handle images inline with base64 encoding
            if isinstance(file_data, bytes):
                image_base64 = base64.b64encode(file_data).decode('utf-8')
            else:
                # If it's already a string, handle accordingly
                image_base64 = file_data
            
            # Create the data URL format for the image as the message content
            message_content = f"data:{file_type};base64,{image_base64}"
            message_type = 'image_file'
    
            LOGGER.info(f"Received and yielded image: {file_name} ({file_type})")
        else:
            # Handle non-image files by uploading to S3
            try:
                # TODO: Implement S3 upload logic here
                # For now, we'll log that we need to handle this file type
                LOGGER.warning(f"Non-image file received: {file_name} ({file_type}) - S3 upload not yet implemented")
                
                # Yield a file link message
                message_content = f"File received: {file_name} (upload pending)"
                message_type = 'file_link'
                
            except Exception as e:
                LOGGER.error(f"Error handling file {file_name}: {e}")
                # Continue without failing the entire response
        
        message_id = self.bond_provider.threads.add_message(
            thread_id=thread_id,
            user_id=user_id,
            role=message_role,
            message_type=message_type,
            content=message_content,
            metadata={
                'agent_id': self.agent_id,
                'model': self.model,
                'bedrock_agent_id': self.bedrock_agent_id
            }
        )

        # Yield file message
        yield (
            f'<_bondmessage '
            f'id="{message_id}" '
            f'thread_id="{thread_id}" '
            f'agent_id="{self.agent_id}" '
            f'type="{message_type}" '
            f'role="{message_role}" '
            f'is_error="false" '
            f'is_done="false">'
        )
        yield message_content
        yield '</_bondmessage>'

    
    def create_user_message(self, prompt: str, thread_id: str, 
                          attachments: Optional[List] = None,
                          override_role: str = "user") -> str:
        """
        Create a user message in a thread.
        
        Args:
            prompt: The message content
            thread_id: Thread to add message to
            attachments: Optional attachments (not yet implemented)
            override_role: Role override (default: "user")
            
        Returns:
            Message ID
        """
        # Get user ID from agent metadata
        user_id = self.bond_provider.threads.get_thread_owner(thread_id=thread_id)
        if not user_id:
            raise ValueError("Agent must have user_id in metadata")
        
        # Add the message to the thread
        # Note: session_id is extracted from thread_id in add_message
        message_id = self.bond_provider.threads.add_message(
            thread_id=thread_id,
            user_id=user_id,
            role=override_role,
            message_type='text',
            content=prompt,
            attachments=attachments,
            metadata={
                'agent_id': self.agent_id,
                'override_role': override_role
            }
        )
        
        LOGGER.info(f"Created user message {message_id} in thread {thread_id}")
        return message_id
    
    def stream_response(self, prompt: Optional[str] = None, 
                       thread_id: Optional[str] = None,
                       attachments: Optional[List] = None,
                       override_role: str = "user") -> Generator[str, None, None]:
        """
        Stream a response from the agent using Bedrock Agents API.
        
        Args:
            prompt: Optional prompt to add to thread
            thread_id: Thread ID (required)
            attachments: Optional attachments
            override_role: Role for the prompt message
            
        Yields:
            Response chunks in Bond message format
        """
        if not thread_id:
            raise ValueError("thread_id is required for streaming response")
        
        if not self.bedrock_agent_id:
            LOGGER.error(f"Bedrock Agent ID not found for agent {self.agent_id}")
            LOGGER.error(f"Agent record exists: {self.metadata.get_bedrock_agent(self.agent_id) is not None}")
            raise ValueError("Bedrock Agent ID not configured. Please create a Bedrock Agent first.")

        user_id = self.bond_provider.threads.get_thread_owner(thread_id=thread_id)
        if not user_id:
            raise ValueError("Agent must have user_id in metadata")
        
        try:

            # Get session ID and state from thread
            session_id = self.bond_provider.threads.get_thread_session_id(thread_id)
            session_state = self.bond_provider.threads.get_thread_session_state(thread_id, user_id)
            LOGGER.info(f"Invoking Bedrock Agent {self.bedrock_agent_id} with session {session_id}")

            # Add user message if prompt provided
            if prompt:
                self.create_user_message(prompt, thread_id, attachments, override_role)
            else:
                # If no prompt, we need to get the last user message
                messages = self.bond_provider.threads.get_messages(thread_id, limit=1)
                if not messages:
                    raise ValueError("No user message to respond to")
                # Get the most recent message
                last_msg = list(messages.values())[0]
                if last_msg.role != 'user':
                    raise ValueError("No user message to respond to")
                prompt = last_msg.clob.get_content() if hasattr(last_msg, 'clob') else str(last_msg)
            
            # Build request for invoke_agent
            request = {
                'agentId': self.bedrock_agent_id,
                'agentAliasId': self.bedrock_agent_alias_id,
                'sessionId': session_id,
                'inputText': prompt,
                'enableTrace': True,  # Enable for debugging
                'streamingConfigurations': {
                    'streamFinalResponse': True  # Enable streaming!
                }
            }
            
            # Generate Bond message start tag
            full_content = ""
            response_id = str(uuid.uuid4())
            response_type = "text"
            response_role = "assistant"
            yield (
                f'<_bondmessage '
                f'id="{response_id}" '
                f'thread_id="{thread_id}" '
                f'agent_id="{self.agent_id}" '
                f'type="{response_type}" '
                f'role="{response_role}" '
                f'is_error="false" '
                f'is_done="false">'
            )

            # augment this with any code interpreter files from the tool_resources for this agent
            # only do this for the first message
            if self.bond_provider.threads.get_response_message_count(thread_id=thread_id) == 0:
                session_files = self.bond_provider.files.get_files_invocation(self.tool_resources)
                if session_files:
                    session_state['files'] = session_files

            # add files from attachments
            if attachments:
                LOGGER.info(f"Streaming response with attachments\n: {json.dumps(attachments, indent=2)}")

            # Add session state if available
            request['sessionState'] = session_state

            
            # Invoke the agent (this returns a streaming response)
            LOGGER.debug(f"Sending request: {request}")
            response = self.bond_provider.bedrock_agent_runtime_client.invoke_agent(**request)

            # Process the streaming response
            new_session_state = None
            seen_file_hashes = set()  # Track files we've already sent
            
            # The response contains an EventStream that we need to iterate
            event_stream = response.get('completion')
            if event_stream:
                event_count = 0
                for event in event_stream:
                    event_count += 1
                    # LOGGER.debug(f"Processing event {event_count}: {list(event.keys())}")
                    
                    # Handle text chunks
                    if 'chunk' in event:
                        chunk = event['chunk']
                        # LOGGER.debug(f" --- Received chunk: {list(chunk.keys())}")
                        if 'bytes' in chunk:
                            text = chunk['bytes'].decode('utf-8')
                            # LOGGER.debug(f"Processing text chunk of length {len(text)}")
                            yield text
                            full_content += text
                    
                    # Handle files event (this is where files from code interpreter come)
                    elif 'files' in event:
                        files_event = event['files']
                        if 'files' in files_event:
                            for file_info in files_event['files']:
                                # Check for duplicate files
                                file_hash = self._compute_file_hash(file_info)
                                if file_hash:
                                    if file_hash in seen_file_hashes:
                                        # Duplicate file - log and skip
                                        file_name = file_info.get('name', 'unknown')
                                        LOGGER.debug(f"Skipping duplicate file: {file_name} (hash: {file_hash})")
                                        continue
                                    seen_file_hashes.add(file_hash)
                                

                                if full_content and len(full_content) > 0:
                                    # Need to save off any content here as a message
                                    message_id = self.bond_provider.threads.add_message(
                                        message_id=response_id,
                                        thread_id=thread_id,
                                        user_id=user_id,
                                        role=response_role,
                                        message_type=response_type,
                                        content=full_content,
                                        attachments=attachments,
                                        metadata={
                                            'agent_id': self.agent_id,
                                            'model': self.model,
                                            'bedrock_agent_id': self.bedrock_agent_id
                                        }
                                    )
                                    full_content = ''

                                # finish the text message
                                yield '</_bondmessage>'
                                # send the file message
                                yield from self._handle_file_event(file_info=file_info, 
                                                                   thread_id=thread_id, 
                                                                   user_id=user_id)
                                
                                # start a new text message
                                response_id = str(uuid.uuid4())
                                yield (
                                    f'<_bondmessage '
                                    f'id="{response_id}" '
                                    f'thread_id="{thread_id}" '
                                    f'agent_id="{self.agent_id}" '
                                    f'type="{response_type}" '
                                    f'role="{response_role}" '
                                    f'is_error="false" '
                                    f'is_done="false">'
                                )

                    # Handle returnControl events for MCP tools
                    elif 'returnControl' in event:
                        return_control = event['returnControl']
                        LOGGER.info("Received returnControl event for tool execution")
                        
                        # Handle the tool execution
                        tool_results = self._handle_return_control(return_control)
                        
                        if tool_results:
                            # Continue the agent with the tool results
                            continuation_request = {
                                'agentId': self.bedrock_agent_id,
                                'agentAliasId': self.bedrock_agent_alias_id,
                                'sessionId': session_id,
                                'sessionState': {
                                    'invocationId': return_control.get('invocationId'),
                                    'returnControlInvocationResults': tool_results
                                },
                                'enableTrace': True,
                                'streamingConfigurations': {
                                    'streamFinalResponse': True
                                }
                            }
                            
                            # Get continuation response
                            continuation_response = self.bond_provider.bedrock_agent_runtime_client.invoke_agent(**continuation_request)
                            continuation_stream = continuation_response.get('completion')
                            
                            if continuation_stream:
                                for cont_event in continuation_stream:
                                    if 'chunk' in cont_event:
                                        chunk = cont_event['chunk']
                                        if 'bytes' in chunk:
                                            text = chunk['bytes'].decode('utf-8')
                                            yield text
                                            full_content += text
                                    elif 'files' in cont_event:
                                        # Handle files in continuation stream
                                        files_event = cont_event['files']
                                        if 'files' in files_event:
                                            for file_info in files_event['files']:
                                                # Check for duplicate files
                                                file_hash = self._compute_file_hash(file_info)
                                                if file_hash:
                                                    if file_hash in seen_file_hashes:
                                                        # Duplicate file - log and skip
                                                        file_name = file_info.get('name', 'unknown')
                                                        LOGGER.debug(f"Skipping duplicate file in continuation: {file_name} (hash: {file_hash})")
                                                        continue
                                                    seen_file_hashes.add(file_hash)
                                                
                                                # from here
                                                if full_content and len(full_content) > 0:
                                                    # Need to save off any content here as a message
                                                    message_id = self.bond_provider.threads.add_message(
                                                        message_id=response_id,
                                                        thread_id=thread_id,
                                                        user_id=user_id,
                                                        role=response_role,
                                                        message_type=response_type,
                                                        content=full_content,
                                                        attachments=attachments,
                                                        metadata={
                                                            'agent_id': self.agent_id,
                                                            'model': self.model,
                                                            'bedrock_agent_id': self.bedrock_agent_id
                                                        }
                                                    )
                                                    full_content = ''

                                                # finish the text message
                                                yield '</_bondmessage>'
                                                # send the file message
                                                yield from self._handle_file_event(file_info=file_info, 
                                                                                    thread_id=thread_id, 
                                                                                    user_id=user_id)
                                                
                                                # start a new text message
                                                response_id = str(uuid.uuid4())
                                                yield (
                                                    f'<_bondmessage '
                                                    f'id="{response_id}" '
                                                    f'thread_id="{thread_id}" '
                                                    f'agent_id="{self.agent_id}" '
                                                    f'type="{response_type}" '
                                                    f'role="{response_role}" '
                                                    f'is_error="false" '
                                                    f'is_done="false">'
                                                )

                                    elif 'sessionState' in cont_event:
                                        new_session_state = cont_event['sessionState']
                    
                    # Handle session state updates
                    elif 'sessionState' in event:
                        new_session_state = event['sessionState']
                        LOGGER.debug("Received session state update")

                    elif 'trace' in event:
                        event_trace = event['trace']
                        LOGGER.debug(f" --- Received trace: {list(event_trace.keys())}")
                
                LOGGER.info(f"Processed {event_count} events from completion stream")
            
            # Close the Bond message
            yield '</_bondmessage>'
            
            # Save the complete response to the thread
            if full_content and len(full_content) > 0:
                self.bond_provider.threads.add_message(
                    message_id=response_id,
                    thread_id=thread_id,
                    user_id=user_id,
                    role=response_role,
                    message_type=response_type,
                    content=full_content,
                    metadata={
                        'agent_id': self.agent_id,
                        'model': self.model,
                        'bedrock_agent_id': self.bedrock_agent_id
                    }
                )

                LOGGER.info(f"Saved assistant response to thread {thread_id}")
            
            # Update session state if provided
            if new_session_state:
                self.bond_provider.threads.update_thread_session(
                    thread_id=thread_id, 
                    user_id=user_id, 
                    session_id=session_id,
                    session_state=new_session_state)
                LOGGER.debug(f"Updated session state for thread {thread_id}: session state \n{json.dumps(new_session_state, indent=4)}")
            else:
                LOGGER.debug("No updated session state was returned from bedrock")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = str(e)
            LOGGER.error(f"Bedrock Agent API error: {error_code} - {error_message}")
            yield from self._yield_error_message(thread_id, error_message, error_code)
            
        except Exception as e:
            LOGGER.exception(f"Unexpected error in stream_response: {e}")
            yield from self._yield_error_message(thread_id, str(e))
    
    def _handle_return_control(self, return_control: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Handle returnControl event from Bedrock for tool execution.
        
        Args:
            return_control: The returnControl event data
            
        Returns:
            List of tool execution results to send back to Bedrock
        """
        invocation_inputs = return_control.get('invocationInputs', [])
        results = []
        
        for inv_input in invocation_inputs:
            # Check both possible input types
            action_input = None
            if 'actionGroupInvocationInput' in inv_input:
                action_input = inv_input['actionGroupInvocationInput']
            elif 'apiInvocationInput' in inv_input:
                action_input = inv_input['apiInvocationInput']
            
            if action_input:
                api_path = action_input.get('apiPath')
                
                # Check if this is an MCP tool
                if api_path and api_path.startswith('/_bond_mcp_tool_'):
                    # Extract tool name
                    tool_name = api_path.replace('/_bond_mcp_tool_', '')
                    
                    # Get parameters
                    parameters = {}
                    if 'parameters' in action_input:
                        # Parameters might be in different formats
                        for param in action_input['parameters']:
                            if 'name' in param and 'value' in param:
                                parameters[param['name']] = param['value']
                    elif 'requestBody' in action_input:
                        # Parameters might be in request body
                        request_body = action_input.get('requestBody', {})
                        content = request_body.get('content', {})
                        if 'application/json' in content:
                            body_str = content['application/json'].get('body', '{}')
                            try:
                                parameters = json.loads(body_str)
                            except json.JSONDecodeError:
                                LOGGER.error(f"Failed to parse request body JSON: {body_str}")
                    
                    LOGGER.info(f"Executing MCP tool: {tool_name} with parameters: {parameters}")
                    
                    # Execute MCP tool
                    try:
                        # Get MCP config
                        from bondable.bond.config import Config
                        config = Config.config()
                        mcp_config = config.get_mcp_config()
                        
                        if mcp_config:
                            result = execute_mcp_tool_sync(mcp_config, tool_name, parameters)
                            
                            # Format response
                            response_body = json.dumps({
                                "result": result.get('result', result.get('error', 'Unknown error'))
                            })
                            
                            tool_response = {
                                "actionGroup": action_input.get('actionGroup') or action_input.get('actionGroupName'),
                                "apiPath": api_path,
                                "httpMethod": action_input.get('httpMethod', 'POST'),
                                "httpStatusCode": 200 if result.get('success') else 500,
                                "responseBody": {
                                    "application/json": {
                                        "body": response_body
                                    }
                                }
                            }
                            
                            # Wrap in apiResult if it was an apiInvocationInput
                            if 'apiInvocationInput' in inv_input:
                                tool_response = {"apiResult": tool_response}
                            
                            results.append(tool_response)
                        else:
                            LOGGER.error("No MCP config available")
                    except Exception as e:
                        LOGGER.error(f"Error executing MCP tool {tool_name}: {e}")
                        # Return error response
                        error_response = {
                            "actionGroup": action_input.get('actionGroup') or action_input.get('actionGroupName'),
                            "apiPath": api_path,
                            "httpMethod": action_input.get('httpMethod', 'POST'),
                            "httpStatusCode": 500,
                            "responseBody": {
                                "application/json": {
                                    "body": json.dumps({"error": str(e)})
                                }
                            }
                        }
                        
                        # Wrap in apiResult if it was an apiInvocationInput
                        if 'apiInvocationInput' in inv_input:
                            error_response = {"apiResult": error_response}
                            
                        results.append(error_response)
        
        return results


class BedrockAgentProvider(AgentProvider):
    """Bedrock implementation of the AgentProvider interface"""
    
    def __init__(self, bedrock_client: boto3.client, metadata: BedrockMetadata):
        self.bedrock_client = bedrock_client
        self.metadata = metadata
        LOGGER.info("Initialized BedrockAgentProvider")
    
    @override
    def get_agent(self, agent_id: str) -> Agent:
        session = self.metadata.get_db_session()
        try:
            agent_record = session.query(AgentRecord).filter_by(agent_id=agent_id).first()
            if not agent_record:
                raise ValueError(f"Agent {agent_id} not found in metadata")
            bedrock_options = session.query(BedrockAgentOptions).filter_by(agent_id=agent_id).first()
            if not bedrock_options:
                raise ValueError(f"Bedrock options for agent {agent_id} not found in metadata")
            return BedrockAgent(
                agent_id=agent_id,
                name=agent_record.name,
                introduction=agent_record.introduction or "",
                reminder=agent_record.reminder or "",
                owner_user_id=agent_record.owner_user_id,
                bedrock_options=bedrock_options
            )
        except Exception as e:
            LOGGER.error(f"Error getting agent {agent_id}: {e}")
            return None
        finally:
            session.close()

    @override
    def delete_agent_resource(self, agent_id: str) -> bool:
        """
        Delete an agent resource.
        
        This deletes both the Bond agent records and the corresponding
        Bedrock Agent if it exists.
        """
        try:
            # First get the Bedrock Agent info before deleting metadata
            agent: BedrockAgent = self.get_agent(agent_id=agent_id)
            
            # Store the Bedrock IDs if we found the agent
            bedrock_agent_id = None
            bedrock_agent_alias_id = None
            if agent:
                bedrock_agent_id = agent.bedrock_agent_id
                bedrock_agent_alias_id = agent.bedrock_agent_alias_id
            
            # Delete from metadata
            session = self.metadata.get_db_session()
            try:
                # Delete agent record (which now includes Bedrock-specific fields)
                session.query(AgentRecord).filter_by(agent_id=agent_id).delete()
                session.query(BedrockAgentOptions).filter_by(agent_id=agent_id).delete()
                session.commit()
                LOGGER.info(f"Deleted agent {agent_id} from metadata")
                
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error deleting agent {agent_id} from metadata: {e}")
                return False
            finally:
                session.close()
            
            # Delete the Bedrock agent if we have the IDs
            if bedrock_agent_id and bedrock_agent_alias_id:
                delete_bedrock_agent(bedrock_agent_id=bedrock_agent_id,
                                     bedrock_agent_alias_id=bedrock_agent_alias_id)
            else:
                LOGGER.warning(f"No Bedrock agent IDs found for {agent_id}, skipping AWS deletion")
                
            return True
                
        except Exception as e:
            LOGGER.error(f"Error in delete_agent_resource: {e}")
            return False
    
    @override
    def create_or_update_agent_resource(self, agent_def: AgentDefinition, owner_user_id: str) -> Agent:
        """
        Create or update an agent.
        
        Args:
            agent_def: Agent definition
            owner_user_id: User who owns this agent
            
        Returns:
            BedrockAgent instance
        """

        # Log the incoming agent definition
        LOGGER.info(f"[BedrockAgent] Received AgentDefinition:")
        LOGGER.info(f"  - name: {agent_def.name}")
        LOGGER.info(f"  - mcp_tools: {agent_def.mcp_tools}")
        LOGGER.info(f"  - mcp_resources: {agent_def.mcp_resources}")
        LOGGER.info(f"  - has mcp_tools attr: {hasattr(agent_def, 'mcp_tools')}")
        
        # create or update the actual bedrock agent
        agent_id = agent_def.id
        bedrock_agent_id = None
        bedrock_agent_alias_id = None
        session = self.metadata.get_db_session()
        bedrock_options = None
        try:
            if not agent_id:
                agent_id = f"bedrock_agent_{uuid.uuid4().hex}"
                bedrock_agent_id, bedrock_agent_alias_id = create_bedrock_agent(
                    agent_id=agent_id,
                    agent_def=agent_def
                )
                bedrock_options = BedrockAgentOptions(
                    agent_id=agent_id,
                    bedrock_agent_id=bedrock_agent_id,
                    bedrock_agent_alias_id=bedrock_agent_alias_id,
                    temperature=agent_def.temperature or DEFAULT_TEMPERATURE,
                    tools=agent_def.tools or {},
                    tool_resources=agent_def.tool_resources or {},
                    mcp_tools=agent_def.mcp_tools or [],
                    mcp_resources=agent_def.mcp_resources or [],
                    agent_metadata=agent_def.metadata or {},
                )
                session.add(bedrock_options)
            else:
                bedrock_options = session.query(BedrockAgentOptions).filter_by(agent_id=agent_id).first()
                if bedrock_options:
                    bedrock_agent_id = bedrock_options.bedrock_agent_id
                    bedrock_agent_alias_id = bedrock_options.bedrock_agent_alias_id

                    # Update existing options
                    bedrock_options.temperature = agent_def.temperature or DEFAULT_TEMPERATURE
                    bedrock_options.tools = agent_def.tools or {}
                    bedrock_options.tool_resources = agent_def.tool_resources or {}
                    bedrock_options.mcp_tools = agent_def.mcp_tools or []
                    bedrock_options.mcp_resources = agent_def.mcp_resources or []
                    bedrock_options.agent_metadata = agent_def.metadata or {}
                else: 
                    raise ValueError(f"Bedrock options for agent {agent_id} not found in database")
                
                bedrock_agent_id, bedrock_agent_alias_id = update_bedrock_agent(
                    agent_def=agent_def,
                    bedrock_agent_id=bedrock_agent_id,
                    bedrock_agent_alias_id=bedrock_agent_alias_id
                )

            session.commit()  
            
            bedrock_agent = BedrockAgent(
                agent_id=agent_id,
                name=agent_def.name,
                introduction=agent_def.introduction,
                reminder=agent_def.reminder,
                owner_user_id=owner_user_id,
                bedrock_options=bedrock_options
            )
            LOGGER.info(f"Stored agent record for {agent_id} with Bedrock IDs: {bedrock_agent_id}, {bedrock_agent_alias_id}")    
            return bedrock_agent            
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error storing agent record: {e}")
            raise
        finally:
            session.close()

        # # Update agent definition with ID and user
        # agent_def.id = agent_id
        # if not agent_def.metadata:
        #     agent_def.metadata = {}
        # agent_def.metadata['user_id'] = owner_user_id


    @override            
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models.
        
        Returns:
            List of available model information
        """
        # Delegate to the main provider's get_available_models method
        # We need to access it through the metadata's reference
        try:
            # Get the provider instance through metadata
            if hasattr(self.metadata, '_provider') and self.metadata._provider:
                return self.metadata._provider.get_available_models()
            else:
                # Fallback: we need the bedrock client (not runtime) to list models
                # Try to get it from the bedrock_agent_client's session
                response = self.bedrock_client.list_foundation_models(
                    byOutputModality='TEXT'
                )
                models = []
                default_model = os.getenv('BEDROCK_DEFAULT_MODEL', 'us.anthropic.claude-3-haiku-20240307-v1:0')
                
                for model in response.get('modelSummaries', []):
                    if model.get('responseStreamingSupported', False) and 'TEXT' in model.get('outputModalities', []):
                        model_id = model['modelId']
                        models.append({
                            'name': model_id,
                            'description': f"{model['providerName']} - {model['modelName']}",
                            'is_default': model_id == default_model
                        })
                
                # Add default model if not in list
                if default_model and not any(m['name'] == default_model for m in models):
                    models.append({
                        'name': default_model,
                        'description': 'Default model from environment',
                        'is_default': True
                    })
                
                return models
        except Exception as e:
            LOGGER.error(f"Error getting available models: {e}")
            return []
    
