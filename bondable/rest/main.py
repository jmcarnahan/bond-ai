import os
from typing import Union, Optional, Annotated # Added Annotated
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer # Added
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from bondable.bond.auth import GoogleAuth
from bondable.bond.agent import Agent
from bondable.bond.builder import AgentBuilder # Added
from bondable.bond.definition import AgentDefinition # Added
from bondable.bond.threads import Threads
from bondable.bond.config import Config
from pydantic import BaseModel, Field # Added Field
from typing import List, Dict, Any # Added for Pydantic models
import logging

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

class ToolResourceCodeInterpreterRequest(BaseModel):
    file_ids: List[str] = Field(default_factory=list)

class ToolResourceFileSearchRequest(BaseModel):
    vector_store_ids: List[str] = Field(default_factory=list)

class ToolResourcesRequest(BaseModel):
    code_interpreter: Optional[ToolResourceCodeInterpreterRequest] = None
    file_search: Optional[ToolResourceFileSearchRequest] = None

class AgentCreateRequest(BaseModel): # New model for agent creation
    name: str # Name is required for creation
    description: Optional[str] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_resources: Optional[ToolResourcesRequest] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentUpdateRequest(BaseModel): 
    name: Optional[str] = None # Name can be updated if desired, or other fields
    description: Optional[str] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_resources: Optional[ToolResourcesRequest] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentResponse(BaseModel): # General response for agent operations
    agent_id: str
    name: str

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


@app.get("/auth/google/callback", response_model=Token, tags=["Authentication"])
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
        return {"access_token": access_token, "token_type": "bearer"}

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
    agent_refs = [AgentRef(id=agent.get_id(), name=agent.get_name(), description=agent.get_description()) for agent in agents]
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
    

@app.get("/threads/{thread_id}/messages", response_model=list[MessageRef], tags=["Messages"])
async def get_messages(thread_id: str, current_user: Annotated[User, Depends(get_current_user)], limit: Optional[int] = 100):
    """
    Protected endpoint that requires a valid JWT Bearer token.
    Returns the list of messages for a specific thread, with an optional limit on the number of messages.
    """
    try:
        messages = Threads.threads(user_id=current_user.email).get_messages(thread_id=thread_id, limit=limit)
        message_refs = [
            MessageRef(
                id=message['message_id'],
                type=message['type'],
                role=message['role'],
                content=message['content']
            )
            for message in messages
        ]
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

        # TODO: Check if thread_id is valid and user has access to it

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
        
        tool_resources_for_def = {}
        if request_data.tool_resources:
            if request_data.tool_resources.code_interpreter:
                tool_resources_for_def["code_interpreter"] = {
                    "file_ids": request_data.tool_resources.code_interpreter.file_ids
                }
            if request_data.tool_resources.file_search:
                 tool_resources_for_def["file_search"] = {
                    "vector_store_ids": request_data.tool_resources.file_search.vector_store_ids
                }
        
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

        agent_instance = builder.get_agent(agent_def, user_id=current_user.email)
        
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
        
        tool_resources_for_def = {}
        if request_data.tool_resources:
            if request_data.tool_resources.code_interpreter:
                tool_resources_for_def["code_interpreter"] = {
                    "file_ids": request_data.tool_resources.code_interpreter.file_ids
                }
            if request_data.tool_resources.file_search:
                 tool_resources_for_def["file_search"] = {
                    "vector_store_ids": request_data.tool_resources.file_search.vector_store_ids
                }
        
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
        
        agent_instance = builder.get_agent(agent_def, user_id=current_user.email)
        
        LOGGER.info(f"Updated agent '{agent_instance.get_name()}' with ID '{agent_instance.get_id()}' for user {current_user.email}.")
        return AgentResponse(agent_id=agent_instance.get_id(), name=agent_instance.get_name())

    except Exception as e:
        LOGGER.error(f"Error updating agent ID '{assistant_id}' for user {current_user.email}: {e}", exc_info=True)
        if "not found" in str(e).lower(): # Basic check for not found error from builder
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not update agent: {str(e)}")
