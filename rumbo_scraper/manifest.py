"""Reproducible manifest of the local scrape artifacts.

The counts of a run only mean something next to the counts of the previous one.
This module records, for every artifact in ``data/``, its hash and the size of
every list it contains, so a silent collapse -- a section that used to hold 829
rows and now holds 20 -- becomes visible before anybody loads it into Supabase.

It never reads the artifact values, only their shape: the manifest carries no
scraped content and no credentials.
"""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path("data")
MANIFEST_DIR = Path("manifests")


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def count_collections(payload: object, prefix: str = "") -> dict[str, int]:
    """Return the length of every list in the document, keyed by dotted path."""
    counts: dict[str, int] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, list):
                counts[path] = len(value)
            else:
                counts.update(count_collections(value, path))
    return counts


def describe_artifact(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    entry: dict[str, object] = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "modified_at": datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
    }
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        entry["error"] = f"JSON inválido: {error}"
        return entry
    entry["conteos"] = count_collections(payload)
    for field in ("extraido_en", "extraido_at", "generado_at", "periodo"):
        value = payload.get(field) if isinstance(payload, dict) else None
        if value is not None:
            entry[field] = value
    return entry


def build_manifest(data_dir: Path = DATA_DIR) -> dict[str, object]:
    artifacts = {
        path.name: describe_artifact(path) for path in sorted(data_dir.glob("*.json"))
    }
    return {
        "generado_at": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(),
        "artefactos": artifacts,
    }


def latest_manifest(manifest_dir: Path = MANIFEST_DIR) -> tuple[Path, dict[str, object]] | None:
    candidates = sorted(manifest_dir.glob("*.json"))
    if not candidates:
        return None
    path = candidates[-1]
    return path, json.loads(path.read_text())


def compare(previous: dict[str, object], current: dict[str, object]) -> list[dict[str, object]]:
    """Report every count that changed between two manifests."""
    changes: list[dict[str, object]] = []
    before = previous.get("artefactos", {})
    after = current.get("artefactos", {})
    for name in sorted(set(before) | set(after)):
        old_counts = before.get(name, {}).get("conteos", {})
        new_counts = after.get(name, {}).get("conteos", {})
        if name not in after:
            changes.append({"artefacto": name, "seccion": "*", "antes": None, "ahora": None,
                            "detalle": "artefacto ausente"})
            continue
        if name not in before:
            changes.append({"artefacto": name, "seccion": "*", "antes": None, "ahora": None,
                            "detalle": "artefacto nuevo"})
            continue
        for section in sorted(set(old_counts) | set(new_counts)):
            old = old_counts.get(section)
            new = new_counts.get(section)
            if old == new:
                continue
            drop = None
            if isinstance(old, int) and isinstance(new, int) and old > 0:
                drop = max(0.0, (old - new) / old)
            changes.append({"artefacto": name, "seccion": section, "antes": old,
                            "ahora": new, "caida": drop})
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Manifiesto reproducible de los artefactos locales")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--manifest-dir", type=Path, default=MANIFEST_DIR)
    parser.add_argument("--write", action="store_true", help="guardar el manifiesto como baseline")
    parser.add_argument("--max-drop", type=float, default=None,
                        help="caída relativa máxima tolerada por sección, por ejemplo 0.2")
    args = parser.parse_args()

    if not args.data_dir.is_dir():
        print(f"No existe {args.data_dir}; ejecutá primero los spiders.")
        return 1

    current = build_manifest(args.data_dir)
    if not current["artefactos"]:
        print(f"No hay artefactos JSON en {args.data_dir}.")
        return 1

    for name, entry in current["artefactos"].items():
        print(f"\n{name}  {entry['bytes']:,} bytes  sha256:{entry['sha256'][:12]}")
        if "error" in entry:
            print(f"  {entry['error']}")
            continue
        for section, count in sorted(entry["conteos"].items()):
            print(f"  {count:>7,}  {section}")

    exit_code = 0
    baseline = latest_manifest(args.manifest_dir)
    if baseline is None:
        print("\nNo hay baseline previo; este manifiesto puede ser el primero (--write).")
    else:
        baseline_path, previous = baseline
        changes = compare(previous, current)
        print(f"\nComparación contra {baseline_path}: {len(changes)} diferencias")
        for change in changes:
            caida = change.get("caida")
            marca = ""
            if args.max_drop is not None and caida is not None and caida > args.max_drop:
                marca = "  <-- supera el umbral"
                exit_code = 2
            detalle = change.get("detalle")
            if detalle:
                print(f"  {change['artefacto']}: {detalle}")
            else:
                print(f"  {change['artefacto']}.{change['seccion']}: "
                      f"{change['antes']} -> {change['ahora']}{marca}")

    if args.write:
        args.manifest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = args.manifest_dir / f"{stamp}.json"
        target.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n")
        print(f"\nManifiesto guardado en {target}")
    else:
        print("\nVista previa; usá --write para guardarlo como baseline.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
