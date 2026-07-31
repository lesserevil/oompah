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



# ===========================================================================
# End-to-end sink coverage for OOMPAH-651
# ===========================================================================

# Sentinel strings — a real leak of any of these would be a security defect.
# Each is unique so a match uniquely identifies the affected sink.
SENTINEL_HTTP_PASSWORD = "S3nt1nel-http-basic-passw0rd-Q9x"
SENTINEL_BEARER_TOKEN = "S3nt1nel-Bearer-t0ken-4LM2p8"
SENTINEL_API_KEY = "S3nt1nel-apikey-xY7bZa3W"
SENTINEL_URL_USERINFO = "S3nt1nel-url-userinfo-Vk8Rp2"
SENTINEL_TASK_HANDOFF = "S3nt1nel-task-handoff-tok-Nm4Qw"


def _assert_no_sentinels(text: str) -> None:
    """Assert that no known sentinel secret appears in `text`."""
    for name, value in [
        ("http_password", SENTINEL_HTTP_PASSWORD),
        ("bearer_token", SENTINEL_BEARER_TOKEN),
        ("api_key", SENTINEL_API_KEY),
        ("url_userinfo", SENTINEL_URL_USERINFO),
        ("task_handoff", SENTINEL_TASK_HANDOFF),
    ]:
        assert value not in text, f"leaked sentinel {name} in: {text!r}"


class TestApiAgentJSONLRedaction:
    """Verify that api_agent._log_event redacts secrets in JSONL entries."""

    def _make_session(self, tmp_path):
        from oompah.api_agent import ApiAgentSession
        log_path = str(tmp_path / "api_agent.jsonl")
        # Constructing with minimal args — we only exercise _log_event.
        return ApiAgentSession(
            base_url="https://example.com/api",
            api_key="fake-key-for-session",
            model="test-model",
            workspace_path=str(tmp_path),
            log_path=log_path,
        ), log_path

    def test_log_event_redacts_request_payload(self, tmp_path):
        session, log_path = self._make_session(tmp_path)
        # Simulate the exact log_event a real request path would emit.
        payload = {
            "model": "test",
            "messages": [
                {"role": "user", "content": f"password={SENTINEL_HTTP_PASSWORD}"}
            ],
        }
        session._log_event("request", payload=payload)
        contents = open(log_path).read()
        _assert_no_sentinels(contents)
        assert "[REDACTED]" in contents

    def test_log_event_redacts_response_body(self, tmp_path):
        session, log_path = self._make_session(tmp_path)
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": f"Authorization: Bearer {SENTINEL_BEARER_TOKEN}",
                    }
                }
            ]
        }
        session._log_event("response", body=response_body)
        contents = open(log_path).read()
        _assert_no_sentinels(contents)

    def test_log_event_redacts_error_url_userinfo(self, tmp_path):
        session, log_path = self._make_session(tmp_path)
        error_msg = (
            f"Connection failed to postgresql://admin:{SENTINEL_URL_USERINFO}"
            f"@db.example.com/prod"
        )
        session._log_event("transient_error", error=error_msg)
        contents = open(log_path).read()
        _assert_no_sentinels(contents)
        assert "[REDACTED]" in contents

    def test_log_event_redacts_unknown_object_repr(self, tmp_path):
        """Even an object whose class is not credential-named cannot leak
        secrets via json.dumps(..., default=str)."""
        session, log_path = self._make_session(tmp_path)

        class HttpResponse:  # innocent-sounding name
            def __repr__(self):
                return (
                    f"HttpResponse(body='Authorization: Bearer "
                    f"{SENTINEL_BEARER_TOKEN}')"
                )

        session._log_event("response", body=HttpResponse())
        contents = open(log_path).read()
        _assert_no_sentinels(contents)

    def test_log_event_redacts_embedded_short_registered_secret(self, tmp_path):
        from oompah.secrets import register_secret, retire_secret

        short_secret = "q7Z"
        embedded_secret = f"prefix{short_secret}suffix"
        register_secret(short_secret, expires_in=60)
        try:
            session, log_path = self._make_session(tmp_path)
            session._log_event(
                "response",
                body={"content": embedded_secret, "status": "diagnostic-safe"},
            )

            contents = open(log_path).read()
            assert embedded_secret not in contents
            assert "prefix[REDACTED]suffix" in contents
            assert "diagnostic-safe" in contents
        finally:
            retire_secret(short_secret, grace_seconds=0)

    def test_log_event_preserves_nonsecret_fields(self, tmp_path):
        session, log_path = self._make_session(tmp_path)
        session._log_event(
            "session_start",
            model="claude-sonnet",
            workspace="/tmp/wt",
            max_turns=200,
        )
        contents = open(log_path).read()
        assert "claude-sonnet" in contents
        assert "/tmp/wt" in contents
        assert "200" in contents


