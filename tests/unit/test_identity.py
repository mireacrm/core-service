from mireacrm_common import identity


class TestParse:
    def test_reads_headers_from_gateway(self) -> None:
        caller = identity.parse({
            identity.HEADER_SUBJECT: "8f1c0e4e-0000-4000-8000-000000000001",
            identity.HEADER_USERNAME: "%D0%9E%D0%BB%D1%8C%D0%B3%D0%B0",
            identity.HEADER_ROLES: "admin,manager",
        })
        assert caller.known
        assert caller.username == "Ольга"
        assert caller.has_any("manager")
        assert not caller.has_any("specialist")

    def test_roles_without_subject_ignored(self) -> None:
        """Роли без идентификатора — попытка подделки, а не частичные данные."""
        caller = identity.parse({identity.HEADER_ROLES: "admin"})
        assert not caller.known
        assert caller.roles == frozenset()

    def test_empty_headers_give_anonymous(self) -> None:
        assert identity.parse({}) is identity.ANONYMOUS


class TestOutgoing:
    def test_round_trip_through_metadata(self) -> None:
        original = identity.Caller(
            subject="8f1c0e4e-0000-4000-8000-000000000001",
            username="Ольга",
            roles=frozenset({"admin"}),
        )
        identity.set_current(original)
        try:
            assert identity.parse(dict(identity.metadata())) == original
        finally:
            identity.set_current(identity.ANONYMOUS)

    def test_anonymous_adds_nothing(self) -> None:
        identity.set_current(identity.ANONYMOUS)
        assert identity.metadata() == []
