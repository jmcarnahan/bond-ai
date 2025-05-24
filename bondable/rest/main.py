import os
from typing import Union, Optional, Annotated # Added Annotated
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, status, Request, File, UploadFile # Added File, UploadFile
from fastapi.security import OAuth2PasswordBearer # Added
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from bondable.bond.auth import GoogleAuth
from bondable.bond.agent import Agent
from bondable.bond.builder import AgentBuilder # Added
from bondable.bond.definition import AgentDefinition # Added
from bondable.bond.threads import Threads
from bondable.bond.metadata import Metadata # Added Metadata
from bondable.bond.config import Config
from pydantic import BaseModel, Field # Added Field
from typing import List, Dict, Any # Added for Pydantic models
import logging
import openai # For specific exception handling if needed from metadata

# Load environment variables (if using .env file)
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
load_dotenv()

# --- Configuration ---
jwt_config = Config.config().get_jwt_config()

# --- Logging ---
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,  # Important to avoid interfering with uvicorn's loggers
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["default"],
    },
    "loggers": {
        "uvicorn": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False,  # prevents it from going to the root logger again
        },
        "uvicorn.error": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False,
        },
        "uvicorn.access": {
            "level": "WARNING",  # optional: suppress overly verbose access logs
            "handlers": ["default"],
            "propagate": False,
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
LOGGER = logging.getLogger(__name__)


# --- FastAPI App ---
app = FastAPI()

# --- CORS Middleware ---
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost",         # Allow localhost (any port)
    "http://localhost:5000",    # Specifically allow Flutter dev server
    # Add any other origins your Flutter app might be served from (e.g., deployed URL)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # List of origins that are allowed to make cross-origin requests.
    allow_credentials=True, # Allows cookies to be included in cross-origin requests.
    allow_methods=["*"],    # Allows all methods (GET, POST, PUT, etc.).
    allow_headers=["*"],    # Allows all headers.
)
LOGGER.info("CORSMiddleware added to FastAPI app with origins: %s", origins)

# --- Pydantic Models ---
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel): # Added user model for dependency return type hint
    email: str
    name: Optional[str] = None

