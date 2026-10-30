import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from rumbo_scraper.database.load_ucema import load_careers


class _Query:
    def __init__(self, db: dict, table: str) -> None:
        self.db, self.table, self.filters, self.op = db, table, [], ("select", None)

    def select(self, _columns: str) -> "_Query":
        return self

    def eq(self, column: str, value: object) -> "_Query":
        self.filters.append((column, value))
        return self

    def upsert(self, row: dict, on_conflict: str) -> "_Query":
        self.op = ("upsert", row)
        return self

    def update(self, fields: dict) -> "_Query":
        self.op = ("update", fields)
        return self

    def execute(self) -> SimpleNamespace:
        rows = self.db.setdefault(self.table, [])
        kind, payload = self.op
        if kind == "upsert":
            rows.append({"id": f"nuevo-{len(rows)}", **payload})
            return SimpleNamespace(data=[rows[-1]])
        chosen = [r for r in rows if all(r.get(c) == v for c, v in self.filters)]
        if kind == "update":
            for row in chosen:
                row.update(payload)
        return SimpleNamespace(data=chosen)


class _Client:
    def __init__(self, db: dict) -> None:
        self.db = db

    def table(self, name: str) -> _Query:
        return _Query(self.db, name)


def _career(name: str, title: str | None, years: float | None) -> dict:
    return {"id": name, "universidad_id": "u", "nombre_carrera": name, "titulo_otorgado": title,
            "duracion_anios": years, "descripcion_breve": None}


class LoadCareersTests(unittest.TestCase):
    def setUp(self) -> None:
        reading = json.loads(Path("data/ucema_completo.json").read_text(encoding="utf-8"))
        data = reading["datos"]
        keep = ("Marketing", "Ingeniería en Inteligencia Artificial")
        data["carreras"] = [r for r in data["carreras"] if r["nombre_carrera"] in keep]
        data["ofertas"] = [r for r in data["ofertas"] if r["carrera_nombre"] in keep]
        for row in data["carreras"]:
            if row["nombre_carrera"].startswith("Ingeniería"):
                row.update(titulo_otorgado="Ingeniero/a en Inteligencia Artificial", duracion_anios=5.0)
        data["carreras"].append({**data["carreras"][0], "nombre_carrera": "BA - Artes Liberales y Ciencias",
                                 "denominacion_canonica": "BA - Artes Liberales y Ciencias"})
        data["ofertas"].append({**data["ofertas"][0], "carrera_nombre": "BA - Artes Liberales y Ciencias"})
        reading["control_calidad"]["programas_descubiertos"] = (
            len(data["carreras"]) + len(data["posgrados"])
            + len(reading["control_calidad"]["programas_excluidos"]))
        self.reading = reading
        self.db = {"universidades": [{"id": "u", "nombre_oficial": data["universidades"][0]["nombre_oficial"]}],
                   "carreras": [_career("Marketing", "Licenciado/a en Marketing", 4.0),
                                _career("Ingeniería en Inteligencia Artificial", None, None)]}

    def test_adds_the_new_career_and_fills_only_what_is_empty(self) -> None:
        actions = load_careers(self.reading, apply=True, client=_Client(self.db))
        self.assertEqual([(kind, name) for kind, name, _ in actions],
                         [("completada", "Ingeniería en Inteligencia Artificial"),
                          ("nueva", "BA - Artes Liberales y Ciencias")])
        careers = {r["nombre_carrera"]: r for r in self.db["carreras"]}
        self.assertEqual(careers["Ingeniería en Inteligencia Artificial"]["duracion_anios"], 5.0)
        self.assertEqual(careers["Marketing"]["titulo_otorgado"], "Licenciado/a en Marketing")
        self.assertEqual(len(careers), 3)
        self.assertNotIn("materias", self.db)

    def test_preview_writes_nothing(self) -> None:
        load_careers(self.reading, apply=False, client=_Client(self.db))
        self.assertEqual(len(self.db["carreras"]), 2)
        self.assertIsNone(self.db["carreras"][1]["duracion_anios"])


if __name__ == "__main__":
    unittest.main()
