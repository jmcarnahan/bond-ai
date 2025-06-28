"""
BedrockMetadata - Extended metadata storage for AWS Bedrock provider

This module extends the base Metadata class to add message storage capabilities
since Bedrock doesn't have built-in thread/conversation management.
"""

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Integer, Index, Float
from sqlalchemy.orm import relationship
from bondable.bond.providers.metadata import Metadata, Base, Thread, AgentRecord, FileRecord, VectorStore
import datetime
import uuid
import logging
from typing import List, Dict, Optional, Any, Tuple

LOGGER = logging.getLogger(__name__)
DEFAULT_TEMPERATURE = 0.0  # Default temperature for Bedrock agents

# Extend the Thread model with Bedrock-specific fields
# These fields support native Bedrock Agent session management
Thread.session_id = Column(String, nullable=True)  # Bedrock Agent session ID
Thread.session_state = Column(JSON, default=dict)  # Bedrock Agent session state

# # Extend the AgentRecord model with Bedrock-specific fields
# # These fields map Bond agents to AWS Bedrock Agents
# AgentRecord.bedrock_agent_id = Column(String, nullable=True)  # AWS Bedrock Agent ID
# AgentRecord.bedrock_agent_alias_id = Column(String, nullable=True)  # AWS Bedrock Agent Alias ID
# # AgentRecord.model_id = Column(String, nullable=True)  # Model ID used by agent
# # AgentRecord.system_prompt = Column(String, nullable=True)  # System prompt/instructions
# AgentRecord.temperature = Column(String, nullable=True)  # Temperature setting (stored as string for flexibility)
# # AgentRecord.max_tokens = Column(Integer, nullable=True)  # Max tokens setting
# AgentRecord.tools = Column(JSON, nullable=True)  # Tool configurations
# AgentRecord.tool_resources = Column(JSON, nullable=True) 
# AgentRecord.mcp_tools = Column(JSON, nullable=True)  # MCP tools list
# AgentRecord.mcp_resources = Column(JSON, nullable=True)  # MCP resources list

class BedrockAgentOptions(Base):
    """Store Bedrock Agent options for each agent"""
    __tablename__ = 'bedrock_agent_options'
    
    agent_id = Column(String, ForeignKey('agents.agent_id'), primary_key=True)
    """Foreign key to AgentRecord"""

    bedrock_agent_id = Column(String, nullable=False)  # AWS Bedrock Agent ID
    bedrock_agent_alias_id = Column(String, nullable=False)  # AWS Bedrock Agent Alias ID
    temperature = Column(Float, nullable=False, default=DEFAULT_TEMPERATURE)  
    tools = Column(JSON, nullable=False, default=dict)  # Tool configurations
    tool_resources = Column(JSON, nullable=False, default=dict)  # Tool resources configuration
    mcp_tools = Column(JSON, nullable=False, default=dict)  # MCP tools list
    mcp_resources = Column(JSON, nullable=False, default=dict)  # MCP resources list
    agent_metadata = Column(JSON, nullable=True, default=dict)  # Additional metadata for the agent
    
    __table_args__ = (
        Index('idx_bedrock_agent_id', 'bedrock_agent_id'),
    )


class BedrockMessage(Base):
    """Store conversation messages for Bedrock threads"""
    __tablename__ = 'bedrock_messages'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    session_id = Column(String, nullable=True)  # Bedrock Agent session ID
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    type = Column(String, nullable=False)  # 'text', 'image_file', etc.
    content = Column(JSON, nullable=False)  # Store full message content including attachments
    message_index = Column(Integer, nullable=False)  # Order within thread
    created_at = Column(DateTime, default=datetime.datetime.now)
    message_metadata = Column(JSON, default=dict)  # Additional metadata (tokens, model, etc.)
    
    # Create composite index for efficient queries
    __table_args__ = (
        Index('idx_thread_user_index', 'thread_id', 'user_id', 'message_index'),
        Index('idx_thread_created', 'thread_id', 'created_at'),
        Index('idx_session_id', 'session_id'),  # Index for session-based queries
    )


