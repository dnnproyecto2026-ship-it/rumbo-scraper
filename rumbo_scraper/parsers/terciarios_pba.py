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

    institutos: dict[int, dict] = {}
    with Visitante(timeout=30) as visitante:
        distritos = pedir("distritos_desft") or []
        for distrito in distritos:
            for titulo in pedir(f"distritostitulos_desft/{distrito['id_distrito']}") or []:
                for oferta in pedir(f"disxtit2_desft/{titulo['id_titulo']}/{distrito['id_distrito']}") or []:
                    institutos.setdefault(oferta["idserv"], {})
            print(f"{distrito['distrito']}: {len(institutos)} institutos hasta ahora", flush=True)
        for idserv, instituto in institutos.items():
            ficha = pedir(f"escuela/{idserv}") or []
            instituto["escuela"] = ficha[0] if ficha else None
            instituto["ofertas"] = pedir(f"ofertascarreras/{idserv}") or []
    SALIDA.write_text(json.dumps({str(k): v for k, v in institutos.items()}, ensure_ascii=False, indent=1) + "\n")
    print(f"PBA: {len(institutos)} institutos — {SALIDA}")


if __name__ == "__main__":
    main()
