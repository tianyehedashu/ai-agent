from domains.tenancy.domain.policies.team_list_filter import team_metadata_matches_search


def test_team_metadata_matches_search_empty_query() -> None:
    assert team_metadata_matches_search(name="Acme", slug="acme-corp", search=None)
    assert team_metadata_matches_search(name="Acme", slug="acme-corp", search="  ")


def test_team_metadata_matches_search_by_name_or_slug() -> None:
    assert team_metadata_matches_search(name="Outsider Org", slug="outsider-abc", search="outs")
    assert team_metadata_matches_search(name="Outsider Org", slug="outsider-abc", search="ABC")
    assert not team_metadata_matches_search(name="Outsider Org", slug="outsider-abc", search="zzz")
