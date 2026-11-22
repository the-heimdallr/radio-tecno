"""Texto → MP3 con edge-tts (sin clave ni cupo; el texto va al servicio de Microsoft Edge).

edge-tts devuelve MP3 mono de 24 kHz a 48 kbit/s con todas las voces, así que los
pedazos en español e inglés se pueden pegar uno detrás del otro sin convertir nada.
"""
from __future__ import annotations

import asyncio
import unicodedata

from .guion import Segmento

BYTES_POR_SEGUNDO = 48_000 // 8
INTENTOS = 3


def limpiar(texto: str) -> str:
    """Saca emojis, símbolos y escrituras asiáticas, que las voces en español e inglés no leen."""
    t = "".join(c for c in texto if unicodedata.category(c) not in ("So", "Cs") and ord(c) < 0x2E80)
    return " ".join(t.split()).strip(" .,;:")


async def _sintetizar(texto: str, voz: str) -> bytes:
    import edge_tts  # se importa acá para que --dry-run y las pruebas no lo necesiten

    partes: list[bytes] = []
    async for trozo in edge_tts.Communicate(texto, voz).stream():
        if trozo.get("type") == "audio":
            partes.append(trozo["data"])
    return b"".join(partes)


async def _todo(segmentos: list[Segmento], voces: dict[str, str]) -> bytes:
    audio: list[bytes] = []
    for seg in segmentos:
        texto = limpiar(seg.texto)
        if not texto:
            continue
        for intento in range(1, INTENTOS + 1):
            try:
                audio.append(await asyncio.wait_for(_sintetizar(texto, voces[seg.idioma]), timeout=60))
                break
            except Exception:
                if intento == INTENTOS:
                    raise
                await asyncio.sleep(3 * intento)
    return b"".join(audio)


def sintetizar(segmentos: list[Segmento], voces: dict[str, str]) -> bytes:
    audio = asyncio.run(_todo(segmentos, voces))
    if not audio:
        raise RuntimeError("edge-tts no devolvió audio")
    return audio


def duracion_segundos(cantidad_bytes: int) -> int:
    return round(cantidad_bytes / BYTES_POR_SEGUNDO)
