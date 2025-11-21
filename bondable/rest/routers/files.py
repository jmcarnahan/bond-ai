from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from fastapi.responses import StreamingResponse
import logging
import openai
import io

from bondable.bond.providers.provider import Provider
from bondable.rest.models.auth import User
from bondable.rest.models.files import FileUploadResponse, FileDeleteResponse, FileDetailsResponse
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/files", tags=["File Management"])
LOGGER = logging.getLogger(__name__)

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
            user_id=current_user.user_id,
            file_tuple=(file_name, file_content)
        )
        
        suggested_tool = get_suggested_tool(file_details.mime_type)
        
        LOGGER.info(f"File '{file_name}' processed for user {current_user.user_id} ({current_user.email}). Provider File ID: {file_details.file_id}, MIME type: {file_details.mime_type}, Suggested tool: {suggested_tool}")
        return FileUploadResponse(
            provider_file_id=file_details.file_id,
            file_name=file_name,
            mime_type=file_details.mime_type,
            suggested_tool=suggested_tool,
            message="File processed successfully."
        )
        
    except openai.APIError as e:
        LOGGER.error(f"File provider API error while uploading file '{file.filename}' for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"File provider error: {str(e)}")
    except Exception as e:
        LOGGER.error(f"Error uploading file '{file.filename}' for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
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
            LOGGER.info(f"File {provider_file_id} deletion process completed by user {current_user.user_id} ({current_user.email}).")
            return FileDeleteResponse(
                provider_file_id=provider_file_id,
                status="deleted",
                message="File deletion process completed."
            )
        else:
            LOGGER.warning(f"File {provider_file_id} not found in local records for deletion by user {current_user.user_id} ({current_user.email}).")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in local records."
            )

    except openai.APIError as e:
        LOGGER.error(f"File provider API Error while deleting file {provider_file_id} for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        if hasattr(e, 'status_code') and e.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found with provider: {provider_file_id}"
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"File provider API error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Unexpected error deleting file {provider_file_id} for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
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
            if details.owner_user_id == current_user.user_id
        ]
        
        LOGGER.info(f"Retrieved {len(user_files)} file details for user {current_user.user_id} ({current_user.email})")
        
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
        LOGGER.error(f"Error retrieving file details for user {current_user.user_id} ({current_user.email}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not retrieve file details: {str(e)}")


@router.get("/download/{file_id:path}")
async def download_file(
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Provider = Depends(get_bond_provider)
):
    """Download a file by its ID. Verifies user has access to the file."""
    try:
        # Get file details to verify ownership and get metadata
        file_details_list = provider.files.get_file_details([file_id])

        if not file_details_list:
            LOGGER.warning(f"File {file_id} not found for download request by user {current_user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        file_details = file_details_list[0]

        # Verify the user owns this file or has access to it
        if file_details.owner_user_id != current_user.user_id:
            LOGGER.warning(
                f"User {current_user.user_id} attempted to download file {file_id} "
                f"owned by {file_details.owner_user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this file"
            )

        # Get file bytes from S3
        file_bytes_io = provider.files.get_file_bytes((file_id, None))

        # Get the original filename from file_path
        filename = file_details.file_path

        LOGGER.info(
            f"Streaming file {file_id} ({filename}) to user {current_user.user_id} "
            f"({current_user.email}), size: {file_details.file_size} bytes"
        )

        # Stream the file with proper headers
        return StreamingResponse(
            file_bytes_io,
            media_type=file_details.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(file_details.file_size) if file_details.file_size else None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(
            f"Error downloading file {file_id} for user {current_user.user_id} "
            f"({current_user.email}): {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not download file: {str(e)}"
        )