# Extend the FileRecord model with Bedrock-specific fields
FileRecord.s3_bucket = Column(String, nullable=True)  # S3 bucket name
FileRecord.s3_key = Column(String, nullable=True)  # S3 object key
FileRecord.presigned_url_expires_at = Column(DateTime, nullable=True)  # Presigned URL expiration

# Extend the VectorStore model with Bedrock Knowledge Base fields
VectorStore.knowledge_base_id = Column(String, nullable=True, unique=True)  # AWS Knowledge Base ID
VectorStore.embedding_model_arn = Column(String, nullable=True)  # Embedding model ARN
VectorStore.storage_configuration = Column(JSON, nullable=True)  # Storage backend config


class BedrockMetadata(Metadata):
    """Extended metadata for Bedrock provider with message storage"""
    
    def __init__(self, metadata_db_url: str):
        super().__init__(metadata_db_url)
        LOGGER.info("Initialized BedrockMetadata with message storage")
    
    def create_all(self):
        """Create all tables including Bedrock-specific ones"""
        Base.metadata.create_all(self.engine)
        LOGGER.info("Created all Bedrock metadata tables")
    
    # Message Management Methods
    def create_message(self, thread_id: str, user_id: str, role: str, message_type: str, 
                      content: List[Dict], metadata: Optional[Dict] = None,
                      session_id: Optional[str] = None, message_id: Optional[str] = None) -> str:
        """Create a new message in a thread"""
        session = self.get_db_session()
        try:
            # Get the session_id from thread if not provided
            if not session_id:
                thread = session.query(Thread)\
                    .filter_by(thread_id=thread_id, user_id=user_id)\
                    .first()
                if thread:
                    session_id = thread.session_id
            
            # Get the next message index for this thread
            max_index = session.query(BedrockMessage.message_index)\
                .filter_by(thread_id=thread_id, user_id=user_id)\
                .order_by(BedrockMessage.message_index.desc())\
                .first()
            
            message_index = (max_index[0] + 1) if max_index else 0
            
            message = BedrockMessage(
                id=message_id or str(uuid.uuid4()),
                thread_id=thread_id,
                user_id=user_id,
                session_id=session_id,
                role=role,
                type=message_type,
                content=content,
                message_index=message_index,
                message_metadata=metadata or {}
            )
            
            session.add(message)
            session.commit()
            
            LOGGER.info(f"Created message {message.id} in thread {thread_id} with session {session_id} - message index {message_index}")
            return message.id
            
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error creating message: {e}")
            raise
        finally:
            session.close()
    
    def get_messages(self, thread_id: str, user_id: str, 
                    limit: Optional[int] = None, 
                    after_index: Optional[int] = None) -> List[BedrockMessage]:
        """Get messages from a thread"""
        session = self.get_db_session()
        try:
            query = session.query(BedrockMessage)\
                .filter_by(thread_id=thread_id, user_id=user_id)\
                .order_by(BedrockMessage.message_index)
            
            if after_index is not None:
                query = query.filter(BedrockMessage.message_index > after_index)
            
            if limit:
                query = query.limit(limit)
            
            messages = query.all()
            
            # Detach all messages from session
            for msg in messages:
                session.expunge(msg)
            
            return messages
            
        finally:
            session.close()
    
    # def get_conversation_messages(self, thread_id: str, user_id: str) -> List[Dict]:
    #     """Get messages formatted for Bedrock Converse API"""
    #     messages = self.get_messages(thread_id, user_id)
        
    #     # Convert to Bedrock format
    #     bedrock_messages = []
    #     for msg in messages:
    #         bedrock_messages.append({
    #             'role': msg.role,
    #             'content': msg.content
    #         })
        
    #     return bedrock_messages
    
    def delete_thread_messages(self, thread_id: str, user_id: str) -> int:
        """Delete all messages in a thread"""
        session = self.get_db_session()
        try:
            count = session.query(BedrockMessage)\
                .filter_by(thread_id=thread_id, user_id=user_id)\
                .delete()
            session.commit()
            LOGGER.info(f"Deleted {count} messages from thread {thread_id}")
            return count
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error deleting messages: {e}")
            raise
        finally:
            session.close()
    
    def has_new_messages(self, thread_id: str, user_id: str, 
                        last_message_id: Optional[str]) -> bool:
        """Check if there are new messages after a given message ID"""
        if not last_message_id:
            # If no last message ID, check if thread has any messages
            session = self.get_db_session()
            try:
                count = session.query(BedrockMessage)\
                    .filter_by(thread_id=thread_id, user_id=user_id)\
                    .count()
                return count > 0
            finally:
                session.close()
        
        session = self.get_db_session()
        try:
            # Get the index of the last message
            last_msg = session.query(BedrockMessage)\
                .filter_by(id=last_message_id, thread_id=thread_id, user_id=user_id)\
                .first()
            
            if not last_msg:
                # Last message not found, assume there are new messages
                return True
            
            # Check if there are messages with higher index
            count = session.query(BedrockMessage)\
                .filter_by(thread_id=thread_id, user_id=user_id)\
                .filter(BedrockMessage.message_index > last_msg.message_index)\
                .count()
            
            return count > 0
            
        finally:
            session.close()
    
    # # Agent Management Methods
    
    # def create_or_update_bedrock_agent(self, agent_id: str, model_id: str,
    #                                   system_prompt: Optional[str] = None,
    #                                   temperature: Optional[float] = None,
    #                                   max_tokens: Optional[int] = None,
    #                                   tools: Optional[List[Dict]] = None,
    #                                   tool_resources: Optional[Dict] = None,
    #                                   guardrail_config: Optional[Dict] = None,
    #                                   bedrock_agent_id: Optional[str] = None,
    #                                   bedrock_agent_alias_id: Optional[str] = None,
    #                                   mcp_tools: Optional[List[str]] = None,
    #                                   mcp_resources: Optional[List[str]] = None) -> None:
    #     """Update Bedrock-specific fields on an existing agent"""
    #     LOGGER.info(f"[BedrockMetadata] create_or_update_bedrock_agent called with:")
    #     LOGGER.info(f"  - agent_id: {agent_id}")
    #     LOGGER.info(f"  - mcp_tools: {mcp_tools}")
    #     LOGGER.info(f"  - mcp_resources: {mcp_resources}")
        
    #     session = self.get_db_session()
    #     try:
    #         agent: AgentRecord = session.query(AgentRecord).filter_by(agent_id=agent_id).first()
            
    #         if not agent:
    #             raise ValueError(f"Agent {agent_id} not found")
            
    #         # Update Bedrock-specific fields
    #         agent.model_id = model_id
    #         if system_prompt is not None:
    #             agent.system_prompt = system_prompt
    #         if temperature is not None:
    #             agent.temperature = str(temperature)
    #         if max_tokens is not None:
    #             agent.max_tokens = max_tokens
    #         if tools is not None:
    #             agent.tools = tools
    #         if tool_resources is not None:
    #             agent.tool_resources = tool_resources
    #         if guardrail_config is not None:
    #             agent.guardrail_config = guardrail_config
    #         if bedrock_agent_id is not None:
    #             agent.bedrock_agent_id = bedrock_agent_id
    #         if bedrock_agent_alias_id is not None:
    #             agent.bedrock_agent_alias_id = bedrock_agent_alias_id
    #         if mcp_tools is not None:
    #             agent.mcp_tools = mcp_tools
    #             LOGGER.info(f"  - Set agent.mcp_tools to: {agent.mcp_tools}")
    #         if mcp_resources is not None:
    #             agent.mcp_resources = mcp_resources
    #             LOGGER.info(f"  - Set agent.mcp_resources to: {agent.mcp_resources}")
            
    #         session.commit()
    #         LOGGER.info(f"Updated Bedrock configuration for agent {agent_id}")
    #         LOGGER.info(f"  - Final agent.mcp_tools: {agent.mcp_tools}")
    #         LOGGER.info(f"  - Final agent.mcp_resources: {agent.mcp_resources}")
            
    #     except Exception as e:
    #         session.rollback()
    #         LOGGER.error(f"Error updating Bedrock agent: {e}")
    #         raise
    #     finally:
    #         session.close()
    
    # def get_bedrock_agent(self, agent_id: str) -> Optional[AgentRecord]:
    #     """Get agent record with Bedrock-specific fields"""
    #     session = self.get_db_session()
    #     try:
    #         agent = session.query(AgentRecord).filter_by(agent_id=agent_id).first()
    #         if not agent:
    #             return None
            
    #         # Detach from session so it can be used outside
    #         session.expunge(agent)
    #         return agent
    #     finally:
    #         session.close()
    
    # Knowledge Base Management Methods
    
    # def create_knowledge_base_mapping(self, vector_store_id: str, 
    #                                 knowledge_base_id: str,
    #                                 embedding_model_arn: Optional[str] = None,
    #                                 storage_configuration: Optional[Dict] = None) -> None:
    #     """Update vector store with Bedrock knowledge base information"""
    #     session = self.get_db_session()
    #     try:
    #         vector_store = session.query(VectorStore).filter_by(vector_store_id=vector_store_id).first()
    #         if not vector_store:
    #             raise ValueError(f"Vector store {vector_store_id} not found")
            
    #         vector_store.knowledge_base_id = knowledge_base_id
    #         vector_store.embedding_model_arn = embedding_model_arn
    #         vector_store.storage_configuration = storage_configuration
            
    #         session.commit()
    #         LOGGER.info(f"Updated vector store {vector_store_id} with knowledge base {knowledge_base_id}")
    #     except Exception as e:
    #         session.rollback()
    #         LOGGER.error(f"Error updating knowledge base mapping: {e}")
    #         raise
    #     finally:
    #         session.close()
    
    # def get_knowledge_base_id(self, vector_store_id: str) -> Optional[str]:
    #     """Get the Knowledge Base ID for a vector store"""
    #     session = self.get_db_session()
    #     try:
    #         vector_store = session.query(VectorStore).filter_by(vector_store_id=vector_store_id).first()
    #         return vector_store.knowledge_base_id if vector_store and hasattr(vector_store, 'knowledge_base_id') else None
    #     finally:
    #         session.close()
    
    # File Management Methods
    
    def create_file_mapping(self, file_id: str, s3_bucket: str, s3_key: str,
                          presigned_url_expires_at: Optional[datetime.datetime] = None) -> None:
        """Update file record with S3 location"""
        session = self.get_db_session()
        try:
            file_record = session.query(FileRecord).filter_by(file_id=file_id).first()
            if not file_record:
                raise ValueError(f"File {file_id} not found")
            
            file_record.s3_bucket = s3_bucket
            file_record.s3_key = s3_key
            file_record.presigned_url_expires_at = presigned_url_expires_at
            
            session.commit()
            LOGGER.info(f"Updated file {file_id} with S3 location s3://{s3_bucket}/{s3_key}")
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error updating file mapping: {e}")
            raise
        finally:
            session.close()
    
    def get_file_s3_location(self, file_id: str) -> Optional[Dict]:
        """Get the S3 location for a file"""
        session = self.get_db_session()
        try:
            file_record = session.query(FileRecord).filter_by(file_id=file_id).first()
            if not file_record or not hasattr(file_record, 's3_bucket'):
                return None
            
            return {
                's3_bucket': file_record.s3_bucket,
                's3_key': file_record.s3_key,
                'presigned_url_expires_at': getattr(file_record, 'presigned_url_expires_at', None)
            }
        finally:
            session.close()