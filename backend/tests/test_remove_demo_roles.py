from data_pipeline.remove_demo_roles import TITLES, owner_is_disposable


def test_only_demo_or_throwaway_owners_can_lose_a_posting():
    assert owner_is_disposable("seed-recruiter@jobbridge.example.org", True)
    assert owner_is_disposable("week2-recruiter-ec24d635@example.com", False)
    assert owner_is_disposable("verify-recruiter@EXAMPLE.COM", False)
    assert not owner_is_disposable("njoroge.wachira@strathmore.edu", False)
    assert not owner_is_disposable("someone@example.com.ke", False)


def test_titles_are_exact_and_never_catch_real_it_roles():
    assert "Accountant" in TITLES
    for keep in ("Penetration Tester", "IT Auditor", "QA Automation Engineer", "DevOps Engineer", "Business Analyst"):
        assert keep not in TITLES
