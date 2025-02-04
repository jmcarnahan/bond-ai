import streamlit as st
import io
import json
from PIL import Image
from bond_ai.bond.config import Config
from bond_ai.bond.broker import AgentResponseMessage
from typing_extensions import override
from openai import OpenAI, AssistantEventHandler
from openai.types.beta.threads import (
    Run,
    Text,
    Message,
    ImageFile,
    TextDelta,
    MessageDelta,
    MessageContent,
    MessageContentDelta,
)
from openai.types.beta.threads.runs.run_step import RunStep
from queue import Queue
import threading
import logging
import base64
import abc




import ijson

LOGGER = logging.getLogger(__name__)


class GeneratorBytesIO(io.RawIOBase):
    """
    Wrap a generator that yields pieces of text, providing a .read() method
    so it behaves like a file for streaming parsers (e.g. ijson), but returns bytes.
    """
    def __init__(self, text_generator, encoding='utf-8'):
        super().__init__()
        self._gen = iter(text_generator)
        self._buffer = b""
        self._encoding = encoding

    def read(self, size=-1):
        if size < 0:
            # Read ALL remaining data from the generator
            chunks = [self._buffer]
            self._buffer = b""
            for chunk in self._gen:
                chunks.append(chunk.encode(self._encoding))
            return b"".join(chunks)
        else:
            # Read 'size' bytes (or until the generator is exhausted).
            while len(self._buffer) < size:
                try:
                    next_chunk = next(self._gen).encode(self._encoding)
                    self._buffer += next_chunk
                except StopIteration:
                    break
            result = self._buffer[:size]
            self._buffer = self._buffer[size:]
            return result


class EventHandler(AssistantEventHandler):  

    def __init__(self, message_queue: Queue, openai_client: OpenAI, functions, thread_id, threads, wrap_json:bool=False):
        super().__init__()
        self.message_queue = message_queue
        self.openai_client = openai_client
        self.functions = functions
        self.wrap_json = wrap_json
        self.thread_id = thread_id
        self.threads = threads

        self.current_msg = None
        self.wrap_state = 0
        self.files = {}
        LOGGER.debug("EventHandler initialized with wrap_json: ", wrap_json)

    @override
    def on_message_created(self, message: Message) -> None:
        # print(f"on_message_created: {message}")
        if self.current_msg is not None:
            LOGGER.error(f"Message created before previous message was done: {self.current_msg}")
        self.current_msg = message

    @override 
    def on_message_delta(self, delta: MessageDelta, snapshot: Message) -> None:
        for part in delta.content:
            if self.wrap_json:
                part_id = f"{self.current_msg.id}_{part.index}"
                if part.type == 'image_file':
                    # Need to close the previous part if it is open
                    if self.wrap_state > 0:
                        self.message_queue.put('},\n')
                        self.wrap_state = 0

                    if part.image_file.file_id not in self.files:
                        self.message_queue.put('{"id": "' + part_id + 
                                               '", "role": "' + str(self.current_msg.role) + 
                                               '", "type": "text", "content": "No image found."},\n')
                    else:
                        json_img_src = json.dumps(self.files[part.image_file.file_id])
                        self.message_queue.put('{"id": "' + part_id + 
                                               '", "role": "' + str(self.current_msg.role) + 
                                               '", "type": "' + part.type + 
                                               '", "content": "' + json_img_src[1:-1] + '"},\n')
                elif part.type == 'text':
                    # initialize the content if necessary
                    if self.wrap_state == 0:
                        self.message_queue.put('{"id": "' + part_id + 
                                               '", "role": "' + str(self.current_msg.role) + 
                                               '", "type": "' + part.type + 
                                               '", "content": "')
                        
                    # always add to the content and increment the state
                    self.message_queue.put(json.dumps(part.text.value)[1:-1])
                    self.wrap_state += 1

                else:
                    if part.type == 'image_file':
                        if part.image_file.file_id not in self.files:
                            self.message_queue.put(f"|No image found.|")
                        else:
                            self.message_queue.put(f"|{part.image_file.file_id}|")
                    elif part.type == 'text':
                        self.message_queue.put(part.text.value)
                    else:
                        LOGGER.info(f"Delta message of unhandled type: {delta}")


    @override 
    def on_message_done(self, message: Message) -> None:
        if self.wrap_json:
            if self.wrap_state > 0:
                self.message_queue.put('"},\n')
                self.wrap_state = 0
        else:
            self.message_queue.put('\n')
        self.current_msg = None

    @override
    def on_end(self) -> None:
        self.message_queue.put(None)

    @override
    def on_image_file_done(self, image_file: ImageFile) -> None:
        response_content = self.openai_client.files.content(image_file.file_id)
        data_in_bytes = response_content.read()
        readable_buffer = io.BytesIO(data_in_bytes)
        img_src = 'data:image/png;base64,' + base64.b64encode(readable_buffer.getvalue()).decode('utf-8')
        self.files[image_file.file_id] = img_src

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
                        function_to_call = getattr(self.functions, tool_call.function.name, None)
                        arguments =  json.loads(tool_call.function.arguments) if hasattr(tool_call.function, 'arguments') else {}
                        if function_to_call:
                            try:
                                LOGGER.debug(f"Calling function {tool_call.function.name}")
                                result = function_to_call(**arguments)
                                tool_call_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": result
                                })
                            except Exception as e:
                                LOGGER.error(f"Error calling function {tool_call.function.name}: {e}")
                        else:
                            LOGGER.error(f"No function was defined: {tool_call.function.name}")
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
                                thread_id=self.thread_id,
                                threads=self.threads,
                                wrap_json=self.wrap_json,
                            )
                        ) as stream:
                            stream.until_done() 
                    except Exception as e:
                        LOGGER.error(f"Failed to submit tool outputs {tool_call_outputs}: {e}")
            case _:
                LOGGER.warning(f"Run status is not handled: {self.current_run.status}")

