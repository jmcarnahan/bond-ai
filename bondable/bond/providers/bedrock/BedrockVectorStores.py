"""
Bedrock Vector Stores Provider Implementation

Provides vector store functionality using AWS Bedrock Knowledge Bases.
Supports both 'direct' mode (5-file limit) and 'knowledge_base' mode (unlimited).
"""

import os
import uuid
import json
import time
from typing import Optional, List, Dict, Any
from bondable.bond.providers.vectorstores import VectorStoresProvider
import logging
from typing_extensions import override
from bondable.bond.providers.bedrock.BedrockMetadata import BedrockVectorStoreFile, KnowledgeBaseFile

LOGGER = logging.getLogger(__name__)


class BedrockVectorStoresProvider(VectorStoresProvider):
    """
    Vector store provider using AWS Bedrock Knowledge Bases.

    Supports two modes:
    - 'direct': Files attached directly to agents (5-file limit)
    - 'knowledge_base': Files stored in Bedrock KB via S3 (unlimited)
    """

    def __init__(self, metadata_provider, s3_client=None, bedrock_agent_client=None, bedrock_agent_runtime_client=None):
        """Initialize with metadata provider and optional AWS clients"""
        self.metadata = metadata_provider
        self.files_provider = None  # Will be set by BedrockProvider

        # AWS clients (injected by BedrockProvider)
        self.s3_client = s3_client
        self.bedrock_agent_client = bedrock_agent_client
        self.bedrock_agent_runtime_client = bedrock_agent_runtime_client

        # Knowledge Base configuration from environment
        self.knowledge_base_id = os.getenv('BEDROCK_KNOWLEDGE_BASE_ID', '')
        self.data_source_id = os.getenv('BEDROCK_KB_DATA_SOURCE_ID', '')
        self.kb_s3_prefix = os.getenv('BEDROCK_KB_S3_PREFIX', 'knowledge-base/')
        self.s3_bucket_name = os.getenv('S3_BUCKET_NAME', '')

        # KB is enabled if we have a knowledge base ID
        self.kb_enabled = bool(self.knowledge_base_id)

        if self.kb_enabled:
            LOGGER.info(f"Initialized BedrockVectorStoresProvider with Knowledge Base: {self.knowledge_base_id}")
        else:
            LOGGER.info("Initialized BedrockVectorStoresProvider (Knowledge Base disabled)")

    def get_files_provider(self):
        """Returns the files provider instance."""
        return self.files_provider

    # =====================================================
    # Knowledge Base Methods
    # =====================================================

    def is_kb_enabled(self) -> bool:
        """Check if Knowledge Base functionality is enabled"""
        return self.kb_enabled and self.s3_client is not None

    def upload_file_to_knowledge_base(
        self,
        file_id: str,
        agent_id: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str
    ) -> Optional[str]:
        """
        Upload a file to S3 for Knowledge Base ingestion.

        Args:
            file_id: The file ID from the files table
            agent_id: The agent ID this file belongs to
            file_bytes: Raw file content
            file_name: Original file name
            mime_type: MIME type of the file

        Returns:
            S3 key of uploaded file, or None if failed
        """
        LOGGER.debug(f"[KB VectorStore] upload_file_to_knowledge_base called for file_id={file_id}, agent_id={agent_id}, file_name={file_name}")

        if not self.is_kb_enabled():
            LOGGER.warning("[KB VectorStore] Knowledge Base not enabled, cannot upload file")
            return None

        if not self.s3_bucket_name:
            LOGGER.error("[KB VectorStore] S3_BUCKET_NAME not configured")
            return None

        LOGGER.debug(f"[KB VectorStore] Using bucket: {self.s3_bucket_name}, KB prefix: {self.kb_s3_prefix}")

        try:
            # Create S3 key: knowledge-base/{agent_id}/{uuid}/{filename}
            file_uuid = str(uuid.uuid4())
            s3_key = f"{self.kb_s3_prefix}{agent_id}/{file_uuid}/{file_name}"
            LOGGER.debug(f"[KB VectorStore] Uploading to S3 key: {s3_key}")

            # Upload file to S3
            self.s3_client.put_object(
                Bucket=self.s3_bucket_name,
                Key=s3_key,
                Body=file_bytes,
                ContentType=mime_type
            )
            LOGGER.debug(f"[KB VectorStore] SUCCESS - Uploaded file to S3: s3://{self.s3_bucket_name}/{s3_key}")

            # Create metadata.json for filtering (required by Bedrock KB)
            # IMPORTANT: Only include attributes that have corresponding columns in Aurora
            # Aurora KB columns: id, embedding, chunks, metadata, agent_id, file_id, file_name
            # Do NOT include attributes like mime_type, uploaded_at unless columns exist
            metadata = {
                "metadataAttributes": {
                    "agent_id": agent_id,
                    "file_id": file_id,
                    "file_name": file_name
                }
            }
            metadata_key = f"{self.kb_s3_prefix}{agent_id}/{file_uuid}/{file_name}.metadata.json"
            LOGGER.debug(f"[KB VectorStore] Uploading metadata to: {metadata_key}")
            LOGGER.debug(f"[KB VectorStore] Metadata content: {json.dumps(metadata)}")
            self.s3_client.put_object(
                Bucket=self.s3_bucket_name,
                Key=metadata_key,
                Body=json.dumps(metadata),
                ContentType='application/json'
            )
            LOGGER.debug(f"[KB VectorStore] SUCCESS - Uploaded metadata to S3: s3://{self.s3_bucket_name}/{metadata_key}")

            # Track in KnowledgeBaseFile table
            session = self.metadata.get_db_session()
            try:
                # Check if record already exists (defensive - caller should check first)
                existing = session.query(KnowledgeBaseFile).filter(
                    KnowledgeBaseFile.file_id == file_id,
                    KnowledgeBaseFile.agent_id == agent_id
                ).first()
                if existing:
                    LOGGER.debug(f"KnowledgeBaseFile already exists for file {file_id}, agent {agent_id} - returning existing S3 key")
                    return existing.s3_key

                kb_file = KnowledgeBaseFile(
                    file_id=file_id,
                    agent_id=agent_id,
                    s3_key=s3_key,
                    ingestion_status='pending'
                )
                session.add(kb_file)
                session.commit()
                LOGGER.info(f"Created KnowledgeBaseFile record for file {file_id}")
            except Exception as e:
                session.rollback()
                LOGGER.error(f"Error creating KnowledgeBaseFile record: {e}")
                raise
            finally:
                session.close()

            return s3_key

        except Exception as e:
            LOGGER.error(f"Error uploading file to Knowledge Base: {e}", exc_info=True)
            return None

    def trigger_ingestion_job(
        self,
        agent_id: Optional[str] = None,
        wait_for_completion: bool = False,
        timeout_seconds: int = 600
    ) -> Optional[Dict[str, Any]]:
        """
        Start a Knowledge Base ingestion job.

        This syncs all changes from S3 to the Knowledge Base:
        - New files are indexed
        - Modified files are re-indexed
        - Deleted files (missing from S3) are removed from KB

        Args:
            agent_id: Optional agent ID to filter pending files (for logging)
            wait_for_completion: If True, poll until job completes
            timeout_seconds: Max time to wait if waiting for completion

        Returns:
            Dict with 'job_id' and 'status' (and 'statistics' if waited), or None if failed
        """
        LOGGER.debug(f"[KB Ingestion] trigger_ingestion_job called for agent_id={agent_id}")

        if not self.is_kb_enabled():
            LOGGER.warning("[KB Ingestion] Knowledge Base not enabled, cannot trigger ingestion")
            return None

        if not self.bedrock_agent_client:
            LOGGER.error("[KB Ingestion] Bedrock agent client not available")
            return None

        LOGGER.debug(f"[KB Ingestion] Starting ingestion for KB={self.knowledge_base_id}, DataSource={self.data_source_id}")

        try:
            # Start ingestion job
            response = self.bedrock_agent_client.start_ingestion_job(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
                description=f"Ingestion for agent {agent_id}" if agent_id else "Manual ingestion"
            )

            job_id = response.get('ingestionJob', {}).get('ingestionJobId')
            status = response.get('ingestionJob', {}).get('status')
            if not job_id:
                LOGGER.error("[KB Ingestion] No ingestion job ID in response")
                return None

            LOGGER.debug(f"[KB Ingestion] SUCCESS - Started ingestion job: {job_id}, initial status: {status}")

            # Update KnowledgeBaseFile records with job ID
            if agent_id:
                session = self.metadata.get_db_session()
                try:
                    session.query(KnowledgeBaseFile).filter(
                        KnowledgeBaseFile.agent_id == agent_id,
                        KnowledgeBaseFile.ingestion_status == 'pending'
                    ).update({
                        'ingestion_job_id': job_id,
                        'ingestion_status': 'in_progress'
                    })
                    session.commit()
                except Exception as e:
                    session.rollback()
                    LOGGER.error(f"Error updating KnowledgeBaseFile records: {e}")
                finally:
                    session.close()

            # Return immediately if not waiting
            if not wait_for_completion:
                return {'job_id': job_id, 'status': status}

            # Wait for completion and return full result with stats
            return self.wait_for_ingestion_job(job_id, timeout_seconds)

        except Exception as e:
            LOGGER.error(f"Error starting ingestion job: {e}", exc_info=True)
            return None

    def get_ingestion_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of an ingestion job.

        Args:
            job_id: The ingestion job ID

        Returns:
            Job status dict with 'status', 'statistics', etc.
        """
        if not self.bedrock_agent_client:
            return None

        try:
            response = self.bedrock_agent_client.get_ingestion_job(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
                ingestionJobId=job_id
            )

            job = response.get('ingestionJob', {})
            return {
                'job_id': job.get('ingestionJobId'),
                'status': job.get('status'),  # STARTING, IN_PROGRESS, COMPLETE, FAILED
                'statistics': job.get('statistics', {}),
                'failure_reasons': job.get('failureReasons', [])
            }
        except Exception as e:
            LOGGER.error(f"Error getting ingestion job status: {e}")
            return None

    def _log_ingestion_results(self, result: Dict[str, Any]) -> None:
        """Log detailed statistics from an ingestion job."""
        status = result.get('status', 'UNKNOWN')
        stats = result.get('statistics', {})
        job_id = result.get('job_id', 'unknown')

        LOGGER.info(f"Ingestion job {job_id} completed: {status}")
        LOGGER.info(f"  Scanned:  {stats.get('numberOfDocumentsScanned', 0)} docs, "
                    f"{stats.get('numberOfMetadataDocumentsScanned', 0)} metadata files")
        LOGGER.info(f"  Added:    {stats.get('numberOfNewDocumentsIndexed', 0)}")
        LOGGER.info(f"  Modified: {stats.get('numberOfModifiedDocumentsIndexed', 0)}")
        LOGGER.info(f"  Deleted:  {stats.get('numberOfDocumentsDeleted', 0)}")
        LOGGER.info(f"  Failed:   {stats.get('numberOfDocumentsFailed', 0)}")

        if result.get('failure_reasons'):
            for reason in result['failure_reasons']:
                LOGGER.error(f"  Failure: {reason}")

    def wait_for_ingestion_job(
        self,
        job_id: str,
        timeout_seconds: int = 600,
        poll_interval_seconds: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for an ingestion job to complete by polling.

        Args:
            job_id: The ingestion job ID
            timeout_seconds: Maximum time to wait (default 10 minutes)
            poll_interval_seconds: Time between status checks

        Returns:
            Final job status dict with statistics, or None if timeout/error
        """
        if not self.bedrock_agent_client:
            LOGGER.error("Bedrock agent client not available")
            return None

        start_time = time.time()
        terminal_states = {'COMPLETE', 'FAILED', 'STOPPED'}

        LOGGER.info(f"Waiting for ingestion job {job_id} to complete (timeout: {timeout_seconds}s)...")

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                LOGGER.warning(f"Ingestion job {job_id} timed out after {timeout_seconds}s")
                return None

            try:
                response = self.bedrock_agent_client.get_ingestion_job(
                    knowledgeBaseId=self.knowledge_base_id,
                    dataSourceId=self.data_source_id,
                    ingestionJobId=job_id
                )

                job = response.get('ingestionJob', {})
                status = job.get('status')

                LOGGER.debug(f"Ingestion job {job_id} status: {status} (elapsed: {int(elapsed)}s)")

                if status in terminal_states:
                    result = {
                        'job_id': job.get('ingestionJobId'),
                        'status': status,
                        'statistics': job.get('statistics', {}),
                        'failure_reasons': job.get('failureReasons', []),
                        'started_at': job.get('startedAt'),
                        'updated_at': job.get('updatedAt')
                    }
                    self._log_ingestion_results(result)
                    return result

                time.sleep(poll_interval_seconds)

            except Exception as e:
                LOGGER.error(f"Error polling ingestion job status: {e}")
                return None

    def query_knowledge_base(
        self,
        query: str,
        agent_id: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query the Knowledge Base for relevant documents.

        Args:
            query: The search query
            agent_id: Agent ID to filter results
            max_results: Maximum number of results to return

        Returns:
            List of document chunks with content and metadata
        """
        if not self.is_kb_enabled():
            LOGGER.debug("Knowledge Base not enabled, returning empty results")
            return []

        if not self.bedrock_agent_runtime_client:
            LOGGER.error("Bedrock agent runtime client not available")
            return []

        try:
            # Build retrieve params with agent_id metadata filter
            retrieve_params = {
                'knowledgeBaseId': self.knowledge_base_id,
                'retrievalQuery': {
                    'text': query
                },
                'retrievalConfiguration': {
                    'vectorSearchConfiguration': {
                        'numberOfResults': max_results,
                        'filter': {
                            'equals': {
                                'key': 'agent_id',
                                'value': agent_id
                            }
                        }
                    }
                }
            }

            LOGGER.debug(f"Querying KB {self.knowledge_base_id} for agent {agent_id}: '{query[:50]}...'")
            response = self.bedrock_agent_runtime_client.retrieve(**retrieve_params)

            results = []
            for result in response.get('retrievalResults', []):
                content = result.get('content', {}).get('text', '')
                metadata = result.get('metadata', {})
                location = result.get('location', {})
                score = result.get('score', 0.0)

                results.append({
                    'content': content,
                    'metadata': metadata,
                    'location': location,
                    'score': score
                })

            LOGGER.debug(f"KB query returned {len(results)} results for agent {agent_id}")
            return results

        except Exception as e:
            LOGGER.error(f"Error querying Knowledge Base: {e}", exc_info=True)
            return []

    def remove_file_from_knowledge_base(self, file_id: str, agent_id: str) -> bool:
        """
        Remove a file from the Knowledge Base.

        This method:
        1. Deletes the S3 objects (file + metadata)
        2. Removes the tracking record from our database

        The actual KB removal happens when start_ingestion_job runs - it detects
        that the S3 file is gone and removes it from the vector store (incremental sync).

        Args:
            file_id: The file ID to remove
            agent_id: The agent ID

        Returns:
            True if successful, False otherwise
        """
        if not self.is_kb_enabled():
            LOGGER.warning("Knowledge Base not enabled")
            return False

        session = self.metadata.get_db_session()
        try:
            # Get the KB file record
            kb_file = session.query(KnowledgeBaseFile).filter(
                KnowledgeBaseFile.file_id == file_id,
                KnowledgeBaseFile.agent_id == agent_id
            ).first()

            if not kb_file:
                LOGGER.warning(f"KnowledgeBaseFile not found for file {file_id}, agent {agent_id}")
                return True  # Already removed

            s3_key = kb_file.s3_key

            # Step 1: Delete from S3 (this triggers removal from KB on next ingestion sync)
            if self.s3_client and self.s3_bucket_name:
                try:
                    # Delete the file
                    self.s3_client.delete_object(
                        Bucket=self.s3_bucket_name,
                        Key=s3_key
                    )
                    # Delete the metadata file
                    metadata_key = f"{s3_key}.metadata.json"
                    self.s3_client.delete_object(
                        Bucket=self.s3_bucket_name,
                        Key=metadata_key
                    )
                    LOGGER.info(f"Deleted S3 objects: {s3_key}")
                except Exception as e:
                    LOGGER.error(f"Error deleting S3 objects: {e}")
                    # Continue to delete DB record anyway

            # Step 2: Delete from our database
            session.delete(kb_file)
            session.commit()
            LOGGER.info(f"Removed KnowledgeBaseFile record for file {file_id}")

            return True

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error removing file from Knowledge Base: {e}", exc_info=True)
            return False
        finally:
            session.close()

    def get_agent_kb_files(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Get all Knowledge Base files for an agent.

        Args:
            agent_id: The agent ID

        Returns:
            List of KB file records
        """
        session = self.metadata.get_db_session()
        try:
            kb_files = session.query(KnowledgeBaseFile).filter(
                KnowledgeBaseFile.agent_id == agent_id
            ).all()

            return [
                {
                    'id': f.id,
                    'file_id': f.file_id,
                    'agent_id': f.agent_id,
                    's3_key': f.s3_key,
                    'ingestion_job_id': f.ingestion_job_id,
                    'ingestion_status': f.ingestion_status,
                    'created_at': f.created_at.isoformat() if f.created_at else None,
                    'updated_at': f.updated_at.isoformat() if f.updated_at else None
                }
                for f in kb_files
            ]
        finally:
            session.close()

    def get_agent_kb_file_ids(self, agent_id: str) -> set:
        """
        Get set of file_ids already in KB for an agent.

        Args:
            agent_id: The agent ID

        Returns:
            Set of file_ids in the KB for this agent
        """
        session = self.metadata.get_db_session()
        try:
            kb_files = session.query(KnowledgeBaseFile.file_id).filter(
                KnowledgeBaseFile.agent_id == agent_id
            ).all()
            return {f.file_id for f in kb_files}
        finally:
            session.close()

    def update_ingestion_status(self, agent_id: str, job_id: str, status: str) -> None:
        """
        Update ingestion status for files with a given job ID.

        Args:
            agent_id: The agent ID
            job_id: The ingestion job ID
            status: New status (completed, failed, etc.)
        """
        session = self.metadata.get_db_session()
        try:
            session.query(KnowledgeBaseFile).filter(
                KnowledgeBaseFile.agent_id == agent_id,
                KnowledgeBaseFile.ingestion_job_id == job_id
            ).update({'ingestion_status': status})
            session.commit()
            LOGGER.info(f"Updated ingestion status to {status} for job {job_id}")
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Error updating ingestion status: {e}")
        finally:
            session.close()

    # =====================================================
    # Original Vector Store Methods (for 'direct' mode)
    # =====================================================
    # NOTE: update_vector_store_file_ids is NOT overridden here.
    # The base class VectorStoresProvider.update_vector_store_file_ids handles
    # both adding new files AND removing files that are no longer in the list.

    @override
    def delete_vector_store_resource(self, vector_store_id: str) -> bool:
        """
        Delete vector store resource.
        The parent class handles database cleanup.
        """
        session = self.metadata.get_db_session()
        try:
            deleted_rows_count = session.query(BedrockVectorStoreFile).filter(
                BedrockVectorStoreFile.vector_store_id == vector_store_id
            ).delete()
            session.commit()
            LOGGER.info(f"Deleted {deleted_rows_count} mappings for vector store {vector_store_id}")
        except Exception as e:
            LOGGER.error(f"Error deleting vector store resource {vector_store_id}: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

        return True

    @override
    def create_vector_store_resource(self, name: str) -> str:
        """Create a vector store."""
        vector_store_id = f"bedrock_vs_{uuid.uuid4()}"
        LOGGER.debug(f"Created vector store {vector_store_id} with name {name}")
        return vector_store_id

    @override
    def add_vector_store_file(self, vector_store_id: str, file_id: str) -> bool:
        """Add a file to a vector store."""
        session = self.metadata.get_db_session()
        try:
            # Check if the mapping already exists
            existing_mapping = session.query(BedrockVectorStoreFile).filter_by(
                vector_store_id=vector_store_id, file_id=file_id
            ).first()
            if existing_mapping:
                LOGGER.debug(f"Mapping already exists for vector store {vector_store_id} and file {file_id}")
                return True

            # Create a new mapping
            new_mapping = BedrockVectorStoreFile(
                vector_store_id=vector_store_id,
                file_id=file_id
            )
            session.add(new_mapping)
            session.commit()
            LOGGER.info(f"Added file {file_id} to vector store {vector_store_id}")
        except Exception as e:
            LOGGER.error(f"Error adding file {file_id} to vector store {vector_store_id}: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

        return True

    @override
    def remove_vector_store_file(self, vector_store_id: str, file_id: str) -> bool:
        """Remove a file from a vector store."""
        session = self.metadata.get_db_session()
        try:
            deleted_rows_count = session.query(BedrockVectorStoreFile).filter(
                BedrockVectorStoreFile.vector_store_id == vector_store_id,
                BedrockVectorStoreFile.file_id == file_id
            ).delete()
            session.commit()
            if deleted_rows_count > 0:
                LOGGER.info(f"Removed file {file_id} from vector store {vector_store_id}")
            else:
                LOGGER.warning(f"No mapping found for vector store {vector_store_id} and file {file_id}")
        except Exception as e:
            LOGGER.error(f"Error removing file {file_id} from vector store {vector_store_id}: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

        return True

    @override
    def get_vector_store_file_ids(self, vector_store_id: str) -> List[str]:
        """Get list of file IDs in a vector store."""
        with self.metadata.get_db_session() as session:
            file_ids = session.query(BedrockVectorStoreFile.file_id).filter(
                BedrockVectorStoreFile.vector_store_id == vector_store_id
            ).all()
            if file_ids:
                return [file_id[0] for file_id in file_ids]
            LOGGER.debug(f"No files found for vector store {vector_store_id}")

        return []
