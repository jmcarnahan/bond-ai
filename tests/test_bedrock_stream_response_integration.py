"""
Integration test for BedrockAgent.stream_response method.
This test actually calls AWS Bedrock to validate the streaming functionality.
"""

import os
import json
import pytest
pytestmark = pytest.mark.skip(reason="Integration test: requires live AWS Bedrock streaming API")
import logging
import io
from bondable.bond.config import Config
from bondable.bond.definition import AgentDefinition
from bondable.bond.broker import BondMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def provider():
    """Get the configured Bedrock provider"""
    os.environ['BOND_PROVIDER_CLASS'] = 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'
    os.environ['BOND_MCP_CONFIG'] = json.dumps({
        "mcpServers": {
            "test_server": {
                "url": "http://127.0.0.1:5555/mcp"
            }
        }
    })
    config = Config.config()
    return config.get_provider()

class TestStreamResponseIntegration:
    """Integration tests that actually call AWS Bedrock"""

    def test_basic_text_streaming(self, provider):
        """Test basic text streaming functionality"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="Integration Test Agent",
            description="Agent for integration testing",
            instructions="You are a helpful assistant. Keep responses brief.",
            model=provider.get_default_model()
        )

        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()

        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="Integration Test Thread"
        )
        thread_id = thread.thread_id

        try:
            # Stream a simple response
            response_chunks = []
            bond_message_count = 0

            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt="What is 2+2? Answer with just the number."
            ):
                response_chunks.append(chunk)
                if chunk.startswith('<_bondmessage'):
                    bond_message_count += 1
                    logger.info(f"Bond message started: {chunk[:100]}...")
                elif chunk == '</_bondmessage>':
                    logger.info("Bond message ended")

            # Verify response
            full_response = ''.join(response_chunks)
            assert '4' in full_response
            assert bond_message_count == 1

            # Check database
            messages = provider.threads.get_messages(thread_id=thread_id)
            assert len(messages) >= 2  # User + assistant

            logger.info("✓ Basic text streaming test passed")

        finally:
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)

    def test_image_generation_streaming(self, provider):
        """Test streaming with image generation"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="Image Generation Test Agent",
            description="Agent for testing image generation",
            instructions="You are a helpful assistant that can create visualizations using code interpreter.",
            model=provider.get_default_model()
        )

        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()

        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="Image Test Thread"
        )
        thread_id = thread.thread_id

        try:
            # Request image generation
            prompt = "Using code interpreter, create a simple bar chart with 3 data points: A=10, B=20, C=15. Save it as an image."

            message_types = []
            current_type = None

            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt=prompt
            ):
                if 'type="text"' in chunk:
                    current_type = 'text'
                    message_types.append('text')
                    logger.info("Started text message")
                elif 'type="image_file"' in chunk:
                    current_type = 'image_file'
                    message_types.append('image_file')
                    logger.info("Started image message")
                elif 'data:image' in chunk and current_type == 'image_file':
                    logger.info(f"Received image data (length: {len(chunk)})")

            # Verify we got both text and image
            assert 'text' in message_types
            assert 'image_file' in message_types

            logger.info("✓ Image generation streaming test passed")

        finally:
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)

    def test_mcp_tool_streaming(self, provider):
        """Test streaming with MCP tool execution"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="MCP Tool Test Agent",
            description="Agent for testing MCP tools",
            instructions="You are a helpful assistant. When asked for the time, use the current_time tool.",
            model=provider.get_default_model(),
            mcp_tools=["current_time"]
        )

        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()

        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="MCP Test Thread"
        )
        thread_id = thread.thread_id

        try:
            # Request MCP tool use
            response_chunks = []

            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt="What is the current time?"
            ):
                response_chunks.append(chunk)
                if 'returnControl' in chunk:
                    logger.info("MCP tool invocation detected")

            # Verify response mentions time
            full_response = ''.join(response_chunks).lower()
            assert any(word in full_response for word in ['time', 'clock', 'hour', 'minute'])

            logger.info("✓ MCP tool streaming test passed")

        finally:
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)

    def test_attachments_streaming(self, provider):
        """Test streaming with file attachments"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="Attachment Test Agent",
            description="Agent for testing file attachments",
            instructions="You are a helpful assistant that can analyze files. When given a file, describe its contents.",
            model=provider.get_default_model()
        )

        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()

        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="Attachment Test Thread"
        )
        thread_id = thread.thread_id

        # Create test file - use simple CSV
        test_content = "Name,Age\nAlice,30\nBob,25"

        # Get file ID - pass user_id and tuple of (filename, bytes)
        file_details = provider.files.get_or_create_file_id(
            "integration-test-user",
            ("test_data.csv", test_content.encode('utf-8'))
        )
        file_id = file_details.file_id

        try:
            # Create attachment with single file
            attachments = [
                {
                    "file_id": file_id,
                    "tools": [{"type": "code_interpreter"}]
                }
            ]

            # Stream response with attachments
            response_chunks = []

            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt="What data is in the CSV file?",
                attachments=attachments
            ):
                response_chunks.append(chunk)

            # Verify response mentions the files
            full_response = ''.join(response_chunks)
            logger.info(f"Response: {full_response}")

            # Check that we got a response
            assert len(response_chunks) > 0, "No response received"
            assert len(full_response) > 0, "Empty response"

            # Verify the agent analyzed the CSV content
            assert 'CSV' in full_response or 'csv' in full_response, "Response doesn't mention CSV"
            assert 'Alice' in full_response, "Response doesn't mention Alice from the data"
            assert 'Bob' in full_response, "Response doesn't mention Bob from the data"

            # Check messages for attachments
            messages = provider.threads.get_messages(thread_id=thread_id)

            # Find the user message with attachments
            user_message: BondMessage = None
            # messages is Dict[str, BondMessage]
            for msg_id, msg in messages.items():
                bond_msg: BondMessage = msg
                logger.info(f"Message{msg_id}: {bond_msg} {bond_msg.type} {bond_msg.role} - {bond_msg.clob.get_content()}")
                if bond_msg.role == 'user' and hasattr(bond_msg, 'metadata') and bond_msg.metadata:
                    user_message = bond_msg
                    logger.info(f"Found user message with attachments: {user_message}")
                    break
                # if msg['role'] == 'user' and msg.get('attachments'):
                #     user_message = msg
                #     break

            assert user_message is not None, "No user message with attachments found"
            assert len(user_message.metadata['attachments']) == 1

            # Verify attachment structure
            attachment = user_message.metadata['attachments'][0]['data']
            assert 'file_id' in attachment
            assert attachment['file_id'].startswith('s3://')
            assert 'file_path' in attachment
            assert attachment['file_path'] == 'test_data.csv'


            logger.info("✓ Attachments streaming test passed")

        finally:
            # Clean up
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)
            provider.files.delete_file(file_id)

    def test_multiple_attachments_streaming(self, provider):
        """Test streaming with multiple file attachments"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="Multi Attachment Test Agent",
            description="Agent for testing multiple file attachments",
            instructions="You are a helpful assistant that can analyze multiple files. When given files, describe the contents of each one.",
            model=provider.get_default_model()
        )

        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()

        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="Multi Attachment Test Thread"
        )
        thread_id = thread.thread_id

        # Create multiple test files
        # File 1: CSV data
        csv_content = "Product,Price,Stock\nApple,1.99,100\nBanana,0.99,150\nOrange,2.49,75"

        # File 2: Simple CSV data
        csv_content2 = "Name,Value\nTest1,100\nTest2,200"

        # File 3: Simple text file
        text_content = "Simple text\nLine 2\nLine 3"

        # Upload all files
        file_details_csv = provider.files.get_or_create_file_id(
            "integration-test-user",
            ("products.csv", csv_content.encode('utf-8'))
        )
        file_id_csv = file_details_csv.file_id

        file_details_csv2 = provider.files.get_or_create_file_id(
            "integration-test-user",
            ("data.csv", csv_content2.encode('utf-8'))
        )
        file_id_csv2 = file_details_csv2.file_id

        file_details_txt = provider.files.get_or_create_file_id(
            "integration-test-user",
            ("readme.txt", text_content.encode('utf-8'))
        )
        file_id_txt = file_details_txt.file_id

        logger.info(f"Created files:")
        logger.info(f"  CSV: {file_id_csv} ({file_details_csv.file_size} bytes)")
        logger.info(f"  CSV2: {file_id_csv2} ({file_details_csv2.file_size} bytes)")
        logger.info(f"  TXT: {file_id_txt} ({file_details_txt.file_size} bytes)")

        try:
            # Create attachments with all files
            attachments = [
                {
                    "file_id": file_id_csv,
                    "tools": [{"type": "code_interpreter"}]
                },
                {
                    "file_id": file_id_csv2,
                    "tools": [{"type": "code_interpreter"}]
                },
                {
                    "file_id": file_id_txt,
                    "tools": [{"type": "code_interpreter"}]
                }
            ]

            # Stream response with multiple attachments
            response_chunks = []

            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt="Analyze the uploaded files",
                attachments=attachments
            ):
                response_chunks.append(chunk)

            # Verify response
            full_response = ''.join(response_chunks)
            logger.info(f"Response length: {len(full_response)} characters")
            logger.info(f"Response content: {full_response}")

            # Check that all files were mentioned
            assert len(response_chunks) > 0, "No response received"
            assert len(full_response) > 0, "Empty response"

            # Verify content from each file is mentioned
            # CSV content checks
            assert any(term in full_response for term in ['CSV', 'csv', 'products', 'Apple', 'Banana', 'Orange']), \
                "Response doesn't mention CSV content"

            # CSV2 content checks - just check if the second file is mentioned
            assert any(term in full_response for term in ['data.csv', 'Test1', 'Test2', 'Name', 'Value']), \
                "Response doesn't mention second CSV content"

            # Text file content checks - check for any mention of the text file
            assert any(term in full_response for term in ['readme.txt', 'text file', 'Simple text']), \
                "Response doesn't mention text file content"

            logger.info("✓ Multiple attachments streaming test passed")

        finally:
            # Clean up
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)
            provider.files.delete_file(file_id_csv)
            provider.files.delete_file(file_id_csv2)
            provider.files.delete_file(file_id_txt)

    def test_single_csv_attachment_streaming(self, provider):
        """Test streaming with a single CSV file attachment (CODE_INTERPRETER)"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="CSV Analysis Test Agent",
            description="Agent for testing CSV file analysis",
            instructions="You are a helpful data analyst. Analyze CSV files and provide insights.",
            model=provider.get_default_model()
        )

        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()

        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="CSV Analysis Test Thread"
        )
        thread_id = thread.thread_id

        # Create CSV with sales data
        csv_content = """Product,Quantity,Revenue
Widget A,150,4498.50
Widget B,87,4349.13
Widget C,203,4057.97
Widget D,112,4478.88
Total,,17384.48"""

        # Upload CSV file
        file_details = provider.files.get_or_create_file_id(
            "integration-test-user",
            ("sales_data.csv", csv_content.encode('utf-8'))
        )
        file_id = file_details.file_id

        try:
            # Create attachment for code interpreter
            attachments = [
                {
                    "file_id": file_id,
                    "tools": [{"type": "code_interpreter"}]
                }
            ]

            # Stream response
            response_chunks = []

            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt="What is the total revenue from this sales data?",
                attachments=attachments
            ):
                response_chunks.append(chunk)

            # Verify response
            full_response = ''.join(response_chunks)
            logger.info(f"CSV analysis response: {full_response[:200]}...")

            # Check response mentions the total
            assert "17384" in full_response or "17,384" in full_response, \
                "Response doesn't mention the correct total revenue"

            logger.info("✓ Single CSV attachment streaming test passed")

        finally:
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)
            provider.files.delete_file(file_id)

    def test_single_pdf_attachment_streaming(self, provider):
        """Test streaming with a single PDF file attachment (CHAT/file_search)"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="PDF Analysis Test Agent",
            description="Agent for testing PDF file analysis",
            instructions="You are a helpful document analyst. Analyze documents and answer questions about them.",
            model=provider.get_default_model()
        )

        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()

        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="PDF Analysis Test Thread"
        )
        thread_id = thread.thread_id

        # Create mock PDF content (as text for simplicity)
        pdf_content = b"SubscriblyAI Documentation - A comprehensive SaaS subscription management platform"

        # Upload PDF file
        file_details = provider.files.get_or_create_file_id(
            "integration-test-user",
            ("platform_docs.pdf", pdf_content)
        )
        file_id = file_details.file_id

        try:
            # Create attachment for file search
            attachments = [
                {
                    "file_id": file_id,
                    "tools": [{"type": "file_search"}]
                }
            ]

            # Stream response
            response_chunks = []

            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt="What platform is described in this documentation?",
                attachments=attachments
            ):
                response_chunks.append(chunk)

            # Verify response
            full_response = ''.join(response_chunks)
            logger.info(f"PDF analysis response: {full_response[:200]}...")

            # Check response mentions the platform
            assert "subscribly" in full_response.lower() or "subscription" in full_response.lower(), \
                "Response doesn't mention the platform from the PDF"

            logger.info("✓ Single PDF attachment streaming test passed")

        finally:
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)
            provider.files.delete_file(file_id)

    def test_mixed_attachment_types_streaming(self, provider):
        """Test streaming with mixed attachment types (CSV + PDF)"""
        agent_def = AgentDefinition(
            user_id="integration-test-user",
            name="Mixed Files Analysis Agent",
            description="Agent for analyzing both data files and documents",
            instructions="You are a helpful assistant that can analyze both data files and documents.",
            model=provider.get_default_model()
        )

        agent = provider.agents.create_or_update_agent(
            agent_def=agent_def,
            user_id="integration-test-user"
        )
        agent_id = agent.get_agent_id()

        thread = provider.threads.create_thread(
            user_id="integration-test-user",
            name="Mixed Files Test Thread"
        )
        thread_id = thread.thread_id

        # Create CSV with revenue data
        csv_content = """Month,Revenue,Growth
