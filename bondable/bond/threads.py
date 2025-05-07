import io
import base64
from bondable.bond.config import Config
from bondable.bond.metadata import Metadata, Thread as OrmThread # Import the SQLAlchemy Thread model
from bondable.bond.broker import BondMessage
from bondable.bond.broker import Broker
from bondable.bond.cache import bond_cache
import logging
from typing import Optional # Added import for Optional

LOGGER = logging.getLogger(__name__)

class Threads:
     
    user_id: str = None

    def __init__(self, user_id):
        self.user_id = user_id
        self.config = Config.config()
        self.metadata = Metadata.metadata()
        self.broker = Broker.broker()
        LOGGER.info(f"Created new threads instance for user: ({self.user_id})")

    @classmethod
    @bond_cache
    def threads(cls, user_id):
        return Threads(user_id=user_id)

    def close(self):
        pass

    def get_user_id(self):
        return self.user_id

    def update_thread_name(self, thread_id) -> str:
        thread_name = "New Thread"
        messages = self.config.get_openai_client().beta.threads.messages.list(thread_id=thread_id, limit=1, order="asc")
        if len(messages.data) > 0:
            thread_name = messages.data[0].content[0].text.value.replace("\'", " ")
            self.metadata.update_thread_name(thread_id=thread_id, thread_name=thread_name)
        return thread_name
    
    def get_current_threads(self, count=10) -> list:
        thread_list = self.metadata.get_current_threads(user_id=self.user_id, count=count)
        for thread in thread_list:
            if thread['name'] == None or thread['name'] == "":
                thread['name'] = self.update_thread_name(thread_id=thread['thread_id'])
        return thread_list

    def create_thread(self, name: Optional[str] = None) -> OrmThread: # Return the ORM Thread object
        return self.metadata.create_thread(user_id=self.user_id, name=name) # Pass name

    def get_current_thread_id(self, session) -> str:
        if 'thread' not in session:
            threads_list = self.get_current_threads(count=1) # Renamed to avoid conflict with Threads class
            if len(threads_list) > 0:
                session['thread'] = threads_list[0]['thread_id']
            else:
                # create_thread now returns an ORM object. We need its thread_id.
                new_thread_orm = self.create_thread()
                session['thread'] = new_thread_orm.thread_id
        return session['thread']
    
    def grant_thread(self, thread_id: str, user_id: Optional[str] = None, name: Optional[str] = None) -> OrmThread:
        """Grants an existing thread to a user, or updates their access name. Fails if thread doesn't exist."""
        granting_user_id = user_id if user_id is not None else self.user_id
        
        # Call metadata.grant_thread with fail_if_missing=True because this method
        # is intended for granting access to threads that should already exist.
        # The 'name' parameter here can be used to set/update the name associated
        # with this specific user's access to the thread.
        granted_thread_orm = self.metadata.grant_thread(
            thread_id=thread_id,
            user_id=granting_user_id,
            name=name, # Pass the name if provided
            fail_if_missing=True
        )
        LOGGER.info(f"Granted/updated access for thread {granted_thread_orm.thread_id} to user {granting_user_id} with name '{granted_thread_orm.name}'")
        return granted_thread_orm
    
    def has_messages(self, thread_id, last_message_id) -> bool:
        response = self.config.get_openai_client().beta.threads.messages.list(thread_id, limit=1, after=last_message_id)
        return not response.data

    def get_messages(self, thread_id, limit=100) -> dict:
        response_msgs = []
        messages = self.config.get_openai_client().beta.threads.messages.list(thread_id=thread_id, limit=limit, order="asc")
        for message in messages.data:
            part_idx = 0

            metadata = message.metadata
            if metadata is not None and "override_role" in metadata:
                message.role = metadata["override_role"]

            for part in message.content:
                LOGGER.debug(f"Processing message part: {str(part)}")
                part_id = f"{message.id}_{part_idx}"
                if part.type == "text":
                    response_msgs.append(BondMessage(thread_id=thread_id, message_id=part_id, type=part.type, role=message.role, content=part.text.value))
                elif part.type == "image_file":
                    image_content = self.config.get_openai_client().files.content(part.image_file.file_id)
                    data_in_bytes = image_content.read()
                    readable_buffer = io.BytesIO(data_in_bytes)
                    img_src = 'data:image/png;base64,' + base64.b64encode(readable_buffer.getvalue()).decode('utf-8')
                    # data_in_bytes = response_content.read()
                    # readable_buffer = io.BytesIO(data_in_bytes)
                    # image = Image.open(readable_buffer)
                    response_msgs.append(BondMessage(thread_id=thread_id, message_id=part_id, type=part.type, role=message.role, content=img_src))
                part_idx += 1
        return {message.message_id: message for message in response_msgs}

    # def get_messages(self, thread_id):
    #     response_msgs = []
    #     messages = self.openai_client.beta.threads.messages.list(
    #         thread_id=thread_id
    #     )
    #     for message in reversed(messages.data):
    #         part_idx = 0

    #         metadata = message.metadata
    #         if metadata is not None and "override_role" in metadata:
    #             message.role = metadata["override_role"]

    #         for part in message.content:
    #             part_idx += 1
    #             part_id = f"{message.id}_{part_idx}"
    #             if part.type == "text":
    #                 response_msgs.append({"id": part_id, "role": message.role, "content": part.text.value})
    #             elif part.type == "image_file":
    #                 response_content = self.openai_client.files.content(part.image_file.file_id)
    #                 data_in_bytes = response_content.read()
    #                 readable_buffer = io.BytesIO(data_in_bytes)
    #                 image = Image.open(readable_buffer)
    #                 response_msgs.append({"id": part_id, "role": message.role, "content": image})
    #     return response_msgs


    def delete_thread(self, thread_id) -> None:
        self.config.get_openai_client().beta.threads.delete(thread_id=thread_id)
        self.metadata.delete_thread(thread_id=thread_id)

    def get_thread(self, thread_id):
        return self.metadata.get_thread(thread_id=thread_id)
