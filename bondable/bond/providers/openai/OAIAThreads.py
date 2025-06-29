from abc import ABC, abstractmethod
from bondable.bond.providers.threads import ThreadsProvider
from bondable.bond.providers.openai.OAIAMetadata import OAIAMetadata
from bondable.bond.cache import bond_cache
import openai
import logging
from typing_extensions import override
import io
import base64
from bondable.bond.broker import BondMessage
from typing import Dict

LOGGER = logging.getLogger(__name__)

class OAIAThreadsProvider(ThreadsProvider):

    def __init__(self, openai_client, metadata):
        super().__init__(metadata=metadata)
        self.openai_client = openai_client

    # @classmethod
    # @bond_cache
    # def provider(cls) -> ThreadsProvider:
    #     return OAIAThreadsProvider()


    @override
    def delete_thread_resource(self, thread_id: str) -> bool:
        """
        Deletes a thread by its id. 
        Don't throw an exception if it does not exist, just return False.
        """
        try:
            self.openai_client.beta.threads.delete(thread_id)
            LOGGER.info(f"Successfully deleted thread {thread_id} from openai")
            return True
        except openai.NotFoundError: 
            LOGGER.warning(f"File {thread_id} not found on provider")
            return False
        except Exception as e:
            LOGGER.error(f"Error deleting file {thread_id} from provider: {e}", exc_info=True)
            raise e

    @override
    def create_thread_resource(self) -> str:
        """
        Creates a new thread. 
        Returns the thread_id of the created thread.
        """
        try:
            openai_thread = self.openai_client.beta.threads.create()
            LOGGER.info(f"Successfully created thread {openai_thread.id} from provider")
            return openai_thread.id
        except Exception as e:
            LOGGER.error(f"Error creating thread from provider: {e}", exc_info=True)
            raise e
        
    @override
    def has_messages(self, thread_id, last_message_id=None) -> bool:
        response = self.openai_client.beta.threads.messages.list(thread_id, limit=1, after=last_message_id)
        return not response.data

    @override
    def get_messages(self, thread_id, limit=100) -> Dict[str, BondMessage]:
        response_msgs = []
        messages = self.openai_client.beta.threads.messages.list(thread_id=thread_id, limit=limit, order="asc")
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
                    image_content = self.openai_client.files.content(part.image_file.file_id)
                    data_in_bytes = image_content.read()
                    readable_buffer = io.BytesIO(data_in_bytes)
                    img_src = 'data:image/png;base64,' + base64.b64encode(readable_buffer.getvalue()).decode('utf-8')
                    # data_in_bytes = response_content.read()
                    # readable_buffer = io.BytesIO(data_in_bytes)
                    # image = Image.open(readable_buffer)
                    response_msgs.append(BondMessage(thread_id=thread_id, message_id=part_id, type=part.type, role=message.role, content=img_src))
                part_idx += 1
        return {message.message_id: message for message in response_msgs}