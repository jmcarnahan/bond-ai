"""
Unit tests for agent forwarding via bond://forward/AgentName links.

Verifies that stream_response_generator() detects bond://forward links in
agent responses, resolves the target agent, and chains invocations on the
same thread — with protection against circular forwarding and depth limits.
"""

import re
import uuid
import pytest
from unittest.mock import MagicMock
from xml.sax.saxutils import escape as xml_escape

from bondable.rest.routers.chat import _FORWARD_PATTERN, _MAX_FORWARD_DEPTH, _build_system_message


# ---------------------------------------------------------------------------
# Test helper: simulate the forwarding-aware stream_response_generator
# ---------------------------------------------------------------------------

def _simulate_forwarding_generator(
    agent_instance,
    provider,
    thread_id="test-thread-123",
    agent_id="test-agent-456",
    agent_name="TestAgent",
    prompt="Hello",
    current_user=None,
):
    """
    Reproduce the forwarding-aware stream_response_generator logic from chat.py
    without needing FastAPI dependencies.
    """
    if current_user is None:
        current_user = MagicMock()
        current_user.user_id = "test-user-id"

    current_agent = agent_instance
    current_agent_id = agent_id
    current_agent_name = agent_name
    current_prompt = prompt
    current_attachments = []
    current_hidden = False
    visited_agent_ids = {agent_id}
    forward_depth = 0

    while True:
        bond_message_open = False
        has_yielded_bond_message = False
        has_yielded_done = False
        has_yielded_assistant_content = False
        current_is_assistant = False
        accumulated_text = ""

        try:
            for response_chunk in current_agent.stream_response(
                thread_id=thread_id,
                prompt=current_prompt,
                attachments=current_attachments,
                hidden=current_hidden,
                current_user=current_user,
                jwt_token=None,
            ):
                if isinstance(response_chunk, str):
                    if response_chunk.startswith('<_bondmessage '):
                        bond_message_open = True
                        has_yielded_bond_message = True
                        if 'is_done="true"' in response_chunk:
                            has_yielded_done = True
                        current_is_assistant = 'role="assistant"' in response_chunk
                    elif response_chunk == '</_bondmessage>':
                        bond_message_open = False
                        current_is_assistant = False
                    elif current_is_assistant and response_chunk.strip():
                        has_yielded_assistant_content = True
                        accumulated_text += response_chunk
                yield response_chunk

        except Exception as e:
            error_id = str(uuid.uuid4())
            if bond_message_open:
                yield '</_bondmessage>'
            yield (
                f'<_bondmessage '
                f'id="{error_id}" '
                f'thread_id="{thread_id}" '
                f'agent_id="{current_agent_id}" '
                f'type="error" '
                f'role="system" '
                f'is_error="true" '
                f'is_done="true">'
            )
            yield f"Error: {e}"
            yield '</_bondmessage>'
            return  # No forwarding after errors

        # --- Check for agent forwarding ---
        forward_match = _FORWARD_PATTERN.search(accumulated_text) if accumulated_text else None

        if forward_match and forward_depth < _MAX_FORWARD_DEPTH:
            target_agent_ref = forward_match.group(2).strip()
            target_display_name = forward_match.group(1).strip() or target_agent_ref
            forward_depth += 1

            # Resolve target agent by slug
            target_agent = None
            try:
                target_agent = provider.agents.get_agent_by_slug(slug=target_agent_ref)
            except Exception:
                pass

            if not target_agent:
                yield _build_system_message(
                    thread_id, current_agent_id,
                    f"Could not forward: agent '{target_display_name}' not found."
                )
            else:
                target_agent_id = target_agent.get_agent_id()
                target_agent_name = target_agent.get_name()

                # Circular forwarding check
                if target_agent_id in visited_agent_ids:
                    yield _build_system_message(
                        thread_id, current_agent_id,
                        "Could not forward: circular forwarding detected."
                    )
                else:
                    # Access check
                    target_accessible = False
                    try:
                        default_agent = provider.agents.get_default_agent()
                        is_target_default = default_agent and default_agent.get_agent_id() == target_agent_id
                        target_accessible = is_target_default or provider.agents.can_user_access_agent(
                            user_id=current_user.user_id, agent_id=target_agent_id
                        )
                    except Exception:
                        pass

                    if not target_accessible:
                        yield _build_system_message(
                            thread_id, current_agent_id,
                            f"Could not forward: you do not have access to agent "
                            f"'{target_agent_name}'."
                        )
                    else:
                        # T27: Apply read-only permission on forwarded agent
                        if not is_target_default:
                            try:
                                target_perm = provider.agents.get_user_agent_permission(
                                    current_user.user_id, target_agent_id
                                )
                                if target_perm == 'can_use_read_only':
                                    if hasattr(target_agent, 'metadata') and isinstance(target_agent.metadata, dict):
                                        target_agent.metadata['allow_write_tools'] = False
                            except Exception:
                                pass

                        # Don't update last_agent_id — forwarding is transparent
                        yield _build_system_message(
                            thread_id, target_agent_id,
                            f"Forwarding to {target_agent_name}..."
                        )

                        visited_agent_ids.add(target_agent_id)
                        source_agent_name = current_agent_name
                        current_agent = target_agent
                        current_agent_id = target_agent_id
                        current_agent_name = target_agent_name
                        current_prompt = (
                            f"The previous agent ({source_agent_name}) forwarded this "
                            f"conversation to you. The user's original request was: "
                            f"{prompt}"
                        )
                        current_attachments = []
                        current_hidden = False
                        continue  # Loop to stream the forwarded agent

        # --- Post-stream safety-net guarantees ---
        if has_yielded_bond_message and not has_yielded_assistant_content:
            if bond_message_open:
                yield '</_bondmessage>'
                bond_message_open = False
            fallback_id = str(uuid.uuid4())
            yield (
                f'<_bondmessage '
                f'id="{fallback_id}" '
                f'thread_id="{thread_id}" '
                f'agent_id="{current_agent_id}" '
                f'type="error" '
                f'role="system" '
                f'is_error="true" '
                f'is_done="true">'
            )
            yield "The agent was unable to generate a response. Please try again."
            yield '</_bondmessage>'
            has_yielded_done = True

        if has_yielded_bond_message and not has_yielded_done:
            if bond_message_open:
                yield '</_bondmessage>'
                bond_message_open = False
            done_id = str(uuid.uuid4())
            yield (
                f'<_bondmessage '
                f'id="{done_id}" '
                f'thread_id="{thread_id}" '
                f'agent_id="{current_agent_id}" '
                f'type="text" '
                f'role="system" '
                f'is_error="false" '
                f'is_done="true">'
            )
            yield "Done."
            yield '</_bondmessage>'

        break  # Normal exit


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_mock_agent(agent_id, agent_name, response_chunks):
    """Create a mock agent with a stream_response that yields given chunks."""
    agent = MagicMock()
    agent.get_agent_id.return_value = agent_id
    agent.get_name.return_value = agent_name

    def stream_response(**kwargs):
        yield from response_chunks
    agent.stream_response.side_effect = stream_response
    return agent


