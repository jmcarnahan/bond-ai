import logging
LOGGER = logging.getLogger(__name__)

import json
import datetime
import atexit
import types
import io
import time
from bondable.bond.config import Config
from bondable.bond.agent import Agent
from bondable.bond.broker import Broker, BrokerConnectionEmpty
from bondable.bond.cache import bond_cache
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, text, inspect, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import List, Dict, Any, Optional
from IPython.display import Image, display
from pydantic import BaseModel, Field
import threading
import base64
import hashlib



Base = declarative_base()
class AgentRecord(Base):
    __tablename__ = "agents"
    name = Column(String, primary_key=True)
    assistant_id = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
class ThreadRecord(Base):
    __tablename__ = "threads"
    thread_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
class FileRecord(Base):
    __tablename__ = "files"
    path = Column(String, primary_key=True)
    file_hash = Column(String, nullable=False)
    file_id = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)
class VectorStore(Base):
    __tablename__ = "vector_stores"
    name = Column(String, primary_key=True)
    vector_store_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)


class AgentDefinition:
    name: str
    description: str
    instructions: str
    model: str
    tools: List = []
    tool_resources: Dict = {}
    metadata: Dict = {}

    def __init__(self, name: str, description: str, instructions: str, 
                 tools: List = [], tool_resources: Dict = {}, metadata: Dict = {}):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.model = Config.config().get_openai_deployment()
        self.metadata = metadata
        builder = AgentBuilder.builder()

        # load the tools
        self.tools = []
        for i, tool in enumerate(tools):
            if isinstance(tool, types.MethodType) and hasattr(tool, "__bondtool__"):
                tool = tool.__bondtool__['schema']
            tool = self.to_dict(tool)
            if 'type' in tool and tool['type'] == 'file_search':
                tool.pop('file_search', None)
            LOGGER.debug(f"Creating Agent Definition with tool -> {tool}")
            self.tools.append(tool)
        LOGGER.debug(f"Tools: {json.dumps(self.tools, sort_keys=True, indent=4)}")

        # load the tool resources
        self.tool_resources = {}
        for tool_name, tool_resource in self.to_dict(tool_resources).items():
            if tool_resource is None:
                continue
            if tool_name == "code_interpreter":
                self.tool_resources[tool_name] = {
                    "file_ids": tool_resource['file_ids'] if 'file_ids' in tool_resource else []
                }
                if 'files' in tool_resource:
                    for file_path in tool_resource['files']:
                        file_id = builder.get_file_id(file_path)
                        self.tool_resources[tool_name]['file_ids'].append(file_id)
            elif tool_name == "file_search":
                self.tool_resources[tool_name] = {
                    "vector_store_ids": tool_resource['vector_store_ids'] if 'vector_store_ids' in tool_resource else []
                }
                if 'files' in tool_resource:
                    vector_store_id = builder.get_vector_store(name=f"{name}_{tool_name}", files=tool_resource['files'])
                    self.tool_resources[tool_name]['vector_store_ids'].append(vector_store_id)
            else:
                LOGGER.error(f"Unknown tool name: {tool_name}")
        
        # normalize things
        if 'code_interpreter' not in self.tool_resources:
            self.tool_resources['code_interpreter'] = {"file_ids": []}
        if 'file_search' not in self.tool_resources:
            self.tool_resources['file_search'] = {"vector_store_ids": []}

        LOGGER.debug(f"Tool Resources: {json.dumps(self.tool_resources, sort_keys=True, indent=4)}")

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
    def from_assistant(cls, assistant):
        agent_def = cls(
            name=assistant.name,
            description=assistant.description,
            instructions=assistant.instructions,
            tools=assistant.tools,
            tool_resources=assistant.tool_resources,
            metadata=assistant.metadata
        )
        agent_def.model = assistant.model
        return agent_def

    def __dict__(self):
        return {
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
        return hash(
            (self.name, self.description, self.instructions, self.model, 
                json.dumps(self.metadata, sort_keys=True), 
                json.dumps(self.tools, sort_keys=True),
                json.dumps(self.tool_resources, sort_keys=True))
        )



DEFAULT_DB_URL = "sqlite:///.bondcache.db"
class AgentBuilder:

    # Using this class so that I dont need to set up and tear down assistants each time
    def __init__(self, db_url: str = DEFAULT_DB_URL):
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.openai_client = Config.config().get_openai_client()
        self.context = {"agents": {}}
        atexit.register(self.cleanup)
        LOGGER.info(f"Created AgentBuilder instance using database engine: {db_url}")

    @classmethod
    @bond_cache
    def builder(cls, db_url: str = DEFAULT_DB_URL):
        return AgentBuilder(db_url=db_url)

    def cleanup(self):
        session = self.Session()

        for assistant_id_tuple in session.query(AgentRecord.assistant_id).all():
            assistant_id = assistant_id_tuple[0]
            try:
                self.openai_client.beta.assistants.delete(assistant_id)
                LOGGER.info(f"Deleting assistant with assistant_id: {assistant_id}")
            except Exception as e:
                LOGGER.error(f"Error deleting assistant with assistant_id: {assistant_id}. Error: {e}")
        session.query(AgentRecord).delete()
        session.commit()

        for thread_id_tuple in session.query(ThreadRecord.thread_id).all():
            thread_id = thread_id_tuple[0]
            try:
                self.openai_client.beta.threads.delete(thread_id)
                LOGGER.info(f"Deleting thread with thread_id: {thread_id}")
            except Exception as e:
                LOGGER.error(f"Error deleting thread with thread_id: {thread_id}. Error: {e}")
        session.query(ThreadRecord).delete()
        session.commit()

        for file_record in session.query(FileRecord).all():
            if file_record.file_id is None:
                continue
            try:
                self.openai_client.files.delete(file_record.file_id)
                LOGGER.info(f"Deleting file with file_id: {file_record.file_id}")
            except Exception as e:
                LOGGER.error(f"Error deleting file with file_id: {file_record.file_id}. Error: {e}")
        session.query(FileRecord).delete()
        session.commit()

        for vector_store_record in session.query(VectorStore).all():
            try:
                self.openai_client.beta.vector_stores.delete(vector_store_record.vector_store_id)
                LOGGER.info(f"Deleting vector store with vector_store_id: {vector_store_record.vector_store_id}")
            except Exception as e:
                LOGGER.error(f"Error deleting vector store with vector_store_id: {vector_store_record.vector_store_id}. Error: {e}")
        session.query(VectorStore).delete()
        session.commit()

        # session.query(VectorStoreFileRecord).delete()
        # session.commit()

        session.close()



    # def get_function_summary(source_code: str, signature: str) -> Dict[str, str]:
    #     """Uses OpenAI's structured output (function calling) to generate a function summary and argument descriptions."""
        
    #     # Define the expected JSON response schema
    #     function_schema = {
    #         "name": "summarize_function",
    #         "description": "Analyze a Python function and return a structured description of its purpose and arguments.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "description": {
    #                     "type": "string",
    #                     "description": "A concise summary of what the function does."
    #                 },
    #                 "arguments": {
    #                     "type": "object",
    #                     "description": "A dictionary of argument names with their descriptions.",
    #                     "additionalProperties": {
    #                         "type": "string"
    #                     }
    #                 }
    #             },
    #             "required": ["description", "arguments"]
    #         }
    #     }

    #     messages = [
    #         {"role": "system", "content": "You are an expert Python code analyst."},
    #         {
    #             "role": "user",
    #             "content": f"""
    #             Analyze the following Python function and return:
    #             1. A one-sentence description of its purpose.
    #             2. A dictionary where each key is an argument name and the value is its description.

    #             Function Signature:
    #             {signature}

    #             Function Code:
    #             {source_code}
    #             """
    #         }
    #     ]

    #     # try:
    #     #     response = openai.ChatCompletion.create(
    #     #         model="gpt-4-turbo",  # Use GPT-4 turbo for cost efficiency
    #     #         messages=messages,
    #     #         functions=[function_schema],  # Structured function calling
    #     #         function_call={"name": "summarize_function"},
    #     #         response_format="json",  # Ensure JSON response
    #     #     )

    #     #     # Extract structured response
    #     #     result = response["choices"][0]["message"]["function_call"]["arguments"]
    #     #     return result  # This is already a structured dict

    #     # except Exception as e:
    #     #     LOGGER.error(f"OpenAI API call failed: {e}")
    #     #     return {"description": "Could not generate function description.", "arguments": {}}


    def get_agent(self, agent_def: AgentDefinition) -> None:

        session = self.Session()
        agent_record = session.query(AgentRecord).filter(AgentRecord.name == agent_def.name).first()
        agent = None

        if agent_record:
            assistant_id = agent_record.assistant_id
            assistant = self.openai_client.beta.assistants.retrieve(assistant_id)
            existing_agent_def = AgentDefinition.from_assistant(assistant)
            LOGGER.debug(f"Existing Agent Def: {existing_agent_def}")
            LOGGER.debug(f"New Agent Def: {agent_def}")

            if existing_agent_def.get_hash() != agent_def.get_hash():
                assistant = self.openai_client.beta.assistants.update(
                    assistant_id=assistant_id,
                    name=agent_def.name,
                    description=agent_def.description,
                    instructions=agent_def.instructions,
                    model=agent_def.model,
                    tools=agent_def.tools,
                    tool_resources=agent_def.tool_resources,
                    metadata=agent_def.metadata
                )
                LOGGER.debug(f"Tool Resources: {json.dumps(agent_def.tool_resources, sort_keys=True, indent=4)}")
                LOGGER.info(f"Updated agent [{agent_def.name}] with assistant_id: {assistant_id}")
            else:
                LOGGER.debug(f"Tool Resources: {json.dumps(agent_def.tool_resources, sort_keys=True, indent=4)}")
                LOGGER.info(f"Reusing agent [{agent_def.name}] with assistant_id: {assistant_id}")
            agent = Agent(assistant=assistant)
        else:
            assistant = self.openai_client.beta.assistants.create(
                name=agent_def.name,
                description=agent_def.description,
                instructions=agent_def.instructions,
                model=agent_def.model,
                tools=agent_def.tools,
                tool_resources=agent_def.tool_resources,
                metadata=agent_def.metadata
            )
            agent = Agent(assistant=assistant)
            agent_record = AgentRecord(name=agent_def.name, assistant_id=assistant.id)
            session.add(agent_record)
            session.commit()
            LOGGER.debug(f"Tool Resources: {json.dumps(agent_def.tool_resources, sort_keys=True, indent=4)}")
            LOGGER.info(f"Created new agent [{agent_def.name}] with assistant_id: {assistant.id}")

        self.context["agents"][agent_def.name] = agent
        session.close()
        return agent

    def create_thread(self):
        session = self.Session()
        thread = self.openai_client.beta.threads.create()
        thread_record = ThreadRecord(name=thread.id, thread_id=thread.id)
        session.add(thread_record)
        session.commit()
        session.close()
        return thread.id
    
    def delete_thread(self, thread_id: str):
        session = self.Session()
        self.openai_client.beta.threads.delete(thread_id)
        session.query(ThreadRecord).filter(ThreadRecord.thread_id == thread_id).delete()
        session.commit()
        session.close()

    def _get_file_record(self, file_path: str) -> str:
        session = self.Session()
        file_record = None
        file_content = None
        with open(file_path, "rb") as file:
            file_content = file.read()
            file_hash = hashlib.sha256(file_content).hexdigest()

            file_record = session.query(FileRecord).filter(FileRecord.path == file_path).first()
            if file_record:
                if file_record.file_hash == file_hash:
                    LOGGER.debug(f"File {file_path} is same in the database")
                    file_content = None
                else:
                    file_record.file_hash = file_hash
                    session.commit()
                    LOGGER.info(f"Updated file record for {file_path}")
            else:
                file_record = FileRecord(path=file_path, file_hash=file_hash)
                session.add(file_record)
                session.commit()
                LOGGER.info(f"Created new file record for {file_path}")

        file_dict = {'path': file_record.path, 
                     'file_hash': file_record.file_hash, 
                     'file_id': file_record.file_id,
                     'content': file_content}
        session.close()
        return file_dict

    def get_file_id(self, file_path: str) -> str:
        LOGGER.debug(f"Getting file id for {file_path}")
        file_dict = self._get_file_record(file_path)
        # TODO: need to delete the file in openai if the file_stream is not None and the file_id is not None
        if file_dict['content'] is not None:
            file_stream = io.BytesIO(file_dict['content'])
            openai_file = self.openai_client.files.create(
                file=(file_path, file_stream),
                purpose='assistants'
            )
            file_dict['file_id'] = openai_file.id
            session = self.Session()    
            file_record = session.query(FileRecord).filter(FileRecord.path == file_path).first()
            file_record.file_id = file_dict['file_id']
            session.commit()
            LOGGER.debug(f"Updated file record for {file_path} with file_id: {file_dict['file_id']}")
            session.close()
        return file_dict['file_id']

    def _get_or_create_vector_store(self, name: str) -> str:
        session = self.Session()
        vector_store_record = session.query(VectorStore).filter(VectorStore.name == name).first()
        if vector_store_record:
            LOGGER.debug(f"Reusing vector store {name} with vector_store_id: {vector_store_record.vector_store_id}")
        else: 
            vector_store = self.openai_client.beta.vector_stores.create(name=name)
            vector_store_record = VectorStore(name=name, vector_store_id=vector_store.id)
            session.add(vector_store_record)
            session.commit()
            LOGGER.info(f"Created new vector store {name} with vector_store_id: {vector_store_record.vector_store_id}")
        vector_store_id = vector_store_record.vector_store_id
        session.close()
        return vector_store_id
    
    def upload_vector_store_file(self, vector_store_id, file_id):
        vector_store_file = self.openai_client.beta.vector_stores.files.create_and_poll(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
        while vector_store_file.status == "in_progress":
            time.sleep(1)
        return vector_store_file.status == "completed"
    

    def get_vector_store(self, name: str, files: List[str]) -> str:

        # TODO: page in the files
        max_limit = 100
        if len(files) > max_limit:
            raise Exception(f"Too many files to upload to vector store. Limit is {max_limit}")

        # first get the vector store id for the given name
        vector_store_id = self._get_or_create_vector_store(name)

        # get the current file ids associated with the vector store
        vector_store_files = self.openai_client.beta.vector_stores.files.list(
            vector_store_id=vector_store_id,
            limit=max_limit
        )
        vector_store_file_ids = [record['id'] for record in vector_store_files.to_dict()['data']]

        for file_path in files:
            file_id = self.get_file_id(file_path)
            if file_id not in vector_store_file_ids:
                if self.upload_vector_store_file(vector_store_id, file_id):
                    LOGGER.info(f"Created new vector store [{vector_store_id}] file record for file: {file_path}")
                else:
                    LOGGER.error(f"Error uploading file {file_id} to vector store {vector_store_id}")
            else:
                vector_store_file_ids.remove(file_id)
                LOGGER.debug(f"Reusing vector store [{vector_store_id}] file record for file: {file_path}")
                
        # next remove any files left over
        for file_id in vector_store_file_ids:
            self.openai_client.beta.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
            LOGGER.info(f"Deleted vector store [{vector_store_id}] file record for file: {file_id}")

        return vector_store_id

    def get_context(self):
        return self.context

    def display_message (self, message):
        if message.role == 'system':
            LOGGER.debug(f"Received system message, ignoring {message.message_id}")
            return
        if message.type == "text":
            print(f"[{message.message_id}/{message.role}] => {message.clob.get_content()}")
        elif message.type == "image_file":
            print(f"[{message.message_id}/{message.role}] => ")
            content = message.clob.get_content()
            if content.startswith('data:image/png;base64,'):
                base64_image = content[len('data:image/png;base64,'):]
                image_data = base64.b64decode(base64_image)
                display(Image(data=image_data))
            else:
                print(content)
        else:
            LOGGER.error(f"Unknown message type {type}")

    def print_responses (self, user_id, prompts, agent_def: AgentDefinition):
        thread_id = self.create_thread()
        try:
            broker = Broker.broker()
            conn = broker.connect(thread_id=thread_id, subscriber_id=user_id)
            agent = self.get_agent(agent_def)
            for prompt in prompts:
            
                message = agent.create_user_message(prompt, thread_id)
                thread = threading.Thread(target=agent.broadcast_response, args=(None, thread_id), daemon=True)
                thread.start()
                while True:
                    try:
                        bond_msg = conn.wait_for_message(timeout=5)
                        if bond_msg is None:
                            break
                        self.display_message(bond_msg)
                        if bond_msg.is_done:
                            break
                    except BrokerConnectionEmpty:
                        continue
                    except Exception as e:
                        LOGGER.error(f"Error: {e}")
                        break
                thread.join()

            conn.close()
        finally:
            self.delete_thread(thread_id)

