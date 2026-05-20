"""vector_backend_policy 单测。"""

from domains.agent.domain.vector_backend_policy import effective_vector_db_type


def test_pytest_forces_chroma() -> None:
    assert effective_vector_db_type("qdrant", pytest_chroma_ephemeral=True) == "chroma"


def test_uses_configured_when_not_pytest() -> None:
    assert effective_vector_db_type("qdrant", pytest_chroma_ephemeral=False) == "qdrant"
    assert effective_vector_db_type("chroma", pytest_chroma_ephemeral=False) == "chroma"
