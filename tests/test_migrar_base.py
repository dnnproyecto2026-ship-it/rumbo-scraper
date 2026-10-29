import unittest

from rumbo_scraper.database.migrar_base import esquema_sql

OPENAPI = {"definitions": {
    "carreras": {"required": ["id", "universidad_id", "nombre_carrera"], "properties": {
        "id": {"format": "uuid", "type": "string", "default": "gen_random_uuid()",
               "description": "Note:\nThis is a Primary Key.<pk/>"},
        "universidad_id": {"format": "uuid", "type": "string",
                           "description": "Note:\nThis is a Foreign Key to `universidades.id`.<fk table='universidades' column='id'/>"},
        "nombre_carrera": {"format": "text", "type": "string"},
        "duracion": {"format": "integer", "type": "integer"},
        "tags": {"type": "array", "items": {"format": "text", "type": "string"}},
        "extra": {"format": "jsonb", "type": "object"}}},
    "universidades": {"required": ["id", "nombre_oficial"], "properties": {
        "id": {"format": "uuid", "type": "string", "default": "gen_random_uuid()",
               "description": "Note:\nThis is a Primary Key.<pk/>"},
        "nombre_oficial": {"format": "text", "type": "string"},
        "creada": {"format": "timestamp with time zone", "type": "string", "default": "now()"}}}}}


class EsquemaSql(unittest.TestCase):
    def test_crea_las_tablas_en_el_orden_de_sus_claves_y_las_unicas_de_los_loaders(self):
        sql, estructura = esquema_sql(OPENAPI)
        self.assertEqual(estructura["orden"], ["universidades", "carreras"])
        self.assertLess(sql.index('create table if not exists "universidades"'), sql.index('create table if not exists "carreras"'))
        self.assertIn('"id" uuid default gen_random_uuid()', sql)
        self.assertIn('"nombre_carrera" text not null', sql)
        self.assertIn('"tags" text[]', sql)
        self.assertIn('"extra" jsonb', sql)
        self.assertIn('"creada" timestamptz default now()', sql)
        self.assertIn('primary key ("id")', sql)
        self.assertIn('alter table "carreras" add foreign key ("universidad_id") references "universidades" ("id");', sql)
        self.assertIn('on "carreras" ("universidad_id", "nombre_carrera")', sql)
        self.assertIn('on "universidades" ("nombre_oficial")', sql)