class AgentRef(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    model: Optional[str] = None
    tool_types: Optional[List[str]] = None
    created_at_display: Optional[str] = None
    sample_prompt: Optional[str] = None

class ThreadRef(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class CreateThreadRequest(BaseModel): # Model for the request body
    name: Optional[str] = None

class ChatRequest(BaseModel): # Model for the /chat POST request body
    thread_id: str
    agent_id: str
    prompt: str

class MessageRef(BaseModel):
    id: str
    type: str
    role: str
    content: str

# Updated/New Pydantic Models for Agent Details and Tool Resources
class AgentFileDetail(BaseModel):
    file_id: str
    file_name: str

class ToolResourceFilesList(BaseModel): # Replaces ToolResourceCodeInterpreterRequest and part of ToolResourceFileSearchRequest
    file_ids: List[str] = Field(default_factory=list)

class ToolResourcesResponse(BaseModel): # For GET /agents/{assistant_id}
    code_interpreter: Optional[ToolResourceFilesList] = None
    file_search: Optional[ToolResourceFilesList] = None

class AgentDetailResponse(BaseModel): # For GET /agents/{assistant_id}
    id: str
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_resources: Optional[ToolResourcesResponse] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ToolResourcesRequest(BaseModel): # For POST /agents and PUT /agents/{assistant_id}
    code_interpreter: Optional[ToolResourceFilesList] = None
    file_search: Optional[ToolResourceFilesList] = None # Client will send file_ids

class AgentCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_resources: Optional[ToolResourcesRequest] = None # Uses updated ToolResourcesRequest
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_resources: Optional[ToolResourcesRequest] = None # Uses updated ToolResourcesRequest
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentResponse(BaseModel):
    agent_id: str # Consider renaming to id for consistency with AgentDetailResponse
    name: str

class FileUploadResponse(BaseModel):
    provider_file_id: str
    file_name: str
    message: str

class FileDeleteResponse(BaseModel):
    provider_file_id: str
    status: str
    message: Optional[str] = None

# --- Security Schemes ---
# Point tokenUrl to an endpoint that *issues* tokens. /auth/google/callback does this,
# but OAuth2PasswordBearer expects a form submission. For documentation purposes,
# we can point it here or to a placeholder. The actual verification logic
# doesn't depend on this URL being functional in the bearer flow.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google/callback")


# --- JWT Helper Functions ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
    return encoded_jwt

# --- Dependency for Getting Current User ---
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """
    Dependency to verify JWT token and return user data.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, jwt_config.JWT_SECRET_KEY, algorithms=[jwt_config.JWT_ALGORITHM])
        email: str = payload.get("sub")
        name: Optional[str] = payload.get("name")
        if email is None:
            LOGGER.warning("Token payload missing 'sub' (email).")
            raise credentials_exception
        # Optional: Add checks for token expiration ('exp' claim is auto-verified by python-jose)
        # Optional: Fetch user from DB if needed, here we just return from token
        return User(email=email, name=name)
    except JWTError as e:
        LOGGER.error(f"JWT Error during token decode: {e}", exc_info=True)
        raise credentials_exception
    except Exception as e: # Catch any other unexpected errors
        LOGGER.error(f"Unexpected error during token validation: {e}", exc_info=True)
        raise credentials_exception


# --- Authentication Endpoints ---
@app.get("/login", tags=["Authentication"])
async def login():
    """
    Initiates the Google OAuth2 login flow by redirecting the user to Google.
    """
    try:
        auth = GoogleAuth.auth()
        authorization_url = auth.get_auth_url()
        LOGGER.info(f"Redirecting user to Google for authentication: {authorization_url}")
        # Use RedirectResponse for proper redirection
        return RedirectResponse(url=authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    except Exception as e:
        LOGGER.error(f"Error generating Google auth URL: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not initiate authentication flow.")

# @app.get("/auth/google/callback", response_model=Token, tags=["Authentication"])
@app.get("/auth/google/callback", tags=["Authentication"])
async def auth_callback(request: Request):
    """
    Callback endpoint for Google OAuth2. Google redirects here after user authentication.
    Receives the authorization code, exchanges it for user info, and returns a JWT.
    """
    auth_code = request.query_params.get('code')
    if not auth_code:
        LOGGER.error("Authorization code not found in callback request.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code missing.")

    try:
        auth = GoogleAuth.auth()
        user_info = auth.get_user_info_from_code(auth_code) # This handles fetching token and verifying
        LOGGER.info(f"Successfully authenticated user: {user_info.get('email')}")

        # Create JWT
        access_token_expires = timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_info.get("email"), "name": user_info.get("name")}, # Use email as subject
            expires_delta=access_token_expires
        )
        LOGGER.info(f"Generated JWT for user: {user_info.get('email')}")

        # return {"access_token": access_token, "token_type": "bearer"}

        # Flutter web uses hash routing by default, so '/#/auth-callback' so let's use this as a standard.
        flutter_redirect_url = f"{jwt_config.JWT_REDIRECT_URI}/#/auth-callback?token={access_token}"
        return RedirectResponse(url=flutter_redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


    except ValueError as e: # Specific error from GoogleAuth for invalid email
        LOGGER.error(f"Authentication failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        LOGGER.error(f"Error processing Google callback: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authentication failed.")

# --- Example Protected Endpoint ---
# Apply the dependency to protect this route
@app.get("/users/me", response_model=User, tags=["Users"])
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Protected endpoint that requires a valid JWT Bearer token.
    Returns the authenticated user's information.
    """
    LOGGER.info(f"Access granted to /users/me for user: {current_user.email}")
    return current_user

@app.get("/agents", response_model=list[AgentRef], tags=["Agent"])
async def get_agents(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Protected endpoint that requires a valid JWT Bearer token.
    Returns the list of agents for the authenticated user.
    """
    agents = Agent.list_agents(user_id=current_user.email)
    agent_refs = []
    for agent in agents:
        tool_types = []
        if agent.agent_def and agent.agent_def.tools:
            for tool in agent.agent_def.tools:
                if isinstance(tool, dict) and 'type' in tool:
                    tool_types.append(tool['type'])
                elif hasattr(tool, 'type'): # For OpenAI's ToolDefinition objects
                    tool_types.append(tool.type)
        
        created_at_timestamp = agent.get_created_at() # Assuming Agent class will have this method
        created_at_dt = datetime.fromtimestamp(created_at_timestamp, timezone.utc) if created_at_timestamp else None
        created_at_display_str = created_at_dt.strftime("%b %d, %Y") if created_at_dt else None

        sample_prompt_text = None
        if agent.metadata and isinstance(agent.metadata, dict):
            sample_prompt_text = agent.metadata.get("sample_prompt")

        agent_refs.append(AgentRef(
            id=agent.get_id(),
            name=agent.get_name(),
            description=agent.get_description(),
            model=agent.agent_def.model if agent.agent_def else None,
            tool_types=tool_types if tool_types else [], # Ensure it's a list or None
            created_at_display=created_at_display_str,
            sample_prompt=sample_prompt_text
        ))
    return agent_refs

@app.get("/threads", response_model=list[ThreadRef], tags=["Thread"])
async def get_threads(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Protected endpoint that requires a valid JWT Bearer token.
    Returns the list of threads for the authenticated user.
    """
    threads = Threads.threads(user_id=current_user.email).get_current_threads()
    thread_refs = [ThreadRef(id=thread['thread_id'], name=thread['name'], description=thread.get('description')) for thread in threads] # Added description
    return thread_refs

@app.post("/threads", response_model=ThreadRef, status_code=status.HTTP_201_CREATED, tags=["Thread"])
async def create_new_thread(
    request_body: CreateThreadRequest, # Accept request body
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Protected endpoint to create a new thread for the authenticated user.
    An optional 'name' can be provided in the request body.
    Returns the ID and details of the newly created thread.
    """
    try:
        threads = Threads.threads(user_id=current_user.email)
        # threads_service.create_thread now returns the ORM Thread object
        created_thread_orm = threads.create_thread(name=request_body.name)
        
        # The ORM object (created_thread_orm) will have the thread_id and the actual name
        # (either the one provided or the default from the DB, e.g., "New Thread").
        # No need for separate update_thread_name call or complex logic for thread_name_to_return.

        LOGGER.info(f"User {current_user.email} created new thread with ID: {created_thread_orm.thread_id} and name: {created_thread_orm.name}")
        return ThreadRef(id=created_thread_orm.thread_id, name=created_thread_orm.name, description=None)
    except Exception as e:
        LOGGER.error(f"Error creating thread for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create new thread.")


@app.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Thread"])
async def delete_thread_endpoint(
    thread_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Protected endpoint to delete a specific thread for the authenticated user.
    """
    try:
        threads_service = Threads.threads(user_id=current_user.email)
        threads_service.delete_thread(thread_id=thread_id)
        LOGGER.info(f"User {current_user.email} deleted thread with ID: {thread_id}")
        # HTTP 204 No Content is returned automatically
    except Exception as e: # Be more specific with exception handling if possible
        LOGGER.error(f"Error deleting thread {thread_id} for user {current_user.email}: {e}", exc_info=True)
        if "not found" in str(e).lower() or "no row was found" in str(e).lower(): # Adjust based on actual errors
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found or not accessible.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete thread.")
    

@app.get("/threads/{thread_id}/messages", response_model=list[MessageRef], tags=["Messages"])
async def get_messages(thread_id: str, current_user: Annotated[User, Depends(get_current_user)], limit: Optional[int] = 100):
    """
    Protected endpoint that requires a valid JWT Bearer token.
    Returns the list of messages for a specific thread, with an optional limit on the number of messages.
    """
    try:
        # messages_dict is a dictionary: {message_id: BondMessage_object}
        messages_dict = Threads.threads(user_id=current_user.email).get_messages(thread_id=thread_id, limit=limit)
        message_refs = []
        for msg_obj in messages_dict.values(): # Iterate over BondMessage objects
            # Assuming BondMessage objects have attributes: message_id, type, role, content
            # If BondMessage is a Pydantic model or has a .model_dump() or similar, that could be used.
            # For now, direct attribute access is assumed.
            actual_content = ""
            if msg_obj.clob: # msg_obj is an instance of BondMessage
                actual_content = msg_obj.clob.get_content() # Use the method to ensure content is finalized

            message_refs.append(MessageRef(
                id=getattr(msg_obj, 'message_id', getattr(msg_obj, 'id', None)), # Prefer message_id, fallback to id
                type=getattr(msg_obj, 'type', 'text'), # Default type if not present
                role=getattr(msg_obj, 'role', 'assistant'), # Default role
                content=actual_content # Use the content retrieved from the clob
            ))
        return message_refs
    except Exception as e:
        LOGGER.error(f"Error fetching messages for thread {thread_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch messages.")


@app.post("/chat", tags=["Chat"]) # Changed from GET to POST
async def chat(
    request_body: ChatRequest, # Use request body model
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Protected endpoint that requires a valid JWT Bearer token.
    Accepts thread_id, agent_id, and prompt in the request body.
    Streams chat responses for a specific thread and agent, after adding the user's prompt.
    """
    try:
        thread_id = request_body.thread_id
        agent_id = request_body.agent_id
        prompt = request_body.prompt

        # for now agent id is the same as assistant_id (OpenAI's term)
        assistant_id = agent_id 

        # Get the agent using the assistant_id
        agent = Agent.get_agent(assistant_id)

        # Validate that the user has access to this agent
        # The agent instance knows its own ID (self.assistant_id), so no need to pass agent_id here.
        if not agent.validate_user_access(user_id=current_user.email):
            LOGGER.warning(f"User {current_user.email} attempted to access agent {assistant_id} without permission.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this agent is forbidden.")

        # TODO: Check if thread_id is valid and user has access to it (Threads(user_id).get_thread(thread_id) then check users list)

        # Define a generator function for streaming responses
        def stream_response_generator(): 
            for response_chunk in agent.stream_response(thread_id=thread_id, prompt=prompt): 
                yield response_chunk

        # Return a StreamingResponse
        return StreamingResponse(stream_response_generator(), media_type="text/event-stream")
    except Exception as e:
        LOGGER.error(f"Error during chat streaming for thread {request_body.thread_id}, agent {request_body.agent_id}, prompt '{request_body.prompt}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not stream chat responses.")

@app.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED, tags=["Agent Management"])
async def create_agent_endpoint( # Renamed to avoid conflict if an old 'create_agent' existed
    request_data: AgentCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Creates a new agent. The agent name must be unique for the user.
    """
    try:
        builder = AgentBuilder.builder()
        metadata_service = Metadata.metadata()

        tool_resources_for_def = {}
        if request_data.tool_resources:
            if request_data.tool_resources.code_interpreter and request_data.tool_resources.code_interpreter.file_ids:
                tool_resources_for_def["code_interpreter"] = {
                    "file_ids": request_data.tool_resources.code_interpreter.file_ids
                }
            
            if request_data.tool_resources.file_search and request_data.tool_resources.file_search.file_ids:
                requested_fs_file_ids = request_data.tool_resources.file_search.file_ids
                file_tuples_for_fs = []
                if requested_fs_file_ids:
                    file_path_dicts = metadata_service.get_file_paths(file_ids=requested_fs_file_ids)
                    if file_path_dicts:
                        for fpd in file_path_dicts:
                            if fpd and 'file_path' in fpd:
                                file_tuples_for_fs.append((fpd['file_path'], None))
                tool_resources_for_def["file_search"] = {"files": file_tuples_for_fs}
        
        agent_def = AgentDefinition(
            name=request_data.name,
            description=request_data.description,
            instructions=request_data.instructions,
            tools=request_data.tools,
            tool_resources=tool_resources_for_def,
            metadata=request_data.metadata,
            id=None # ID is None for creation
        )
        
        if request_data.model:
            agent_def.model = request_data.model

        agent_instance = builder.refresh_agent(agent_def, user_id=current_user.email) # Changed to refresh_agent
        
        LOGGER.info(f"Created agent '{agent_instance.get_name()}' with ID '{agent_instance.get_id()}' for user {current_user.email}.")
        return AgentResponse(agent_id=agent_instance.get_id(), name=agent_instance.get_name())

    except Exception as e:
        LOGGER.error(f"Error creating agent '{request_data.name}' for user {current_user.email}: {e}", exc_info=True)
        if "already exists for this user" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not create agent: {str(e)}")

@app.put("/agents/{assistant_id}", response_model=AgentResponse, tags=["Agent Management"])
async def update_agent_endpoint( # Renamed to avoid conflict
    assistant_id: str, 
    request_data: AgentUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Updates an existing agent identified by assistant_id.
    """
    try:
        builder = AgentBuilder.builder()
        metadata_service = Metadata.metadata()

        tool_resources_for_def = {}
        # Ensure to only populate if file_ids are present, AgentDefinition handles empty lists correctly
        if request_data.tool_resources:
            if request_data.tool_resources.code_interpreter and request_data.tool_resources.code_interpreter.file_ids:
                tool_resources_for_def["code_interpreter"] = {
                    "file_ids": request_data.tool_resources.code_interpreter.file_ids
                }
            
            if request_data.tool_resources.file_search and request_data.tool_resources.file_search.file_ids:
                requested_fs_file_ids = request_data.tool_resources.file_search.file_ids
                file_tuples_for_fs = []
                if requested_fs_file_ids: # Only proceed if there are IDs
                    file_path_dicts = metadata_service.get_file_paths(file_ids=requested_fs_file_ids)
                    if file_path_dicts:
                        for fpd in file_path_dicts:
                            if fpd and 'file_path' in fpd:
                                file_tuples_for_fs.append((fpd['file_path'], None))
                # Pass even if file_tuples_for_fs is empty; AgentDefinition handles it.
                tool_resources_for_def["file_search"] = {"files": file_tuples_for_fs}
        
        agent_def = AgentDefinition(
            id=assistant_id, # ID from path
            name=request_data.name, # Name from body, can be None if not updating name
            description=request_data.description,
            instructions=request_data.instructions,
            tools=request_data.tools,
            tool_resources=tool_resources_for_def,
            metadata=request_data.metadata
        )
        if request_data.model: # Override model if provided
            agent_def.model = request_data.model
        
        agent_instance = builder.refresh_agent(agent_def, user_id=current_user.email) # Changed to refresh_agent
        
        LOGGER.info(f"Updated agent '{agent_instance.get_name()}' with ID '{agent_instance.get_id()}' for user {current_user.email}.")
        return AgentResponse(agent_id=agent_instance.get_id(), name=agent_instance.get_name())

    except Exception as e:
        LOGGER.error(f"Error updating agent ID '{assistant_id}' for user {current_user.email}: {e}", exc_info=True)
        if "not found" in str(e).lower(): # Basic check for not found error from builder
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not update agent: {str(e)}")

@app.get("/agents/{assistant_id}", response_model=AgentDetailResponse, tags=["Agent Management"])
async def get_agent_details(
    assistant_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Retrieves detailed information for a specific agent, including resolved file names.
    """
    try:
        agent = Agent.get_agent(assistant_id=assistant_id) # Fetches the OpenAI assistant object
        if not agent.validate_user_access(user_id=current_user.email):
            LOGGER.warning(f"User {current_user.email} attempted to access agent {assistant_id} without permission.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this agent is forbidden.")

        # AgentDefinition.from_assistant might be useful if we need to re-parse full definition
        # For now, directly use the agent object and its tool_resources.
        # The agent.tool_resources from OpenAI directly contains 'file_ids' for code_interpreter
        # and 'vector_store_ids' for file_search.

        metadata_service = Metadata.metadata()
        
        response_tool_resources = ToolResourcesResponse()
        agent_tool_resources_dict = AgentDefinition.to_dict(agent.get_tool_resources())


        if agent_tool_resources_dict and "code_interpreter" in agent_tool_resources_dict:
            ci_file_ids = agent_tool_resources_dict["code_interpreter"].get("file_ids", [])
            if ci_file_ids:
                ci_file_details = []
                file_path_data = metadata_service.get_file_paths(file_ids=ci_file_ids)
                for fp_data in file_path_data:
                    ci_file_details.append(AgentFileDetail(file_id=fp_data['file_id'], file_name=os.path.basename(fp_data['file_path'])))
                response_tool_resources.code_interpreter = ToolResourceFilesList(file_ids=[f.file_id for f in ci_file_details], files=ci_file_details)


        if agent_tool_resources_dict and "file_search" in agent_tool_resources_dict:
            fs_vector_store_ids = agent_tool_resources_dict["file_search"].get("vector_store_ids", [])
            if fs_vector_store_ids:
                fs_file_details = []
                # We need to get files from each vector store. 
                # get_vector_store_file_paths returns a list of dicts, each dict is a file with its associated vector_store_id
                all_fs_files_data = metadata_service.get_vector_store_file_paths(vector_store_ids=fs_vector_store_ids)
                processed_file_ids = set() # To avoid duplicates if a file is in multiple VStores listed
                for fs_fp_data in all_fs_files_data:
                    if fs_fp_data['file_id'] not in processed_file_ids:
                        fs_file_details.append(AgentFileDetail(file_id=fs_fp_data['file_id'], file_name=os.path.basename(fs_fp_data['file_path'])))
                        processed_file_ids.add(fs_fp_data['file_id'])
                response_tool_resources.file_search = ToolResourceFilesList(file_ids=list(processed_file_ids), files=fs_file_details)


        return AgentDetailResponse(
            id=agent.get_id(),
            name=agent.get_name(),
            description=agent.get_description(),
            instructions=agent.get_instructions(),
            model=agent.get_model(), # Assuming Agent class has get_model()
            tools=[AgentDefinition.to_dict(t) for t in agent.get_tools()], # Convert tool objects to dicts
            tool_resources=response_tool_resources,
            metadata=AgentDefinition.to_dict(agent.get_metadata()) # Convert metadata to dict
        )

    except openai.NotFoundError:
        LOGGER.warning(f"Agent with ID '{assistant_id}' not found for user {current_user.email}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    except HTTPException as e: # Re-raise HTTPExceptions directly
        raise e
    except Exception as e:
        LOGGER.error(f"Error retrieving agent details for ID '{assistant_id}', user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not retrieve agent details: {str(e)}")


# --- File Management Endpoints ---
@app.post("/files", response_model=FileUploadResponse, tags=["File Management"])
async def upload_resource_file(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...)
):
    """
    Uploads a file to be associated with agents.
    The file content is processed, and a provider-specific file ID is returned.
    """
    metadata_service = Metadata.metadata()
    try:
        file_content = await file.read()
        file_name = file.filename
        file_tuple = (file_name, file_content)
        
        # get_file_id handles uploading to OpenAI and DB record creation/reuse
        provider_file_id = metadata_service.get_file_id(file_tuple=file_tuple) 
        
        LOGGER.info(f"File '{file_name}' processed for user {current_user.email}. Provider File ID: {provider_file_id}")
        return FileUploadResponse(
            provider_file_id=provider_file_id, 
            file_name=file_name, 
            message="File processed successfully."
        )
    except openai.APIError as e: # Catch specific OpenAI errors if get_file_id propagates them
        LOGGER.error(f"OpenAI API error while uploading file '{file.filename}' for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"File provider error: {str(e)}")
    except Exception as e:
        LOGGER.error(f"Error uploading file '{file.filename}' for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not process file: {str(e)}")

@app.delete("/files/{provider_file_id}", response_model=FileDeleteResponse, tags=["File Management"])
async def delete_resource_file(
    provider_file_id: str, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Deletes a file from the provider and local metadata.
    """
    metadata_service = Metadata.metadata()
    try:
        # The delete_file method in Metadata handles both OpenAI deletion and DB record removal.
        # It returns True on success, or raises an exception.
        # It handles openai.NotFoundError gracefully by logging and considering provider part done.
        success = metadata_service.delete_file(provider_file_id=provider_file_id)
        
        if success:
            LOGGER.info(f"File {provider_file_id} deleted successfully by user {current_user.email}.")
            return FileDeleteResponse(provider_file_id=provider_file_id, status="deleted", message="File deleted successfully.")
        else:
            # This case should ideally not be reached if delete_file raises exceptions on failure
            LOGGER.error(f"delete_file returned False for {provider_file_id} without raising an exception.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete file, unknown reason.")

    except openai.NotFoundError: # Should be caught within delete_file, but as a safeguard
        LOGGER.warning(f"File {provider_file_id} not found on provider during delete attempt by {current_user.email}.")
        # Even if not found on provider, metadata.delete_file attempts DB cleanup.
        # If DB cleanup was also "not found", this is effectively a 404 for the resource.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found with provider or in local records.")
    except openai.APIStatusError as e: # Catch other OpenAI API errors that are not NotFoundError
        LOGGER.error(f"OpenAI API Status Error while deleting file {provider_file_id} for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"File provider API error: {str(e)}")
    except Exception as e: # Catch other exceptions from delete_file (e.g., DB errors, or simulated generic exceptions in tests)
        # For generic exceptions, log a more concise message at this layer.
        # The assumption is that if it's a critical, unexpected error from a lower layer (e.g., metadata.py),
        # that layer would have logged the full traceback.
        LOGGER.error(f"Unexpected error deleting file {provider_file_id} for user {current_user.email}: {str(e)}")
        # Check if the exception message from metadata.py indicates it was a provider "not found" error
        # This is a fallback, as openai.NotFoundError should be caught explicitly by metadata.py or above.
        if "not found on provider" in str(e).lower():
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found with provider: {provider_file_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not delete file: {str(e)}")
