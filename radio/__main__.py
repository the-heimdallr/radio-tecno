"""Arma el episodio del día.

    python -m radio --dry-run          # muestra el guion, no genera audio
    python -m radio                    # genera el MP3 y actualiza publico/
    python -m radio --base-url https://usuario.github.io/radio-tecno
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import feeds, guion, podcast, voz

RAIZ = Path(__file__).resolve().parent.parent
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def cargar_config(ruta: Path) -> dict:
    with ruta.open("rb") as archivo:
        return tomllib.load(archivo)


def bajar_todo(config: dict) -> list[tuple[dict, list[feeds.Noticia]]]:
    """Baja todas las fuentes en paralelo. Una fuente caída no frena el episodio."""
    fuentes = [(s["nombre"], f) for s in config["seccion"] for f in s["fuentes"]]

    def una(par: tuple[str, dict]) -> tuple[dict, list[feeds.Noticia]]:
        seccion, fuente = par
        try:
            noticias = feeds.leer(feeds.bajar(fuente["url"]))
        except Exception as exc:  # red, XML roto, etc.
            print(f"  ! {seccion} / {fuente['nombre']}: {exc}", file=sys.stderr)
            return fuente, []
        for n in noticias:
            n.fuente, n.idioma, n.seccion = fuente["nombre"], fuente.get("idioma", "es"), seccion
        return fuente, noticias

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(una, fuentes))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Radio Tecno: noticias de tecnología en un podcast diario.")
    p.add_argument("--config", type=Path, default=RAIZ / "feeds.toml")
    p.add_argument("--salida", type=Path, default=RAIZ / "publico")
    p.add_argument("--base-url", default="http://localhost:8000", help="dirección donde se publica la carpeta de salida")
    p.add_argument("--dry-run", action="store_true", help="solo mostrar el guion")
    p.add_argument("--forzar", action="store_true", help="rehacer el episodio de hoy si ya existe")
    args = p.parse_args(argv)

    config = cargar_config(args.config)
    cfg = config["radio"]
    ahora = datetime.now(ZONA)
    vistos = podcast.cargar_vistos(args.salida)
    hoy = ahora.date().isoformat()
    if podcast.hay_episodio(args.salida, hoy) and not args.dry_run:
        if not args.forzar:
            print(f"Ya hay episodio del {hoy}; para rehacerlo: --forzar")
            return 0
        vistos = {e: f for e, f in vistos.items() if f < hoy}  # se vuelve a leer lo de hoy

    por_fuente = bajar_todo(config)
    noticias = guion.elegir(por_fuente, set(vistos), ahora, cfg["horas"], cfg["max_por_fuente"], cfg["max_noticias"])
    sin_resumen = {f"{s['nombre']}/{f['nombre']}" for s in config["seccion"] for f in s["fuentes"] if f.get("resumen") is False}
    repos = {f"{s['nombre']}/{f['nombre']}" for s in config["seccion"] for f in s["fuentes"] if f.get("repo")}
    segmentos = guion.armar(noticias, cfg["titulo"], ahora, cfg["max_caracteres_resumen"], sin_resumen, repos)

    if not noticias and not args.dry_run:
        print("No hay noticias nuevas: hoy no se arma episodio.")
        return 0
    if args.dry_run:
        for seg in segmentos:
            print(f"[{seg.idioma}] {seg.texto}")
        caracteres = sum(len(s.texto) for s in segmentos)
        print(f"\n{len(noticias)} noticias, {caracteres} caracteres (~{caracteres // 900} min de audio)")
        return 0

    audio = voz.sintetizar(segmentos, {"es": cfg["voz_es"], "en": cfg["voz_en"]})
    dia = hoy
    episodio = {
        "id": f"radio-tecno-{dia}",
        "titulo": f"{cfg['titulo']} · {guion.fecha_hablada(ahora).capitalize()}",
        "publicado": ahora.isoformat(timespec="seconds"),
        "archivo": f"episodios/{dia}.mp3",
        "bytes": len(audio),
        "segundos": voz.duracion_segundos(len(audio)),
        "notas": guion.notas_html(noticias),
    }
    args.salida.mkdir(parents=True, exist_ok=True)
    episodios = podcast.agregar_episodio(args.salida, audio, episodio, cfg["episodios_guardados"])
    podcast.guardar_vistos(args.salida, vistos, [n.enlace for n in noticias], ahora)
    podcast.escribir_feed(args.salida, episodios, cfg, args.base_url)
    podcast.escribir_pagina(args.salida, episodios, cfg)
    print(f"Episodio {episodio['archivo']}: {len(noticias)} noticias, "
          f"{episodio['segundos'] // 60} min {episodio['segundos'] % 60} s, {len(audio) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
