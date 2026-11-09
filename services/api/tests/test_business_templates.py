import math

import pytest
from cryptography.fernet import Fernet

from app.business.templates import DIM, TemplatesUnavailable, TemplateVault, normalise, vault_for
from app.core.config import Settings


def vector(seed: float = 1.0) -> list[float]:
    return [math.sin(seed * (i + 1)) for i in range(DIM)]


def test_sealed_template_round_trips_as_a_unit_vector() -> None:
    vault = TemplateVault(Fernet.generate_key().decode())
    sealed = vault.seal(vector())
    opened = vault.open(sealed)
    assert len(opened) == DIM
    assert math.isclose(sum(v * v for v in opened), 1.0, rel_tol=1e-5)
    assert sealed != vault.seal(vector())


def test_a_different_key_cannot_open_a_template() -> None:
    sealed = TemplateVault(Fernet.generate_key().decode()).seal(vector())
    with pytest.raises(TemplatesUnavailable):
        TemplateVault(Fernet.generate_key().decode()).open(sealed)


def test_templates_must_be_128_finite_numbers() -> None:
    with pytest.raises(ValueError):
        normalise([1.0] * 10)
    with pytest.raises(ValueError):
        normalise([float("nan")] * DIM)
    with pytest.raises(ValueError):
        normalise([0.0] * DIM)


def test_cloud_deployments_and_missing_keys_refuse_templates() -> None:
    key = Fernet.generate_key().decode()
    with pytest.raises(TemplatesUnavailable, match="local server"):
        vault_for(Settings(deployment="cloud", template_key=key))
    with pytest.raises(TemplatesUnavailable, match="DINEMATE_TEMPLATE_KEY"):
        vault_for(Settings(deployment="local", template_key=None))
    with pytest.raises(TemplatesUnavailable, match="not a valid"):
        vault_for(Settings(deployment="local", template_key="short"))
    assert isinstance(vault_for(Settings(deployment="local", template_key=key)), TemplateVault)
