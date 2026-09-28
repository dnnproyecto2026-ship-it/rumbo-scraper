"""The Province of Buenos Aires' non-university higher institutes and what
they teach, from the province's own school map (mapaescolar.abc.gob.ar).

Its public service answers JSON:

- ``distritos_desft``: the districts with higher institutes;
- ``distritostitulos_desft/<distrito>``: the degrees taught in a district;
- ``disxtit2_desft/<titulo>/<distrito>``: the institutes giving a degree there;
- ``escuela/<idserv>``: an institute (CUE, name, address, sector);
- ``ofertascarreras/<idserv>``: every degree an institute gives, with its
  resolution, the years taught and whether it opens this year.

    python -m rumbo_scraper.parsers.terciarios_pba    (writes data/terciarios_pba.json)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

API = "https://mapaescolar.abc.gob.ar/escuela/"
SALIDA = Path("data/terciarios_pba.json")
PAUSA = 1.0


def main() -> None:
    from rumbo_scraper.spiders.visitante import Visitante

    def pedir(ruta: str):
        for _ in range(3):
            try:
                respuesta = visitante.client.get(API + ruta, headers={"Accept": "application/json"})
                if respuesta.status_code == 200:
                    time.sleep(PAUSA)
                    return respuesta.json()
            except Exception:
                pass
            time.sleep(5)
        return None

    # What was read is kept as it is read: a crawl cut short resumes where
    # it stopped.
    avance = SALIDA.with_suffix(".avance.json")
    estado = json.loads(avance.read_text()) if avance.exists() else {"distritos": [], "institutos": {}}
    institutos: dict[str, dict] = estado["institutos"]

    def guardar() -> None:
        avance.write_text(json.dumps(estado, ensure_ascii=False))

    with Visitante(timeout=30) as visitante:
        distritos = pedir("distritos_desft") or []
        for distrito in distritos:
            if distrito["id_distrito"] in estado["distritos"]:
                continue
            for titulo in pedir(f"distritostitulos_desft/{distrito['id_distrito']}") or []:
                for oferta in pedir(f"disxtit2_desft/{titulo['id_titulo']}/{distrito['id_distrito']}") or []:
                    institutos.setdefault(str(oferta["idserv"]), {})
            estado["distritos"].append(distrito["id_distrito"])
            guardar()
            print(f"{distrito['distrito']}: {len(institutos)} institutos hasta ahora", flush=True)
        for numero, (idserv, instituto) in enumerate(institutos.items()):
            if "ofertas" in instituto:
                continue
            ficha = pedir(f"escuela/{idserv}") or []
            instituto["escuela"] = ficha[0] if ficha else None
            instituto["ofertas"] = pedir(f"ofertascarreras/{idserv}") or []
            if numero % 25 == 0:
                guardar()
    guardar()
    SALIDA.write_text(json.dumps(institutos, ensure_ascii=False, indent=1) + "\n")
    print(f"PBA: {len(institutos)} institutos — {SALIDA}")


if __name__ == "__main__":
    main()
