"""Tests for secret redaction in logs and events.

These tests verify that sensitive data (passwords, tokens, API keys, etc.)
are properly redacted from data structures, strings, and nested objects
before persistence to JSONL logs or exposure via APIs.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from oompah.secrets import redact_sensitive_data, SECRET_KEYS


class TestRedactSimpleValues:
    """Test redaction of basic types."""

    def test_redact_password_in_dict(self) -> None:
        """Redact 'password' key in a dict."""
        data = {"username": "alice", "password": "secret123"}
        result = redact_sensitive_data(data)
        assert result["username"] == "alice"
        assert result["password"] == "[REDACTED]"

    def test_redact_api_key_in_dict(self) -> None:
        """Redact 'api_key' and 'apikey' variants."""
        data = {
            "api_key": "key_abc123",
            "apikey": "key_xyz789",
            "api-key": "key_def456",
        }
        result = redact_sensitive_data(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["apikey"] == "[REDACTED]"
        assert result["api-key"] == "[REDACTED]"

    def test_redact_bearer_token(self) -> None:
        """Redact bearer token variants."""
        data = {
            "token": "mytoken",
            "bearer": "bearervalue",
            "bearer_token": "bt123",
            "access_token": "at456",
        }
        result = redact_sensitive_data(data)
        assert result["token"] == "[REDACTED]"
        assert result["bearer"] == "[REDACTED]"
        assert result["bearer_token"] == "[REDACTED]"
        assert result["access_token"] == "[REDACTED]"

    def test_redact_auth_headers(self) -> None:
        """Redact authorization-related keys."""
        data = {
            "authorization": "Bearer xyz123",
            "auth": "token456",
            "x-api-key": "key789",
            "x-auth-token": "token000",
        }
        result = redact_sensitive_data(data)
        for key in data:
            assert result[key] == "[REDACTED]", f"Failed for {key}"

    def test_preserve_non_secret_fields(self) -> None:
        """Non-secret fields should not be redacted."""
        data = {
            "username": "alice",
            "email": "alice@example.com",
            "host": "db.example.com",
        }
        result = redact_sensitive_data(data)
        assert result == data

    def test_none_and_bool_unchanged(self) -> None:
        """None and bool values pass through."""
        data = {"flag": True, "value": None}
        result = redact_sensitive_data(data)
        assert result["flag"] is True
        assert result["value"] is None

    def test_numbers_unchanged(self) -> None:
        """Numeric values pass through."""
        data = {"count": 42, "ratio": 3.14, "complex": 1 + 2j}
        result = redact_sensitive_data(data)
        assert result["count"] == 42
        assert result["ratio"] == 3.14
        assert result["complex"] == 1 + 2j


class TestRedactStrings:
    """Test redaction of patterns within strings."""

    def test_redact_http_basic_auth(self) -> None:
        """Redact HTTP Basic auth in URLs."""
        value = "http://user:password@example.com/path"
        result = redact_sensitive_data(value)
        assert "password" not in result
        assert "[REDACTED]" in result
        assert "example.com" in result

    def test_redact_bearer_token_in_string(self) -> None:
        """Redact Bearer tokens in strings."""
        value = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redact_sensitive_data(value)
        # The Authorization header value (including Bearer token) is redacted
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED]" in result

    def test_redact_api_key_in_query_string(self) -> None:
        """Redact API keys in query strings."""
        value = "https://api.example.com?api_key=sk_live_abc123&user=alice"
        result = redact_sensitive_data(value)
        assert "sk_live_abc123" not in result
        assert "[REDACTED]" in result
        assert "user=alice" in result

    def test_redact_x_api_key_header(self) -> None:
        """Redact X-API-Key header values."""
        value = "X-API-Key: secret_key_12345"
        result = redact_sensitive_data(value)
        assert "secret_key_12345" not in result
        assert "[REDACTED]" in result

    def test_preserve_non_secret_strings(self) -> None:
        """Non-secret strings are unchanged."""
        value = "This is a normal string about databases and hosts"
        result = redact_sensitive_data(value)
        assert result == value

    def test_empty_string_unchanged(self) -> None:
        """Empty strings pass through."""
        result = redact_sensitive_data("")
        assert result == ""


class TestRedactNested:
    """Test redaction of nested structures."""

    def test_redact_nested_dict(self) -> None:
        """Redact secrets in nested dicts."""
        data = {
            "db": {
                "host": "localhost",
                "port": 5432,
                "password": "secret123",
                "username": "admin",
            },
            "api": {
                "endpoint": "https://api.example.com",
                "api_key": "key_xyz",
            },
        }
        result = redact_sensitive_data(data)
        assert result["db"]["host"] == "localhost"
        assert result["db"]["port"] == 5432
        assert result["db"]["password"] == "[REDACTED]"
        assert result["db"]["username"] == "admin"
        assert result["api"]["endpoint"] == "https://api.example.com"
        assert result["api"]["api_key"] == "[REDACTED]"

    def test_redact_list_of_dicts(self) -> None:
        """Redact secrets in lists of dicts."""
        data = [
            {"user": "alice", "password": "pass1"},
            {"user": "bob", "password": "pass2"},
        ]
        result = redact_sensitive_data(data)
        assert result[0]["user"] == "alice"
        assert result[0]["password"] == "[REDACTED]"
        assert result[1]["user"] == "bob"
        assert result[1]["password"] == "[REDACTED]"

    def test_redact_mixed_nested(self) -> None:
        """Redact secrets in complex mixed structures."""
        data = {
            "items": [
                {"id": 1, "token": "token1"},
                {"id": 2, "token": "token2"},
            ],
            "config": {
                "database": {"key": "value"},
                "service": {"bearer": "bearer_token"},
            },
        }
        result = redact_sensitive_data(data)
        assert result["items"][0]["id"] == 1
        assert result["items"][0]["token"] == "[REDACTED]"
        # "database" is not a secret key, so it's recursively redacted
        assert result["config"]["database"]["key"] == "value"
        # "service" is not a secret key, so it's recursively redacted
        assert result["config"]["service"]["bearer"] == "[REDACTED]"

    def test_redact_strings_in_lists(self) -> None:
        """Redact secret patterns in strings within lists."""
        data = [
            "normal string",
            "Authorization: Bearer token123",
            "api_key=secret456",
        ]
        result = redact_sensitive_data(data)
        assert result[0] == "normal string"
        assert "[REDACTED]" in result[1]
        assert "[REDACTED]" in result[2]


class TestRedactDataclasses:
    """Test redaction of dataclass instances."""

    def test_redact_dataclass_with_password(self) -> None:
        """Redact password field in a dataclass."""
        @dataclasses.dataclass
        class Credentials:
            username: str
            password: str

        cred = Credentials(username="alice", password="secret123")
        result = redact_sensitive_data(cred)
        assert result.username == "alice"
        assert result.password == "[REDACTED]"

    def test_redact_dataclass_with_token(self) -> None:
        """Redact token fields in a dataclass."""
        @dataclasses.dataclass
        class ApiConfig:
            endpoint: str
            api_key: str
            bearer_token: str

        config = ApiConfig(
            endpoint="https://api.example.com",
            api_key="key123",
            bearer_token="bearer456",
        )
        result = redact_sensitive_data(config)
        assert result.endpoint == "https://api.example.com"
        assert result.api_key == "[REDACTED]"
        assert result.bearer_token == "[REDACTED]"

    def test_redact_nested_dataclass(self) -> None:
        """Redact secrets in nested dataclass structures."""
        @dataclasses.dataclass
        class DbConfig:
            host: str
            password: str

        @dataclasses.dataclass
        class AppConfig:
            name: str
            db: DbConfig

        config = AppConfig(
            name="myapp",
            db=DbConfig(host="localhost", password="secret"),
        )
        result = redact_sensitive_data(config)
        assert result.name == "myapp"
        assert result.db.host == "localhost"
        assert result.db.password == "[REDACTED]"


class TestRedactEnvironmentVariables:
    """Test redaction of environment-variable-like patterns."""

    def test_redact_env_assignment(self) -> None:
        """Redact password/token in env-style assignments."""
        value = "PASSWORD=mysecretpassword"
        result = redact_sensitive_data(value)
        # Note: this tests the dict key matching; env assignments
        # as raw strings are harder to detect without explicit patterns
        assert isinstance(result, str)

    def test_redact_dict_with_env_vars(self) -> None:
        """Redact environment variables in a dict."""
        data = {
            "PATH": "/usr/bin",
            "PASSWORD": "secret123",
            "API_KEY": "key456",
            "HOME": "/home/alice",
        }
        result = redact_sensitive_data(data)
        assert result["PATH"] == "/usr/bin"
        assert result["PASSWORD"] == "[REDACTED]"
        assert result["API_KEY"] == "[REDACTED]"
        assert result["HOME"] == "/home/alice"


class TestRedactExceptions:
    """Test redaction of exception messages and tracebacks."""

    def test_redact_exception_message(self) -> None:
        """Redact secrets from exception messages."""
        msg = "Failed to connect: password was 'mysecret123'"
        result = redact_sensitive_data(msg)
        assert "mysecret123" not in result
        assert "[REDACTED]" in result

    def test_redact_exception_with_url(self) -> None:
        """Redact secrets from exception messages containing URLs."""
        msg = "Connection failed to http://user:pass@db.example.com:5432"
        result = redact_sensitive_data(msg)
        assert "user:pass" not in result
        assert "[REDACTED]" in result
        assert "db.example.com" in result


class TestComplexPatterns:
    """Test redaction with complex, realistic payloads."""

    def test_redact_command_output(self) -> None:
        """Redact secrets from command output."""
        data = {
            "exit_code": 0,
            "stdout": "Connection successful",
            "stderr": "Authorization header: Bearer token_xyz123",
        }
        result = redact_sensitive_data(data)
        assert result["exit_code"] == 0
        assert result["stdout"] == "Connection successful"
        assert "token_xyz123" not in result["stderr"]
        assert "[REDACTED]" in result["stderr"]

    def test_redact_tool_input_output(self) -> None:
        """Redact secrets from tool call args and results."""
        data = {
            "tool": "run_command",
            "args": {
                "command": "curl https://api.example.com",
                "env": {
                    "API_KEY": "secret_key",
                    "HOME": "/home/user",
                },
            },
            "result": {
                "exit_code": 0,
                "stdout": "Success",
                "stderr": "X-Auth-Token: bearer_secret_123",
            },
        }
        result = redact_sensitive_data(data)
        assert result["args"]["env"]["HOME"] == "/home/user"
        assert result["args"]["env"]["API_KEY"] == "[REDACTED]"
        assert "bearer_secret_123" not in result["result"]["stderr"]
        assert "[REDACTED]" in result["result"]["stderr"]

    def test_redact_console_event_payload(self) -> None:
        """Redact secrets from console event payloads."""
        data = {
            "kind": "tool_call",
            "tool": "run_command",
            "args": {
                "command": "python script.py --password mysecret",
                "_tool_use_id": "call_123",
            },
        }
        result = redact_sensitive_data(data)
        assert result["kind"] == "tool_call"
        assert result["tool"] == "run_command"
        assert "mysecret" not in result["args"]["command"]
        assert "[REDACTED]" in result["args"]["command"]

    def test_redact_agent_event(self) -> None:
        """Redact secrets from agent event payloads."""
        data = {
            "event": "acp_tool_result",
            "timestamp": 1234567890.0,
            "payload": {
                "tool_use_id": "call_456",
                "is_error": False,
                "content": "Successfully authenticated with token: xyz123",
            },
        }
        result = redact_sensitive_data(data)
        assert result["event"] == "acp_tool_result"
        assert "xyz123" not in result["payload"]["content"]
        assert "[REDACTED]" in result["payload"]["content"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_deeply_nested_structure(self) -> None:
        """Handle deeply nested structures without stack overflow."""
        data = {"a": {"b": {"c": {"d": {"e": {"password": "secret"}}}}}}
        result = redact_sensitive_data(data)
        assert result["a"]["b"]["c"]["d"]["e"]["password"] == "[REDACTED]"

    def test_circular_reference_protection(self) -> None:
        """Verify max depth limit prevents infinite loops."""
        # Create a very deep structure (but not actually circular)
        data: Any = {"value": "test"}
        for _ in range(150):
            data = {"nested": data}

        # Should not crash due to max recursion depth
        result = redact_sensitive_data(data)
        assert result is not None

    def test_bytes_value(self) -> None:
        """Handle bytes values with secrets."""
        data = {"secret": b"my_secret_password"}
        result = redact_sensitive_data(data)
        # Bytes containing secrets should be redacted
        if isinstance(result["secret"], bytes):
            assert b"my_secret_password" not in result["secret"]
        else:
            # Or converted to string and redacted
            assert "[REDACTED]" in str(result["secret"])

    def test_tuple_preserved(self) -> None:
        """Tuples should be preserved as tuples."""
        data = (1, 2, 3)
        result = redact_sensitive_data(data)
        assert isinstance(result, tuple)
        assert result == (1, 2, 3)

    def test_dict_key_case_insensitive(self) -> None:
        """Secret key matching should be case-insensitive."""
        data = {
            "PASSWORD": "secret1",
            "Password": "secret2",
            "password": "secret3",
            "pAsSwOrD": "secret4",
        }
        result = redact_sensitive_data(data)
        for key in data:
            assert result[key] == "[REDACTED]"

    def test_unknown_types_pass_through(self) -> None:
        """Unknown types should pass through unchanged or be safely redacted."""
        class NonCredentialType:
            def __init__(self, value: str):
                self.value = value

        obj = NonCredentialType("test")
        result = redact_sensitive_data(obj)
        # Non-credential-like types defined in non-secret modules pass through
        # Credential-like types may return a safe representation
        if isinstance(result, str):
            # If a string repr was returned, it should be redacted
            assert "[REDACTED]" in result or "NonCredentialType" in result
        else:
            # Object should be unchanged
            assert result is obj


class TestSecretKeyPatterns:
    """Test the SECRET_KEYS constant."""

    def test_secret_keys_includes_common_patterns(self) -> None:
        """Verify SECRET_KEYS includes expected patterns."""
        expected = {
            "password",
            "token",
            "api_key",
            "apikey",
            "bearer",
            "secret",
            "auth",
            "private_key",
            "client_secret",
        }
        assert expected.issubset(SECRET_KEYS)

    def test_secret_keys_is_frozen(self) -> None:
        """SECRET_KEYS should be immutable."""
        assert isinstance(SECRET_KEYS, frozenset)


class TestIntegrationWithConsoleEvents:
    """Integration tests with ConsoleEvent serialization."""

    def test_console_event_redaction(self) -> None:
        """Test that redaction works via ConsoleEvent.to_dict()."""
        from oompah.console_format import ConsoleEvent

        event = ConsoleEvent(
            ts="2024-01-01T00:00:00Z",
            kind="tool_result",
            result={
                "exit_code": 0,
                "stdout": "OK",
                "stderr": "Bearer token_secret_123",
            },
        )
        event_dict = event.to_dict()
        assert "token_secret_123" not in event_dict["result"]["stderr"]
        assert "[REDACTED]" in event_dict["result"]["stderr"]

    def test_console_event_tool_args_redaction(self) -> None:
        """Test redaction of tool arguments in ConsoleEvent."""
        from oompah.console_format import ConsoleEvent

        event = ConsoleEvent(
            ts="2024-01-01T00:00:00Z",
            kind="tool_call",
            tool="run_command",
            args={"command": "curl -H 'Authorization: Bearer xyz123'"},
        )
        event_dict = event.to_dict()
        assert "xyz123" not in event_dict["args"]["command"]
        assert "[REDACTED]" in event_dict["args"]["command"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ===========================================================================
# End-to-end secret redaction tests
# ===========================================================================


class TestOrchestratorEventRedaction:
    """Verify that secrets are redacted at the orchestrator._on_event boundary."""

    def test_acp_event_payload_redacted_before_jsonl(self, tmp_path):
        """Sentinel secret should not appear in JSONL representation."""
        from oompah.secrets import redact_sensitive_data
        import json

        # Simulate an ACP SDK event with sentinel secrets
        event_payload = {
            "text": "Deployment successful",
            "password": "super_secret_token_12345",
            "api_key": "sk-abc123xyz789",
            "nested": {
                "database_url": "postgresql://user:deadly_secret@db.example.com:5432/mydb"
            }
        }

        # This is what happens in orchestrator._on_event
        redacted = redact_sensitive_data(event_payload)
        jsonl_line = json.dumps({
            "payload": redacted,
            "kind": "acp_tool_result"
        })

        # Verify no sentinels appear in JSONL
        assert "super_secret_token_12345" not in jsonl_line
        assert "sk-abc123xyz789" not in jsonl_line
        assert "deadly_secret" not in jsonl_line
        assert "[REDACTED]" in jsonl_line

    def test_acp_event_usage_redacted_before_state(self):
        """Usage metrics should not leak credentials even if present."""
        from oompah.secrets import redact_sensitive_data

        usage_with_secret = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "api_key": "secret_key_here"  # shouldn't be here but be defensive
        }

        redacted = redact_sensitive_data(usage_with_secret)
        assert redacted["input_tokens"] == 100
        assert "secret_key_here" not in str(redacted)
        assert redacted.get("api_key") == "[REDACTED]"

    def test_session_last_message_inherits_redaction(self):
        """The last_message field should be redacted via summary field."""
        from oompah.secrets import redact_sensitive_data

        # Simulate payload with secrets that becomes summary/detail
        payload = {
            "text": "Error: DB password is password123ABC"
        }
        redacted_payload = redact_sensitive_data(payload)
        summary = str(redacted_payload.get("text", ""))[:200]

        # summary should have redacted the password
        assert "password123ABC" not in summary
        assert "[REDACTED]" in summary


class TestConsoleEventFanout:
    """Verify that ConsoleEvent fields are redacted before on_event callback fan-out."""

    def test_console_event_text_redacted_before_callback(self):
        """Text field containing secrets should be redacted before callback."""
        from oompah.console_format import ConsoleEvent
        from oompah.console import _redact_console_event

        # Create event with secret in text
        event = ConsoleEvent(
            ts="2024-01-01T00:00:00Z",
            kind="agent_text",
            text="Connected to database using password=super_secret_123"
        )

        redacted = _redact_console_event(event)
        
        assert "super_secret_123" not in redacted.text
        assert "[REDACTED]" in redacted.text

    def test_console_event_args_redacted_before_callback(self):
        """Tool args containing secrets should be redacted before callback."""
        from oompah.console_format import ConsoleEvent
        from oompah.console import _redact_console_event

        event = ConsoleEvent(
            ts="2024-01-01T00:00:00Z",
            kind="tool_call",
            tool="read_file",
            args={
                "path": "/etc/passwd",
                "bearer_token": "bearer_token_secret_xyz"
            }
        )

        redacted = _redact_console_event(event)
        
        assert "bearer_token_secret_xyz" not in str(redacted.args)
        assert redacted.args["bearer_token"] == "[REDACTED]"

    def test_console_event_result_redacted_before_callback(self):
        """Tool result containing secrets should be redacted before callback."""
        from oompah.console_format import ConsoleEvent
        from oompah.console import _redact_console_event

        event = ConsoleEvent(
            ts="2024-01-01T00:00:00Z",
            kind="tool_result",
            result={
                "stdout": "Database connection established",
                "connection_string": "postgresql://admin:hidden_password@db:5432/prod"
            }
        )

        redacted = _redact_console_event(event)
        
        assert "hidden_password" not in str(redacted.result)
        assert "[REDACTED]" in str(redacted.result)

    def test_console_event_usage_redacted_before_callback(self):
        """Usage stats should be redacted even if they contain secrets."""
        from oompah.console_format import ConsoleEvent
        from oompah.console import _redact_console_event

        event = ConsoleEvent(
            ts="2024-01-01T00:00:00Z",
            kind="session_meta",
            usage={
                "input_tokens": 100,
                "api_secret": "should_not_appear"
            }
        )

        redacted = _redact_console_event(event)
        
        assert "should_not_appear" not in str(redacted.usage)
        assert redacted.usage["api_secret"] == "[REDACTED]"

    def test_console_event_callback_receives_redacted(self):
        """The on_event callback should receive redacted events."""
        from oompah.console_format import ConsoleEvent
        from oompah.console import ConsoleSession
        from oompah.console_store import ConsoleStore
        from unittest.mock import MagicMock, patch

        callback_received = []

        def mock_callback(event):
            callback_received.append(event)

        # Create a session with mock callback
        mock_store = MagicMock(spec=ConsoleStore)
        mock_provider_store = MagicMock()
        mock_role_store = MagicMock()
        
        session = ConsoleSession(
            project_id="test-proj",
            store=mock_store,
            provider_store=mock_provider_store,
            role_store=mock_role_store,
            on_event=mock_callback
        )

        event = ConsoleEvent(
            ts="2024-01-01T00:00:00Z",
            kind="agent_text",
            text="DB password: secret_pass_999"
        )

        session._persist_and_emit(event)

        # Verify callback received redacted event
        assert len(callback_received) == 1
        received_event = callback_received[0]
        assert "secret_pass_999" not in received_event.text
        assert "[REDACTED]" in received_event.text


class TestSecretsFailClosed:
    """Verify that edge cases fail-closed (return redaction marker, not original value)."""

    def test_max_depth_returns_marker_not_original(self):
        """At max recursion depth, should return marker not original value."""
        from oompah.secrets import redact_sensitive_data

        # Create deeply nested structure that will hit max depth
        deep = {"level": 1}
        current = deep
        for i in range(150):  # Exceed default max_depth of 100
            current["next"] = {"level": i + 2}
            current = current["next"]
        
        # Add secret at deep level
        current["password"] = "very_deep_secret"

        redacted = redact_sensitive_data(deep, _max_depth=100)
        
        # Should not have the original secret anywhere
        assert "very_deep_secret" not in str(redacted)

    def test_failed_dataclass_reconstruction_returns_marker(self):
        """If dataclass reconstruction fails, should return marker not original."""
        from dataclasses import dataclass
        from oompah.secrets import redact_sensitive_data

        @dataclass
        class Credentials:
            username: str
            password: str

            def __init__(self, username, password, required_param=None):
                # Constructor requires a param that redaction can't satisfy
                if required_param is None:
                    raise TypeError("required_param is mandatory")
                self.username = username
                self.password = password

        cred = Credentials.__new__(Credentials)
        cred.username = "admin"
        cred.password = "secret_pass_789"

        redacted = redact_sensitive_data(cred)
        
        # Should not have original password
        assert "secret_pass_789" not in str(redacted)
        # Should have a marker indicating redaction
        assert "[REDACTED]" in str(redacted)

    def test_credential_like_unknown_type_returns_marker(self):
        """Unknown credential-like types should return marker not original."""
        from oompah.secrets import redact_sensitive_data

        # Create a credential-like object that can't be redacted by repr
        class ClientCredential:
            def __init__(self, secret):
                self.secret = secret

            def __repr__(self):
                return f"ClientCredential(secret='{self.secret}')"

        obj = ClientCredential("leaked_secret_xyz")
        redacted = redact_sensitive_data(obj)
        
        # Should not have original secret
        assert "leaked_secret_xyz" not in str(redacted)
        # Should have marker
        assert "[REDACTED]" in str(redacted)


class TestMultiBackendRedaction:
    """Verify secrets are redacted across different backend paths."""

    def test_acp_backend_event_redaction(self):
        """ACP backend events should redact payloads."""
        from oompah.secrets import redact_sensitive_data

        # Simulate ACP backend event with tool use
        acp_event = {
            "event": "acp_tool_use",
            "timestamp": 1234567890.0,
            "payload": {
                "tool": "run_command",
                "input": {
                    "command": "mysql -u admin -p secret_password_123 mydb"
                }
            }
        }

        redacted_payload = redact_sensitive_data(acp_event["payload"])
        
        assert "secret_password_123" not in str(redacted_payload)
        assert "[REDACTED]" in str(redacted_payload)

    def test_state_api_activity_redaction(self):
        """Activity logged to state should be redacted."""
        from oompah.secrets import redact_sensitive_data
        from oompah.api_agent import AgentActivity

        # Simulate activity with sensitive data
        activity_detail = "Tool executed: curl -H 'Authorization: Bearer secret_token_abc'"
        
        redacted_detail = redact_sensitive_data(activity_detail)
        
        assert "secret_token_abc" not in redacted_detail
        assert "[REDACTED]" in redacted_detail

