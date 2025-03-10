import io
from PIL import Image
from bondable.bond.config import Config
from bondable.bond.functions import Functions
from bondable.bond.broker import Broker
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
import json


LOGGER = logging.getLogger(__name__)


class EventHandler(AssistantEventHandler):  

    def __init__(self, message_queue: Queue, openai_client: OpenAI, functions, thread_id):
        super().__init__()
        self.message_queue = message_queue
        self.openai_client = openai_client
        self.functions = functions
        self.thread_id = thread_id

        self.current_msg = None
        self.message_state = 0
        self.files = {}
        LOGGER.debug("EventHandler initialized")

    @override
    def on_message_created(self, message: Message) -> None:
        # print(f"on_message_created: {message}")
        if self.current_msg is not None:
            LOGGER.error(f"Message created before previous message was done: {self.current_msg}")
        self.current_msg = message


    @override 
    def on_message_delta(self, delta: MessageDelta, snapshot: Message) -> None:
        LOGGER.debug(f"on_message_delta: {delta}")
        for part in delta.content:
            part_id = f"{self.current_msg.id}_{part.index}"
            if part.type == 'image_file':
                if self.message_state > 0:
                    self.message_queue.put('</_bondmessage>')
                    self.message_state = 0
                
                if part.image_file.file_id not in self.files:
                    self.message_queue.put(f"<_bondmessage id=\"{part_id}\" role=\"{self.current_msg.role}\" type=\"error\" thread_id=\"{self.thread_id}\" is_done=\"false\">")
                    self.message_queue.put("No image found.")
                    self.message_queue.put("</_bondmessage>")
                else:
                    self.message_queue.put(f"<_bondmessage id=\"{part_id}\" role=\"{self.current_msg.role}\" type=\"image_file\" thread_id=\"{self.thread_id}\" file=\"{part.image_file.file_id}\" is_done=\"false\">")
                    self.message_queue.put(f"{self.files[part.image_file.file_id]}")
                    self.message_queue.put("</_bondmessage>")
    
            elif part.type == 'text':
                if self.message_state == 0:
                    self.message_queue.put(f"<_bondmessage id=\"{part_id}\" role=\"{self.current_msg.role}\" type=\"text\" thread_id=\"{self.thread_id}\" is_done=\"false\">")
                self.message_queue.put(part.text.value)
                self.message_state += 1
            else:
                LOGGER.warning(f"Delta message of unhandled type: {delta}")


    @override 
    def on_message_done(self, message: Message) -> None:
        if self.message_state > 0:
            self.message_queue.put('</_bondmessage>')
            self.message_state = 0
        self.current_msg = None


    @override
    def on_end(self) -> None:
        self.message_queue.put(f"<_bondmessage id=\"-1\" role=\"system\" type=\"text\" thread_id=\"{self.thread_id}\" is_done=\"true\">")
        self.message_queue.put("Done.")
        self.message_queue.put("</_bondmessage>")
        self.message_queue.put(None)

    @override
    def on_exception(self, exception):
        LOGGER.error(f"Received assistant exception: {exception}")
        self.message_queue.put(f"<_bondmessage id=\"-1\" role=\"system\" type=\"text\" thread_id=\"{self.thread_id}\" is_done=\"false\" is_error=\"true\">")
        self.message_queue.put(f"An error occurred: " + str(exception))
        self.message_queue.put("</_bondmessage>")       

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
                                thread_id=self.thread_id
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

    def __init__(self, assistant):
        self.assistant_id = assistant.id
        self.name = assistant.name
        self.metadata = assistant.metadata
        self.description = assistant.description
        self.openai_client = Config.config().get_openai_client()
        self.functions = Functions.functions()
        self.broker = Broker.broker()
        LOGGER.debug(f"Agent initialized: {self.name}")

    def __str__(self):
        return f"Agent: {self.name} ({self.assistant_id})"

    def get_assistant_id(self):
        return self.assistant_id

    def get_name(self):
        return self.name
    
    def get_description(self):
        return self.description

    @classmethod
    def list_agents(cls, limit=100):
        assistants = Config.config().get_openai_client().beta.assistants.list(order="desc",limit=str(limit))
        agents = []
        for asst in assistants.data:
            agents.append(cls(assistant=asst))
        return agents

    @classmethod
    def get_agent_by_name(cls, name):
        # TODO: fix this to handle more than 100 assistants
        assistants = Config.config().get_openai_client().beta.assistants.list(order="desc",limit="100")
        for asst in assistants.data:
            if asst.name == name:
                return cls(assistant=asst)
        return None
    
    def get_metadata_value(self, key, default_value=None):
        if key in self.metadata:
            return self.metadata[key]
        else:
            return default_value

    def create_user_message(self, prompt, thread_id, attachments=None, override_role="user"):
        msg = self.openai_client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt,
            attachments=attachments,
            metadata={"override_role": override_role}
        )
        LOGGER.debug(f"Broadcasting new message: {prompt}")
        self.broker.publish(thread_id=thread_id, message=f"<_bondmessage id=\"{msg.id}\" role=\"{override_role}\" type=\"text\" thread_id=\"{thread_id}\" is_done=\"false\">")
        self.broker.publish(thread_id=thread_id, message=prompt)
        self.broker.publish(thread_id=thread_id, message="</_bondmessage>")
        return msg

    def stream_response(self, prompt=None, thread_id=None):
        LOGGER.debug(f"Agent streaming response using assistant id: {self.assistant_id}")

        if prompt is not None:
            user_message = self.create_user_message(prompt=prompt, thread_id=thread_id, attachments=None)
            LOGGER.debug(f"Created new user message: {user_message.id}")
        message_queue = Queue()

        with self.openai_client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
            event_handler=EventHandler(
                message_queue=message_queue,
                openai_client=self.openai_client,
                functions=self.functions,
                thread_id=thread_id
            )
        ) as stream:
            stream_thread: threading.Thread = threading.Thread(target=stream.until_done, daemon=True)
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
                        metadata={"override_role": "system"}
                    )
                LOGGER.info(f"Added code files to thread: {code_file_ids} from functions")
            return
        
    def broadcast_response(self, prompt=None, thread_id=None):
        try:
            for content in self.stream_response(prompt=prompt, thread_id=thread_id):
                LOGGER.debug(f"Broadcasting content: {content}")
                self.broker.publish(thread_id=thread_id, message=content)
        except Exception as e:
            LOGGER.exception(f"Error handling response: {str(e)}")
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




        
                    


