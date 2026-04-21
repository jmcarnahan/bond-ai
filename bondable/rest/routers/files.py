from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from fastapi.responses import StreamingResponse
import logging
import openai
import io
import os
import re

from bondable.bond.providers.provider import Provider
from bondable.bond.providers.files import to_opaque_id as _to_opaque_id  # re-export for backward compat
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

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {
    # Documents
    '.txt', '.md', '.html', '.htm', '.pdf',
    '.doc', '.docx', '.rtf',
    # Spreadsheets
    '.csv', '.tsv', '.xls', '.xlsx',
    # Presentations
    '.ppt', '.pptx',
    # Data
    '.json', '.yaml', '.yml', '.xml',
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.webp',
}

# Dangerous file extensions that are always blocked (defense-in-depth)
BLOCKED_EXTENSIONS = {
    '.exe', '.dll', '.so', '.dylib', '.bat', '.cmd', '.sh', '.bash',
    '.ps1', '.vbs', '.msi', '.com', '.scr', '.pif', '.jar', '.app',
}


def _resolve_file_id(file_id: str, provider) -> str:
    """Resolve an opaque file ID to the full S3 URI.

    Accepts both formats for backward compatibility:
    - Full S3 URI (s3://...) -- validated to match the configured bucket
    - Opaque ID (bond_file_xxx) -- reconstructed to full S3 URI
    """
    if file_id.startswith('s3://'):
        # Validate the S3 URI points to the configured bucket (prevent cross-bucket access)
        expected_prefix = f"s3://{provider.files.bucket_name}/"
        if not file_id.startswith(expected_prefix):
            raise ValueError(f"Invalid file ID: references unauthorized bucket")
        return file_id
    if not re.match(r'^bond_file_[0-9a-f]+$', file_id):
        raise ValueError(f"Invalid file ID format: {file_id}")
    return f"s3://{provider.files.bucket_name}/files/{file_id}"


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

        # Validate file extension
        ext = os.path.splitext(file_name)[1].lower() if file_name else ''
        if ext in BLOCKED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File type '{ext}' is not allowed. Executable and script files cannot be uploaded."
            )
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File type '{ext}' is not supported. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        file_details = provider.files.get_or_create_file_id(
            user_id=current_user.user_id,
            file_tuple=(file_name, file_content)
        )

        suggested_tool = get_suggested_tool(file_details.mime_type)

        LOGGER.info(f"File '{file_name}' processed for user {current_user.user_id} ({current_user.email}). Provider File ID: {file_details.file_id}, MIME type: {file_details.mime_type}, Suggested tool: {suggested_tool}")
        return FileUploadResponse(
            provider_file_id=_to_opaque_id(file_details.file_id),
            file_name=file_name,
            mime_type=file_details.mime_type,
            suggested_tool=suggested_tool,
            message="File processed successfully."
        )

    except HTTPException:
        raise
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
        # Resolve opaque ID to full S3 URI for internal use
        try:
            resolved_id = _resolve_file_id(provider_file_id, provider)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file ID format")

        # T15: Verify ownership at query level (defense-in-depth)
        file_details_list = provider.files.get_file_details([resolved_id], user_id=current_user.user_id)
        if not file_details_list:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        file_details = file_details_list[0]
        if file_details.owner_user_id != current_user.user_id:
            LOGGER.warning(
                f"User {current_user.user_id} attempted to delete file {resolved_id} "
                f"owned by {file_details.owner_user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this file"
            )

        success = provider.files.delete_file(file_id=resolved_id)

        if success:
            LOGGER.info(f"File {resolved_id} deletion process completed by user {current_user.user_id} ({current_user.email}).")
            return FileDeleteResponse(
                provider_file_id=_to_opaque_id(resolved_id),
                status="deleted",
                message="File deletion process completed."
            )
        else:
            LOGGER.warning(f"File {resolved_id} not found in local records for deletion by user {current_user.user_id} ({current_user.email}).")
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
    try:
        # Resolve opaque IDs to full S3 URIs for internal use
        resolved_ids = []
        for fid in file_ids:
            try:
                resolved_ids.append(_resolve_file_id(fid, provider))
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid file ID format: {fid}")

        # T15: Filter at ORM query level (defense-in-depth, not just router filtering)
        user_files = provider.files.get_file_details(resolved_ids, user_id=current_user.user_id)

        LOGGER.info(f"Retrieved {len(user_files)} file details for user {current_user.user_id} ({current_user.email})")

        return [
            FileDetailsResponse(
                file_id=_to_opaque_id(details.file_id),
                file_path=details.file_path,
                file_hash=details.file_hash,
                mime_type=details.mime_type,
                owner_user_id=details.owner_user_id
            )
            for details in user_files
        ]

    except HTTPException:
        raise
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
        # Resolve opaque ID to full S3 URI for internal use
        try:
            resolved_id = _resolve_file_id(file_id, provider)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file ID format")

        # T15: Get file details with user_id filter (defense-in-depth)
        file_details_list = provider.files.get_file_details([resolved_id], user_id=current_user.user_id)

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
        file_bytes_io = provider.files.get_file_bytes((resolved_id, None))

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