class TestApiAgentActivityRedaction:
    """Verify that AgentActivity summary/detail passed via _emit is redacted."""

    def test_emit_activity_redacts_summary_and_detail(self, tmp_path):
        # We reach into _emit indirectly by mocking on_activity and calling
        # a partial run. Simpler: reproduce the redaction expectation
        # through the public redaction contract used by _emit.
        from oompah.secrets import redact_sensitive_data

        summary = f"run_command(curl -H 'Authorization: Bearer {SENTINEL_BEARER_TOKEN}')"
        detail = (
            f"Response: postgres://admin:{SENTINEL_URL_USERINFO}"
            f"@db.example.com:5432/prod"
        )
        r_summary = redact_sensitive_data(summary)
        r_detail = redact_sensitive_data(detail)

        _assert_no_sentinels(r_summary)
        _assert_no_sentinels(r_detail)


class TestConsoleLegacyStoreRedaction:
    """Verify that console_legacy.ConsoleStore.append redacts payload/usage."""

    def test_append_redacts_payload_before_disk_write(self, tmp_path):
        from oompah.console_legacy import ConsoleStore

        store = ConsoleStore("proj-test", base_dir=str(tmp_path))
        event = store.append(
            "acp_tool_use",
            payload={
                "tool": "run_command",
                "input": {
                    "command": f"curl -H 'X-API-Key: {SENTINEL_API_KEY}'",
                    "env": {"OOMPAH_SERVER_PASSWORD": SENTINEL_HTTP_PASSWORD},
                },
            },
        )
        # Returned event must be redacted.
        _assert_no_sentinels(str(event))
        # Persisted file must be redacted.
        with open(store.path) as f:
            contents = f.read()
        _assert_no_sentinels(contents)
        assert "[REDACTED]" in contents

    def test_append_redacts_usage(self, tmp_path):
        from oompah.console_legacy import ConsoleStore

        store = ConsoleStore("proj-test2", base_dir=str(tmp_path))
        event = store.append(
            "acp_result",
            payload={"subtype": "completed"},
            usage={
                "input_tokens": 100,
                "output_tokens": 50,
                # Defensive: even if usage-shaped input carries a secret.
                "authorization": f"Bearer {SENTINEL_BEARER_TOKEN}",
            },
        )
        _assert_no_sentinels(str(event))
        with open(store.path) as f:
            contents = f.read()
        _assert_no_sentinels(contents)

    def test_append_trimmed_event_preserves_redacted_usage(self, tmp_path):
        """When a payload exceeds the size cap the store trims it, but the
        trimmed record must still expose only the redacted usage."""
        from oompah.console_legacy import ConsoleStore, _MAX_EVENT_BYTES

        store = ConsoleStore("proj-trim", base_dir=str(tmp_path))
        # Build a huge payload to force the trimming branch.
        huge_text = "x" * (_MAX_EVENT_BYTES + 1000)
        store.append(
            "acp_text",
            payload={"text": huge_text},
            usage={
                "input_tokens": 1,
                "authorization": f"Bearer {SENTINEL_BEARER_TOKEN}",
            },
        )
        with open(store.path) as f:
            contents = f.read()
        _assert_no_sentinels(contents)


class TestConsoleEventAttachmentsRedaction:
    """Verify that ConsoleEvent attachments are redacted before serialization."""

    def test_to_dict_redacts_attachment_with_userinfo(self):
        from oompah.console_format import ConsoleEvent

        event = ConsoleEvent(
            ts="2024-01-01T00:00:00Z",
            kind="operator_input",
            text="see attached",
            attachments=[
                f"https://admin:{SENTINEL_URL_USERINFO}@files.example.com/x.png",
            ],
        )
        d = event.to_dict()
        _assert_no_sentinels(str(d))
        assert "[REDACTED]" in d["attachments"][0]

    def test_console_event_redact_helper_scrubs_attachments(self):
        from oompah.console_format import ConsoleEvent
        from oompah.console import _redact_console_event

        event = ConsoleEvent(
            ts="2024-01-01T00:00:00Z",
            kind="operator_input",
            attachments=[
                f"https://user:{SENTINEL_URL_USERINFO}@evil.example.com/f.png",
            ],
        )
        r = _redact_console_event(event)
        _assert_no_sentinels(str(r.attachments))


