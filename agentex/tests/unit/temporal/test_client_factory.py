import datetime
from unittest.mock import MagicMock, patch

import pytest
from src.adapters.temporal.client_factory import (
    DateTimeJSONEncoder,
    DateTimeJSONTypeConverter,
    DateTimePayloadConverter,
    TemporalClientFactory,
    custom_data_converter,
)
from src.adapters.temporal.exceptions import TemporalConnectionError
from temporalio.converter import JSONTypeConverter

# ── DateTimeJSONEncoder ──────────────────────────────────────────────


@pytest.mark.unit
def test_datetime_encoder_isoformat():
    encoder = DateTimeJSONEncoder()
    dt = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.UTC)
    assert encoder.default(dt) == "2024-01-15T10:30:00+00:00"


@pytest.mark.unit
def test_datetime_encoder_delegates_non_datetime():
    encoder = DateTimeJSONEncoder()
    with pytest.raises(TypeError):
        encoder.default(object())


# ── DateTimeJSONTypeConverter ────────────────────────────────────────


@pytest.mark.unit
def test_type_converter_returns_datetime_for_hint():
    converter = DateTimeJSONTypeConverter()
    result = converter.to_typed_value(datetime.datetime, "2024-01-15T10:30:00+00:00")
    assert isinstance(result, datetime.datetime)
    assert result.year == 2024


@pytest.mark.unit
def test_type_converter_returns_unhandled_for_other_hints():
    converter = DateTimeJSONTypeConverter()
    result = converter.to_typed_value(str, "hello")
    assert result is JSONTypeConverter.Unhandled


# ── DateTimePayloadConverter ─────────────────────────────────────────


@pytest.mark.unit
def test_payload_converter_instantiates():
    converter = DateTimePayloadConverter()
    assert converter is not None
    assert len(converter.converters) > 0


# ── custom_data_converter ────────────────────────────────────────────


@pytest.mark.unit
def test_custom_data_converter_has_datetime_payload_class():
    assert custom_data_converter.payload_converter_class is DateTimePayloadConverter


# ── TemporalClientFactory.create_client ──────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_client_raises_for_empty_address():
    with pytest.raises(TemporalConnectionError):
        await TemporalClientFactory.create_client(temporal_address="")


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("bad_addr", ["false", "False", "null", "None", "undefined"])
async def test_create_client_raises_for_invalid_address_strings(bad_addr):
    with pytest.raises(TemporalConnectionError):
        await TemporalClientFactory.create_client(temporal_address=bad_addr)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_client_success(monkeypatch):
    fake_client = MagicMock()

    async def fake_connect(**kwargs):
        return fake_client

    monkeypatch.setattr(
        "src.adapters.temporal.client_factory.Client.connect", fake_connect
    )

    client = await TemporalClientFactory.create_client(
        temporal_address="localhost:7233",
        temporal_namespace="default",
    )
    assert client is fake_client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_client_with_metrics_url(monkeypatch):
    fake_client = MagicMock()
    captured_kwargs = {}

    async def fake_connect(**kwargs):
        captured_kwargs.update(kwargs)
        return fake_client

    monkeypatch.setattr(
        "src.adapters.temporal.client_factory.Client.connect", fake_connect
    )

    client = await TemporalClientFactory.create_client(
        temporal_address="localhost:7233",
        metrics_url="http://otel:4318",
    )
    assert client is fake_client
    assert "runtime" in captured_kwargs


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_client_uses_custom_data_converter_by_default(monkeypatch):
    captured_kwargs = {}

    async def fake_connect(**kwargs):
        captured_kwargs.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(
        "src.adapters.temporal.client_factory.Client.connect", fake_connect
    )

    await TemporalClientFactory.create_client(temporal_address="localhost:7233")
    assert captured_kwargs["data_converter"] is custom_data_converter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_client_wraps_generic_exception():
    with patch(
        "src.adapters.temporal.client_factory.Client.connect",
        side_effect=RuntimeError("connection refused"),
    ):
        with pytest.raises(TemporalConnectionError, match="Failed to connect"):
            await TemporalClientFactory.create_client(temporal_address="bad-host:7233")


# ── TemporalClientFactory.create_client_from_env ────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_client_from_env_delegates(monkeypatch):
    fake_env = MagicMock()
    fake_env.TEMPORAL_ADDRESS = "localhost:7233"
    fake_env.TEMPORAL_NAMESPACE = "ns"

    fake_client = MagicMock()

    async def fake_create_client(**kwargs):
        return fake_client

    monkeypatch.setattr(
        TemporalClientFactory, "create_client", staticmethod(fake_create_client)
    )

    client = await TemporalClientFactory.create_client_from_env(
        environment_variables=fake_env, metrics_url="http://otel:4318"
    )
    assert client is fake_client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_client_from_env_refreshes_when_none(monkeypatch):
    fake_env = MagicMock()
    fake_env.TEMPORAL_ADDRESS = "localhost:7233"
    fake_env.TEMPORAL_NAMESPACE = None

    monkeypatch.setattr(
        "src.adapters.temporal.client_factory.EnvironmentVariables.refresh",
        staticmethod(lambda: fake_env),
    )

    fake_client = MagicMock()

    async def fake_create_client(**kwargs):
        return fake_client

    monkeypatch.setattr(
        TemporalClientFactory, "create_client", staticmethod(fake_create_client)
    )

    client = await TemporalClientFactory.create_client_from_env()
    assert client is fake_client


# ── TemporalClientFactory.is_temporal_configured ─────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    "address,expected",
    [
        ("localhost:7233", True),
        ("false", False),
        ("False", False),
        ("null", False),
        ("None", False),
        ("", False),
        ("undefined", False),
        (False, False),
        (None, False),
    ],
)
def test_is_temporal_configured(address, expected):
    env = MagicMock()
    env.TEMPORAL_ADDRESS = address
    assert TemporalClientFactory.is_temporal_configured(env) is expected


@pytest.mark.unit
def test_is_temporal_configured_refreshes_when_none(monkeypatch):
    fake_env = MagicMock()
    fake_env.TEMPORAL_ADDRESS = "localhost:7233"
    monkeypatch.setattr(
        "src.adapters.temporal.client_factory.EnvironmentVariables.refresh",
        staticmethod(lambda: fake_env),
    )
    assert TemporalClientFactory.is_temporal_configured() is True
