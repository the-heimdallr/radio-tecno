"""Elegir las noticias del día y armar el guion que se lee en voz alta (sin IA).

El episodio tiene dos partes: primero todas las noticias en español y después todas
las de fuentes en inglés (anunciadas en inglés, para practicar el idioma).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape

from .feeds import Noticia

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
COSTO_FIJO = 30  # caracteres de "De Fuente: " y pausas que suma cada noticia


@dataclass
class Segmento:
    idioma: str        # "es" o "en": define la voz
    texto: str
    tipo: str = "texto"  # "seccion", "titulo" o "texto": cómo se muestra en la transcripción


@dataclass
class Fuente:
    """Una fuente de feeds.toml, con los valores por defecto de [radio] ya aplicados."""
    nombre: str
    url: str
    idioma: str
    seccion: str
    seccion_en: str
    maximo: int
    horas: int
    resumen: bool = True
    repo: bool = False
    filtro: tuple[str, ...] = ()


def fuentes_de(config: dict) -> list[Fuente]:
    r = config["radio"]
    lista = []
    for s in config["seccion"]:
        for f in s["fuentes"]:
            lista.append(Fuente(
                nombre=f["nombre"], url=f["url"], idioma=f.get("idioma", "es"),
                seccion=s["nombre"], seccion_en=s.get("nombre_en", s["nombre"]),
                maximo=int(f.get("max", r["max_por_fuente"])), horas=int(f.get("horas", r["horas"])),
                resumen=f.get("resumen", True), repo=f.get("repo", False),
                filtro=tuple(p.lower() for p in f.get("filtro", [])),
            ))
    return lista


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


def cuerpo(n: Noticia, fuente: Fuente, max_caracteres: int) -> str:
    """El texto que se lee después del título."""
    if not fuente.resumen:
        return ""
    if fuente.repo:  # en las tendencias de GitHub, el primer párrafo es la descripción del repo
        return recortar(n.resumen, max_caracteres)
    texto = n.texto or n.resumen
    if texto.lower().startswith(n.titulo.lower().rstrip(".")):  # algunos feeds repiten el título
        texto = texto[len(n.titulo):].lstrip(" .:-")
    return recortar(texto, max_caracteres)


def _pasa_filtro(n: Noticia, fuente: Fuente) -> bool:
    if not fuente.filtro:
        return True
    texto = f" {n.titulo} {n.resumen} ".lower()
    return any(re.search(rf"\b{re.escape(p)}\b", texto) for p in fuente.filtro)


def candidatas(por_fuente: list[tuple[Fuente, list[Noticia]]], vistos: set[str],
               ahora: datetime) -> list[tuple[Fuente, list[Noticia]]]:
    """Por fuente, las noticias que se pueden leer hoy: recientes, nuevas, del tema y sin repetir."""
    titulos: set[str] = set()
    resultado = []
    for fuente, noticias in por_fuente:
        desde = ahora - timedelta(hours=fuente.horas)
        lista = []
        for n in noticias:
            clave = re.sub(r"\W+", " ", n.titulo.lower()).strip()
            if len(lista) >= fuente.maximo or n.enlace in vistos or clave in titulos:
                continue
            if (n.fecha is not None and n.fecha < desde) or not _pasa_filtro(n, fuente):
                continue
            lista.append(n)
            titulos.add(clave)
        resultado.append((fuente, lista))
    return resultado


def elegir(por_fuente: list[tuple[Fuente, list[Noticia]]], vistos: set[str], ahora: datetime,
           caracteres: int, max_caracteres: int) -> list[tuple[Fuente, Noticia]]:
    """Elige hasta llenar `caracteres` (la duración buscada), mitad en español y mitad en inglés.

    Dentro de cada idioma toma una noticia de cada fuente por vuelta, así no se llena con
    la primera fuente. Si un idioma no llega a su mitad, lo que sobra pasa al otro.
    Devuelve las elegidas en el orden de lectura: español, inglés; sección y fuente según feeds.toml.
    """
    cola = candidatas(por_fuente, vistos, ahora)
    orden = {id(f): i for i, (f, _) in enumerate(cola)}
    pendientes = {idioma: [(f, list(ns)) for f, ns in cola if f.idioma == idioma and ns] for idioma in ("es", "en")}
    elegidas: list[tuple[Fuente, Noticia]] = []
    usados = {"es": 0, "en": 0}

    def tomar(idioma: str, tope: int) -> None:
        while usados[idioma] < tope and pendientes[idioma]:
            for par in list(pendientes[idioma]):
                fuente, noticias = par
                n = noticias.pop(0)
                if not noticias:
                    pendientes[idioma].remove(par)
                elegidas.append((fuente, n))
                usados[idioma] += len(n.titulo) + len(cuerpo(n, fuente, max_caracteres)) + COSTO_FIJO
                if usados[idioma] >= tope:
                    break

    mitad = caracteres // 2
    tomar("es", mitad)
    tomar("en", mitad)
    tomar("es", caracteres - usados["en"])  # lo que no usó el inglés
    tomar("en", caracteres - usados["es"])  # y al revés
    idioma_orden = {"es": 0, "en": 1}
    posicion = {id(n): i for i, (_, n) in enumerate(elegidas)}
    elegidas.sort(key=lambda par: (idioma_orden[par[0].idioma], _orden_seccion(cola, par[0]),
                                   orden[id(par[0])], posicion[id(par[1])]))
    return elegidas


def _orden_seccion(cola: list[tuple[Fuente, list[Noticia]]], fuente: Fuente) -> int:
    secciones: list[str] = []
    for f, _ in cola:
        if f.seccion not in secciones:
            secciones.append(f.seccion)
    return secciones.index(fuente.seccion)


def oracion(texto: str) -> str:
    """Termina el texto con punto, salvo que ya cierre con un signo."""
    texto = texto.strip()
    return texto if texto[-1:] in ".?!…" else f"{texto}."


def nombre_repo(titulo: str, idioma: str = "es") -> str:
    """'dueño/repo-nombre' → 'repo nombre, de dueño' (la barra y los guiones no se leen bien)."""
    duenio, _, repo = titulo.partition("/")
    if not repo:
        return titulo
    return f"{re.sub(r'[-_]+', ' ', repo)}, {'de' if idioma == 'es' else 'by'} {duenio}"


def armar(elegidas: list[tuple[Fuente, Noticia]], titulo_radio: str, dia: datetime,
          max_caracteres: int) -> list[Segmento]:
    es = [(f, n) for f, n in elegidas if f.idioma == "es"]
    en = [(f, n) for f, n in elegidas if f.idioma == "en"]
    segmentos = [Segmento("es", f"Hola. Esto es {titulo_radio}, {fecha_hablada(dia)}. "
                                f"Hoy hay {len(es)} noticias en español y {len(en)} en inglés.")]
    if not elegidas:
        segmentos.append(Segmento("es", "No encontré noticias nuevas en las fuentes. Hasta mañana."))
        return segmentos
    if es:
        segmentos.append(Segmento("es", "Primero, las noticias en español."))
        segmentos += _bloque(es, "es", max_caracteres)
    if en:
        segmentos.append(Segmento("es", "Ahora, las noticias en inglés, para practicar."))
        segmentos.append(Segmento("en", "And now, the news in English."))
        segmentos += _bloque(en, "en", max_caracteres)
        segmentos.append(Segmento("en", "That's all for today. See you tomorrow."))
    segmentos.append(Segmento("es", f"Eso es todo por hoy en {titulo_radio}. "
                                    "Los enlaces y el texto están en las notas del episodio. Hasta mañana."))
    return segmentos


def _bloque(elegidas: list[tuple[Fuente, Noticia]], idioma: str, max_caracteres: int) -> list[Segmento]:
    segmentos: list[Segmento] = []
    seccion_actual = None
    for fuente, n in elegidas:
        seccion = fuente.seccion if idioma == "es" else fuente.seccion_en
        if seccion != seccion_actual:
            seccion_actual = seccion
            segmentos.append(Segmento(idioma, f"{seccion}.", "seccion"))
        if fuente.repo:
            encabezado = f"{'Repositorio' if idioma == 'es' else 'Repository'} {nombre_repo(n.titulo, idioma)}."
        else:
            encabezado = oracion(f"{'De' if idioma == 'es' else 'From'} {fuente.nombre}: {n.titulo}")
        segmentos.append(Segmento(idioma, encabezado, "titulo"))
        texto = cuerpo(n, fuente, max_caracteres)
        if texto:
            segmentos.append(Segmento(idioma, texto))
    return segmentos


def notas_html(elegidas: list[tuple[Fuente, Noticia]]) -> str:
    """Notas del episodio: las noticias con su enlace, separadas por idioma."""
    partes = []
    for idioma, nombre in (("es", "En español"), ("en", "En inglés")):
        filas = "".join(
            f'<li>{escape(f.seccion)} · {escape(f.nombre)}: <a href="{escape(n.enlace)}">{escape(n.titulo)}</a></li>'
            for f, n in elegidas if f.idioma == idioma
        )
        if filas:
            partes.append(f"<p><b>{nombre}</b></p><ul>{filas}</ul>")
    return "".join(partes)
