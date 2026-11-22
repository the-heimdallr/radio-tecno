"""La carpeta pública del podcast: MP3, lista de episodios, feed RSS y una página simple.

Estructura de `publico/` (es lo que se sube a la rama gh-pages):
    episodios/AAAA-MM-DD.mp3
    episodios/AAAA-MM-DD.json  transcripción con el tiempo de cada palabra (la usa escuchar.html)
    episodios/AAAA-MM-DD.vtt   subtítulos (AntennaPod los muestra como transcripción)
    episodios.json   lista de episodios, del más nuevo al más viejo
    vistos.json      enlaces ya leídos (para no repetir), con su fecha
    feed.xml         el feed de podcast que se agrega en AntennaPod
    index.html       página con la lista de episodios
    escuchar.html    página para escuchar y leer a la vez: marca cada palabra mientras suena
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from importlib import resources
from email.utils import format_datetime
from html import escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from .voz import Tramo, fichas

DIAS_VISTOS = 10
PALABRAS_POR_SUBTITULO = 14
EXTENSIONES = (".mp3", ".json", ".vtt")


def _leer_json(ruta: Path, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def _guardar_json(ruta: Path, datos) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cargar_vistos(carpeta: Path) -> dict[str, str]:
    return _leer_json(carpeta / "vistos.json", {})


def guardar_vistos(carpeta: Path, vistos: dict[str, str], enlaces: list[str], hoy: datetime) -> None:
    limite = (hoy - timedelta(days=DIAS_VISTOS)).date().isoformat()
    vistos = {e: f for e, f in vistos.items() if f >= limite}
    for enlace in enlaces:
        vistos[enlace] = hoy.date().isoformat()
    _guardar_json(carpeta / "vistos.json", vistos)


def hay_episodio(carpeta: Path, dia: str) -> bool:
    return any(e["archivo"] == f"episodios/{dia}.mp3" for e in _leer_json(carpeta / "episodios.json", []))


def agregar_episodio(carpeta: Path, audio: bytes, episodio: dict, guardar: int) -> list[dict]:
    """Guarda el MP3, suma el episodio a la lista y borra los que pasan de `guardar`."""
    (carpeta / "episodios").mkdir(parents=True, exist_ok=True)
    (carpeta / episodio["archivo"]).write_bytes(audio)
    episodios = [e for e in _leer_json(carpeta / "episodios.json", []) if e["id"] != episodio["id"]]
    episodios.insert(0, episodio)
    for viejo in episodios[guardar:]:
        for extension in EXTENSIONES:
            (carpeta / viejo["archivo"]).with_suffix(extension).unlink(missing_ok=True)
    episodios = episodios[:guardar]
    _guardar_json(carpeta / "episodios.json", episodios)
    return episodios


def guardar_transcripcion(carpeta: Path, dia: str, tramos: list[Tramo]) -> None:
    """Escribe la transcripción del episodio en JSON (para escuchar.html) y en VTT (subtítulos)."""
    (carpeta / "episodios").mkdir(parents=True, exist_ok=True)
    datos = {"tramos": [{"idioma": t.idioma, "tipo": t.tipo, "inicio": t.inicio_ms, "fin": t.fin_ms,
                         "fichas": fichas(t)} for t in tramos]}
    (carpeta / f"episodios/{dia}.json").write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
                                                   encoding="utf-8")
    (carpeta / f"episodios/{dia}.vtt").write_text(vtt(tramos), encoding="utf-8")


def _hora_vtt(ms: int) -> str:
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"


def vtt(tramos: list[Tramo]) -> str:
    """Subtítulos WebVTT: cada tramo se parte en renglones de unas 14 palabras, con su puntuación."""
    lineas = ["WEBVTT", ""]
    for t in tramos:
        grupos: list[tuple[int, str]] = []  # (ms de inicio, texto)
        inicio, texto, cuenta = None, "", 0
        for ms, trozo in fichas(t):
            if ms >= 0:
                if cuenta == PALABRAS_POR_SUBTITULO:
                    grupos.append((inicio, texto))
                    inicio, texto, cuenta = None, "", 0
                inicio = ms if inicio is None else inicio
                cuenta += 1
            texto += trozo
        if texto.strip():
            grupos.append((t.inicio_ms if inicio is None else inicio, texto))
        for i, (desde, renglon) in enumerate(grupos):
            hasta = grupos[i + 1][0] if i + 1 < len(grupos) else t.fin_ms
            lineas += [f"{_hora_vtt(desde)} --> {_hora_vtt(max(hasta, desde + 1))}", renglon.strip(), ""]
    return "\n".join(lineas)


def _duracion(segundos: int) -> str:
    return f"{segundos // 3600:02d}:{segundos % 3600 // 60:02d}:{segundos % 60:02d}"


def escribir_feed(carpeta: Path, episodios: list[dict], cfg: dict, base_url: str) -> None:
    base = base_url.rstrip("/")
    items = []
    for e in episodios:
        fecha = format_datetime(datetime.fromisoformat(e["publicado"]))
        transcripcion = ""
        if e.get("vtt"):
            transcripcion = (f'\n      <podcast:transcript url="{xml_escape(f"{base}/{e['vtt']}")}" type="text/vtt"/>'
                             f'\n      <link>{xml_escape(f"{base}/escuchar.html?e={e['id'][-10:]}")}</link>')
        items.append(f"""    <item>
      <title>{xml_escape(e["titulo"])}</title>
      <description><![CDATA[{e["notas"]}]]></description>
      <guid isPermaLink="false">{xml_escape(e["id"])}</guid>
      <pubDate>{fecha}</pubDate>
      <enclosure url="{xml_escape(f'{base}/{e["archivo"]}')}" length="{e["bytes"]}" type="audio/mpeg"/>
      <itunes:duration>{_duracion(e["segundos"])}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>{transcripcion}
    </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>{xml_escape(cfg["titulo"])}</title>
    <link>{xml_escape(base)}/</link>
    <atom:link href="{xml_escape(base)}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>{xml_escape(cfg["descripcion"])}</description>
    <language>{xml_escape(cfg.get("idioma", "es"))}</language>
    <itunes:author>{xml_escape(cfg.get("autor", cfg["titulo"]))}</itunes:author>
    <itunes:explicit>false</itunes:explicit>
    <itunes:category text="Technology"/>
{chr(10).join(items)}
  </channel>