def _make_provider(agents_by_slug=None, can_access=True, default_agent=None):
    """Create a mock provider with configurable agent lookup by slug."""
    if agents_by_slug is None:
        agents_by_slug = {}
    provider = MagicMock()
    provider.agents.get_agent_by_slug.side_effect = lambda slug: agents_by_slug.get(slug)
    provider.agents.can_user_access_agent.return_value = can_access
    provider.agents.get_default_agent.return_value = default_agent
    return provider


def _bond_msg(agent_id="a", role="assistant", is_done="false", content=""):
    """Generate bond message chunks for testing."""
    msg_id = str(uuid.uuid4())
    chunks = [
        f'<_bondmessage id="{msg_id}" thread_id="t" agent_id="{agent_id}" '
        f'type="text" role="{role}" is_error="false" is_done="{is_done}">',
    ]
    if content:
        chunks.append(content)
    chunks.append('</_bondmessage>')
    return chunks


# ---------------------------------------------------------------------------
# Forward pattern regex tests
# ---------------------------------------------------------------------------

class TestForwardPattern:
    def test_matches_simple_forward(self):
        text = "Talk to [Helper](bond://forward/Helper) for this."
        m = _FORWARD_PATTERN.search(text)
        assert m is not None
        assert m.group(1) == "Helper"
        assert m.group(2) == "Helper"

    def test_matches_forward_with_spaces_in_name(self):
        text = "See [My Agent](bond://forward/My Agent) for details."
        m = _FORWARD_PATTERN.search(text)
        assert m is not None
        assert m.group(2) == "My Agent"

    def test_no_match_on_bond_prompt(self):
        text = "Click [here](bond://prompt) to continue."
        assert _FORWARD_PATTERN.search(text) is None

    def test_no_match_on_plain_text(self):
        text = "Just a normal response with no links."
        assert _FORWARD_PATTERN.search(text) is None

    def test_first_match_wins(self):
        text = "Go to [A](bond://forward/AgentA) or [B](bond://forward/AgentB)."
        m = _FORWARD_PATTERN.search(text)
        assert m.group(2) == "AgentA"