January,10000,0
February,12000,20
March,15000,25
Q1 Total,37000,50"""

        # Create mock PDF documentation
        pdf_content = b"SubscriblyAI Q1 Report - This report analyzes subscription revenue performance for Q1"

        # Upload both files
        csv_details = provider.files.get_or_create_file_id(
            "integration-test-user",
            ("q1_revenue.csv", csv_content.encode('utf-8'))
        )
        csv_file_id = csv_details.file_id

        pdf_details = provider.files.get_or_create_file_id(
            "integration-test-user",
            ("q1_report.pdf", pdf_content)
        )
        pdf_file_id = pdf_details.file_id

        logger.info(f"Uploaded CSV: {csv_file_id}")
        logger.info(f"Uploaded PDF: {pdf_file_id}")

        try:
            # Create mixed attachments
            attachments = [
                {
                    "file_id": csv_file_id,
                    "tools": [{"type": "code_interpreter"}]
                },
                {
                    "file_id": pdf_file_id,
                    "tools": [{"type": "file_search"}]
                }
            ]

            # Stream response - this will use two-phase processing
            response_chunks = []
            phase_count = 0

            for chunk in agent.stream_response(
                thread_id=thread_id,
                prompt="Based on the report and data, what was the Q1 total revenue and what platform does this report analyze?",
                attachments=attachments
            ):
                response_chunks.append(chunk)
                # Count bond messages (phases)
                if chunk.startswith('<_bondmessage'):
                    phase_count += 1
                    logger.info(f"Phase {phase_count} started")

            # Verify response
            full_response = ''.join(response_chunks)
            logger.info(f"Mixed files response (phases: {phase_count}): {full_response[:300]}...")

            # Should have processed in 2 phases
            assert phase_count == 2, f"Expected 2 phases for mixed files, got {phase_count}"

            # Check that both pieces of information are present (from different phases)
            # Note: Due to phase separation, the response might mention not having access to one file in each phase
            assert "37000" in full_response or "37,000" in full_response or "Q1" in full_response.upper(), \
                "Response doesn't mention Q1 revenue data"

            assert "subscribly" in full_response.lower() or "subscription" in full_response.lower(), \
                "Response doesn't mention the platform from the PDF"

            logger.info("✓ Mixed attachment types streaming test passed")

        finally:
            provider.threads.delete_thread(thread_id=thread_id, user_id="integration-test-user")
            provider.agents.delete_agent(agent_id)
            provider.files.delete_file(csv_file_id)
            provider.files.delete_file(pdf_file_id)


# Run with: poetry run pytest tests/test_bedrock_stream_response_integration.py -v -m integration