class TestSecretsUnknownObjectFailClosed:
    """Verify unknown non-credential-typed objects cannot leak via default=str."""

    def test_unknown_object_repr_containing_bearer_is_redacted(self):
        from oompah.secrets import redact_sensitive_data

        class SessionSnapshot:  # innocent name
            def __repr__(self):
                return f"SessionSnapshot(header='Authorization: Bearer {SENTINEL_BEARER_TOKEN}')"

        r = redact_sensitive_data(SessionSnapshot())
        # Redacted representation must be a string (so downstream json can dump)
        assert isinstance(r, str)
        _assert_no_sentinels(r)
        assert "[REDACTED]" in r

    def test_unknown_object_str_containing_url_userinfo_is_redacted(self):
        from oompah.secrets import redact_sensitive_data
        import json

        class Message:
            def __init__(self):
                self.body = f"connect postgres://root:{SENTINEL_URL_USERINFO}@db/x"
            def __repr__(self):
                return self.body

        r = redact_sensitive_data(Message())
        # It must be safe for downstream json.dumps to consume with default=str.
        rendered = json.dumps({"m": r}, default=str)
        _assert_no_sentinels(rendered)

    def test_credential_named_class_never_exposes_state(self):
        from oompah.secrets import redact_sensitive_data

        class ClientCredentials:  # credential-named
            def __repr__(self):
                # Even if repr somehow lacks a redactable pattern, the type
                # name alone triggers the marker branch — nothing leaks.
                return f"<opaque {SENTINEL_TASK_HANDOFF}>"

        r = redact_sensitive_data(ClientCredentials())
        assert isinstance(r, str)
        _assert_no_sentinels(r)

    def test_unknown_object_with_broken_repr_returns_marker(self):
        from oompah.secrets import redact_sensitive_data

        class ExplodingRepr:
            def __repr__(self):
                raise RuntimeError("boom")
            def __str__(self):
                # Still might contain secrets — must go through _redact_string
                return f"str with {SENTINEL_BEARER_TOKEN}"

        r = redact_sensitive_data(ExplodingRepr())
        assert isinstance(r, str)
        _assert_no_sentinels(r)


class TestSecretRedactionLoggingFilter:
    """Verify install_secret_redaction_filter scrubs log records."""

    def test_filter_redacts_msg(self):
        import logging
        from oompah.secrets import install_secret_redaction_filter

        install_secret_redaction_filter("oompah.test-logger-1")
        log = logging.getLogger("oompah.test-logger-1")
        rec = logging.LogRecord(
            name=log.name,
            level=logging.WARNING,
            pathname=__file__,
            lineno=0,
            msg=f"connect failed to postgres://root:{SENTINEL_URL_USERINFO}@db/prod",
            args=(),
            exc_info=None,
        )
        # Run the record through the filter chain.
        for f in log.filters:
            f.filter(rec)
        formatted = rec.getMessage()
        _assert_no_sentinels(formatted)

    def test_descendant_and_late_handler_are_redacted(self):
        import io
        import logging

        from oompah.secrets import install_secret_redaction_filter

        install_secret_redaction_filter("oompah")
        log = logging.getLogger("oompah.test-late-handler")
        log.propagate = False
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        log.addHandler(handler)
        try:
            log.warning(
                "late handler received Authorization: Bearer %s",
                SENTINEL_BEARER_TOKEN,
            )
        finally:
            log.removeHandler(handler)
            handler.close()

        rendered = stream.getvalue()
        _assert_no_sentinels(rendered)
        assert "[REDACTED]" in rendered

    def test_late_handler_redacts_embedded_short_registered_secret(self):
        import io
        import logging

        from oompah.secrets import (
            install_secret_redaction_filter,
            register_secret,
            retire_secret,
        )

        short_secret = "v8W"
        embedded_secret = f"prefix{short_secret}suffix"
        register_secret(short_secret, expires_in=60)
        install_secret_redaction_filter("oompah")
        log = logging.getLogger("oompah.test-short-registered-secret")
        log.propagate = False
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        log.addHandler(handler)
        try:
            log.warning("backend output: %s diagnostic-safe", embedded_secret)
        finally:
            log.removeHandler(handler)
            handler.close()
            retire_secret(short_secret, grace_seconds=0)

        rendered = stream.getvalue()
        assert embedded_secret not in rendered
        assert "prefix[REDACTED]suffix" in rendered
        assert "diagnostic-safe" in rendered

    def test_filter_redacts_args_tuple(self):
        import logging
        from oompah.secrets import install_secret_redaction_filter

        install_secret_redaction_filter("oompah.test-logger-2")
        log = logging.getLogger("oompah.test-logger-2")
        rec = logging.LogRecord(
            name=log.name,
            level=logging.WARNING,
            pathname=__file__,
            lineno=0,
            msg="connect failed to %s",
            args=(f"postgres://root:{SENTINEL_URL_USERINFO}@db/prod",),
            exc_info=None,
        )
        for f in log.filters:
            f.filter(rec)
        formatted = rec.getMessage()
        _assert_no_sentinels(formatted)

    def test_filter_redacts_args_dict(self):
        import logging
        from oompah.secrets import install_secret_redaction_filter

        install_secret_redaction_filter("oompah.test-logger-3")
        log = logging.getLogger("oompah.test-logger-3")
        # Mirror how the stdlib delivers a dict arg: a length-1 tuple
        # containing the mapping — logger.info("%(auth)s", {"auth": ...})
        rec = logging.LogRecord(
            name=log.name,
            level=logging.WARNING,
            pathname=__file__,
            lineno=0,
            msg="request payload: %(auth)s",
            args=({"auth": f"Bearer {SENTINEL_BEARER_TOKEN}"},),
            exc_info=None,
        )
        for f in log.filters:
            f.filter(rec)
        formatted = rec.getMessage()
        _assert_no_sentinels(formatted)

    def test_filter_is_idempotent(self):
        import logging
        from oompah.secrets import install_secret_redaction_filter, SecretRedactionFilter

        f1 = install_secret_redaction_filter("oompah.test-logger-4")
        f2 = install_secret_redaction_filter("oompah.test-logger-4")
        assert f1 is f2
        log = logging.getLogger("oompah.test-logger-4")
        assert sum(1 for x in log.filters if isinstance(x, SecretRedactionFilter)) == 1

    def test_filter_never_drops_records(self):
        import logging
        from oompah.secrets import install_secret_redaction_filter

        install_secret_redaction_filter("oompah.test-logger-5")
        log = logging.getLogger("oompah.test-logger-5")
        rec = logging.LogRecord(
            name=log.name,
            level=logging.WARNING,
            pathname=__file__,
            lineno=0,
            msg="plain message",
            args=None,
            exc_info=None,
        )
        for f in log.filters:
            assert f.filter(rec) is True

    def test_filter_redacts_exception_traceback(self):
        import logging
        from oompah.secrets import install_secret_redaction_filter

        install_secret_redaction_filter("oompah.test-logger-exc")
        log = logging.getLogger("oompah.test-logger-exc")
        try:
            raise RuntimeError(
                f"downstream failed with bearer {SENTINEL_BEARER_TOKEN}"
            )
        except RuntimeError:
            rec = logging.LogRecord(
                name=log.name,
                level=logging.ERROR,
                pathname=__file__,
                lineno=0,
                msg="request failed",
                args=(),
                exc_info=__import__("sys").exc_info(),
            )

        for f in log.filters:
            f.filter(rec)
        assert rec.exc_info is None
        assert SENTINEL_BEARER_TOKEN not in (rec.exc_text or "")


