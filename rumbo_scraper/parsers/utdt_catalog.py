"""Parsers for the public UTDT Looker Studio course catalogue."""

from __future__ import annotations

import re
from typing import Any

from rumbo_scraper.normalizers.text import clean_text


COURSE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[^()]*)\)\s*$")
DETAIL_CODE_RE = re.compile(r"^(?P<code>.+?)\s*-\s*S(?P<section>[^\s]+)$", re.I)
TIME_RE = re.compile(r"^(?P<start>\d{1,2}:\d{2})\s*-\s*(?P<end>\d{1,2}:\d{2})$")


def parse_course_label(value: str) -> tuple[str, str]:
    """Split the final parenthesized code without breaking names containing parentheses."""
    text = clean_text(value)
    match = COURSE_RE.match(text)
    if not match:
        return text, text
    return clean_text(match.group("name")), clean_text(match.group("code"))


def parse_detail_label(value: str) -> tuple[str, str, str]:
    """Return course name, code and section from labels such as ``Name (1302 - S1)``."""
    name, compound = parse_course_label(value)
    match = DETAIL_CODE_RE.match(compound)
    if not match:
        return name, compound, ""
    return name, clean_text(match.group("code")), clean_text(match.group("section"))


def split_teachers(value: str) -> list[str]:
    """Split UTDT's ``Surname, Given, Surname, Given`` display format."""
    text = clean_text(value)
    if not text or text.casefold() in {"a designar", "docente a confirmar", "equipo docente"}:
        return []
    text = re.sub(r"^a designar\s*,\s*", "", text, flags=re.I)
    parts = [clean_text(part) for part in text.split(",") if clean_text(part)]
    if len(parts) >= 2 and len(parts) % 2 == 0:
        return [f"{parts[index]}, {parts[index + 1]}" for index in range(0, len(parts), 2)]
    return [text] if text else []


def parse_schedule_row(values: list[str]) -> dict[str, Any]:
    if len(values) != 6:
        raise ValueError(f"Fila de horario inválida: se esperaban 6 columnas y llegaron {len(values)}")
    name, code = parse_course_label(values[0])
    time_match = TIME_RE.match(clean_text(values[5]))
    return {
        "codigo_materia": code,
        "nombre_materia": name,
        "seccion": clean_text(values[1]),
        "tipo_clase": clean_text(values[2]) or None,
        "docentes": split_teachers(values[3]),
        "dia": clean_text(values[4]) or None,
        "hora_inicio": time_match.group("start") if time_match else None,
        "hora_fin": time_match.group("end") if time_match else None,
    }


def parse_detail_row(values: list[str], link: str | None = None) -> dict[str, Any]:
    if len(values) != 4:
        raise ValueError(f"Fila de detalle inválida: se esperaban 4 columnas y llegaron {len(values)}")
    name, code, section = parse_detail_label(values[0])
    return {
        "codigo_materia": code,
        "nombre_materia": name,
        "seccion": section,
        "contenido": clean_text(values[1]) or None,
        "condiciones_aprobacion": clean_text(values[2]) or None,
        "programa_url": link or clean_text(values[3]) or None,
    }
