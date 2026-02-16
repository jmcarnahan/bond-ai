import logging
LOGGER = logging.getLogger(__name__)

from typing import List, Dict, Optional
from bondable.bond.config import Config
from types import MethodType
import json
import hashlib

class AgentDefinition:
    id: Optional[str] = None
    name: str
    description: str
    instructions: str
    introduction: str
    reminder: str
    model: str
    tools: List = []
    tool_resources: Dict = {}
    metadata: Dict = {}
    user_id: str = None
    mcp_tools: List[str] = []  # List of MCP tool identifiers
    mcp_resources: List[str] = []  # List of MCP resource identifiers
    temperature: float = 0.0
    top_p: float = 0.5
    file_storage: str = 'direct'  # 'direct' | 'knowledge_base'

    def __init__(self, user_id: str, name: str, description: str, instructions: str, model: str,
                 tools: List = [], tool_resources: Dict = {}, metadata: Dict = {},
                 id: Optional[str] = None, introduction: str = "", reminder: str = "",
                 mcp_tools: List[str] = [], mcp_resources: List[str] = [],
                 temperature: float = 0.0, top_p: float = 0.5,
                 file_storage: str = 'direct'):
        self.id = id
        self.name = name
        self.description = description
        self.instructions = instructions
        self.introduction = introduction
        self.reminder = reminder
        self.model = model
        self.metadata = metadata
        self.user_id = user_id
        self.mcp_tools = mcp_tools or []
        self.mcp_resources = mcp_resources or []
        self.config = Config.config()
        self.provider = self.config.get_provider()
        self.temperature = temperature
        self.top_p = top_p
        self.file_storage = file_storage

        if user_id is None:
            raise ValueError("User ID must be provided for agent definition.")

        if name is None or name.strip() == "":
            raise ValueError("Agent name must be provided and cannot be empty.")

        # load the tools
        self.tools = []
        for i, tool in enumerate(tools):
            if isinstance(tool, MethodType) and hasattr(tool, "__bondtool__"):
                tool = tool.__bondtool__['schema']
            tool = self.to_dict(tool)
            if 'type' in tool and tool['type'] == 'file_search':
                tool.pop('file_search', None)
            LOGGER.debug(f"Agent[{self.name}] adding tool -> {tool}")
            self.tools.append(tool)
        LOGGER.debug(f"Agent[{self.name}] Tools: {json.dumps(self.tools, sort_keys=True, indent=4)}")

        self.tool_resources = self.to_dict(tool_resources) # Convert Pydantic models etc., if any
        LOGGER.debug(f"Agent[{self.name}] Initial Tool Resources: {json.dumps(self.tool_resources, sort_keys=True, indent=4)}")


        if "code_interpreter" in self.tool_resources and self.tool_resources["code_interpreter"] is not None:
            file_ids = []
            if "file_ids" in self.tool_resources["code_interpreter"] and self.tool_resources["code_interpreter"]["file_ids"] is not None:
                file_ids = self.tool_resources["code_interpreter"]["file_ids"]
            if "files" in self.tool_resources["code_interpreter"]:
                LOGGER.info(f"Processing files for code_interpreter: {self.tool_resources['code_interpreter']['files']}")
                for file_tuple in self.tool_resources["code_interpreter"]["files"]:
                    file_details = self.provider.files.get_or_create_file_id(user_id=user_id, file_tuple=file_tuple)
                    if file_details.file_id not in file_ids:
                        file_ids.append(file_details.file_id)
            self.tool_resources["code_interpreter"] = {
                "file_ids": list(set(file_ids))
            }
        else:
            # Only create default code_interpreter resources if code_interpreter is in tools list
            has_code_interpreter = any(
                isinstance(t, dict) and t.get('type') == 'code_interpreter'
                for t in self.tools
            )
            if has_code_interpreter:
                self.tool_resources["code_interpreter"] = {"file_ids": []}

        # Always create a default vector store for the agent
        default_vector_store_id = self.provider.vectorstores.get_or_create_default_vector_store_id(user_id=user_id, agent_id=self.id)
        vector_store_ids = [default_vector_store_id]

        if "file_search" in self.tool_resources and self.tool_resources["file_search"] is not None:
            # Process existing file_search resources
            if "vector_store_ids" in self.tool_resources["file_search"] and self.tool_resources["file_search"]["vector_store_ids"] is not None:
                vector_store_ids.extend(self.tool_resources["file_search"]["vector_store_ids"])

            if 'file_ids' in self.tool_resources["file_search"] and self.tool_resources["file_search"]["file_ids"] is not None:
                self.provider.vectorstores.update_vector_store_file_ids(vector_store_id=default_vector_store_id, file_ids=self.tool_resources["file_search"]["file_ids"])

            if "files" in self.tool_resources["file_search"]:
                file_ids = []
                for file_tuple in self.tool_resources["file_search"]["files"]:
                    file_details = self.provider.files.get_or_create_file_id(user_id=user_id, file_tuple=file_tuple)
                    if file_details.file_id not in file_ids:
                        file_ids.append(file_details.file_id)
                self.provider.vectorstores.update_vector_store_file_ids(vector_store_id=default_vector_store_id, file_ids=file_ids)

        # Always ensure file_search has the default vector store
        # Preserve file_ids for knowledge_base mode (they're needed for KB upload)
        preserved_file_ids = None
        if "file_search" in self.tool_resources and self.tool_resources["file_search"]:
            preserved_file_ids = self.tool_resources["file_search"].get("file_ids")

        self.tool_resources["file_search"] = {
            "vector_store_ids": list(set(vector_store_ids))
        }

        # Restore file_ids if they existed (needed for knowledge_base upload)
        if preserved_file_ids:
            self.tool_resources["file_search"]["file_ids"] = preserved_file_ids
            LOGGER.debug(f"Agent[{self.name}] Preserved file_ids for potential KB upload: {preserved_file_ids}")

        LOGGER.debug(f"Agent[{self.name}] Tool Resources: {json.dumps(self.tool_resources, sort_keys=True, indent=4)}")

    @classmethod
    def to_dict(cls, obj):
      # LOGGER.debug(f"Before conversion to dict: {obj}")
      if hasattr(obj, "__dict__"):
          obj = obj.__dict__
          for key, value in obj.items():
              obj[key] = cls.to_dict(value)
      # LOGGER.debug(f"After conversion to dict: {obj}")
      return obj

    def __dict__(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "introduction": self.introduction,
            "reminder": self.reminder,
            "model": self.model,
            "tools": self.tools,
            "tool_resources": self.tool_resources,
            "metadata": self.metadata,
            "mcp_tools": self.mcp_tools,
            "mcp_resources": self.mcp_resources,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "file_storage": self.file_storage,
        }

    def __str__(self):
        return json.dumps(self.__dict__(), sort_keys=True, indent=4)

    def get_hash(self):
        # The hash should represent the configuration, not the ID.
        # So, self.id is intentionally excluded from the hash.
        return hash(
            (self.name, self.description, self.instructions, self.introduction, self.reminder, self.model,
                json.dumps(self.metadata, sort_keys=True),
                json.dumps(self.tools, sort_keys=True),
                json.dumps(self.tool_resources, sort_keys=True),
                json.dumps(self.mcp_tools, sort_keys=True),
                json.dumps(self.mcp_resources, sort_keys=True),
                self.temperature, self.top_p, self.file_storage)
        )