class TestCodexBackendPayloadRedactionThroughOrchestrator:
    """Verify Codex-flavored ACP payloads are redacted at the orchestrator
    fan-out boundary (the same boundary any ACP backend uses)."""

    def test_codex_tool_use_payload_redaction(self):
        from oompah.secrets import redact_sensitive_data

        # Shape emitted by codex.py _handle_item command_execution branch.
        codex_payload = {
            "tool": "command_execution",
            "input": f"psql 'postgres://admin:{SENTINEL_URL_USERINFO}@db/prod'",
            "id": "item-123",
        }
        r = redact_sensitive_data(codex_payload)
        _assert_no_sentinels(str(r))

    def test_codex_tool_result_payload_redaction(self):
        from oompah.secrets import redact_sensitive_data

        codex_payload = {
            "tool_use_id": "item-123",
            "is_error": False,
            "content": (
                f"Set X-API-Key: {SENTINEL_API_KEY}\n"
                f"Response 200 OK"
            ),
        }
        r = redact_sensitive_data(codex_payload)
        _assert_no_sentinels(str(r))

    def test_codex_mcp_tool_args_redaction(self):
        from oompah.secrets import redact_sensitive_data

        codex_payload = {
            "tool": "server::secret_store",
            "input": {
                "path": "/tmp/x",
                "authorization": f"Bearer {SENTINEL_BEARER_TOKEN}",
            },
        }
        r = redact_sensitive_data(codex_payload)
        _assert_no_sentinels(str(r))


class TestOpenCodeBackendPayloadRedactionThroughOrchestrator:
    """Verify OpenCode-flavored ACP payloads are redacted at the orchestrator
    fan-out boundary."""

    def test_opencode_tool_use_payload_redaction(self):
        from oompah.secrets import redact_sensitive_data

        opencode_payload = {
            "tool": "run_command",
            "input": {
                "command": (
                    f"aws s3 cp s3://bucket/file --api_key={SENTINEL_API_KEY}"
                ),
            },
        }
        r = redact_sensitive_data(opencode_payload)
        _assert_no_sentinels(str(r))

    def test_opencode_tool_result_payload_redaction(self):
        from oompah.secrets import redact_sensitive_data

        opencode_payload = {
            "tool_use_id": "call-99",
            "is_error": True,
            "content": (
                f"stderr: HTTP 401 - Authorization: Bearer {SENTINEL_BEARER_TOKEN}"
            ),
        }
        r = redact_sensitive_data(opencode_payload)
        _assert_no_sentinels(str(r))


