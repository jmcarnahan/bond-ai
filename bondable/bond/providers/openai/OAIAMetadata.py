from bondable.bond.providers.metadata import Metadata
from bondable.bond.cache import bond_cache

class OAIAMetadata(Metadata):
    
    def __init__(self, metadata_db_url):
        super().__init__(metadata_db_url=metadata_db_url)

    # @classmethod
    # @bond_cache
    # def metadata(cls, metadata_db_url) -> Metadata:
    #     return OAIAMetadata(metadata_db_url=metadata_db_url)
    
