"""memory_index_policy 纯函数单测。"""

from domains.agent.domain.memory_index_policy import (
    langgraph_namespace,
    langgraph_namespace_candidates,
    memory_collection_name,
    vector_filter_for_session,
    vector_payload_for_memory,
)


def test_memory_collection_session() -> None:
    assert memory_collection_name(purpose="session") == "memories"


def test_langgraph_namespace() -> None:
    assert langgraph_namespace("s1", "simplemem_atom") == (
        "session_s1",
        "memories",
        "simplemem_atom",
    )


def test_namespace_candidates_order() -> None:
    cands = langgraph_namespace_candidates(
        "s1",
        memory_type="fact",
        result_memory_type="simplemem_atom",
    )
    assert cands[0] == ("session_s1", "memories", "fact")
    assert ("session_s1", "memories", "simplemem_atom") in cands
    assert ("session_s1", "memories") in cands


def test_vector_filter_and_payload() -> None:
    assert vector_filter_for_session("abc") == {"session_id": "abc"}
    payload = vector_payload_for_memory(
        session_id="abc",
        memory_type="fact",
        content="hello",
        importance=7.0,
        metadata={"k": "v"},
    )
    assert payload["text"] == "hello"
    assert payload["session_id"] == "abc"
    assert payload["memory_type"] == "fact"
    assert payload["importance"] == 7.0
    assert payload["k"] == "v"