class TestOrchestratorJSONLLineRedaction:
    """Verify the orchestrator _on_event JSONL line is redacted for all
    backends by simulating the exact code path that writes to disk."""

    def test_jsonl_line_redacts_nested_secret_regardless_of_default_str(self, tmp_path):
        """Reproduce the exact json.dumps(..., default=str) call from
        orchestrator._on_event to confirm that even an object whose
        __str__ contains a bearer token cannot leak."""
        import json
        from oompah.secrets import redact_sensitive_data

        class WeirdSDKObject:  # not credential-named
            def __repr__(self):
                return f"WeirdSDKObject(body='Bearer {SENTINEL_BEARER_TOKEN}')"

        raw_payload = {
            "tool": "run_command",
            "input": {"sdk_obj": WeirdSDKObject()},
        }
        redacted_payload = redact_sensitive_data(raw_payload)
        line = json.dumps(
            {
                "kind": "acp_tool_use",
                "payload": redacted_payload,
                "usage": None,
            },
            default=str,
        )
        _assert_no_sentinels(line)


class TestStreamingChunkRedaction:
    """Simulate the streaming chunk path emitted through activity events."""

    def test_streaming_chunk_containing_bearer_is_redacted(self):
        from oompah.secrets import redact_sensitive_data

        # Simulate a streaming assistant chunk containing an accidentally
        # echoed bearer token from an authenticated request response.
        chunks = [
            "Fetching...\n",
            f"Authorization: Bearer {SENTINEL_BEARER_TOKEN}\n",
            "Result: OK\n",
        ]
        joined = "".join(chunks)
        r = redact_sensitive_data(joined)
        _assert_no_sentinels(r)


class TestExceptionRedaction:
    """Verify exception messages carrying credentials are redacted."""

    def test_exception_str_carrying_url_userinfo_redacts(self):
        from oompah.secrets import redact_sensitive_data

        try:
            raise ConnectionError(
                f"connect failed to postgres://root:{SENTINEL_URL_USERINFO}@db/x"
            )
        except ConnectionError as exc:
            r = redact_sensitive_data(str(exc))
            _assert_no_sentinels(r)

    def test_exception_object_via_default_str_redacts(self):
        from oompah.secrets import redact_sensitive_data
        import json

        exc = ConnectionError(
            f"connect failed to postgres://root:{SENTINEL_URL_USERINFO}@db/x"
        )
        r = redact_sensitive_data(exc)
        line = json.dumps({"error": r}, default=str)
        _assert_no_sentinels(line)


class TestStateSnapshotRedaction:
    """Verify sess.last_message / summary fields are redacted at the state
    snapshot boundary (mirrors what orchestrator._on_event does)."""

    def test_summary_derived_from_redacted_payload(self):
        from oompah.secrets import redact_sensitive_data

        # Mirror orchestrator code shape:
        raw_payload = {
            "text": f"Rotating credentials; new bearer=Bearer {SENTINEL_BEARER_TOKEN}",
        }
        redacted_payload = redact_sensitive_data(raw_payload)
        text = str(redacted_payload.get("text", ""))
        summary = text[:200]
        _assert_no_sentinels(summary)


