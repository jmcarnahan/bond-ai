"""
BedrockStreaming - Streaming utilities for AWS Bedrock provider

This module handles the conversion between Bedrock's streaming format
and Bond's expected message streaming format.
"""

import logging
import queue
import threading
from typing import Generator, Optional, Dict, Any
from bondable.bond.broker import Broker

LOGGER = logging.getLogger(__name__)


class BedrockStreamHandler:
    """Handles streaming responses from Bedrock and converts to Bond format"""
    
    def __init__(self, thread_id: str, message_id: str, agent_id: str, role: str = "assistant"):
        self.thread_id = thread_id
        self.message_id = message_id
        self.agent_id = agent_id
        self.role = role
        self.broker = Broker.broker()
        self.message_index = 0
        self.is_first_chunk = True
        self.full_content = ""
        
        LOGGER.info(f"Initialized BedrockStreamHandler for thread {thread_id}, message {message_id}")
    
    def start_message(self, message_type: str = "text"):
        """Send the opening message tag"""
        opening_tag = (
            f'<_bondmessage '
            f'id="{self.message_id}" '
            f'thread_id="{self.thread_id}" '
            f'agent_id="{self.agent_id}" '
            f'type="{message_type}" '
            f'role="{self.role}" '
            f'message_index="{self.message_index}" '
            f'is_error="false" '
            f'is_done="false">'
        )
        self.broker.publish(self.thread_id, opening_tag)
        LOGGER.debug(f"Published opening tag for message {self.message_id}")
    
    def send_chunk(self, text: str):
        """Send a text chunk"""
        if self.is_first_chunk:
            self.start_message()
            self.is_first_chunk = False
        
        self.full_content += text
        self.broker.publish(self.thread_id, text)
    
    def end_message(self):
        """Send the closing message tag"""
        if self.is_first_chunk:
            # Never sent any content, send opening tag first
            self.start_message()
        
        closing_tag = '</_bondmessage>'
        self.broker.publish(self.thread_id, closing_tag)
        LOGGER.debug(f"Published closing tag for message {self.message_id}")
    
    def send_error(self, error_message: str):
        """Send an error message"""
        error_opening = (
            f'<_bondmessage '
            f'id="{self.message_id}_error" '
            f'thread_id="{self.thread_id}" '
            f'agent_id="{self.agent_id}" '
            f'type="error" '
            f'role="system" '
            f'is_error="true" '
            f'is_done="true">'
        )
        self.broker.publish(self.thread_id, error_opening)
        self.broker.publish(self.thread_id, f"Error: {error_message}")
        self.broker.publish(self.thread_id, '</_bondmessage>')
        LOGGER.error(f"Published error message: {error_message}")
    
    def send_done(self):
        """Send a completion message"""
        done_message = (
            f'<_bondmessage '
            f'id="{self.message_id}_done" '
            f'thread_id="{self.thread_id}" '
            f'agent_id="{self.agent_id}" '
            f'type="text" '
            f'role="system" '
            f'is_error="false" '
            f'is_done="true">'
        )
        self.broker.publish(self.thread_id, done_message)
        self.broker.publish(self.thread_id, "Done.")
        self.broker.publish(self.thread_id, '</_bondmessage>')
        LOGGER.debug("Published done message")
    
    def process_bedrock_stream(self, stream_response: Dict[str, Any]) -> str:
        """
        Process a Bedrock ConverseStream response and publish to broker.
        
        Args:
            stream_response: The response from bedrock_runtime.converse_stream()
            
        Returns:
            The complete response text
        """
        try:
            # Process the stream
            for event in stream_response.get("stream", []):
                if "messageStart" in event:
                    # Message has started
                    LOGGER.debug("Bedrock stream: message started")
                    # We'll start our message when we get the first content
                    
                elif "contentBlockStart" in event:
                    # Content block started - we might want to handle different types
                    LOGGER.debug("Bedrock stream: content block started")
                    
                elif "contentBlockDelta" in event:
                    # Actual content
                    delta = event["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        text_chunk = delta["text"]
                        self.send_chunk(text_chunk)
                        
                elif "contentBlockStop" in event:
                    # Content block ended
                    LOGGER.debug("Bedrock stream: content block stopped")
                    
                elif "messageStop" in event:
                    # Message complete
                    stop_reason = event["messageStop"].get("stopReason", "unknown")
                    LOGGER.debug(f"Bedrock stream: message stopped, reason: {stop_reason}")
                    
                elif "metadata" in event:
                    # Usage information
                    usage = event["metadata"].get("usage", {})
                    LOGGER.info(f"Token usage - Input: {usage.get('inputTokens', 0)}, "
                               f"Output: {usage.get('outputTokens', 0)}")
            
            # End the message
            self.end_message()
            
            # Send done indicator
            self.send_done()
            
            # Signal end of stream to broker
            self.broker.publish(self.thread_id, None)
            
            return self.full_content
            
        except Exception as e:
            LOGGER.error(f"Error processing Bedrock stream: {e}")
            self.send_error(str(e))
            self.broker.publish(self.thread_id, None)
            raise


class BedrockStreamProcessor:
    """Alternative stream processor that yields content instead of using broker"""
    
    def __init__(self, thread_id: str, message_id: str, agent_id: str, 
                 message_index: int = 0, role: str = "assistant"):
        self.thread_id = thread_id
        self.message_id = message_id
        self.agent_id = agent_id
        self.message_index = message_index
        self.role = role
        self.full_content = ""
        self.is_first_chunk = True
    
    def process_stream_to_generator(self, stream_response: Dict[str, Any]) -> Generator[str, None, None]:
        """
        Process a Bedrock ConverseStream response and yield Bond-formatted messages.
        
        Args:
            stream_response: The response from bedrock_runtime.converse_stream()
            
        Yields:
            Bond-formatted message chunks
        """
        try:
            # Yield opening tag
            opening_tag = (
                f'<_bondmessage '
                f'id="{self.message_id}" '
                f'thread_id="{self.thread_id}" '
                f'agent_id="{self.agent_id}" '
                f'type="text" '
                f'role="{self.role}" '
                f'message_index="{self.message_index}" '
                f'is_error="false" '
                f'is_done="false">'
            )
            yield opening_tag
            
            # Process the stream
            for event in stream_response.get("stream", []):
                if "contentBlockDelta" in event:
                    # Actual content
                    delta = event["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        text_chunk = delta["text"]
                        self.full_content += text_chunk
                        yield text_chunk
                        
                elif "metadata" in event:
                    # Log usage information
                    usage = event["metadata"].get("usage", {})
                    LOGGER.info(f"Token usage - Input: {usage.get('inputTokens', 0)}, "
                               f"Output: {usage.get('outputTokens', 0)}")
            
            # Yield closing tag
            yield '</_bondmessage>'
            
            # Yield done message
            done_message = (
                f'<_bondmessage '
                f'id="{self.message_id}_done" '
                f'thread_id="{self.thread_id}" '
                f'agent_id="{self.agent_id}" '
                f'type="text" '
                f'role="system" '
                f'is_error="false" '
                f'is_done="true">'
            )
            yield done_message
            yield "Done."
            yield '</_bondmessage>'
            
        except Exception as e:
            LOGGER.error(f"Error in stream generator: {e}")
            # Yield error message
            error_msg = (
                f'<_bondmessage '
                f'id="{self.message_id}_error" '
                f'thread_id="{self.thread_id}" '
                f'agent_id="{self.agent_id}" '
                f'type="error" '
                f'role="system" '
                f'is_error="true" '
                f'is_done="true">'
            )
            yield error_msg
            yield f"Error: {str(e)}"
            yield '</_bondmessage>'
            raise