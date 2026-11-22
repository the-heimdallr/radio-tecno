"""Elegir las noticias del día y armar el guion que se lee en voz alta (sin IA)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .feeds import Noticia

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


@dataclass
class Segmento:
    idioma: str  # "es" o "en": define la voz
    texto: str


def fecha_hablada(dia: datetime) -> str:
    return f"{DIAS[dia.weekday()]} {dia.day} de {MESES[dia.month - 1]}"


def recortar(texto: str, limite: int) -> str:
    """Corta en el último fin de oración antes del límite; si no hay, en la última palabra."""
    texto = texto.strip()
    if len(texto) <= limite:
        return texto
    corte = texto[:limite]
    fin = max(corte.rfind(". "), corte.rfind("? "), corte.rfind("! "))
    if fin > limite // 3:
        return corte[:fin + 1]
    return corte.rsplit(" ", 1)[0].rstrip(",;:") + "…"


def elegir(por_fuente: list[tuple[dict, list[Noticia]]], vistos: set[str], ahora: datetime,
           horas: int, max_por_fuente: int, max_noticias: int) -> list[Noticia]:
    """Toma de cada fuente las más nuevas que no se leyeron antes, respetando los topes.

    `por_fuente` viene en el orden de feeds.toml; las noticias sin fecha (como las
    tendencias de GitHub) cuentan como nuevas, y `vistos` evita repetirlas.
    """
    desde = ahora - timedelta(hours=horas)
    elegidas: list[Noticia] = []
    titulos: set[str] = set()
    for fuente, noticias in por_fuente:
        tope = int(fuente.get("max", max_por_fuente))
        tomadas = 0
        for n in noticias:
            if tomadas >= tope or len(elegidas) >= max_noticias:
                break
            clave = re.sub(r"\W+", " ", n.titulo.lower()).strip()
            if n.enlace in vistos or clave in titulos:
                continue
            if n.fecha is not None and n.fecha < desde:
                continue
            elegidas.append(n)
            titulos.add(clave)
            tomadas += 1
    return elegidas


def nombre_repo(titulo: str) -> str:
    """'dueño/repo-nombre' → 'repo nombre, de dueño' (la barra y los guiones no se leen bien)."""
    duenio, _, repo = titulo.partition("/")
    if not repo:
        return titulo
    return f"{re.sub(r'[-_]+', ' ', repo)}, de {duenio}"


def armar(noticias: list[Noticia], titulo_radio: str, dia: datetime,
          max_caracteres: int, fuentes_sin_resumen: set[str], fuentes_repo: set[str]) -> list[Segmento]:
    segmentos = [Segmento("es", f"Hola. Esto es {titulo_radio}, {fecha_hablada(dia)}. "
                                f"Hoy hay {len(noticias)} noticias.")]
    if not noticias:
        segmentos.append(Segmento("es", "No encontré noticias nuevas en las fuentes. Hasta mañana."))
        return segmentos
    seccion_actual = None
    for n in noticias:
        if n.seccion != seccion_actual:
            seccion_actual = n.seccion
            segmentos.append(Segmento("es", f"{n.seccion}."))
        clave = f"{n.seccion}/{n.fuente}"
        es_repo = clave in fuentes_repo
        titulo = nombre_repo(n.titulo) if es_repo else n.titulo
        resumen = "" if clave in fuentes_sin_resumen else recortar(n.resumen, max_caracteres)
        if n.idioma == "es":
            texto = f"De {n.fuente}: {titulo.rstrip('.')}. {resumen}"
            segmentos.append(Segmento("es", texto.strip()))
        else:
            aviso = f"Repositorio {titulo}." if es_repo else f"De {n.fuente}, en inglés."
            segmentos.append(Segmento("es", aviso))
            texto = resumen if es_repo else f"{titulo.rstrip('.')}. {resumen}"
            if texto.strip():
                segmentos.append(Segmento("en", texto.strip()))
    segmentos.append(Segmento("es", f"Eso es todo por hoy en {titulo_radio}. "
                                    "Los enlaces están en las notas del episodio. Hasta mañana."))
    return segmentos


def notas_html(noticias: list[Noticia]) -> str:
    """Notas del episodio: la lista de noticias con su enlace."""
    from html import escape
    filas = "".join(
        f'<li>{escape(n.seccion)} · {escape(n.fuente)}: <a href="{escape(n.enlace)}">{escape(n.titulo)}</a></li>'
        for n in noticias
    )
    return f"<ul>{filas}</ul>"