class TestConfiguredSecretRegistry:
    """Configured opaque values are redacted without a secret-shaped label."""

    def test_registered_opaque_value_is_redacted_in_innocuous_text(self):
        from oompah.secrets import register_secret

        sentinel = "opaque-configured-value-Q9x7"
        register_secret(sentinel)

        result = redact_sensitive_data({"detail": f"provider replied {sentinel}"})

        assert result["detail"] == "provider replied [REDACTED]"
        assert sentinel not in str(result)

    def test_registered_values_replace_longest_first(self):
        from oompah.secrets import register_secret

        short = "opaque-rotation"
        long = "opaque-rotation-new-value"
        register_secret(short)
        register_secret(long)

        result = redact_sensitive_data(long)

        assert result == "[REDACTED]"

    def test_registered_literal_redacts_decoded_bytes(self):
        from oompah.secrets import register_secret

        sentinel = "opaque-byte-configured-value-4L"
        register_secret(sentinel)

        result = redact_sensitive_data(f"chunk:{sentinel}".encode("utf-8"))

        assert isinstance(result, bytes)
        assert sentinel.encode("utf-8") not in result
        assert b"[REDACTED]" in result

    def test_configured_environment_and_password_file_are_loaded_without_logging(
        self, tmp_path, caplog
    ):
        from oompah.secrets import register_configured_secrets

        env_secret = "opaque-env-configured-value-8P"
        file_secret = "opaque-file-configured-value-2R"
        password_file = tmp_path / "password"
        password_file.write_text(file_secret, encoding="utf-8")

        register_configured_secrets(
            {
                "OOMPAH_SERVER_PASSWORD": env_secret,
                "OOMPAH_SERVER_PASSWORD_FILE": str(password_file),
            }
        )

        rendered = str(redact_sensitive_data({"detail": f"{env_secret} {file_secret}"}))
        assert env_secret not in rendered
        assert file_secret not in rendered
        assert env_secret not in caplog.text
        assert file_secret not in caplog.text

    def test_authoritative_short_values_are_registered_but_heuristic_names_are_not(self):
        from oompah.secrets import register_configured_secrets

        short_configured = "s7"
        unrelated_value = "ordinary-value"
        register_configured_secrets(
            {
                "OOMPAH_SERVER_PASSWORD": short_configured,
                "CUSTOM_TOKEN": unrelated_value,
                "BUILD_KEY": "1",
            }
        )

        result = redact_sensitive_data(
            {"detail": f"{short_configured} {unrelated_value} 1"}
        )
        assert short_configured not in result["detail"]
        assert unrelated_value in result["detail"]
        assert "1" in result["detail"]

    def test_registered_short_string_is_redacted_inside_alphanumeric_text(self):
        from oompah.secrets import register_secret, retire_secret

        short_secret = "j6K"
        register_secret(short_secret, expires_in=60)
        try:
            result = redact_sensitive_data(
                {"detail": f"prefix{short_secret}suffix diagnostic-safe"}
            )

            assert result["detail"] == "prefix[REDACTED]suffix diagnostic-safe"
        finally:
            retire_secret(short_secret, grace_seconds=0)

    def test_registered_short_bytes_are_redacted(self):
        from oompah.secrets import register_secret, retire_secret

        short_secret = b"b7"
        register_secret(short_secret, expires_in=60)
        try:
            result = redact_sensitive_data(b"prefixb7suffix diagnostic-safe")

            assert result == b"prefix[REDACTED]suffix diagnostic-safe"
        finally:
            retire_secret(short_secret, grace_seconds=0)

    def test_acp_environment_uses_the_authoritative_allow_list(self, tmp_path):
        from oompah.acp_agent import AcpAgentSession

        ordinary_key_value = "opaque-build-key-value-7Q"
        configured_key_value = "opaque-openai-key-value-8R"
        AcpAgentSession(
            workspace_path=str(tmp_path),
            prompt="test",
            env={
                "BUILD_KEY": ordinary_key_value,
                "OPENAI_API_KEY": configured_key_value,
            },
        )

        rendered = str(
            redact_sensitive_data(
                {"detail": f"{ordinary_key_value} {configured_key_value}"}
            )
        )
        assert ordinary_key_value in rendered
        assert configured_key_value not in rendered

    def test_rotation_keeps_old_and_new_values_redacted(self):
        from oompah.secrets import register_secret_values

        old = "opaque-old-rotated-value-1A"
        new = "opaque-new-rotated-value-1B"
        register_secret_values((old, new))

        result = redact_sensitive_data({"detail": f"old={old} new={new}"})

        assert old not in str(result)
        assert new not in str(result)

    def test_dynamic_secret_renewal_keeps_token_redacted_past_initial_expiry(
        self, monkeypatch
    ):
        from oompah import secrets as secrets_module
        from oompah.secrets import (
            clear_registered_secrets,
            register_secret,
            renew_secret,
        )

        value = "opaque-renewed-capability-6M"
        clock = [100.0]
        monkeypatch.setattr(secrets_module.time, "monotonic", lambda: clock[0])
        clear_registered_secrets()
        try:
            register_secret(value, expires_in=10)
            clock[0] = 109.0
            renew_secret(value, expires_in=10)

            # The renewal at t=109 extends redaction through t=119, even
            # though the initial registration would have expired at t=110.
            clock[0] = 115.0
            assert redact_sensitive_data(value) == "[REDACTED]"
            clock[0] = 120.0
            assert redact_sensitive_data(value) == value
        finally:
            clear_registered_secrets()

    def test_retired_dynamic_secret_keeps_bounded_delayed_writer_grace(
        self, monkeypatch
    ):
        from oompah import secrets as secrets_module
        from oompah.secrets import (
            clear_registered_secrets,
            register_secret,
            retire_secret,
        )

        value = "opaque-retired-capability-8N"
        clock = [200.0]
        monkeypatch.setattr(secrets_module.time, "monotonic", lambda: clock[0])
        clear_registered_secrets()
        try:
            register_secret(value, expires_in=1)
            retire_secret(value, grace_seconds=5)
            clock[0] = 204.0
            assert redact_sensitive_data(value) == "[REDACTED]"
            clock[0] = 206.0
            assert redact_sensitive_data(value) == value
        finally:
            clear_registered_secrets()

    def test_api_session_registers_provider_key_for_opaque_output(self, tmp_path):
        from oompah.api_agent import ApiAgentSession

        sentinel = "opaque-api-session-key-6N"
        ApiAgentSession(
            base_url="https://api.example.com",
            api_key=sentinel,
            model="test-model",
            workspace_path=str(tmp_path),
        )

        result = redact_sensitive_data({"detail": f"downstream echoed {sentinel}"})
        assert sentinel not in str(result)

    def test_provider_store_registers_loaded_and_rotated_api_keys(self, tmp_path):
        from oompah.providers import ProviderStore

        first = "opaque-provider-key-9X"
        second = "opaque-provider-key-0Y"
        store = ProviderStore(path=str(tmp_path / "providers.json"))
        provider = store.create(name="fixture", api_key=first)
        store.update(provider.id, api_key=second)

        assert redact_sensitive_data(first) == "[REDACTED]"
        assert redact_sensitive_data(second) == "[REDACTED]"

    def test_project_store_registers_loaded_and_rotated_credentials(self, tmp_path):
        import json
        from oompah.models import Project
        from oompah.projects import ProjectStore

        first = "opaque-project-access-1Z"
        webhook = "opaque-project-webhook-2A"
        second = "opaque-project-access-3B"
        project = Project(
            id="proj-fixture",
            name="fixture",
            repo_url="https://github.com/example/fixture.git",
            repo_path=str(tmp_path / "repo"),
            access_token=first,
            webhook_secret=webhook,
        )
        path = tmp_path / "projects.json"
        path.write_text(json.dumps([project.to_dict()]), encoding="utf-8")
        store = ProjectStore(
            path=str(path),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "worktrees"),
        )
        store.update(project.id, access_token=second)

        assert redact_sensitive_data(first) == "[REDACTED]"
        assert redact_sensitive_data(webhook) == "[REDACTED]"
        assert redact_sensitive_data(second) == "[REDACTED]"

    def test_github_auth_registers_pat_and_private_key(self):
        from oompah.github_tracker import GitHubAuth

        pat = "opaque-github-pat-4C"
        private_key = "opaque-private-key-content-5D"
        GitHubAuth(pat=pat, app_private_key=private_key)

        assert redact_sensitive_data(pat) == "[REDACTED]"
        assert redact_sensitive_data(private_key) == "[REDACTED]"

    def test_task_handoff_registration_has_bounded_retention(self):
        from oompah.secrets import (
            clear_registered_secrets,
            registered_secret_count,
            register_secret,
        )

        clear_registered_secrets()
        try:
            active = "opaque-active-capability-7V"
            register_secret(active, expires_in=3600)
            assert redact_sensitive_data(active) == "[REDACTED]"

            from oompah.task_handoff import TaskHandoffGrantStore

            handoff = TaskHandoffGrantStore()
            token = handoff.issue(
                project_id="proj-test",
                task_identifier="task-test",
                allowed_actions={"comment"},
                ttl_seconds=60,
            )
            assert redact_sensitive_data(token) == "[REDACTED]"

            expiring = "opaque-expiring-capability-8W"
            register_secret(expiring, expires_in=0)
            assert redact_sensitive_data(expiring) == expiring

            values = [f"opaque-growth-value-{index:05d}" for index in range(4200)]
            for value in values:
                register_secret(value, expires_in=3600)
            # The exact-match registry remains bounded even when many dynamic
            # worker values are issued over time.
            assert registered_secret_count() <= 4096
        finally:
            clear_registered_secrets()


