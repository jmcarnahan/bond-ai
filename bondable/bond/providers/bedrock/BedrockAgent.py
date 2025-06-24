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
from typing import List, Dict, Optional, Generator, Any
from botocore.exceptions import ClientError

from bondable.bond.providers.agent import Agent, AgentProvider
from bondable.bond.definition import AgentDefinition
from .BedrockMetadata import BedrockMetadata
from .BedrockThreads import BedrockThreadsProvider
from .BedrockMCP import get_mcp_tool_definitions_sync, execute_mcp_tool_sync

LOGGER = logging.getLogger(__name__)




class BedrockAgent(Agent):
    """Bedrock implementation of the Agent interface"""
    
    def __init__(self, agent_id: str, bedrock_runtime_client, bedrock_agent_runtime_client,
                 threads_provider: BedrockThreadsProvider, metadata: BedrockMetadata, 
                 agent_definition: AgentDefinition):
        self.agent_id = agent_id
        self.bedrock_runtime = bedrock_runtime_client  # Keep for model listing
        self.bedrock_agent_runtime = bedrock_agent_runtime_client  # For invoke_agent
        self.threads = threads_provider
        self.metadata = metadata
        self.agent_def = agent_definition
        
        # Get Bedrock-specific configuration
        agent_record = self.metadata.get_bedrock_agent(agent_id)
        
        if agent_record:
            self.model_id = agent_record.model_id or agent_definition.model
            self.system_prompt = agent_record.system_prompt or agent_definition.instructions
            self.temperature = float(agent_record.temperature) if agent_record.temperature else 0.7
            self.max_tokens = agent_record.max_tokens or 4096
            self.tools = agent_record.tools if hasattr(agent_record, 'tools') and agent_record.tools else []
            # Get Bedrock Agent IDs if available
            self.bedrock_agent_id = getattr(agent_record, 'bedrock_agent_id', None)
            self.bedrock_agent_alias_id = getattr(agent_record, 'bedrock_agent_alias_id', None)
        else:
            # Use defaults from agent definition
            self.model_id = agent_definition.model
            self.system_prompt = agent_definition.instructions
            self.temperature = 0.7
            self.max_tokens = 4096
            self.tools = []
            self.bedrock_agent_id = None
            self.bedrock_agent_alias_id = None
        
        LOGGER.info(f"Initialized BedrockAgent {agent_id} with model {self.model_id}")
        LOGGER.debug(f"  Bedrock Agent ID: {self.bedrock_agent_id}")
        LOGGER.debug(f"  Bedrock Alias ID: {self.bedrock_agent_alias_id}")
        LOGGER.debug(f"  MCP tools from definition: {agent_definition.mcp_tools}")
        LOGGER.debug(f"  MCP tools from record: {getattr(agent_record, 'mcp_tools', None) if agent_record else None}")
    
    def get_agent_id(self) -> str:
        """Get the agent's ID"""
        return self.agent_id
    
    def get_agent_definition(self) -> AgentDefinition:
        """Get the agent's definition"""
        return self.agent_def
    
    def get_name(self) -> str:
        """Get the agent's name"""
        return self.agent_def.name
    
    def get_description(self) -> str:
        """Get the agent's description"""
        return self.agent_def.description or ""
    
    def get_metadata_value(self, key: str, default_value=None):
        """Get a metadata value for the agent"""
        if self.agent_def.metadata:
            return self.agent_def.metadata.get(key, default_value)
        return default_value
    
    def get_metadata(self) -> Dict[str, str]:
        """Get all metadata for the agent"""
        return self.agent_def.metadata or {}
    
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
        
        message_id = self.threads.add_message(
            thread_id=thread_id,
            user_id=user_id,
            role=message_role,
            message_type=message_type,
            content=message_content,
            metadata={
                'agent_id': self.agent_id,
                'model': self.model_id,
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
        user_id = self.get_metadata_value('user_id')
        if not user_id:
            raise ValueError("Agent must have user_id in metadata")
        
        # Add the message to the thread
        # Note: session_id is extracted from thread_id in add_message
        message_id = self.threads.add_message(
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
        
        user_id = self.get_metadata_value('user_id')
        if not user_id:
            raise ValueError("Agent must have user_id in metadata")
        
        try:
            # Add user message if prompt provided
            if prompt:
                self.create_user_message(prompt, thread_id, attachments, override_role)
            else:
                # If no prompt, we need to get the last user message
                messages = self.threads.get_messages(thread_id, limit=1)
                if not messages:
                    raise ValueError("No user message to respond to")
                # Get the most recent message
                last_msg = list(messages.values())[0]
                if last_msg.role != 'user':
                    raise ValueError("No user message to respond to")
                prompt = last_msg.clob.get_content() if hasattr(last_msg, 'clob') else str(last_msg)
            
            # Get session ID and state from thread
            session_id = self.threads.get_thread_session_id(thread_id)
            session_state = self.threads.get_thread_session_state(thread_id, user_id)
            
            LOGGER.info(f"Invoking Bedrock Agent {self.bedrock_agent_id} with session {session_id}")
            
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

            # Add session state if available
            if session_state:
                request['sessionState'] = session_state
            
            # Invoke the agent (this returns a streaming response)
            response = self.bedrock_agent_runtime.invoke_agent(**request)

            # Process the streaming response
            new_session_state = None
            seen_file_hashes = set()  # Track files we've already sent
            
            # The response contains an EventStream that we need to iterate
            event_stream = response.get('completion')
            if event_stream:
                event_count = 0
                for event in event_stream:
                    event_count += 1
                    LOGGER.debug(f"Processing event {event_count}: {list(event.keys())}")
                    
                    # Handle text chunks
                    if 'chunk' in event:
                        chunk = event['chunk']
                        LOGGER.debug(f" --- Received chunk: {list(chunk.keys())}")
                        if 'bytes' in chunk:
                            text = chunk['bytes'].decode('utf-8')
                            LOGGER.debug(f"Processing text chunk of length {len(text)}")
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
                                    message_id = self.threads.add_message(
                                        message_id=response_id,
                                        thread_id=thread_id,
                                        user_id=user_id,
                                        role=response_role,
                                        message_type=response_type,
                                        content=full_content,
                                        attachments=attachments,
                                        metadata={
                                            'agent_id': self.agent_id,
                                            'model': self.model_id,
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
                            continuation_response = self.bedrock_agent_runtime.invoke_agent(**continuation_request)
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
                                                    message_id = self.threads.add_message(
                                                        message_id=response_id,
                                                        thread_id=thread_id,
                                                        user_id=user_id,
                                                        role=response_role,
                                                        message_type=response_type,
                                                        content=full_content,
                                                        attachments=attachments,
                                                        metadata={
                                                            'agent_id': self.agent_id,
                                                            'model': self.model_id,
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
                self.threads.add_message(
                    message_id=response_id,
                    thread_id=thread_id,
                    user_id=user_id,
                    role=response_role,
                    message_type=response_type,
                    content=full_content,
                    metadata={
                        'agent_id': self.agent_id,
                        'model': self.model_id,
                        'bedrock_agent_id': self.bedrock_agent_id
                    }
                )

                LOGGER.info(f"Saved assistant response to thread {thread_id}")
            
            # Update session state if provided
            if new_session_state:
                self.threads.update_thread_session_state(thread_id, user_id, new_session_state)
                LOGGER.info(f"Updated session state for thread {thread_id}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = str(e)
            LOGGER.error(f"Bedrock Agent API error: {error_code} - {error_message}")
            yield from self._yield_error_message(thread_id, error_message, error_code)
            
        except Exception as e:
            LOGGER.error(f"Unexpected error in stream_response: {e}")
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
    
    def __init__(self, bedrock_runtime_client, bedrock_agent_runtime_client,
                 metadata: BedrockMetadata, threads_provider: BedrockThreadsProvider):
        self.bedrock_runtime = bedrock_runtime_client
        self.bedrock_agent_runtime = bedrock_agent_runtime_client
        self.metadata = metadata
        self.threads = threads_provider
        # Get bedrock-agent client for agent management
        self.bedrock_agent_client = None
        try:
            import boto3
            self.bedrock_agent_client = boto3.client(
                service_name='bedrock-agent',
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
        except Exception as e:
            LOGGER.warning(f"Could not initialize bedrock-agent client: {e}")
        LOGGER.info("Initialized BedrockAgentProvider")
    
    def delete_agent_resource(self, agent_id: str) -> bool:
        """
        Delete an agent resource.
        
        This deletes both the Bond agent records and the corresponding
        Bedrock Agent if it exists.
        """
        try:
            # First get the Bedrock Agent info before deleting metadata
            agent_record = self.metadata.get_bedrock_agent(agent_id)
            bedrock_agent_id = getattr(agent_record, 'bedrock_agent_id', None) if agent_record else None
            bedrock_agent_alias_id = getattr(agent_record, 'bedrock_agent_alias_id', None) if agent_record else None
            
            # Delete from metadata
            session = self.metadata.get_db_session()
            try:
                # Delete agent record (which now includes Bedrock-specific fields)
                from bondable.bond.providers.metadata import AgentRecord
                session.query(AgentRecord).filter_by(agent_id=agent_id).delete()
                
                session.commit()
                LOGGER.info(f"Deleted agent {agent_id} from metadata")
                
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error deleting agent {agent_id} from metadata: {e}")
                return False
            finally:
                session.close()
            
            # Delete the Bedrock Agent if it exists
            if bedrock_agent_id and self.bedrock_agent_client:
                try:
                    # Delete alias first if it exists and is not the test alias
                    if bedrock_agent_alias_id and bedrock_agent_alias_id != 'TSTALIASID':
                        try:
                            LOGGER.info(f"Deleting Bedrock Agent alias {bedrock_agent_alias_id}")
                            self.bedrock_agent_client.delete_agent_alias(
                                agentId=bedrock_agent_id,
                                agentAliasId=bedrock_agent_alias_id
                            )
                        except ClientError as e:
                            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                                LOGGER.warning(f"Error deleting alias {bedrock_agent_alias_id}: {e}")
                    
                    # Delete the agent
                    LOGGER.info(f"Deleting Bedrock Agent {bedrock_agent_id}")
                    self.bedrock_agent_client.delete_agent(
                        agentId=bedrock_agent_id,
                        skipResourceInUseCheck=True  # Force delete even if in use
                    )
                    LOGGER.info(f"Successfully deleted Bedrock Agent {bedrock_agent_id}")
                    
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        LOGGER.info(f"Bedrock Agent {bedrock_agent_id} already deleted")
                    else:
                        LOGGER.warning(f"Error deleting Bedrock Agent {bedrock_agent_id}: {e}")
                        # Don't fail the whole operation if we can't delete the Bedrock Agent
                
            return True
                
        except Exception as e:
            LOGGER.error(f"Error in delete_agent_resource: {e}")
            return False
    
    def create_or_update_agent_resource(self, agent_def: AgentDefinition, 
                                      owner_user_id: str) -> Agent:
        """
        Create or update an agent.
        
        Args:
            agent_def: Agent definition
            owner_user_id: User who owns this agent
            
        Returns:
            BedrockAgent instance
        """
        try:
            # Log the incoming agent definition
            LOGGER.info(f"[BedrockAgent] Received AgentDefinition:")
            LOGGER.info(f"  - name: {agent_def.name}")
            LOGGER.info(f"  - mcp_tools: {agent_def.mcp_tools}")
            LOGGER.info(f"  - mcp_resources: {agent_def.mcp_resources}")
            LOGGER.info(f"  - has mcp_tools attr: {hasattr(agent_def, 'mcp_tools')}")
            
            # Generate agent ID if not provided
            agent_id = agent_def.id or f"bedrock_agent_{uuid.uuid4()}"
            
            
            # Store in base metadata
            session = self.metadata.get_db_session()
            try:
                from bondable.bond.providers.metadata import AgentRecord
                
                # Check if agent exists
                agent_record = session.query(AgentRecord).filter_by(agent_id=agent_id).first()
                
                if agent_record:
                    # Update existing
                    agent_record.name = agent_def.name
                    agent_record.introduction = agent_def.introduction or ""
                    agent_record.reminder = agent_def.reminder or ""
                else:
                    # Create new
                    agent_record = AgentRecord(
                        agent_id=agent_id,
                        name=agent_def.name,
                        introduction=agent_def.introduction or "",
                        reminder=agent_def.reminder or "",
                        owner_user_id=owner_user_id
                    )
                    session.add(agent_record)
                
                session.commit()
                
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error storing agent record: {e}")
                raise
            finally:
                session.close()
            
            # Store Bedrock-specific configuration
            model_to_store = agent_def.model or "us.anthropic.claude-3-haiku-20240307-v1:0"
            
            # Check if this is a new agent or update
            existing_agent = self.metadata.get_bedrock_agent(agent_id)
            
            LOGGER.info(f"Creating/updating agent {agent_id} with MCP tools: {agent_def.mcp_tools}")
            
            if not existing_agent or not getattr(existing_agent, 'bedrock_agent_id', None):
                # New agent - create Bedrock Agent
                LOGGER.info(f"Creating new Bedrock Agent for {agent_id}")
                bedrock_agent_id, bedrock_agent_alias_id = self._create_bedrock_agent(
                    agent_id=agent_id,
                    name=agent_def.name,
                    instructions=agent_def.instructions,
                    model=model_to_store,
                    owner_user_id=owner_user_id,
                    mcp_tools=agent_def.mcp_tools,
                    mcp_resources=agent_def.mcp_resources
                )
                LOGGER.info(f"Created Bedrock Agent: {bedrock_agent_id}, Alias: {bedrock_agent_alias_id}")
            else:
                # Existing agent - use stored IDs
                bedrock_agent_id = existing_agent.bedrock_agent_id
                bedrock_agent_alias_id = existing_agent.bedrock_agent_alias_id
                LOGGER.info(f"Using existing Bedrock Agent: {bedrock_agent_id}, Alias: {bedrock_agent_alias_id}")
            
            self.metadata.create_or_update_bedrock_agent(
                agent_id=agent_id,
                model_id=model_to_store,
                system_prompt=agent_def.instructions,
                temperature=float(agent_def.metadata.get('temperature', 0.7)) if agent_def.metadata else 0.7,
                max_tokens=int(agent_def.metadata.get('max_tokens', 4096)) if agent_def.metadata else 4096,
                tools=agent_def.tools,
                knowledge_base_ids=agent_def.metadata.get('knowledge_base_ids', []) if agent_def.metadata else [],
                bedrock_agent_id=bedrock_agent_id,
                bedrock_agent_alias_id=bedrock_agent_alias_id,
                mcp_tools=agent_def.mcp_tools,
                mcp_resources=agent_def.mcp_resources
            )
            
            # Update agent definition with ID and user
            agent_def.id = agent_id
            if not agent_def.metadata:
                agent_def.metadata = {}
            agent_def.metadata['user_id'] = owner_user_id
            
            # Create and return agent instance
            agent = BedrockAgent(
                agent_id=agent_id,
                bedrock_runtime_client=self.bedrock_runtime,
                bedrock_agent_runtime_client=self.bedrock_agent_runtime,
                threads_provider=self.threads,
                metadata=self.metadata,
                agent_definition=agent_def
            )
            
            LOGGER.info(f"Created/updated agent {agent_id} for user {owner_user_id}")
            return agent
            
        except Exception as e:
            LOGGER.error(f"Error creating/updating agent: {e}")
            raise
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """
        Get an agent by ID.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            BedrockAgent instance or None if not found
        """
        try:
            # Get base agent record
            session = self.metadata.get_db_session()
            try:
                from bondable.bond.providers.metadata import AgentRecord
                agent_record = session.query(AgentRecord).filter_by(agent_id=agent_id).first()
                
                if not agent_record:
                    LOGGER.warning(f"Agent {agent_id} not found")
                    return None
                
                # Get agent record with Bedrock configuration
                agent_with_bedrock = self.metadata.get_bedrock_agent(agent_id)
                if not agent_with_bedrock:
                    LOGGER.warning(f"No agent record found for agent {agent_id}")
                    return None
                
                
                # Build agent definition
                agent_def = AgentDefinition(
                    user_id=agent_record.owner_user_id,  # Required parameter
                    id=agent_id,
                    name=agent_record.name,
                    description="",  # Not stored in base record
                    instructions=agent_with_bedrock.system_prompt or "",
                    introduction=agent_record.introduction,
                    reminder=agent_record.reminder,
                    tools=agent_with_bedrock.tools if hasattr(agent_with_bedrock, 'tools') else [],
                    model=agent_with_bedrock.model_id or "",
                    metadata={
                        'user_id': agent_record.owner_user_id,
                        'temperature': str(agent_with_bedrock.temperature) if agent_with_bedrock.temperature else "0.7",
                        'max_tokens': str(agent_with_bedrock.max_tokens) if agent_with_bedrock.max_tokens else "4096",
                        'knowledge_base_ids': getattr(agent_with_bedrock, 'knowledge_base_ids', [])
                    },
                    mcp_tools=getattr(agent_with_bedrock, 'mcp_tools', []),
                    mcp_resources=getattr(agent_with_bedrock, 'mcp_resources', [])
                )
                
                # Create agent instance
                return BedrockAgent(
                    agent_id=agent_id,
                    bedrock_runtime_client=self.bedrock_runtime,
                    bedrock_agent_runtime_client=self.bedrock_agent_runtime,
                    threads_provider=self.threads,
                    metadata=self.metadata,
                    agent_definition=agent_def
                )
                
            finally:
                session.close()
                
        except Exception as e:
            LOGGER.error(f"Error getting agent {agent_id}: {e}")
            return None
    
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
                import boto3
                bedrock_client = boto3.client(
                    service_name='bedrock',
                    region_name=os.getenv('AWS_REGION', 'us-east-1')
                )
                response = bedrock_client.list_foundation_models(
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
    
    def _create_bedrock_agent(self, agent_id: str, name: str, 
                            instructions: str, model: str, owner_user_id: str,
                            mcp_tools: List[str] = None, mcp_resources: List[str] = None) -> tuple[str, str]:
        """
        Create a Bedrock Agent for the Bond agent.
        
        Args:
            agent_id: Bond agent ID (used as Bedrock agent name for uniqueness)
            name: Display name for the agent
            instructions: Agent instructions/system prompt
            model: Model ID to use
            owner_user_id: User who owns this agent
            
        Returns:
            Tuple of (bedrock_agent_id, bedrock_agent_alias_id)
        """
        # Ensure instructions meet minimum length requirement (40 chars for Bedrock)
        MIN_INSTRUCTION_LENGTH = 40
        DEFAULT_INSTRUCTION = "You are a helpful AI assistant. Be helpful, accurate, and concise in your responses."
        
        if not instructions:
            instructions = DEFAULT_INSTRUCTION
        else:
            # Pad with spaces if too short
            instructions = instructions.ljust(MIN_INSTRUCTION_LENGTH)
        
        # Store MCP tools for later action group creation
        self._pending_mcp_tools = mcp_tools
        self._pending_mcp_resources = mcp_resources
        
        if not self.bedrock_agent_client:
            # Fall back to environment variables if client not available
            bedrock_agent_id = os.getenv('BEDROCK_AGENT_ID')
            bedrock_agent_alias_id = os.getenv('BEDROCK_AGENT_ALIAS_ID')
            
            if not bedrock_agent_id:
                raise ValueError(
                    "Cannot create Bedrock Agent: bedrock-agent client not available "
                    "and no BEDROCK_AGENT_ID environment variable set."
                )
            
            LOGGER.warning(f"Using environment variable Bedrock Agent {bedrock_agent_id} for Bond agent {agent_id}")
            return bedrock_agent_id, bedrock_agent_alias_id
        
        try:
            # Step 1: Create the agent
            LOGGER.info(f"Creating Bedrock Agent for Bond agent {agent_id}")
            
            # Get IAM role from environment or use default
            agent_role_arn = os.getenv('BEDROCK_AGENT_ROLE_ARN')
            if not agent_role_arn:
                raise ValueError("BEDROCK_AGENT_ROLE_ARN environment variable must be set")
            
            # Use agent_id as the Bedrock agent name for guaranteed uniqueness
            # Bedrock agent names must match pattern: ([0-9a-zA-Z][_-]?){1,100}
            # Since agent_id is a UUID with format "bedrock_agent_<uuid>", we need to clean it
            bedrock_agent_name = agent_id.replace('-', '_')
            
            # Create tags to store metadata
            tags = {
                'bond_agent_id': agent_id,
                'bond_user_id': owner_user_id,
                'bond_display_name': name
            }
            
            create_response = self.bedrock_agent_client.create_agent(
                agentName=bedrock_agent_name,
                agentResourceRoleArn=agent_role_arn,
                instruction=instructions,
                foundationModel=model,
                description=f"Bond agent '{name}' for user {owner_user_id}",
                idleSessionTTLInSeconds=3600,  # 1 hour timeout
                tags=tags
            )
            
            bedrock_agent_id = create_response['agent']['agentId']
            LOGGER.info(f"Created Bedrock Agent: {bedrock_agent_id}")
            
            # Step 2: Wait for agent to be created
            self._wait_for_resource_status('agent', bedrock_agent_id, ['NOT_PREPARED', 'PREPARED'])
            
            # Step 3: Enable code interpreter (always enabled for all agents)
            LOGGER.info(f"Enabling code interpreter for Bedrock Agent {bedrock_agent_id}")
            try:
                code_interpreter_response = self.bedrock_agent_client.create_agent_action_group(
                    agentId=bedrock_agent_id,
                    agentVersion='DRAFT',
                    actionGroupName='CodeInterpreterActionGroup',
                    parentActionGroupSignature='AMAZON.CodeInterpreter',
                    actionGroupState='ENABLED'
                )
                LOGGER.info(f"Created code interpreter action group: {code_interpreter_response['agentActionGroup']['actionGroupId']}")
            except ClientError as e:
                LOGGER.warning(f"Failed to enable code interpreter: {e}")
                # Continue without code interpreter rather than failing
            
            # Step 4: Prepare the agent
            LOGGER.info(f"Preparing Bedrock Agent {bedrock_agent_id}")
            self.bedrock_agent_client.prepare_agent(agentId=bedrock_agent_id)
            
            # Step 5: Wait for agent to be prepared
            self._wait_for_resource_status('agent', bedrock_agent_id, ['PREPARED'])
            
            # Step 5.5: Create MCP action groups if any MCP tools specified
            if mcp_tools:
                self._create_mcp_action_groups(bedrock_agent_id, mcp_tools, mcp_resources or [])
                # Re-prepare the agent after adding action groups
                LOGGER.info(f"Re-preparing agent after adding MCP action groups")
                self.bedrock_agent_client.prepare_agent(agentId=bedrock_agent_id)
                self._wait_for_resource_status('agent', bedrock_agent_id, ['PREPARED'])
            
            # Step 6: Create alias
            alias_name = f"bond-{uuid.uuid4().hex[:8]}"
            LOGGER.info(f"Creating alias {alias_name} for Bedrock Agent {bedrock_agent_id}")
            
            alias_response = self.bedrock_agent_client.create_agent_alias(
                agentId=bedrock_agent_id,
                agentAliasName=alias_name,
                description=f"Alias for Bond agent {agent_id}"
            )
            
            bedrock_agent_alias_id = alias_response['agentAlias']['agentAliasId']
            
            # Step 7: Wait for alias to be prepared
            self._wait_for_resource_status('alias', bedrock_agent_alias_id, ['PREPARED'], agent_id=bedrock_agent_id)
            
            LOGGER.info(f"Successfully created Bedrock Agent {bedrock_agent_id} with alias {bedrock_agent_alias_id}")
            return bedrock_agent_id, bedrock_agent_alias_id
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            LOGGER.error(f"Failed to create Bedrock Agent: {error_code} - {error_message}")
            
            # Fall back to environment variables if available
            bedrock_agent_id = os.getenv('BEDROCK_AGENT_ID')
            if bedrock_agent_id:
                LOGGER.warning(f"Falling back to environment variable Bedrock Agent {bedrock_agent_id}")
                return bedrock_agent_id, os.getenv('BEDROCK_AGENT_ALIAS_ID')
            
            raise ValueError(f"Failed to create Bedrock Agent: {error_message}")
        
        except Exception as e:
            LOGGER.error(f"Unexpected error creating Bedrock Agent: {e}")
            raise
    
    def _create_mcp_action_groups(self, bedrock_agent_id: str, mcp_tools: List[str], mcp_resources: List[str]):
        """
        Create action groups for MCP tools.
        
        Args:
            bedrock_agent_id: The Bedrock agent ID
            mcp_tools: List of MCP tool names to create action groups for
            mcp_resources: List of MCP resource names (for future use)
        """
        if not mcp_tools:
            return
            
        try:
            # Get MCP config
            from bondable.bond.config import Config
            config = Config.config()
            mcp_config = config.get_mcp_config()
            
            if not mcp_config:
                LOGGER.warning("MCP tools specified but no MCP config available")
                return
            
            # Get tool definitions from MCP
            from .BedrockMCP import get_mcp_tool_definitions_sync
            mcp_tool_definitions = get_mcp_tool_definitions_sync(mcp_config, mcp_tools)
            
            if not mcp_tool_definitions:
                LOGGER.warning("No MCP tool definitions found")
                return
            
            # Build OpenAPI paths for MCP tools
            paths = {}
            for tool in mcp_tool_definitions:
                # Prefix with _bond_mcp_tool_
                tool_path = f"/_bond_mcp_tool_{tool['name']}"
                operation_id = f"_bond_mcp_tool_{tool['name']}"
                
                paths[tool_path] = {
                    "post": {
                        "operationId": operation_id,
                        "summary": tool.get('description', f"MCP tool {tool['name']}"),
                        "description": tool.get('description', f"MCP tool {tool['name']}"),
                        "responses": {
                            "200": {
                                "description": "Tool execution result",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "result": {
                                                    "type": "string",
                                                    "description": "Tool execution result"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                
                # Add parameters if any
                if tool.get('parameters'):
                    paths[tool_path]["post"]["requestBody"] = {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": tool['parameters']
                                }
                            }
                        }
                    }
            
            # Create action group
            action_group_spec = {
                "actionGroupName": "MCPTools",
                "description": "MCP (Model Context Protocol) tools for external integrations",
                "actionGroupExecutor": {
                    "customControl": "RETURN_CONTROL"  # Return control to client for execution
                },
                "apiSchema": {
                    "payload": json.dumps({
                        "openapi": "3.0.0",
                        "info": {
                            "title": "MCP Tools API",
                            "version": "1.0.0",
                            "description": "MCP tools for external integrations"
                        },
                        "paths": paths
                    })
                }
            }
            
            LOGGER.info(f"Creating MCP action group with {len(paths)} tools")
            action_response = self.bedrock_agent_client.create_agent_action_group(
                agentId=bedrock_agent_id,
                agentVersion="DRAFT",
                **action_group_spec
            )
            
            LOGGER.info(f"Created MCP action group: {action_response['agentActionGroup']['actionGroupId']}")
            
        except Exception as e:
            LOGGER.error(f"Error creating MCP action groups: {e}")
            # Continue without MCP tools rather than failing agent creation
    
    def _wait_for_resource_status(self, resource_type: str, resource_id: str, 
                                 target_statuses: List[str], max_attempts: int = 30, 
                                 delay: int = 2, agent_id: Optional[str] = None):
        """
        Generic method to wait for a resource to reach target status.
        
        Args:
            resource_type: 'agent' or 'alias'
            resource_id: The resource ID to check
            target_statuses: List of acceptable statuses
            max_attempts: Maximum number of attempts
            delay: Delay between attempts in seconds
            agent_id: Required for alias resources
        """
        import time
        
        failed_statuses = {
            'agent': ['CREATE_FAILED', 'PREPARE_FAILED'],
            'alias': ['FAILED']
        }
        
        for attempt in range(max_attempts):
            try:
                if resource_type == 'agent':
                    response = self.bedrock_agent_client.get_agent(agentId=resource_id)
                    current_status = response['agent']['agentStatus']
                else:  # alias
                    response = self.bedrock_agent_client.get_agent_alias(
                        agentId=agent_id,
                        agentAliasId=resource_id
                    )
                    current_status = response['agentAlias']['agentAliasStatus']
                
                if current_status in target_statuses:
                    LOGGER.info(f"{resource_type.capitalize()} {resource_id} reached status: {current_status}")
                    return
                
                if current_status in failed_statuses.get(resource_type, []):
                    raise ValueError(f"{resource_type.capitalize()} {resource_id} failed with status: {current_status}")
                
                LOGGER.debug(f"{resource_type.capitalize()} {resource_id} status: {current_status}, waiting...")
                time.sleep(delay)
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    LOGGER.debug(f"{resource_type.capitalize()} {resource_id} not found yet, waiting...")
                    time.sleep(delay)
                else:
                    raise
        
        raise TimeoutError(f"{resource_type.capitalize()} {resource_id} did not reach status {target_statuses} after {max_attempts} attempts")