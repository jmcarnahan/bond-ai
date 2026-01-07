
from bondable.bond.providers.files import FilesProvider
from bondable.bond.providers.openai.OAIAMetadata import OAIAMetadata
from bondable.bond.config import Config
import openai
import io
import logging
from typing_extensions import override
from bondable.bond.cache import bond_cache
LOGGER = logging.getLogger(__name__)



class OAIAFilesProvider(FilesProvider):

    def __init__(self, openai_client, metadata):
        super().__init__(metadata=metadata)
        self.openai_client = openai_client

    # @classmethod
    # @bond_cache
    # def provider(cls) -> FilesProvider:
    #     return OAIAFilesProvider()

    @override
    def delete_file_resource(self, file_id: str) -> bool:
        """
        Deletes a file by its file_id.
        """
        try:
            self.openai_client.files.delete(file_id)
            LOGGER.info(f"Successfully deleted file {file_id} from provider.")
            return True
        except openai.NotFoundError:
            LOGGER.warning(f"File {file_id} not found on provider. Considered 'deleted' for provider part.")
            return False
        except Exception as e:
            LOGGER.error(f"Error deleting file {file_id} from provider: {e}", exc_info=True)
            raise e

    @override
    def create_file_resource(self, file_path: str, file_bytes: io.BytesIO) -> str:
        """
        Creates a new file.
        Returns the file_id of the created file.
        """
        try:
            openai_file = self.openai_client.files.create(
                file=(file_path, file_bytes),
                purpose='assistants'
            )
            file_id = openai_file.id
            LOGGER.info(f"Successfully uploaded '{file_path}' to OpenAI. File ID: {file_id}")
            return file_id
        except Exception as e:
            LOGGER.error(f"Error uploading file '{file_path}' to OpenAI: {e}")
            raise e
