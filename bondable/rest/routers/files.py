from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
import logging
import openai

from bondable.bond.providers.provider import Provider
from bondable.rest.models.auth import User
from bondable.rest.models.files import FileUploadResponse, FileDeleteResponse, FileDetailsResponse
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/files", tags=["File Management"])
logger = logging.getLogger(__name__)

# Mime types that should use code_interpreter
CODE_INTERPRETER_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/x-excel",
    "application/x-msexcel",
    "text/tab-separated-values",
}

def get_suggested_tool(mime_type: str) -> str:
    """Determine the suggested tool based on mime type."""
    if mime_type in CODE_INTERPRETER_MIME_TYPES:
        return "code_interpreter"
    return "file_search"


@router.post("", response_model=FileUploadResponse)
async def upload_file(
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider),
    file: UploadFile = File(...)
):
    """Upload a file to be associated with agents."""
    try:
        file_content = await file.read()
        file_name = file.filename
        
        file_details = provider.files.get_or_create_file_id(
            user_id=current_user.email,
            file_tuple=(file_name, file_content)
        )
        
        suggested_tool = get_suggested_tool(file_details.mime_type)
        
        logger.info(f"File '{file_name}' processed for user {current_user.email}. Provider File ID: {file_details.file_id}, MIME type: {file_details.mime_type}, Suggested tool: {suggested_tool}")
        return FileUploadResponse(
            provider_file_id=file_details.file_id,
            file_name=file_name,
            mime_type=file_details.mime_type,
            suggested_tool=suggested_tool,
            message="File processed successfully."
        )
        
    except openai.APIError as e:
        logger.error(f"File provider API error while uploading file '{file.filename}' for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"File provider error: {str(e)}")
    except Exception as e:
        logger.error(f"Error uploading file '{file.filename}' for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not process file: {str(e)}")


@router.delete("/{provider_file_id}", response_model=FileDeleteResponse)
async def delete_file(
    provider_file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Delete a file from the provider and local metadata."""
    try:
        success = provider.files.delete_file(file_id=provider_file_id)
        
        if success:
            logger.info(f"File {provider_file_id} deletion process completed by user {current_user.email}.")
            return FileDeleteResponse(
                provider_file_id=provider_file_id,
                status="deleted",
                message="File deletion process completed."
            )
        else:
            logger.warning(f"File {provider_file_id} not found in local records for deletion by user {current_user.email}.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in local records."
            )

    except openai.APIError as e:
        logger.error(f"File provider API Error while deleting file {provider_file_id} for user {current_user.email}: {e}", exc_info=True)
        if hasattr(e, 'status_code') and e.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found with provider: {provider_file_id}"
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"File provider API error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting file {provider_file_id} for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not delete file: {str(e)}")


@router.get("/details", response_model=List[FileDetailsResponse])
async def get_file_details(
    file_ids: List[str] = Query(..., description="List of file IDs to get details for"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    provider: Provider = Depends(get_bond_provider)
):
    """Get file details for a list of file IDs."""
    # TODO: we should make sure that the file_ids belong to the current user
    try:
        file_details_list = provider.files.get_file_details(file_ids)
        
        # Filter to only return files owned by the current user for security
        user_files = [
            details for details in file_details_list 
            if details.owner_user_id == current_user.email
        ]
        
        logger.info(f"Retrieved {len(user_files)} file details for user {current_user.email}")
        
        return [
            FileDetailsResponse(
                file_id=details.file_id,
                file_path=details.file_path,
                file_hash=details.file_hash,
                mime_type=details.mime_type,
                owner_user_id=details.owner_user_id
            )
            for details in user_files
        ]
        
    except Exception as e:
        logger.error(f"Error retrieving file details for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not retrieve file details: {str(e)}")