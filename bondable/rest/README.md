# Bondable REST API Endpoints

This document provides examples of how to use the REST API endpoints for the Bondable service.
All examples use `curl` and assume the API is running at `http://localhost:8000`.

## Authentication (Obtaining a JWT Token)

This API uses JWT Bearer tokens for authenticating protected endpoints. The tokens are obtained via a Google OAuth2 flow.

**Steps to obtain a JWT token:**

1.  **Initiate Login Flow**:
    *   Open your web browser and navigate to: `http://localhost:8000/login`
    *   This will redirect you to Google's authentication page.
    *   Log in with your Google account and grant the necessary permissions if prompted.

2.  **Handle the Callback**:
    *   After successful authentication with Google, Google will redirect your browser to the callback URL:
        `http://localhost:8000/auth/google/callback?code=<AUTHORIZATION_CODE>&scope=<SCOPES_GRANTED>`
    *   Your browser will make a GET request to this callback URL.
    *   The API server will exchange the `AUTHORIZATION_CODE` with Google for user information and then generate a JWT.
    *   The server will respond to this callback request with a JSON containing the access token.

    **Example Response from `/auth/google/callback`**:
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyour_email@example.comIiwibmFtZSI6IkpvaG4gRG9lIiwiZXhwIjoxNjc4ODg2NDAwfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        "token_type": "bearer"
    }
    ```
    *   Copy the `access_token` value from this JSON response. This is your JWT token.

3.  **Using the JWT Token**:
    *   For all subsequent requests to protected API endpoints, include this token in the `Authorization` header:
        `Authorization: Bearer <YOUR_JWT_TOKEN>`
    *   Replace `<YOUR_JWT_TOKEN>` with the actual token you copied.

**Note**: You will need to have your Google OAuth 2.0 credentials (client ID, client secret) correctly configured in your application's environment variables (e.g., in your `.env` file, used by `bondable/bond/auth.py`) for this flow to work. The `redirect_uris` in your Google Cloud Console project must also include `http://localhost:8000/auth/google/callback`.

---

**API Endpoint Usage**: All protected endpoints require a JWT Bearer token in the `Authorization` header as described above.
Replace `<YOUR_JWT_TOKEN>` with a valid token in the `curl` examples below.

---

## Agent Management

### 1. Create Agent

Creates a new agent.

-   **Method**: `POST`
-   **Path**: `/agents`
-   **Headers**:
    -   `Authorization: Bearer <YOUR_JWT_TOKEN>`
    -   `Content-Type: application/json`
-   **Request Body**: `AgentCreateRequest`
    ```json
    {
        "name": "My New API Agent",
        "description": "An agent created via the API for demonstration.",
        "instructions": "You are a helpful assistant that loves to talk about APIs.",
        "model": "gpt-4o-mini", // Optional, defaults to system config
        "tools": [{"type": "code_interpreter"}],
        "tool_resources": {
            "code_interpreter": {
                "file_ids": [] // Provide existing OpenAI file IDs if needed
            }
        },
        "metadata": {"version": "1.0", "created_by": "api_doc_example"}
    }
    ```
-   **`curl` Example**:
    ```bash
    curl -X POST "http://localhost:8000/agents" \
    -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "My New API Agent",
        "description": "An agent created via the API for demonstration.",
        "instructions": "You are a helpful assistant that loves to talk about APIs.",
        "tools": [{"type": "code_interpreter"}]
    }'
    ```
-   **Response**: `201 Created` with `AgentResponse`
    ```json
    {
        "agent_id": "asst_xxxxxxxxxxxxxxxxxxxx",
        "name": "My New API Agent"
    }
    ```

### 2. Update Agent

Updates an existing agent identified by its `assistant_id`.

-   **Method**: `PUT`
-   **Path**: `/agents/{assistant_id}`
-   **Headers**:
    -   `Authorization: Bearer <YOUR_JWT_TOKEN>`
    -   `Content-Type: application/json`
-   **Path Parameter**:
    -   `assistant_id`: The ID of the agent to update (e.g., `asst_xxxxxxxxxxxxxxxxxxxx`).
-   **Request Body**: `AgentUpdateRequest` (include only fields to update)
    ```json
    {
        "name": "My Updated API Agent",
        "description": "An updated description for the agent.",
        "instructions": "You are now an expert in Python programming.",
        "tools": [{"type": "code_interpreter"}, {"type": "file_search"}],
        "tool_resources": {
            "file_search": {
                "vector_store_ids": ["vs_yyyyyyyyyyyyyyyyyyyy"] // Provide existing vector store IDs
            }
        }
    }
    ```
-   **`curl` Example**:
    ```bash
    curl -X PUT "http://localhost:8000/agents/<ASSISTANT_ID>" \
    -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "My Updated API Agent",
        "description": "An updated description.",
        "instructions": "New instructions for the agent."
    }'
    ```
-   **Response**: `200 OK` with `AgentResponse`
    ```json
    {
        "agent_id": "<ASSISTANT_ID>",
        "name": "My Updated API Agent"
    }
    ```

### 3. List Agents

Retrieves a list of agents accessible to the authenticated user.

-   **Method**: `GET`
-   **Path**: `/agents`
-   **Headers**:
    -   `Authorization: Bearer <YOUR_JWT_TOKEN>`
