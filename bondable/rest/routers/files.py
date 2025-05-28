from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
import logging
import openai

from bondable.bond.providers.provider import Provider
from bondable.rest.models.auth import User
from bondable.rest.models.files import FileUploadResponse, FileDeleteResponse
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider

router = APIRouter(prefix="/files", tags=["File Management"])
logger = logging.getLogger(__name__)


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
        
        provider_file_id = provider.files.get_or_create_file_id(
            user_id=current_user.email,
            file_tuple=(file_name, file_content)
        )
        
        logger.info(f"File '{file_name}' processed for user {current_user.email}. Provider File ID: {provider_file_id}")
        return FileUploadResponse(
            provider_file_id=provider_file_id,
            file_name=file_name,
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