class Agent:

    assistant_id: str = None
    name: str = None
    openai_client = None

    def __init__(self, assistant_id, name, config, user_id, metadata={}):
        self.assistant_id = assistant_id
        self.name = name
        self.config = config
        self.user_id = user_id
        self.threads = config.get_threads()
        self.openai_client = config.get_openai_client()
        self.functions = config.get_functions()
        self.metadata = metadata

    def __str__(self):
        return f"Agent: {self.name} ({self.assistant_id})"

    @classmethod
    def list_agents(cls, config, user_id, limit=100):
        assistants = config.get_openai_client().beta.assistants.list(order="desc",limit=str(limit))
        agents = []
        for asst in assistants.data:
            agents.append(cls(assistant_id=asst.id, name=asst.name, config=config, user_id=user_id, metadata=asst.metadata))
        return agents

    @classmethod
    def get_agent_by_name(cls, name, config, user_id):
        openai_client = config.get_openai_client()
        # TODO: fix this to handle more than 100 assistants
        assistants = openai_client.beta.assistants.list(order="desc",limit="100")
        for asst in assistants.data:
            if asst.name == name:
                return cls(assistant_id=asst.id, name=asst.name, config=config, user_id=user_id, metadata=asst.metadata)
        return None

    def create_user_message(self, prompt, thread_id, attachments=None):
        msg = self.openai_client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt,
            attachments=attachments,
        )
        user_msg = AgentResponseMessage(id=msg.id, type='text', role='user', thread_id=thread_id, content=prompt)
        self.threads.notify(user_msg)
        return msg
    
    def get_metadata_value(self, key, default_value=None):
        if key in self.metadata:
            return self.metadata[key]
        else:
            return default_value

    def get_messages(self, thread_id):
        response_msgs = []
        messages = self.openai_client.beta.threads.messages.list(
            thread_id=thread_id
        )
        for message in reversed(messages.data):
            part_idx = 0
            for part in message.content:
                part_idx += 1
                part_id = f"{message.id}_{part_idx}"
                if part.type == "text":
                    response_msgs.append({"id": part_id, "role": message.role, "content": part.text.value})
                elif part.type == "image_file":
                    response_content = self.openai_client.files.content(part.image_file.file_id)
                    data_in_bytes = response_content.read()
                    readable_buffer = io.BytesIO(data_in_bytes)
                    image = Image.open(readable_buffer)
                    response_msgs.append({"id": part_id, "role": message.role, "content": image})
        return response_msgs

    def handle_response(self, prompt, thread_id):
        LOGGER.debug("Handling response")
        try:
            agent_gen = self.stream_response(prompt=prompt, thread_id=thread_id, wrap_json=True)
            stream = GeneratorBytesIO(agent_gen)
            current_id = None
            current_type = None
            current_role = None
            for prefix, event, value in ijson.parse(stream, buf_size=100):
                if event == 'string':
                    match prefix:
                        case "item.id":
                            current_id = value
                        case "item.type":
                            current_type = value
                        case "item.role":
                            current_role = value
                        case "item.content":
                            agent_msg = AgentResponseMessage(id=current_id, 
                                                            type=current_type, 
                                                            role=current_role, 
                                                            thread_id=thread_id, 
                                                            content=value)
                            self.threads.notify(agent_msg)
                            LOGGER.debug(f"Notified message: {agent_msg.model_dump_json()}")
                        case _:
                            LOGGER.error(f"Unhandled event: {prefix}, {event}, {value}")
                elif event == 'end_map' or event == 'end_array' or event == 'start_map' or event == 'start_array':
                    current_id = None
                    current_type = None
                    current_role = None
                elif event == 'map_key':
                    LOGGER.debug(f"Map key: {value}")
                else:
                    LOGGER.warning(f"Unhandled event: {prefix}, {event}, {value}")
        except Exception as e:
            LOGGER.exception(f"Error handling response: {str(e)}")
            agent_msg = AgentResponseMessage(id="undefined", 
                                type='error', 
                                role='system', 
                                thread_id=thread_id, 
                                content=str(e),
                                is_error=True)
            self.notify(agent_msg)


    def stream_response(self, prompt=None, thread_id=None, wrap_json:bool=False):
        LOGGER.debug(f"Agent streaming response using assistant id: {self.assistant_id}")
        if prompt is not None:
            user_message = self.create_user_message(prompt, thread_id)
            LOGGER.debug(f"Created new user message: {user_message.id}")
        message_queue = Queue()
        if wrap_json:
            yield '['
        with self.openai_client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
            event_handler=EventHandler(
                message_queue=message_queue,
                openai_client=self.openai_client,
                functions=self.functions,
                thread_id=thread_id,
                threads=self.threads,
                wrap_json=wrap_json,
            )
        ) as stream:
            stream_thread: threading.Thread = threading.Thread(target=stream.until_done)
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
            if wrap_json:
                yield '{}]'
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
                    )
                LOGGER.info(f"Added code files to thread: {code_file_ids} from functions")

            return

    def get_response(self, prompt=None, thread_id=None):
        LOGGER.debug(f"Agent getting response using assistant id: {self.assistant_id}")
        if prompt is not None:
            user_message = self.create_user_message(prompt, thread_id)
            LOGGER.debug(f"Created new user message: {user_message.id}")

        run = self.openai_client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
        )
        for i in range(100):
            match run.status:
                case "completed":
                    return self.get_messages(thread_id)
                case "failed":
                    raise Exception(f"Run failed: {str(run.last_error)}")
                case "expired":
                    raise Exception("Run expired")
                case "cancelled":
                    raise Exception("Run cancelled")
                case "requires_action":
                    # Loop through each tool in the required action section
                    tool_outputs = []
                    for tool in run.required_action.submit_tool_outputs.tool_calls:
                        LOGGER.debug("Looking for function: ", tool.function.name)
                        function_to_call = getattr(self.functions, tool.function.name, None)
                        if function_to_call:
                            try:
                                LOGGER.debug(f"Calling function {tool.function.name}")
                                parameters = json.loads(tool.function.arguments) if hasattr(tool.function, 'arguments') else {}
                                result = function_to_call(**parameters)
                                tool_outputs.append({
                                    "tool_call_id": tool.id,
                                    "output": result
                                })
                            except Exception as e:
                                LOGGER.error(f"Error calling function {tool.function.name}: {e}")

                    # Submit all tool outputs at once after collecting them in a list
                    if tool_outputs:
                        try:
                            run = self.openai_client.beta.threads.runs.submit_tool_outputs_and_poll(
                                thread_id=thread_id,
                                run_id=run.id,
                                tool_outputs=tool_outputs
                            )
                            #print("Tool outputs submitted successfully.")
                        except Exception as e:
                            LOGGER.error(f"Failed to submit tool outputs: {e}")
                    else:
                        LOGGER.trace("No tool outputs to submit.")
                case _:
                    LOGGER.warning(f"Run status: {run.status}")



        
                    