-   **`curl` Example**:
    ```bash
    curl -X GET "http://localhost:8000/agents" \
    -H "Authorization: Bearer <YOUR_JWT_TOKEN>"
    ```
-   **Response**: `200 OK` with a list of `AgentRef` objects.
    ```json
    [
        {
            "id": "asst_xxxxxxxxxxxxxxxxxxxx",
            "name": "My New API Agent",
            "description": "An agent created via the API for demonstration."
        },
        {
            "id": "asst_yyyyyyyyyyyyyyyyyyyy",
            "name": "Another Agent",
            "description": "Description for another agent."
        }
    ]
    ```

---

## Thread Management

### 1. Create Thread

Creates a new thread for the authenticated user.

-   **Method**: `POST`
-   **Path**: `/threads`
-   **Headers**:
    -   `Authorization: Bearer <YOUR_JWT_TOKEN>`
    -   `Content-Type: application/json`
-   **Request Body**: `CreateThreadRequest` (optional `name`)
    ```json
    {
        "name": "My API Test Thread"
    }
    ```
    Or, to use the default name ("New Thread"):
    ```json
    {}
    ```
-   **`curl` Example (with name)**:
    ```bash
    curl -X POST "http://localhost:8000/threads" \
    -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{"name": "My API Test Thread"}'
    ```
-   **Response**: `201 Created` with `ThreadRef`
    ```json
    {
        "id": "thread_zzzzzzzzzzzzzzzzzzzz",
        "name": "My API Test Thread",
        "description": null
    }
    ```

### 2. List Threads

Retrieves a list of threads for the authenticated user.

-   **Method**: `GET`
-   **Path**: `/threads`
-   **Headers**:
    -   `Authorization: Bearer <YOUR_JWT_TOKEN>`
-   **`curl` Example**:
    ```bash
    curl -X GET "http://localhost:8000/threads" \
    -H "Authorization: Bearer <YOUR_JWT_TOKEN>"
    ```
-   **Response**: `200 OK` with a list of `ThreadRef` objects.
    ```json
    [
        {
            "id": "thread_zzzzzzzzzzzzzzzzzzzz",
            "name": "My API Test Thread",
            "description": null
        },
        {
            "id": "thread_wwwwwwwwwwwwwwwwwwww",
            "name": "Another Thread",
            "description": "A thread for other discussions."
        }
    ]
    ```

### 3. Get Thread Messages

Retrieves messages for a specific thread.

-   **Method**: `GET`
-   **Path**: `/threads/{thread_id}/messages`
-   **Headers**:
    -   `Authorization: Bearer <YOUR_JWT_TOKEN>`
-   **Path Parameter**:
    -   `thread_id`: The ID of the thread (e.g., `thread_zzzzzzzzzzzzzzzzzzzz`).
-   **Query Parameter (optional)**:
    -   `limit`: Maximum number of messages to return (default is 100).
-   **`curl` Example**:
    ```bash
    curl -X GET "http://localhost:8000/threads/<THREAD_ID>/messages?limit=10" \
    -H "Authorization: Bearer <YOUR_JWT_TOKEN>"
    ```
-   **Response**: `200 OK` with a list of `MessageRef` objects.
    ```json
    [
        {
            "id": "msg_xxxxxxxxxxxxxxxxxxxx_0",
            "type": "text",
            "role": "user",
            "content": "Hello there!"
        },
        {
            "id": "msg_yyyyyyyyyyyyyyyyyyyy_0",
            "type": "text",
            "role": "assistant",
            "content": "Hi! How can I help you?"
        }
    ]
    ```

---

## Chat

### 1. Chat with Agent (Streaming)

Sends a prompt to an agent within a specific thread and streams the response.

-   **Method**: `POST`
-   **Path**: `/chat`
-   **Headers**:
    -   `Authorization: Bearer <YOUR_JWT_TOKEN>`
    -   `Content-Type: application/json`
-   **Request Body**: `ChatRequest`
    ```json
    {
        "thread_id": "<THREAD_ID>",
        "agent_id": "<ASSISTANT_ID>",
        "prompt": "Hello agent, can you tell me a joke?"
    }
    ```
-   **`curl` Example**:
    ```bash
    curl -X POST "http://localhost:8000/chat" \
    -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
        "thread_id": "<THREAD_ID>",
        "agent_id": "<ASSISTANT_ID>",
        "prompt": "Hello agent, can you tell me a joke?"
    }' \
    --no-buffer 
    ```
    (Note: `--no-buffer` or similar flag might be needed with `curl` to see streaming output immediately.)
-   **Response**: `200 OK` with `text/event-stream` content. The data will be streamed.
    Example of streamed chunks (format may vary slightly based on internal `_bondmessage` structure):
    ```
    <_bondmessage id="msg_xxxxxxxx_0" role="assistant" type="text" thread_id="<THREAD_ID>" is_done="false">Why don't scientists
    </_bondmessage>
    <_bondmessage id="msg_xxxxxxxx_0" role="assistant" type="text" thread_id="<THREAD_ID>" is_done="false"> trust atoms?
    </_bondmessage>
    <_bondmessage id="msg_xxxxxxxx_0" role="assistant" type="text" thread_id="<THREAD_ID>" is_done="false">
    Because they make up everything!
    </_bondmessage>
    <_bondmessage id="-1" role="system" type="text" thread_id="<THREAD_ID>" is_done="true">Done.</_bondmessage>
    ```

---
