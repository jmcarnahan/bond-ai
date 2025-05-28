import logging
LOGGER = logging.getLogger(__name__)

from typing import List, Dict, Optional
from bondable.bond.config import Config
from bondable.bond.metadata import Metadata
from types import MethodType
import json
import hashlib

class AgentDefinition:
    id: Optional[str] = None 
    name: str
    description: str
    instructions: str
    model: str
    tools: List = []
    tool_resources: Dict = {}
    metadata: Dict = {}

    def __init__(self, name: str, description: str, instructions: str, 
                 tools: List = [], tool_resources: Dict = {}, metadata: Dict = {},
                 id: Optional[str] = None): 
        self.id = id
        self.name = name
        self.description = description
        self.instructions = instructions
        self.model = Config.config().get_openai_deployment()
        self.metadata = metadata

        self.bond_metadata = Metadata.metadata()
        # builder = AgentBuilder.builder() # No longer needed within __init__ for file processing

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
                    file_id = self.bond_metadata.get_file_id(file_tuple=file_tuple)
                    if file_id not in file_ids:
                        file_ids.append(file_id)
            self.tool_resources["code_interpreter"] = {
                "file_ids": list(set(file_ids))
            }
        else:
             # Ensure the structure exists even if no resources were provided
            self.tool_resources["code_interpreter"] = {"file_ids": []}

        if "file_search" in self.tool_resources and self.tool_resources["file_search"] is not None:
            vector_store_ids = []
            if "vector_store_ids" in self.tool_resources["file_search"] and self.tool_resources["file_search"]["vector_store_ids"] is not None:
                vector_store_ids = self.tool_resources["file_search"]["vector_store_ids"]
            if "files" in self.tool_resources["file_search"]:
                default_vector_store_name = f"{self.name}_file_search_vs"
                default_vector_store_id = self.bond_metadata.get_vector_store_id(
                    name=default_vector_store_name, file_tuples=self.tool_resources["file_search"]["files"])
                if default_vector_store_id not in vector_store_ids:
                    vector_store_ids.append(default_vector_store_id)
            self.tool_resources["file_search"] = {
                "vector_store_ids": list(set(vector_store_ids))
            }
        else:
            # Ensure the structure exists even if no resources were provided
            self.tool_resources["file_search"] = {"vector_store_ids": []}

        LOGGER.debug(f"Agent[{self.name}] Tool Resources: {json.dumps(self.tool_resources, sort_keys=True, indent=4)}")




    @classmethod
    def to_dict(cls, obj):
      LOGGER.debug(f"Before conversion to dict: {obj}")
      if hasattr(obj, "__dict__"):
          obj = obj.__dict__
          for key, value in obj.items():
              obj[key] = cls.to_dict(value)
      LOGGER.debug(f"After conversion to dict: {obj}")
      return obj

    @classmethod
    def from_assistant(cls, assistant_id: str):
        """Create an AgentDefinition from an OpenAI Assistant ID."""
        openai_client = Config.config().get_openai_client()
        assistant = openai_client.beta.assistants.retrieve(assistant_id)
        agent_def = cls(
            name=assistant.name,
            description=assistant.description,
            instructions=assistant.instructions,
            tools=assistant.tools,
            tool_resources=assistant.tool_resources,
            metadata=assistant.metadata,
            id=assistant.id
        )
        agent_def.model = assistant.model
        return agent_def

    def __dict__(self):
        return {
            "id": self.id, # Added id
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "model": self.model,
            "tools": self.tools,
            "tool_resources": self.tool_resources,
            "metadata": self.metadata
        }
    
    def __str__(self):
        return json.dumps(self.__dict__(), sort_keys=True, indent=4)

    def get_hash(self):
        # The hash should represent the configuration, not the ID.
        # So, self.id is intentionally excluded from the hash.
        return hash(
            (self.name, self.description, self.instructions, self.model, 
                json.dumps(self.metadata, sort_keys=True), 
                json.dumps(self.tools, sort_keys=True),
                json.dumps(self.tool_resources, sort_keys=True))
        )
