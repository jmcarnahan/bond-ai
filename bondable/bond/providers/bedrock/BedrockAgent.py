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
        # Include Bedrock-specific IDs in metadata for debugging
        enhanced_metadata = self.metadata.copy() if self.metadata else {}
        enhanced_metadata.update({
            'bedrock_agent_id': self.bedrock_agent_id,
            'bedrock_agent_alias_id': self.bedrock_agent_alias_id
        })
        
        agent_def = AgentDefinition(
            id=self.agent_id,
            name=self.name,
            description=self.description,
            instructions=self.instructions,
            introduction=self.introduction,
            reminder=self.reminder,
            tools=self.tools,
            tool_resources=self.tool_resources,
            metadata=enhanced_metadata,
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
                # Store file in S3 and get file details
                file_details = self.bond_provider.files.get_or_create_file_id(
                    user_id=user_id,
                    file_tuple=(file_name, file_data)
                )

                # Create message content with file metadata as JSON
                message_content = json.dumps({
                    'file_id': file_details.file_id,
                    'file_name': file_details.file_path,
                    'file_size': file_details.file_size,
                    'mime_type': file_details.mime_type
                })
                message_type = 'file_link'

                LOGGER.info(f"Non-image file stored: {file_name} ({file_type}) with file_id: {file_details.file_id}")

            except Exception as e:
                LOGGER.error(f"Error handling file {file_name}: {e}")
                # Fallback message if upload fails
                message_content = f"Error uploading file: {file_name}"
                message_type = 'file_link'
        
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
                       override_role: str = "user",
                       current_user: Optional[Any] = None,
                       jwt_token: Optional[str] = None) -> Generator[str, None, None]:
        """
        Stream a response from the agent using Bedrock Agents API.

        Args:
            prompt: Optional prompt to add to thread
            thread_id: Thread ID (required)
            attachments: Optional attachments
            override_role: Role for the prompt message
            current_user: User object with authentication context
            jwt_token: Raw JWT token for passing to MCP servers

        Yields:
            Response chunks in Bond message format
        """
        # SECURITY NOTE: Store auth context for use in MCP tool execution
        # This is currently SAFE because BedrockAgentProvider.get_agent() creates
        # a NEW instance for each request (see line 1156).
        # WARNING: If agent instances are ever cached or shared between requests,
        # this will become a CRITICAL SECURITY VULNERABILITY (auth leakage between users).
        # Consider refactoring to use Python's contextvars module for thread-safe storage.
        self._current_user = current_user
        self._jwt_token = jwt_token
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

            # Add user message if needed
            if prompt:
                self.create_user_message(prompt, thread_id, attachments, override_role)
            elif not prompt:
                # Get the last user message
                messages = self.bond_provider.threads.get_messages(thread_id, limit=1)
                if not messages:
                    raise ValueError("No user message to respond to")
                last_msg = list(messages.values())[0]
                if last_msg.role != 'user':
                    raise ValueError("No user message to respond to")
                prompt = last_msg.clob.get_content() if hasattr(last_msg, 'clob') else str(last_msg)

            # Augment this with any files from the tool_resources for this agent
            # only do this for the first message
            all_files = []
            if self.bond_provider.threads.get_response_message_count(thread_id=thread_id) == 0:
                session_files = self.bond_provider.files.get_files_invocation(self.tool_resources)
                if session_files:
                    all_files.extend(session_files)

            # Add files from attachments
            if attachments:
                LOGGER.debug(f"Streaming response with attachments\n: {json.dumps(attachments, indent=2)}")
                attachment_files = self.bond_provider.files.convert_attachments_to_files(attachments)
                if attachment_files:
                    all_files.extend(attachment_files)

            # Check the number of files in session state
            if len(all_files) > 5:
                LOGGER.error(f"Session state has {len(all_files)} files, which exceeds Bedrock limits")
                raise ValueError("Request has too many files. Bedrock supports a maximum of 5 files per request.")
            
            # Separate files by use case
            if all_files:
                chat_files, code_files = self._separate_files_by_use_case(all_files)
                
                # Log file distribution
                LOGGER.info(f"File distribution: {len(chat_files)} CHAT files, {len(code_files)} CODE_INTERPRETER files")
                
                # Check if we have mixed file types
                if chat_files and code_files:
                    LOGGER.info("Processing mixed file types in two phases")
                    
                    # Phase 1: Process CHAT files with context-gathering prompt
                    phase1_prompt = f"""I'm providing some documents for context. Please analyze these documents and keep their content in mind for the upcoming question.

Documents are attached.

Original question: {prompt}

Please briefly acknowledge the documents and indicate you're ready to proceed with the analysis."""
                    
                    yield from self._process_bedrock_invocation(
                        prompt=phase1_prompt,
                        thread_id=thread_id,
                        session_id=session_id,
                        session_state=session_state,
                        files=chat_files,
                        attachments=attachments,
                        override_role=override_role,
                        user_id=user_id,
                        phase_metadata={'phase': 'document_analysis', 'phase_number': 1}
                    )
                    
                    # Phase 2: Process CODE_INTERPRETER files with the original prompt
                    phase2_prompt = f"""Now, using the context from the documents I just analyzed, please address the original question with the data files provided:

{prompt}

Please integrate any relevant insights from the documents with your analysis of the data."""
                    
                    yield from self._process_bedrock_invocation(
                        prompt=phase2_prompt,
                        thread_id=thread_id,
                        session_id=session_id,
                        session_state=session_state,
                        files=code_files,
                        attachments=None,  # Don't re-send attachments in phase 2
                        override_role=override_role,
                        user_id=user_id,
                        phase_metadata={'phase': 'data_analysis', 'phase_number': 2}
                    )
                    
                    return  # Exit early for mixed files
            
            # Single file type or no files - process normally
            LOGGER.info(f"Processing with single file type or no files")
            if all_files:
                LOGGER.info(f"Session state contains {len(all_files)} files")
                for i, file in enumerate(all_files):
                    LOGGER.debug(f"  File {i}: {file.get('name')} - {file.get('source', {}).get('sourceType')}")
            
            # Set files in session state if we have any
            if all_files:
                session_state['files'] = all_files
            
            # Process normally with all the original logic intact
            yield from self._process_bedrock_invocation(
                prompt=prompt,
                thread_id=thread_id,
                session_id=session_id,
                session_state=session_state,
                files=all_files if all_files else None,
                attachments=attachments,
                override_role=override_role,
                user_id=user_id,
            )
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = str(e)
            LOGGER.exception(f"Bedrock Agent API error: {error_code} - {error_message} - {e}")
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
                    
                    LOGGER.info(f"Executing MCP tool: {tool_name}")
                    LOGGER.debug(f"Tool name: {tool_name}, action input: {action_input}")

                    # Get parameters
                    parameters = {}
                    
                    # First check if parameters are in the 'parameters' array
                    if 'parameters' in action_input and action_input['parameters']:
                        # Parameters might be in different formats
                        for param in action_input['parameters']:
                            if 'name' in param and 'value' in param:
                                parameters[param['name']] = param['value']
                    
                    # Also check requestBody (parameters might be there instead or in addition)
                    if 'requestBody' in action_input and not parameters:
                        # Parameters might be in request body
                        request_body = action_input.get('requestBody', {})
                        content = request_body.get('content', {})
                        if 'application/json' in content:
                            json_content = content['application/json']
                            
                            # Check if parameters are in 'properties' array format
                            if 'properties' in json_content:
                                for prop in json_content['properties']:
                                    if 'name' in prop and 'value' in prop:
                                        parameters[prop['name']] = prop['value']
                            # Otherwise check for 'body' string format
                            elif 'body' in json_content:
                                body_str = json_content.get('body', '{}')
                                try:
                                    parameters = json.loads(body_str)
                                except json.JSONDecodeError:
                                    LOGGER.error(f"Failed to parse request body JSON: {body_str}")
                    
                    # Execute MCP tool
                    try:
                        # Get MCP config
                        from bondable.bond.config import Config
                        config = Config.config()
                        mcp_config = config.get_mcp_config()
                        
                        if mcp_config:
                            result = execute_mcp_tool_sync(
                                mcp_config,
                                tool_name,
                                parameters,
                                current_user=self._current_user,
                                jwt_token=self._jwt_token
                            )

                            LOGGER.info(f"Executed MCP tool {tool_name} with result: \n{json.dumps(result, indent=2)}")

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
                            
                            LOGGER.debug(f"Executed MCP tool {tool_name} with response: \n{json.dumps(tool_response, indent=2)}")

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
    
    def _create_bond_message_tag(self, message_id: str, thread_id: str, agent_id: str, 
                                 message_type: str = "text", role: str = "assistant", 
                                 is_error: bool = False) -> str:
        """
        Create a bond message opening tag.
        
        Args:
            message_id: Unique message ID
            thread_id: Thread ID
            agent_id: Agent ID
            message_type: Type of message (text, image_file, etc.)
            role: Role of message sender
            is_error: Whether this is an error message
            
        Returns:
            Bond message opening tag string
        """
        return (
            f'<_bondmessage '
            f'id="{message_id}" '
            f'thread_id="{thread_id}" '
            f'agent_id="{agent_id}" '
            f'type="{message_type}" '
            f'role="{role}" '
            f'is_error="{str(is_error).lower()}" '
            f'is_done="false">'
        )
    
    def _handle_file_event_streaming(self, file_info: Dict[str, Any], thread_id: str, 
                                   user_id: str, current_response_id: str, 
                                   full_content: str, attachments: Optional[List] = None,
                                   seen_file_hashes: set = None) -> Generator[str, None, str]:
        """
        Handle file events during streaming, yielding bond messages.
        
        Args:
            file_info: File information from Bedrock
            thread_id: Thread ID
            user_id: User ID  
            current_response_id: Current response message ID
            full_content: Accumulated text content
            attachments: Optional attachments
            seen_file_hashes: Set of already seen file hashes
            
        Yields:
            Bond message chunks
            
        Returns:
            New response ID for continuation
        """
        # Check for duplicate files
        if seen_file_hashes is not None:
            file_hash = self._compute_file_hash(file_info)
            if file_hash:
                if file_hash in seen_file_hashes:
                    file_name = file_info.get('name', 'unknown')
                    LOGGER.debug(f"Skipping duplicate file: {file_name} (hash: {file_hash})")
                    return current_response_id
                seen_file_hashes.add(file_hash)
        
        # Save any accumulated text content
        if full_content and len(full_content) > 0:
            self.bond_provider.threads.add_message(
                message_id=current_response_id,
                thread_id=thread_id,
                user_id=user_id,
                role="assistant",
                message_type="text",
                content=full_content,
                attachments=attachments,
                metadata={
                    'agent_id': self.agent_id,
                    'model': self.model,
                    'bedrock_agent_id': self.bedrock_agent_id
                }
            )
        
        # Close current text message
        yield '</_bondmessage>'
        
        # Send the file message
        yield from self._handle_file_event(file_info=file_info, 
                                         thread_id=thread_id, 
                                         user_id=user_id)
        
        # Start a new text message
        new_response_id = str(uuid.uuid4())
        yield self._create_bond_message_tag(
            message_id=new_response_id,
            thread_id=thread_id,
            agent_id=self.agent_id,
            message_type="text",
            role="assistant"
        )
        
        return new_response_id
    
    def _handle_chunk_event(self, chunk: Dict[str, Any]) -> Optional[str]:
        """
        Handle a chunk event from Bedrock streaming.
        
        Args:
            chunk: The chunk event data
            
        Returns:
            Decoded text if available, None otherwise
        """
        if 'bytes' in chunk:
            text = chunk['bytes'].decode('utf-8')
            return text
        return None
    
    def _separate_files_by_use_case(self, files: List[Dict[str, Any]]) -> tuple[List[Dict], List[Dict]]:
        """
        Separate files by their use case.
        
        Args:
            files: List of file dictionaries with 'useCase' field
            
        Returns:
            Tuple of (chat_files, code_files)
        """
        chat_files = []
        code_files = []
        
        for file in files:
            # The useCase should already be set by the file conversion process
            use_case = file.get('useCase', 'CHAT')  # Default to CHAT if not specified
            
            if use_case == 'CODE_INTERPRETER':
                code_files.append(file)
            else:
                chat_files.append(file)
        
        return chat_files, code_files
    
    def _process_bedrock_invocation(self, prompt: Optional[str], thread_id: str, session_id: str,
                                   session_state: Dict[str, Any], files: Optional[List[Dict]],
                                   attachments: Optional[List], override_role: str, user_id: str,
                                   phase_metadata: Optional[Dict] = None) -> Generator[str, None, None]:
        """
        Process a single Bedrock invocation with the given files.
        
        This method contains all the common logic for processing responses,
        handling files, MCP tools, etc.
        
        Args:
            prompt: The prompt to send to Bedrock
            thread_id: Thread ID
            session_id: Session ID
            session_state: Current session state
            files: Files to include in this invocation (already have useCase set)
            attachments: Original attachments (only used for first invocation)
            override_role: Role for user message
            user_id: User ID
            phase_metadata: Optional metadata to include (e.g., phase information)
            
        Yields:
            Response chunks in Bond message format
        """
        # Update session state with files if provided
        updated_session_state = session_state.copy()
        if files:
            updated_session_state['files'] = files
            LOGGER.info(f"Session state contains {len(files)} files")
            for i, file in enumerate(files):
                LOGGER.debug(f"  File {i}: {file.get('name')} - useCase: {file.get('useCase')}")

        # Build request
        request = {
            'agentId': self.bedrock_agent_id,
            'agentAliasId': self.bedrock_agent_alias_id,
            'sessionId': session_id,
            'inputText': prompt,
            'enableTrace': True,
            'sessionState': updated_session_state,
            'streamingConfigurations': {
                'streamFinalResponse': True
            }
        }
        
        # Log request
        request_log = {k: v for k, v in request.items() if k != 'sessionState'}
        LOGGER.debug(f"Sending request (without sessionState): {request_log}")
        if 'sessionState' in request and 'files' in request['sessionState']:
            LOGGER.debug(f"Session state files count: {len(request['sessionState']['files'])}")
        
        # Initialize response tracking
        full_content = ""
        response_id = str(uuid.uuid4())
        response_type = "text"
        response_role = "assistant"
        seen_file_hashes = set()
        new_session_state = None
        
        # Start bond message
        yield self._create_bond_message_tag(
            message_id=response_id,
            thread_id=thread_id,
            agent_id=self.agent_id,
            message_type=response_type,
            role=response_role
        )
        
        # Log essential debug info
        LOGGER.debug(f"Invoking Bedrock Agent - ID: {self.bedrock_agent_id}, Alias: {self.bedrock_agent_alias_id}, Region: {self.bond_provider.aws_region}")
        LOGGER.debug(f"Session: {session_id}, Thread: {thread_id}, User: {user_id}")
        
        # Invoke agent
        LOGGER.info(f"Invoking Bedrock Agent {self.bedrock_agent_id}")
        try:
            response = self.bond_provider.bedrock_agent_runtime_client.invoke_agent(**request)
        except Exception as e:
            LOGGER.error(f"Bedrock invocation failed - Agent: {self.bedrock_agent_id}, Error: {str(e)}")
            raise
        
        # Process streaming response
        event_stream = response.get('completion')
        if event_stream:
            event_count = 0
            for event in event_stream:
                event_count += 1
                
                # Handle text chunks
                if 'chunk' in event:
                    text = self._handle_chunk_event(event['chunk'])
                    if text:
                        yield text
                        full_content += text
                
                # Handle files event
                elif 'files' in event:
                    files_event = event['files']
                    if 'files' in files_event:
                        for file_info in files_event['files']:
                            new_response_id = yield from self._handle_file_event_streaming(
                                file_info=file_info,
                                thread_id=thread_id,
                                user_id=user_id,
                                current_response_id=response_id,
                                full_content=full_content,
                                attachments=attachments if not phase_metadata else None,
                                seen_file_hashes=seen_file_hashes
                            )
                            
                            if new_response_id != response_id:
                                response_id = new_response_id
                                full_content = ''
                
                # Handle returnControl events for MCP tools
                elif 'returnControl' in event:
                    return_control = event['returnControl']
                    LOGGER.info("Received returnControl event for tool execution")
                    
                    continuation_generator = self._handle_continuation_response(
                        return_control=return_control,
                        session_id=session_id,
                        thread_id=thread_id,
                        seen_file_hashes=seen_file_hashes,
                        attachments=attachments if not phase_metadata else None
                    )
                    
                    for cont_item in continuation_generator:
                        if isinstance(cont_item, str):
                            yield cont_item
                            full_content += cont_item
                        elif isinstance(cont_item, dict) and 'files_event' in cont_item:
                            files_event = cont_item['files_event']['files']
                            if 'files' in files_event:
                                for file_info in files_event['files']:
                                    new_response_id = yield from self._handle_file_event_streaming(
                                        file_info=file_info,
                                        thread_id=thread_id,
                                        user_id=user_id,
                                        current_response_id=response_id,
                                        full_content=full_content,
                                        attachments=attachments if not phase_metadata else None,
                                        seen_file_hashes=seen_file_hashes
                                    )
                                    if new_response_id != response_id:
                                        response_id = new_response_id
                                        full_content = ''
                        elif isinstance(cont_item, dict):
                            if cont_item.get('session_state'):
                                new_session_state = cont_item['session_state']
                
                # Handle session state updates
                elif 'sessionState' in event:
                    new_session_state = event['sessionState']
                    LOGGER.debug("Received session state update")
                
                elif 'trace' in event:
                    event_trace = event['trace']
                    LOGGER.debug(f" --- Received trace: {list(event_trace.keys())}")
            
            LOGGER.info(f"Processed {event_count} events from completion stream")
        
        # Close bond message
        yield '</_bondmessage>'
        
        # Save response if we have content
        if full_content:
            # Build metadata
            metadata = {
                'agent_id': self.agent_id,
                'model': self.model,
                'bedrock_agent_id': self.bedrock_agent_id
            }
            # Add phase metadata if provided
            if phase_metadata:
                metadata.update(phase_metadata)
            
            self.bond_provider.threads.add_message(
                message_id=response_id,
                thread_id=thread_id,
                user_id=user_id,
                role=response_role,
                message_type=response_type,
                content=full_content,
                metadata=metadata
            )
            LOGGER.info(f"Saved assistant response to thread {thread_id}")
        
        # Update session state if provided
        if new_session_state:
            self.bond_provider.threads.update_thread_session(
                thread_id=thread_id,
                user_id=user_id,
                session_id=session_id,
                session_state=new_session_state
            )
            LOGGER.debug(f"Updated session state for thread {thread_id}")
    
    def _handle_continuation_response(self, return_control: Dict[str, Any], session_id: str,
                                    thread_id: str, seen_file_hashes: set,
                                    attachments: Optional[List] = None) -> Generator[str, None, Dict[str, Any]]:
        """
        Handle continuation response after tool execution.
        
        Args:
            return_control: The returnControl event data
            session_id: Session ID
            thread_id: Thread ID
            seen_file_hashes: Set of already seen file hashes
            attachments: Optional attachments
            
        Yields:
            Response chunks
            
        Returns:
            Dictionary with accumulated content and new session state
        """
        tool_results = self._handle_return_control(return_control)
        full_content = ""
        new_session_state = None
        
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
                        text = self._handle_chunk_event(cont_event['chunk'])
                        if text:
                            yield text
                            full_content += text
                    elif 'files' in cont_event:
                        # Note: File handling in continuation is handled by the caller
                        # We just pass the event through
                        yield {'files_event': cont_event}
                    elif 'sessionState' in cont_event:
                        new_session_state = cont_event['sessionState']
        
        return {'full_content': full_content, 'session_state': new_session_state}


