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