</rss>
"""
    (carpeta / "feed.xml").write_text(feed, encoding="utf-8")


def escribir_pagina(carpeta: Path, episodios: list[dict], cfg: dict) -> None:
    bloques = "".join(
        f'<article><h2>{escape(e["titulo"])}</h2>'
        + (f'<p><a class="leer" href="escuchar.html?e={escape(e["id"][-10:])}">📖 Escuchar leyendo el texto</a></p>'
           if e.get("vtt") else f'<audio controls preload="none" src="{escape(e["archivo"])}"></audio>')
        + f'{e["notas"]}</article>'
        for e in episodios
    )
    pagina = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(cfg["titulo"])}</title>
<link rel="alternate" type="application/rss+xml" href="feed.xml">
<style>body{{font-family:system-ui,sans-serif;max-width:46rem;margin:auto;padding:1rem;line-height:1.5}}
audio{{width:100%}}.leer{{font-size:1.2rem}}article{{border-top:1px solid #ccc;padding:.5rem 0}}li{{margin:.2rem 0}}</style></head>
<body><h1>{escape(cfg["titulo"])}</h1><p>{escape(cfg["descripcion"])}</p>
<p>Para escucharlo como podcast, agregá <a href="feed.xml">feed.xml</a> en AntennaPod.</p>
{bloques}</body></html>
"""
    (carpeta / "index.html").write_text(pagina, encoding="utf-8")
    plantilla = resources.files("radio").joinpath("escuchar.html").read_text(encoding="utf-8")
    (carpeta / "escuchar.html").write_text(plantilla.replace("{{TITULO}}", escape(cfg["titulo"])), encoding="utf-8")
    (carpeta / ".nojekyll").touch()