class BedrockAgentProvider(AgentProvider):
    """Bedrock implementation of the AgentProvider interface"""
    
    def __init__(self, bedrock_client: boto3.client, bedrock_agent_client: boto3.client, metadata: BedrockMetadata):
        self.bedrock_client = bedrock_client
        self.bedrock_agent_client = bedrock_agent_client
        self.metadata = metadata
        LOGGER.info("Initialized BedrockAgentProvider")
    
    def select_material_icon(self, name: str, description: str, instructions: str = None) -> str:
        """
        Select a Material Icon and color for an agent using Bedrock Converse API.
        
        Args:
            name: Agent name
            description: Agent description  
            instructions: Agent instructions (optional)
            
        Returns:
            JSON string with icon name and color
        """
        try:
            # Get the provider instance to access Bedrock runtime client
            provider: BedrockProvider = Config.config().get_provider()
            runtime_client = provider.bedrock_runtime_client
            
            # Read the material icons metadata
            import csv
            icons_data = []
            icons_file_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'assets', 'material_icons_metadata.csv')
            with open(icons_file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    icons_data.append(row)
            
            # Convert icons data to a compact format for the prompt
            icons_list = []
            for icon in icons_data:
                icon_str = f"{icon['name']}|{icon['category']}|{icon['tag1']},{icon['tag2']},{icon['tag3']}"
                icons_list.append(icon_str)
            
            # Special case for Home agent
            if name.lower() == "home":
                return json.dumps({
                    "icon_name": "home",
                    "color": "#4CAF50"  # Material Green
                })
            
            # Build the prompt for icon and color selection
            prompt_parts = [
                f"Select the most appropriate Material Icon and background color for an AI agent with the following characteristics:",
                f"Name: {name}",
                f"Description: {description}"
            ]
            
            # If instructions are provided, add them
            if instructions:
                prompt_parts.append(f"Purpose: {instructions}")
            
            prompt = "\n".join(prompt_parts)
            prompt += "\n\nSelect the icon that best represents this agent's name and purpose, and choose a distinctive color that fits the agent's theme."
            
            # System prompt for structured output
            system_prompt = f"""You are an expert at selecting appropriate icons and colors from Google's Material Icons library.

The Material Icons dataset contains {len(icons_data)} icons. Each icon is formatted as:
icon_name|category|tag1,tag2,tag3

Your task is to:
1. Select the SINGLE MOST APPROPRIATE icon based on the agent's name and description
2. Choose a distinctive background color that fits the agent's theme

Your response should be a JSON object with the following structure:
{{
    "icon_name": "the_icon_name",
    "color": "#HEXCODE",
    "reasoning": "Brief explanation of choices"
}}

ICON GUIDELINES:
1. For a "Pirate Agent", look for icons that exist in the list:
   - Good existing icons: "dangerous", "warning", "flag", "outlined_flag", "report_problem"
2. For a "Cowboy Agent", look for icons that can represent western themes:
   - Good existing icons: "label" (badge), "circle_notifications" (sheriff badge style)
3. For a "Data Agent", look for icons that exist in the list with data/analytics themes:
   - Good existing icons: "query_builder", "table_view", "storage"
4. For a "Analytics Agent", look for icons that represent analytics:
   - Good existing icons: "analytics", "bar_chart", "pie_chart"
4. Always prefer icons that directly represent the agent's name over abstract concepts
5. The icon should be instantly recognizable as representing the agent
6. CRITICAL: Only use icon names that EXACTLY match entries in the provided list - never invent icon names

COLOR GUIDELINES:
1. Use distinctive colors that match the agent's theme:
   - Pirate: Deep red (#B71C1C), dark purple (#4A148C), or black (#212121)
   - Cowboy: Saddle brown (#8B4513), rust (#D84315), or tan (#D2691E)
   - Data/Analytics: Blue (#1976D2), teal (#00796B), or indigo (#303F9F)
   - Science/Tech: Purple (#7B1FA2), deep blue (#1565C0), or cyan (#00ACC1)
2. IMPORTANT: Vary the shade based on the specific agent name and description:
   - Use the agent's full name to determine lightness/darkness within the color family
   - For example, "Data Agent" might use standard blue (#1976D2), while "Data Fetcher" should use a lighter (#42A5F5) or darker (#0D47A1) shade
   - Consider the description: "Database" themes might be darker, "Analytics" themes lighter
   - Even agents with similar purposes should have distinguishable shades
3. Use colors with good contrast against white backgrounds
4. Prefer material design colors but vary the shade (use 300-900 variants)
5. The exact shade should be deterministic based on the name - the same name should always get the same color

COMPLETE ICON LIST:
{chr(10).join(icons_list)}

Remember: Return ONLY the icon name that exists in the above list, and a valid hex color code."""
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
            
            # Use the model from environment or default
            model_id = os.getenv('BEDROCK_DEFAULT_MODEL', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0')
            
            # Call the converse API
            response = runtime_client.converse(
                modelId=model_id,
                messages=messages,
                system=[{"text": system_prompt}],
                inferenceConfig={
                    "maxTokens": 512,
                    "temperature": 0.3  # Lower temperature for more consistent selection
                }
            )
            
            # Extract the response
            response_text = response['output']['message']['content'][0]['text']
            
            # Log the raw response for debugging
            LOGGER.debug(f"Raw response from LLM for agent '{name}': {response_text}")
            
            # Try to parse as JSON - look for the first complete JSON object
            import re
            # More robust regex to find JSON object with icon_name
            json_match = re.search(r'\{[^}]*"icon_name"[^}]*\}', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                try:
                    result = json.loads(json_text)
                    icon_name = result.get('icon_name', '')
                    color = result.get('color', '#757575')  # Default grey
                    if icon_name:
                        LOGGER.info(f"Selected Material Icon '{icon_name}' with color '{color}' for agent '{name}': {result.get('reasoning', 'No reasoning provided')}")
                        return json.dumps({
                            "icon_name": icon_name,
                            "color": color
                        })
                except json.JSONDecodeError as e:
                    LOGGER.error(f"Failed to parse JSON for agent '{name}': {e}")
                    LOGGER.error(f"JSON text was: {json_text}")
            
            LOGGER.warning(f"Could not extract icon name from response for agent '{name}'")
            return json.dumps({
                "icon_name": "smart_toy",
                "color": "#757575"  # Default grey
            })
            
        except Exception as e:
            LOGGER.error(f"Error selecting Material Icon for agent '{name}': {e}")
            return json.dumps({
                "icon_name": "smart_toy",
                "color": "#757575"  # Default grey
            })
    
    @override
    def get_agent(self, agent_id: str) -> Agent:
        """
        Get an agent by ID.

        SECURITY NOTE: This creates a NEW BedrockAgent instance for each call.
        This is intentional to ensure agent instances are NOT shared between requests,
        preventing auth context leakage when using instance variables (see stream_response).
        DO NOT add caching here without refactoring auth storage to use contextvars.
        """
        session = self.metadata.get_db_session()
        try:
            agent_record = session.query(AgentRecord).filter_by(agent_id=agent_id).first()
            if not agent_record:
                raise ValueError(f"Agent {agent_id} not found in metadata")
            bedrock_options = session.query(BedrockAgentOptions).filter_by(agent_id=agent_id).first()
            if not bedrock_options:
                raise ValueError(f"Bedrock options for agent {agent_id} not found in metadata")
            return BedrockAgent(  # Creates NEW instance - not cached
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
                
                # Create the parent AgentRecord first to satisfy foreign key constraint
                agent_record = session.query(AgentRecord).filter_by(agent_id=agent_id).first()
                if not agent_record:
                    agent_record = AgentRecord(
                        agent_id=agent_id,
                        name=agent_def.name,
                        introduction=agent_def.introduction or "",
                        reminder=agent_def.reminder or "",
                        owner_user_id=owner_user_id
                    )
                    session.add(agent_record)
                    session.flush()  # Flush to ensure the record exists before creating child records
                    LOGGER.info(f"Created AgentRecord for {agent_id}")
                
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
                # Select the Material icon if not provided
                LOGGER.debug(f"Creating new agent '{agent_def.name}' - selecting material icon")
                icon_data = self.select_material_icon(
                    name=agent_def.name,
                    description=agent_def.description or "",
                    instructions=agent_def.instructions or ""
                )
                bedrock_options.agent_metadata['icon_svg'] = icon_data
                # Mark the field as modified to ensure SQLAlchemy detects the change
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(bedrock_options, 'agent_metadata')
                LOGGER.info(f"Selected icon data '{icon_data}' for new agent '{agent_def.name}'")
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
                    
                    # Preserve existing icon_svg when updating metadata
                    existing_icon_svg = bedrock_options.agent_metadata.get('icon_svg') if bedrock_options.agent_metadata else None
                    bedrock_options.agent_metadata = agent_def.metadata or {}
                    if existing_icon_svg and 'icon_svg' not in bedrock_options.agent_metadata:
                        bedrock_options.agent_metadata['icon_svg'] = existing_icon_svg
                        # Mark the field as modified to ensure SQLAlchemy detects the change
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(bedrock_options, 'agent_metadata')
                else: 
                    raise ValueError(f"Bedrock options for agent {agent_id} not found in database")
                
                # Update the AgentRecord if it exists (it should exist from create_or_update_agent)
                existing_agent_record = session.query(AgentRecord).filter_by(agent_id=agent_id).first()
                if existing_agent_record:
                    # Update the AgentRecord fields
                    existing_agent_record.name = agent_def.name
                    existing_agent_record.introduction = agent_def.introduction or ""
                    existing_agent_record.reminder = agent_def.reminder or ""
                    existing_agent_record.owner_user_id = owner_user_id
                    session.flush()
                    LOGGER.info(f"Updated AgentRecord for {agent_id}")
                else:
                    # If somehow the AgentRecord doesn't exist, create it
                    LOGGER.warning(f"AgentRecord not found for {agent_id}, creating it now")
                    agent_record = AgentRecord(
                        agent_id=agent_id,
                        name=agent_def.name,
                        introduction=agent_def.introduction or "",
                        reminder=agent_def.reminder or "",
                        owner_user_id=owner_user_id
                    )
                    session.add(agent_record)
                    session.flush()
                # Get current Bedrock agent to check description
                current_bedrock_agent = self.bedrock_agent_client.get_agent(agentId=bedrock_agent_id)
                current_description = current_bedrock_agent['agent'].get('description', '') if 'agent' in current_bedrock_agent else ''
                
                LOGGER.debug(f"Checking if icon update needed for agent '{agent_def.name}':")
                LOGGER.debug(f"  - Current name: '{existing_agent_record.name if existing_agent_record else 'N/A'}'")
                LOGGER.debug(f"  - New name: '{agent_def.name}'")
                LOGGER.debug(f"  - Current description: '{current_description}'")
                LOGGER.debug(f"  - New description: '{agent_def.description or ''}'")
                
                if (existing_agent_record and 
                    (existing_agent_record.name != agent_def.name or 
                     current_description != (agent_def.description or ''))):
                    LOGGER.debug(f"Icon update triggered - name or description changed")
                    icon_data = self.select_material_icon(
                        name=agent_def.name,
                        description=agent_def.description or "",
                        instructions=agent_def.instructions or ""
                    )
                    bedrock_options.agent_metadata['icon_svg'] = icon_data
                    # Mark the field as modified to ensure SQLAlchemy detects the change
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(bedrock_options, 'agent_metadata')
                    LOGGER.info(f"Updated icon data for agent '{agent_def.name}' to '{icon_data}'")
                else:
                    LOGGER.debug(f"No icon update needed - name and description unchanged")
                    current_icon = bedrock_options.agent_metadata.get('icon_svg', 'none')
                    LOGGER.debug(f"Current icon for agent '{agent_def.name}': '{current_icon}'")
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
                # Always use cross-region inference models with us. prefix
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
    