# ---------------------------------------------------------------------------
# Build system message tests
# ---------------------------------------------------------------------------

class TestBuildSystemMessage:
    def test_basic_message(self):
        msg = _build_system_message("t1", "a1", "Hello")
        assert 'thread_id="t1"' in msg
        assert 'agent_id="a1"' in msg
        assert 'role="system"' in msg
        assert 'is_done="false"' in msg
        assert "Hello" in msg
        assert '</_bondmessage>' in msg

    def test_xml_escaping_in_ids(self):
        msg = _build_system_message("t<1>", "a&1", "Test")
        assert 'thread_id="t&lt;1&gt;"' in msg
        assert 'agent_id="a&amp;1"' in msg


# ---------------------------------------------------------------------------
# No forwarding — existing behavior preserved
# ---------------------------------------------------------------------------

class TestNoForwarding:
    def test_normal_response_passes_through(self):
        """Response without bond://forward link streams normally."""
        chunks = _bond_msg(content="Hello world")
        agent = _make_mock_agent("a1", "Agent1", chunks)
        provider = _make_provider()

        results = list(_simulate_forwarding_generator(agent, provider))

        full = ''.join(results)
        assert "Hello world" in full
        # No forwarding message
        assert "Forwarding to" not in full

    def test_bond_prompt_link_not_treated_as_forward(self):
        """bond://prompt links should not trigger forwarding."""
        chunks = _bond_msg(content="Click [here](bond://prompt) to continue")
        agent = _make_mock_agent("a1", "Agent1", chunks)
        provider = _make_provider()

        results = list(_simulate_forwarding_generator(agent, provider))

        full = ''.join(results)
        assert "Forwarding to" not in full
        assert "bond://prompt" in full


# ---------------------------------------------------------------------------
# Short ID normalization (prefix stripped in UI, re-added in backend)
# ---------------------------------------------------------------------------

class TestSlugGeneration:
    def test_generate_slug_format(self):
        """Generated slugs follow adjective-verb-noun pattern."""
        from bondable.bond.slug import generate_slug
        slug = generate_slug()
        parts = slug.split("-")
        assert len(parts) == 3, f"Expected 3 parts, got {parts}"
        assert all(part.isalpha() for part in parts), f"All parts should be alpha: {slug}"

    def test_generate_slug_uniqueness(self):
        """Generated slugs are highly unlikely to collide."""
        from bondable.bond.slug import generate_slug
        slugs = {generate_slug() for _ in range(1000)}
        assert len(slugs) == 1000, f"Expected 1000 unique slugs, got {len(slugs)}"


# ---------------------------------------------------------------------------
# Happy path forwarding (using agent IDs)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Happy path forwarding
# ---------------------------------------------------------------------------

