"""Texto → MP3 con edge-tts (sin clave ni cupo; el texto va al servicio de Microsoft Edge).

edge-tts devuelve MP3 mono de 24 kHz a 48 kbit/s con todas las voces, así que los
pedazos en español e inglés se pueden pegar uno detrás del otro sin convertir nada.
También avisa en qué momento empieza cada palabra (WordBoundary): con eso se arma la
transcripción que se va marcando mientras suena el audio.
"""
from __future__ import annotations

import asyncio
import unicodedata
from dataclasses import dataclass, field

from .guion import Segmento

BYTES_POR_SEGUNDO = 48_000 // 8
INTENTOS = 3
TICKS_POR_MS = 10_000  # edge-tts mide el tiempo en unidades de 100 nanosegundos


@dataclass
class Tramo:
    """Un segmento ya sintetizado: dónde empieza en el episodio y sus palabras con su tiempo."""
    idioma: str
    tipo: str
    texto: str
    inicio_ms: int
    fin_ms: int
    palabras: list[tuple[int, str]] = field(default_factory=list)  # (ms desde el inicio del episodio, palabra)


def limpiar(texto: str) -> str:
    """Saca emojis, símbolos y escrituras asiáticas, que las voces en español e inglés no leen."""
    t = "".join(c for c in texto if unicodedata.category(c) not in ("So", "Cs") and ord(c) < 0x2E80)
    return " ".join(t.split()).strip(" ,;:")


async def _sintetizar(texto: str, voz: str, velocidad: str) -> tuple[bytes, list[tuple[int, str]]]:
    import edge_tts  # se importa acá para que --dry-run y las pruebas no lo necesiten

    partes: list[bytes] = []
    palabras: list[tuple[int, str]] = []
    async for trozo in edge_tts.Communicate(texto, voz, rate=velocidad, boundary="WordBoundary").stream():
        if trozo.get("type") == "audio":
            partes.append(trozo["data"])
        elif trozo.get("type") == "WordBoundary":
            palabras.append((trozo["offset"] // TICKS_POR_MS, trozo["text"]))
    return b"".join(partes), palabras


async def _todo(segmentos: list[Segmento], voces: dict[str, str], velocidades: dict[str, str]
                ) -> tuple[bytes, list[Tramo]]:
    audio: list[bytes] = []
    tramos: list[Tramo] = []
    total_bytes = 0
    for seg in segmentos:
        texto = limpiar(seg.texto)
        if not texto:
            continue
        for intento in range(1, INTENTOS + 1):
            try:
                pedazo, palabras = await asyncio.wait_for(
                    _sintetizar(texto, voces[seg.idioma], velocidades.get(seg.idioma, "+0%")), timeout=90)
                break
            except Exception:
                if intento == INTENTOS:
                    raise
                await asyncio.sleep(3 * intento)
        inicio = duracion_ms(total_bytes)
        total_bytes += len(pedazo)
        tramos.append(Tramo(seg.idioma, seg.tipo, texto, inicio, duracion_ms(total_bytes),
                            [(inicio + ms, palabra) for ms, palabra in palabras]))
        audio.append(pedazo)
    return b"".join(audio), tramos


def sintetizar(segmentos: list[Segmento], voces: dict[str, str],
               velocidades: dict[str, str] | None = None) -> tuple[bytes, list[Tramo]]:
    audio, tramos = asyncio.run(_todo(segmentos, voces, velocidades or {}))
    if not audio:
        raise RuntimeError("edge-tts no devolvió audio")
    return audio, tramos


def duracion_ms(cantidad_bytes: int) -> int:
    return cantidad_bytes * 1000 // BYTES_POR_SEGUNDO


def duracion_segundos(cantidad_bytes: int) -> int:
    return round(cantidad_bytes / BYTES_POR_SEGUNDO)


def fichas(tramo: Tramo) -> list[list]:
    """Parte el texto del tramo en fichas [ms, texto]: palabras con su tiempo y, entre ellas,
    los espacios y signos con ms = -1. Así la página muestra el texto tal cual y marca cada palabra."""
    resultado: list[list] = []
    cursor = 0
    for ms, palabra in tramo.palabras:
        pos = tramo.texto.find(palabra, cursor)
        if pos < 0:  # la voz leyó algo distinto (por ejemplo, un número): no se marca
            continue
        if pos > cursor:
            resultado.append([-1, tramo.texto[cursor:pos]])
        resultado.append([ms, palabra])
        cursor = pos + len(palabra)
    if cursor < len(tramo.texto):
        resultado.append([-1, tramo.texto[cursor:]])
    return resultado
