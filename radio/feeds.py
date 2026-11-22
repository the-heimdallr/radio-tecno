"""Bajar y leer feeds RSS 2.0 y Atom con la librería estándar."""
from __future__ import annotations

import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENIDO = "{http://purl.org/rss/1.0/modules/content/}encoded"
USER_AGENT = "Mozilla/5.0 (Radio Tecno; podcast personal de noticias)"
TIMEOUT = 20
MAX_BYTES = 10_000_000  # tope por feed (el de Hugging Face pesa ~1 MB)
MAX_TEXTO = 3000  # caracteres de cada nota que se guardan (después se recortan en guion.py)
# Pies que agregan WordPress y otros al final de cada nota.
PIES = re.compile(r"(The post .{0,200}? appeared first on .*$|La entrada .{0,200}? se publicó primero en .*$"
                  r"|\[(…|\.\.\.)\]|Continue reading.*$|Seguir leyendo.*$|Read more.*$|Leer más.*$)", re.S | re.I)


@dataclass
class Noticia:
    titulo: str
    enlace: str
    resumen: str  # el primer párrafo con texto
    fecha: datetime | None
    texto: str = ""  # varios párrafos (de content:encoded si el feed lo trae); "" = igual al resumen
    fuente: str = ""
    idioma: str = "es"
    seccion: str = ""


def bajar(url: str, timeout: int = TIMEOUT) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(pedido, timeout=timeout) as respuesta:
        return respuesta.read(MAX_BYTES)


def texto_plano(fragmento: str) -> str:
    """HTML → texto. Si hay párrafos, se queda con el primero que tenga texto."""
    fragmento = fragmento or ""
    for parrafo in re.findall(r"<p[^>]*>(.*?)</p>", fragmento, flags=re.S | re.I):
        limpio = _sin_etiquetas(parrafo)
        if len(limpio) > 20:
            return limpio
    return _sin_etiquetas(fragmento)


def parrafos(fragmento: str, limite: int = MAX_TEXTO) -> str:
    """HTML → texto de varios párrafos seguidos, hasta `limite` caracteres."""
    partes = [_sin_etiquetas(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", fragmento or "", flags=re.S | re.I)]
    partes = [p for p in partes if len(p) > 20] or [_sin_etiquetas(fragmento or "")]
    texto = ""
    for parte in partes:
        if len(texto) >= limite:
            break
        texto = f"{texto} {parte}".strip()
    return PIES.sub("", texto[:limite]).strip()


def _sin_etiquetas(fragmento: str) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragmento, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"\s+([.,;:!?)])", r"\1", t).strip()


def _fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    valor = valor.strip()
    try:
        fecha = parsedate_to_datetime(valor)  # RSS: "Sat, 21 Nov 2026 08:04:28 GMT"
    except (TypeError, ValueError):
        try:
            fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))  # Atom: ISO 8601
        except ValueError:
            return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _texto(nodo: ET.Element | None) -> str:
    return (nodo.text or "").strip() if nodo is not None else ""


def leer(contenido: bytes) -> list[Noticia]:
    """Devuelve las noticias de un feed RSS o Atom, en el orden del feed."""
    raiz = ET.fromstring(contenido)
    noticias: list[Noticia] = []
    for item in raiz.iter("item"):  # RSS 2.0
        descripcion = _texto(item.find("description"))
        contenido = _texto(item.find(CONTENIDO))
        noticias.append(Noticia(
            titulo=texto_plano(_texto(item.find("title"))),
            enlace=_texto(item.find("link")),
            resumen=PIES.sub("", texto_plano(descripcion)).strip(),
            fecha=_fecha(_texto(item.find("pubDate"))),
            texto=parrafos(contenido if len(contenido) > len(descripcion) else descripcion),
        ))
    for entrada in raiz.iter(f"{ATOM}entry"):  # Atom
        enlace = ""
        for link in entrada.findall(f"{ATOM}link"):
            if link.get("rel", "alternate") == "alternate":
                enlace = link.get("href", "")
                break
        resumen = _texto(entrada.find(f"{ATOM}summary"))
        contenido = _texto(entrada.find(f"{ATOM}content"))
        noticias.append(Noticia(
            titulo=texto_plano(_texto(entrada.find(f"{ATOM}title"))),
            enlace=enlace,
            resumen=PIES.sub("", texto_plano(resumen or contenido)).strip(),
            fecha=_fecha(_texto(entrada.find(f"{ATOM}published")) or _texto(entrada.find(f"{ATOM}updated"))),
            texto=parrafos(contenido if len(contenido) > len(resumen) else resumen),
        ))
    return [n for n in noticias if n.titulo and n.enlace]