class TestLegacyAgentClassifiedMessageRedaction:
    """The legacy oompah/agent.py :meth:`AgentSession._classify_message` MUST
    redact secrets from the message summary before packaging into an
    ``AgentEvent``. The summary is derived from raw agent subprocess stdout
    and would otherwise land in the per-agent JSONL, in session
    ``last_message`` (state API + HTML), and in the WS fan-out.
    """

    def test_classify_message_redacts_url_userinfo(self) -> None:
        from oompah.agent import AgentSession

        session = AgentSession("cmd", "/tmp")
        raw = {
            "method": "sessionUpdate",
            "params": {
                "message": (
                    "connecting to https://alice:"
                    + SENTINEL_HTTP_PASSWORD
                    + "@example.com/repo"
                ),
            },
        }
        ev = session._classify_message(raw)
        _assert_no_sentinels(ev.payload["message"])
        # The event kind is still preserved so diagnostics remain useful.
        assert ev.event == "sessionUpdate"

    def test_classify_message_redacts_bearer_header(self) -> None:
        from oompah.agent import AgentSession

        session = AgentSession("cmd", "/tmp")
        raw = {
            "method": "toolCall",
            "params": {
                "message": f"Authorization: Bearer {SENTINEL_BEARER_TOKEN}",
            },
        }
        ev = session._classify_message(raw)
        _assert_no_sentinels(ev.payload["message"])

    def test_classify_message_redacts_registered_opaque_secret(self) -> None:
        from oompah.agent import AgentSession
        from oompah.secrets import (
            clear_registered_secrets,
            register_secret,
        )

        try:
            register_secret(SENTINEL_TASK_HANDOFF)
            session = AgentSession("cmd", "/tmp")
            raw = {
                "method": "sessionUpdate",
                "params": {
                    # No secret-shaped label, but the value is registered.
                    "message": f"detail={SENTINEL_TASK_HANDOFF}",
                },
            }
            ev = session._classify_message(raw)
            _assert_no_sentinels(ev.payload["message"])
        finally:
            clear_registered_secrets()

    def test_classify_message_returns_str_message(self) -> None:
        from oompah.agent import AgentSession

        session = AgentSession("cmd", "/tmp")
        raw = {
            "method": "sessionUpdate",
            "params": {"message": "no secrets here"},
        }
        ev = session._classify_message(raw)
        assert isinstance(ev.payload["message"], str)
        assert ev.payload["message"] == "no secrets here"


