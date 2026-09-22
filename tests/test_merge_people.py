"""Tests for merging people stored twice under different spellings."""

import unittest

from rumbo_scraper.database.merge_people import _richness, find_duplicates, merge

OFFICIAL = "https://www.utdt.edu/ver_contenido.php?id_contenido=1"
CATALOGUE = "https://datastudio.google.com/reporting/30c8c711"


def _person(name: str, source: str, profile: str | None = None, bio: str | None = None,
            row_id: str | None = None) -> dict:
    return {"id": row_id or name, "nombre_completo": name, "fuente_url": source,
            "perfil_url": profile, "biografia": bio}


class _FakeQuery:
    def __init__(self, client: "_FakeClient", table: str) -> None:
        self.client, self.table_name = client, table
        self.filters: dict[str, object] = {}

    def select(self, _columns: str) -> "_FakeQuery":
        return self

    def eq(self, column: str, value: object) -> "_FakeQuery":
        self.filters[column] = value
        return self

    def order(self, column: str) -> "_FakeQuery":
        self.ordered_by = column
        return self

    def range(self, start: int, end: int) -> "_FakeQuery":
        self.start, self.end = start, end
        return self

    def update(self, values: dict) -> "_FakeQuery":
        self.pending = ("update", values)
        return self

    def delete(self) -> "_FakeQuery":
        self.pending = ("delete", None)
        return self

    def execute(self) -> object:
        rows = [row for row in self.client.tables.get(self.table_name, [])
                if all(row.get(key) == value for key, value in self.filters.items())]
        action = getattr(self, "pending", None)
        if action and action[0] == "update":
            for row in rows:
                row.update(action[1])
                self.client.updates.append((self.table_name, row["id"], action[1]))
            return type("R", (), {"data": rows})()
        if action and action[0] == "delete":
            self.client.tables[self.table_name] = [
                row for row in self.client.tables[self.table_name] if row not in rows
            ]
            self.client.deletes.extend(row["id"] for row in rows)
            return type("R", (), {"data": rows})()
        start, end = getattr(self, "start", 0), getattr(self, "end", len(rows) - 1)
        return type("R", (), {"data": rows[start:end + 1]})()


class _FakeClient:
    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self.tables = tables
        self.updates: list[tuple] = []
        self.deletes: list[str] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self, name)


class RichnessTests(unittest.TestCase):
    def test_the_university_page_outranks_the_catalogue(self) -> None:
        official = _person("Juan Carlos Rodriguez", OFFICIAL)
        catalogue = _person("Juan Carlos Rodríguez", CATALOGUE)
        self.assertGreater(_richness(official, "utdt.edu"), _richness(catalogue, "utdt.edu"))

    def test_accents_alone_never_decide(self) -> None:
        # The accented spelling here is the catalogue's, and it must still lose.
        rows = sorted([_person("Juan Carlos Rodríguez", CATALOGUE),
                       _person("Juan Carlos Rodriguez", OFFICIAL)],
                      key=lambda row: _richness(row, "utdt.edu"), reverse=True)
        self.assertEqual(rows[0]["nombre_completo"], "Juan Carlos Rodriguez")

    def test_a_profile_breaks_a_tie_between_two_official_rows(self) -> None:
        with_profile = _person("Ana Pérez", OFFICIAL, profile="https://www.utdt.edu/p")
        without = _person("Ana Perez", OFFICIAL)
        self.assertGreater(_richness(with_profile, "utdt.edu"), _richness(without, "utdt.edu"))


class FindDuplicatesTests(unittest.TestCase):
    def test_groups_only_the_names_that_differ_in_spelling(self) -> None:
        client = _FakeClient({"personas": [
            dict(_person("Agustín Gravano", OFFICIAL), universidad_id="u"),
            dict(_person("Agustin Gravano", CATALOGUE), universidad_id="u"),
            dict(_person("Otra Persona", OFFICIAL), universidad_id="u"),
        ]})
        groups = find_duplicates(client, "u", "utdt.edu")
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0]["nombre_completo"], "Agustín Gravano")

    def test_no_duplicates_yields_no_groups(self) -> None:
        client = _FakeClient({"personas": [dict(_person("Ana", OFFICIAL), universidad_id="u")]})
        self.assertEqual(find_duplicates(client, "u", "utdt.edu"), [])


class MergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _FakeClient({
            "personas": [
                dict(_person("Agustín Gravano", OFFICIAL, row_id="keep"), universidad_id="u"),
                dict(_person("Agustin Gravano", CATALOGUE, row_id="drop"), universidad_id="u"),
            ],
            "roles_academicos": [{"id": "r1", "persona_id": "drop"},
                                 {"id": "r2", "persona_id": "keep"}],
            "docentes_comision": [{"id": "d1", "persona_id": "drop"}],
        })

    def test_repoints_every_reference_and_removes_the_redundant_row(self) -> None:
        groups = find_duplicates(self.client, "u", "utdt.edu")
        counts = merge(self.client, groups)
        self.assertEqual(counts, {"referencias_movidas": 2, "personas_eliminadas": 1})
        self.assertEqual(self.client.deletes, ["drop"])
        self.assertEqual({row["persona_id"] for row in self.client.tables["roles_academicos"]},
                         {"keep"})
        self.assertEqual(self.client.tables["docentes_comision"][0]["persona_id"], "keep")

    def test_the_surviving_person_is_untouched(self) -> None:
        merge(self.client, find_duplicates(self.client, "u", "utdt.edu"))
        remaining = self.client.tables["personas"]
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["nombre_completo"], "Agustín Gravano")

    def test_merging_nothing_changes_nothing(self) -> None:
        self.assertEqual(merge(self.client, []),
                         {"referencias_movidas": 0, "personas_eliminadas": 0})
        self.assertEqual(self.client.deletes, [])
