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
    