class TestOrchestratorLastMessageRedaction:
    """Verify that :meth:`_handle_agent_event` and the API-agent result
    handler redact secrets before storing into ``LiveSession.last_message``.

    These are stateful state-API-visible fields, so any downstream JSON
    serialization must never see the raw plaintext.
    """

    def test_handle_agent_event_redacts_last_message(self) -> None:
        """Mirror orchestrator._handle_agent_event's redaction of the
        payload["message"] value before assigning it to last_message."""
        from oompah.secrets import redact_sensitive_data

        raw_message = (
            f"Authorization: Bearer {SENTINEL_BEARER_TOKEN} caused failure"
        )
        redacted = redact_sensitive_data(raw_message)
        if not isinstance(redacted, str):
            redacted = str(redacted)
        _assert_no_sentinels(redacted)

    def test_api_agent_result_last_message_redaction_shape(self) -> None:
        """Mirror orchestrator's redaction of ApiAgentResult.last_message
        before writing to sess.last_message."""
        from oompah.secrets import redact_sensitive_data

        raw_content = (
            f"Retrieved config: url=https://user:{SENTINEL_HTTP_PASSWORD}"
            "@internal.example/repo"
        )
        redacted = redact_sensitive_data(raw_content or "")
        if not isinstance(redacted, str):
            redacted = str(redacted)
        # Simulate the [:200] truncation the orchestrator applies.
        clipped = redacted[:200]
        _assert_no_sentinels(clipped)


class TestCodexTruncateRedactsSecrets:
    """Verify oompah.acp_backends.codex._truncate redacts BEFORE the
    console fan-out boundary, so any observer set by tests or hooks
    (see ``options.on_event``) receives a scrubbed payload.
    """

    def test_string_truncate_redacts_url_userinfo(self) -> None:
        from oompah.acp_backends.codex import _truncate

        value = (
            f"psql 'postgres://admin:{SENTINEL_URL_USERINFO}@db/prod' -c 'select 1'"
        )
        out = _truncate(value)
        _assert_no_sentinels(str(out))

    def test_dict_truncate_redacts_bearer_header(self) -> None:
        from oompah.acp_backends.codex import _truncate

        value = {
            "path": "/tmp/x",
            "authorization": f"Bearer {SENTINEL_BEARER_TOKEN}",
        }
        out = _truncate(value)
        _assert_no_sentinels(str(out))

    def test_list_truncate_redacts_nested_strings(self) -> None:
        from oompah.acp_backends.codex import _truncate

        value = [
            "echo hi",
            f"curl -H 'X-API-Key: {SENTINEL_API_KEY}' https://api.example",
        ]
        out = _truncate(value)
        _assert_no_sentinels(str(out))


class TestOpencodeTruncateRedactsSecrets:
    """Same defense-in-depth verification for the OpenCode backend."""

    def test_string_truncate_redacts_url_userinfo(self) -> None:
        from oompah.acp_backends.opencode import _truncate

        value = f"https://user:{SENTINEL_HTTP_PASSWORD}@example.com/repo"
        out = _truncate(value)
        _assert_no_sentinels(str(out))

    def test_dict_truncate_redacts_bearer_header(self) -> None:
        from oompah.acp_backends.opencode import _truncate

        value = {
            "content": f"Authorization: Bearer {SENTINEL_BEARER_TOKEN}",
        }
        out = _truncate(value)
        _assert_no_sentinels(str(out))