class TestForwardHappyPath:
    def test_forward_to_another_agent(self):
        """Agent A outputs forward link with slug, Agent B is invoked."""
        agent_a_chunks = _bond_msg(
            agent_id="a1",
            content="You should talk to [Helper](bond://forward/brave-sailing-fox) for this."
        )
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_b_chunks = _bond_msg(agent_id="a2", content="Hello from Helper!")
        agent_b = _make_mock_agent("a2", "Helper", agent_b_chunks)

        provider = _make_provider(agents_by_slug={"brave-sailing-fox": agent_b})

        results = list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        full = ''.join(results)
        assert "You should talk to" in full
        assert "Forwarding to Helper" in full
        assert "Hello from Helper!" in full

        agent_b.stream_response.assert_called_once()
        call_kwargs = agent_b.stream_response.call_args[1]
        assert call_kwargs['thread_id'] == "test-thread-123"
        assert "forwarded" in call_kwargs['prompt'].lower()

    def test_forward_chain_three_agents(self):
        """A -> B -> C chain works correctly."""
        agent_a_chunks = _bond_msg(agent_id="a1", content="Go to [B](bond://forward/calm-diving-oak)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_b_chunks = _bond_msg(agent_id="a2", content="Go to [C](bond://forward/swift-rising-hawk)")
        agent_b = _make_mock_agent("a2", "AgentB", agent_b_chunks)

        agent_c_chunks = _bond_msg(agent_id="a3", content="Final answer from C!")
        agent_c = _make_mock_agent("a3", "AgentC", agent_c_chunks)

        provider = _make_provider(agents_by_slug={
            "calm-diving-oak": agent_b,
            "swift-rising-hawk": agent_c,
        })

        results = list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        full = ''.join(results)
        assert "Forwarding to AgentB" in full
        assert "Forwarding to AgentC" in full
        assert "Final answer from C!" in full

    def test_forward_preserves_thread_id(self):
        """Forwarded agent uses the same thread_id."""
        agent_a_chunks = _bond_msg(content="[X](bond://forward/keen-gliding-elm)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_x_chunks = _bond_msg(content="Response from X")
        agent_x = _make_mock_agent("ax", "AgentX", agent_x_chunks)

        provider = _make_provider(agents_by_slug={"keen-gliding-elm": agent_x})

        list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA",
            thread_id="my-special-thread"
        ))

        call_kwargs = agent_x.stream_response.call_args[1]
        assert call_kwargs['thread_id'] == "my-special-thread"

    def test_forward_does_not_change_last_agent_id(self):
        """Forwarding should NOT update last_agent_id — the user's chosen agent stays current."""
        agent_a_chunks = _bond_msg(content="[X](bond://forward/keen-gliding-elm)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_x_chunks = _bond_msg(content="X response")
        agent_x = _make_mock_agent("ax", "AgentX", agent_x_chunks)

        provider = _make_provider(agents_by_slug={"keen-gliding-elm": agent_x})

        list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        # last_agent_id should NOT be updated during forwarding
        provider.threads.update_thread_last_agent.assert_not_called()

    def test_forward_passes_original_prompt(self):
        """Forwarded agent's prompt contains the original user prompt."""
        agent_a_chunks = _bond_msg(content="[X](bond://forward/keen-gliding-elm)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_x_chunks = _bond_msg(content="X response")
        agent_x = _make_mock_agent("ax", "AgentX", agent_x_chunks)

        provider = _make_provider(agents_by_slug={"keen-gliding-elm": agent_x})

        list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA",
            prompt="Help me with billing"
        ))

        call_kwargs = agent_x.stream_response.call_args[1]
        assert "Help me with billing" in call_kwargs['prompt']

    def test_forward_does_not_pass_attachments(self):
        """Forwarded agent should not receive the original attachments."""
        agent_a_chunks = _bond_msg(content="[X](bond://forward/keen-gliding-elm)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_x_chunks = _bond_msg(content="X response")
        agent_x = _make_mock_agent("ax", "AgentX", agent_x_chunks)

        provider = _make_provider(agents_by_slug={"keen-gliding-elm": agent_x})

        list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        call_kwargs = agent_x.stream_response.call_args[1]
        assert call_kwargs['attachments'] == []


# ---------------------------------------------------------------------------
# Forwarding only from assistant content
# ---------------------------------------------------------------------------

class TestForwardFromAssistantOnly:
    def test_forward_link_in_system_message_ignored(self):
        """Forward links in system (non-assistant) messages are not detected."""
        chunks = [
            '<_bondmessage id="1" thread_id="t" agent_id="a" type="text" role="system" is_error="false" is_done="false">',
            "[X](bond://forward/keen-gliding-elm)",
            '</_bondmessage>',
        ]
        agent = _make_mock_agent("a1", "AgentA", chunks)
        agent_x = _make_mock_agent("ax", "AgentX", [])
        provider = _make_provider(agents_by_slug={"keen-gliding-elm": agent_x})

        results = list(_simulate_forwarding_generator(agent, provider))

        full = ''.join(results)
        assert "Forwarding to" not in full

    def test_forward_link_in_error_message_ignored(self):
        """Forward links in error messages are not detected."""
        chunks = [
            '<_bondmessage id="1" thread_id="t" agent_id="a" type="error" role="system" is_error="true" is_done="true">',
            "[X](bond://forward/keen-gliding-elm)",
            '</_bondmessage>',
        ]
        agent = _make_mock_agent("a1", "AgentA", chunks)
        agent_x = _make_mock_agent("ax", "AgentX", [])
        provider = _make_provider(agents_by_slug={"keen-gliding-elm": agent_x})

        results = list(_simulate_forwarding_generator(agent, provider))

        full = ''.join(results)
        assert "Forwarding to" not in full


# ---------------------------------------------------------------------------
# Forwarding error cases
# ---------------------------------------------------------------------------

class TestForwardAgentNotFound:
    def test_agent_not_found(self):
        """Forward to nonexistent slug emits error message."""
        agent_a_chunks = _bond_msg(content="[Ghost](bond://forward/ghost-missing-agent)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        provider = _make_provider(agents_by_slug={})

        results = list(_simulate_forwarding_generator(agent_a, provider))

        full = ''.join(results)
        assert "not found" in full

    def test_agent_lookup_exception(self):
        """Exception during agent lookup emits not-found message."""
        agent_a_chunks = _bond_msg(content="[X](bond://forward/broken-slug-here)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        provider = _make_provider()
        provider.agents.get_agent_by_slug.side_effect = Exception("DB error")

        results = list(_simulate_forwarding_generator(agent_a, provider))

        full = ''.join(results)
        assert "not found" in full


class TestForwardAccessDenied:
    def test_user_cannot_access_target(self):
        """Forward to agent user can't access emits access error."""
        agent_a_chunks = _bond_msg(content="[Restricted](bond://forward/locked-iron-gate)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_r = _make_mock_agent("ar", "Restricted", [])
        provider = _make_provider(agents_by_slug={"locked-iron-gate": agent_r}, can_access=False)

        results = list(_simulate_forwarding_generator(agent_a, provider))

        full = ''.join(results)
        assert "do not have access" in full
        # Agent R should not have been invoked
        agent_r.stream_response.assert_not_called()


# ---------------------------------------------------------------------------
# Circular forwarding detection
# ---------------------------------------------------------------------------

class TestCircularForwarding:
    def test_a_to_b_to_a_detected(self):
        """A -> B -> A circular forwarding is detected and stopped."""
        agent_a_chunks = _bond_msg(agent_id="a1", content="[B](bond://forward/calm-diving-oak)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        # Agent B tries to forward back to A
        agent_b_chunks = _bond_msg(agent_id="a2", content="[A](bond://forward/bold-running-deer)")
        agent_b = _make_mock_agent("a2", "AgentB", agent_b_chunks)

        agent_a_copy = _make_mock_agent("a1", "AgentA", [])
        provider = _make_provider(agents_by_slug={
            "calm-diving-oak": agent_b,
            "bold-running-deer": agent_a_copy,
        })

        results = list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        full = ''.join(results)
        assert "circular forwarding detected" in full
        agent_a_copy.stream_response.assert_not_called()

    def test_self_forward_detected(self):
        """Agent forwarding to itself is detected as circular."""
        agent_a_chunks = _bond_msg(agent_id="a1", content="[AgentA](bond://forward/bold-running-deer)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_a_copy = _make_mock_agent("a1", "AgentA", [])
        provider = _make_provider(agents_by_slug={"bold-running-deer": agent_a_copy})

        results = list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        full = ''.join(results)
        assert "circular forwarding detected" in full


# ---------------------------------------------------------------------------
# Depth limit
# ---------------------------------------------------------------------------

class TestForwardDepthLimit:
    def test_exceeds_max_depth(self):
        """Forwarding chain that exceeds MAX_FORWARD_DEPTH stops without error."""
        # Build a chain of agents with slugs: slug0 -> slug1 -> ...
        agents_by_slug = {}
        prev_agent = None

        for i in range(_MAX_FORWARD_DEPTH + 2):
            next_slug = f"chain-step-{i + 1}"
            if i <= _MAX_FORWARD_DEPTH:
                chunks = _bond_msg(
                    agent_id=f"id{i}",
                    content=f"Forwarding [Agent{i + 1}](bond://forward/{next_slug})"
                )
            else:
                chunks = _bond_msg(agent_id=f"id{i}", content="Final response")

            agent = _make_mock_agent(f"id{i}", f"Agent{i}", chunks)
            if i > 0:
                agents_by_slug[f"chain-step-{i}"] = agent
            if i == 0:
                prev_agent = agent

        provider = _make_provider(agents_by_slug=agents_by_slug)

        results = list(_simulate_forwarding_generator(
            prev_agent, provider, agent_id="id0", agent_name="Agent0"
        ))

        full = ''.join(results)
        forwarding_count = full.count("Forwarding to")
        assert forwarding_count == _MAX_FORWARD_DEPTH


# ---------------------------------------------------------------------------
# Multiple forward links
# ---------------------------------------------------------------------------

class TestMultipleForwardLinks:
    def test_only_first_forward_link_used(self):
        """When response contains multiple forward links, only the first is used."""
        agent_a_chunks = _bond_msg(
            content="Go to [B](bond://forward/calm-diving-oak) or [C](bond://forward/swift-rising-hawk)"
        )
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_b_chunks = _bond_msg(content="Response from B")
        agent_b = _make_mock_agent("a2", "AgentB", agent_b_chunks)

        agent_c = _make_mock_agent("a3", "AgentC", [])

        provider = _make_provider(agents_by_slug={
            "calm-diving-oak": agent_b,
            "swift-rising-hawk": agent_c,
        })

        results = list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        full = ''.join(results)
        assert "Forwarding to AgentB" in full
        assert "Forwarding to AgentC" not in full
        agent_b.stream_response.assert_called_once()
        agent_c.stream_response.assert_not_called()


# ---------------------------------------------------------------------------
# Exception in forwarded agent
# ---------------------------------------------------------------------------

class TestForwardedException:
    def test_exception_in_forwarded_agent(self):
        """Exception in forwarded agent is handled with error message."""
        agent_a_chunks = _bond_msg(content="[B](bond://forward/calm-diving-oak)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_b = MagicMock()
        agent_b.get_agent_id.return_value = "a2"
        agent_b.get_name.return_value = "AgentB"
        agent_b.stream_response.side_effect = RuntimeError("Bedrock timeout")

        provider = _make_provider(agents_by_slug={"calm-diving-oak": agent_b})

        results = list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        full = ''.join(results)
        assert "Forwarding to AgentB" in full
        assert "Bedrock timeout" in full
        assert 'is_error="true"' in full


# ---------------------------------------------------------------------------
# T27: Read-only permission enforcement on forwarded agents
# ---------------------------------------------------------------------------

class TestForwardT27ReadOnly:
    def test_read_only_permission_applied_to_forwarded_agent(self):
        """T27: Forwarded agent should have write tools disabled for read-only users."""
        agent_a_chunks = _bond_msg(content="[B](bond://forward/calm-diving-oak)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_b_chunks = _bond_msg(content="Response from B")
        agent_b = _make_mock_agent("a2", "AgentB", agent_b_chunks)
        agent_b.metadata = {}

        provider = _make_provider(agents_by_slug={"calm-diving-oak": agent_b})
        provider.agents.get_user_agent_permission.return_value = 'can_use_read_only'

        list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        assert agent_b.metadata.get('allow_write_tools') is False

    def test_non_read_only_user_keeps_write_tools(self):
        """Non-read-only users should retain full tool access on forwarded agent."""
        agent_a_chunks = _bond_msg(content="[B](bond://forward/calm-diving-oak)")
        agent_a = _make_mock_agent("a1", "AgentA", agent_a_chunks)

        agent_b_chunks = _bond_msg(content="Response from B")
        agent_b = _make_mock_agent("a2", "AgentB", agent_b_chunks)
        agent_b.metadata = {}

        provider = _make_provider(agents_by_slug={"calm-diving-oak": agent_b})
        provider.agents.get_user_agent_permission.return_value = 'can_use'

        list(_simulate_forwarding_generator(
            agent_a, provider, agent_id="a1", agent_name="AgentA"
        ))

        assert 'allow_write_tools' not in agent_b.metadata
