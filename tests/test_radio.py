"""Pruebas sin red ni audio:  python -m unittest discover tests"""
from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radio import feeds, guion, podcast, voz

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>X</title>
<item><title><![CDATA[Sale Python 3.15]]></title><link>https://a/1</link>
<description>&lt;p&gt;Novedades del &lt;b&gt;int&#233;rprete&lt;/b&gt;. Mas info en https://python.org&lt;/p&gt;</description>
<pubDate>Sat, 21 Nov 2026 08:00:00 GMT</pubDate></item>
<item><title>Sin enlace</title></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Linux 7.1</title><link rel="alternate" href="https://b/1"/>
<updated>2026-11-21T10:00:00Z</updated><summary>Nuevo kernel.</summary></entry></feed>"""

AHORA = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)


def noticia(titulo: str, enlace: str, horas: float | None = 1, **extra) -> feeds.Noticia:
    fecha = None if horas is None else AHORA - timedelta(hours=horas)
    return feeds.Noticia(titulo, enlace, extra.pop("resumen", ""), fecha, **extra)


class FeedsTest(unittest.TestCase):
    def test_rss(self):
        [n] = feeds.leer(RSS)  # el item sin enlace se descarta
        self.assertEqual(n.titulo, "Sale Python 3.15")
        self.assertEqual(n.resumen, "Novedades del intérprete. Mas info en")
        self.assertEqual(n.fecha, datetime(2026, 11, 21, 8, tzinfo=timezone.utc))

    def test_atom(self):
        [n] = feeds.leer(ATOM)
        self.assertEqual((n.titulo, n.enlace, n.resumen), ("Linux 7.1", "https://b/1", "Nuevo kernel."))
        self.assertEqual(n.fecha.hour, 10)

    def test_primer_parrafo_con_texto(self):
        self.assertEqual(feeds.texto_plano("<p>corto</p><p>Este es el párrafo que vale la pena.</p><p>otro</p>"),
                         "Este es el párrafo que vale la pena.")


def fuente(nombre: str = "F", idioma: str = "es", seccion: str = "S", **extra) -> guion.Fuente:
    datos = dict(nombre=nombre, url="u", idioma=idioma, seccion=seccion, seccion_en=f"{seccion} EN",
                 maximo=5, horas=36)
    datos.update(extra)
    return guion.Fuente(**datos)


class GuionTest(unittest.TestCase):
    def test_fuentes_de_aplica_valores_por_defecto(self):
        config = {"radio": {"max_por_fuente": 2, "horas": 36},
                  "seccion": [{"nombre": "IA", "nombre_en": "AI", "fuentes": [
                      {"nombre": "A", "url": "u"}, {"nombre": "B", "url": "v", "idioma": "en", "max": 4,
                                                    "horas": 168, "filtro": ["Google"]}]}]}
        a, b = guion.fuentes_de(config)
        self.assertEqual((a.idioma, a.maximo, a.horas, a.seccion_en), ("es", 2, 36, "AI"))
        self.assertEqual((b.idioma, b.maximo, b.horas, b.filtro), ("en", 4, 168, ("google",)))

    def test_candidatas_respeta_topes_fecha_vistos_y_filtro(self):
        f = fuente(maximo=2)
        lista = [noticia("vieja", "e/0", horas=50), noticia("ya leída", "e/1"),
                 noticia("nueva uno", "e/2"), noticia("sin fecha", "e/3", horas=None), noticia("sobra", "e/4")]
        [(_, elegidas)] = guion.candidatas([(f, lista)], {"e/1"}, AHORA)
        self.assertEqual([n.titulo for n in elegidas], ["nueva uno", "sin fecha"])
        filtrada = fuente(filtro=("google",))
        [(_, elegidas)] = guion.candidatas([(filtrada, [noticia("Google lanza algo", "g/1"),
                                                        noticia("Recetas de cocina", "g/2"),
                                                        noticia("googleado", "g/3")])], set(), AHORA)
        self.assertEqual([n.enlace for n in elegidas], ["g/1"])  # palabra entera, no "googleado"

    def test_candidatas_saca_titulos_repetidos_entre_fuentes(self):
        a = (fuente("A"), [noticia("Llega GPT-9", "a/1")])
        b = (fuente("B"), [noticia("llega gpt 9", "b/1"), noticia("Otra", "b/2")])
        resultado = guion.candidatas([a, b], set(), AHORA)
        self.assertEqual([n.enlace for _, ns in resultado for n in ns], ["a/1", "b/2"])

    def test_elegir_reparte_por_idioma_y_ordena_espanol_primero(self):
        en = fuente("EN", idioma="en", seccion="S1")
        es1 = fuente("ES1", seccion="S1")
        es2 = fuente("ES2", seccion="S2")
        por_fuente = [(en, [noticia(f"en {i}", f"en/{i}", resumen="x" * 70) for i in range(5)]),
                      (es1, [noticia(f"uno {i}", f"es1/{i}", resumen="x" * 70) for i in range(5)]),
                      (es2, [noticia(f"dos {i}", f"es2/{i}", resumen="x" * 70) for i in range(5)])]
        elegidas = guion.elegir(por_fuente, set(), AHORA, caracteres=416, max_caracteres=700)
        titulos = [n.titulo for _, n in elegidas]
        # 104 o 105 caracteres por noticia: 2 en español (una de cada fuente) y 2 en inglés
        self.assertEqual(titulos, ["uno 0", "dos 0", "en 0", "en 1"])

    def test_elegir_pasa_lo_que_sobra_al_otro_idioma(self):
        es = fuente("ES")
        en = fuente("EN", idioma="en")
        por_fuente = [(es, [noticia("único", "es/0", resumen="x" * 70)]),
                      (en, [noticia(f"en {i}", f"en/{i}", resumen="x" * 70) for i in range(5)])]
        elegidas = guion.elegir(por_fuente, set(), AHORA, caracteres=416, max_caracteres=700)
        self.assertEqual(sum(1 for f, _ in elegidas if f.idioma == "en"), 3)

    def test_elegir_respeta_proporcion_en_y_pasa_sobrante(self):
        es = fuente("ES", maximo=10)
        en = fuente("EN", idioma="en", maximo=10)
        # Cada noticia pesa ~104 caracteres (len("en 0") + 70 + 30 = 104). Con 1040 chars: 10 noticias.
        por_fuente = [
            (es, [noticia(f"es {i}", f"es/{i}", resumen="x" * 70) for i in range(10)]),
            (en, [noticia(f"en {i}", f"en/{i}", resumen="x" * 70) for i in range(10)]),
        ]
        elegidas = guion.elegir(por_fuente, set(), AHORA, caracteres=1040, max_caracteres=700, proporcion_en=0.7)
        cant_es = sum(1 for f, _ in elegidas if f.idioma == "es")
        cant_en = sum(1 for f, _ in elegidas if f.idioma == "en")
        self.assertEqual(cant_es, 3)
        self.assertEqual(cant_en, 7)

        # Si faltan noticias en inglés, lo que sobra pasa al español
        por_fuente_poco_en = [
            (es, [noticia(f"es {i}", f"es/{i}", resumen="x" * 70) for i in range(10)]),
            (en, [noticia(f"en {i}", f"en/{i}", resumen="x" * 70) for i in range(2)]),
        ]
        elegidas2 = guion.elegir(por_fuente_poco_en, set(), AHORA, caracteres=1040, max_caracteres=700, proporcion_en=0.7)
        self.assertEqual(sum(1 for f, _ in elegidas2 if f.idioma == "en"), 2)
        self.assertEqual(sum(1 for f, _ in elegidas2 if f.idioma == "es"), 8)

    def test_recortar_en_fin_de_oracion(self):
        texto = "Primera oración bastante larga. Segunda oración que no entra en el límite."
        self.assertEqual(guion.recortar(texto, 40), "Primera oración bastante larga.")
        self.assertTrue(guion.recortar("palabra " * 20, 30).endswith("…"))

    def test_cuerpo_usa_el_texto_largo_y_saca_el_titulo_repetido(self):
        n = noticia("Sale Linux 7", "l/1", resumen="corto")
        n.texto = "Sale Linux 7. Trae muchas novedades."
        self.assertEqual(guion.cuerpo(n, fuente(), 700), "Trae muchas novedades.")
        self.assertEqual(guion.cuerpo(n, fuente(repo=True), 700), "corto")
        self.assertEqual(guion.cuerpo(n, fuente(resumen=False), 700), "")

    def test_armar_espanol_primero_y_despues_ingles(self):
        elegidas = [
            (fuente("MuyLinux", seccion="Linux"), noticia("Nuevo Debian", "1", resumen="Sale Debian.")),
            (fuente("Blog", idioma="en", seccion="Linux"), noticia("Big release?", "2", resumen="Details.")),
            (fuente("Trending", idioma="en", seccion="GitHub", repo=True), noticia("dueño/mi-repo_genial", "3", resumen="A tool.")),
            (fuente("HN", idioma="en", seccion="GitHub", resumen=False), noticia("Título HN", "4", resumen="Points: 30")),
        ]
        segs = guion.armar(elegidas, "Radio", AHORA, 200)
        textos = [(s.idioma, s.texto) for s in segs]
        self.assertIn("1 noticias en español y 3 en inglés", segs[0].texto)
        self.assertIn("sábado 21 de noviembre", segs[0].texto)
        self.assertLess(textos.index(("es", "De MuyLinux: Nuevo Debian.")), textos.index(("en", "And now, the news in English.")))
        self.assertIn(("es", "Linux."), textos)
        self.assertIn(("en", "Linux EN."), textos)  # la sección se anuncia en inglés
        self.assertIn(("en", "From Blog: Big release?"), textos)  # sin "?." doble
        self.assertIn(("en", "Repository mi repo genial, by dueño."), textos)
        self.assertIn(("en", "A tool."), textos)
        self.assertIn(("en", "From HN: Título HN."), textos)
        self.assertNotIn(("en", "Points: 30"), textos)
        self.assertEqual([s.tipo for s in segs if s.texto == "Linux."], ["seccion"])

    def test_armar_sin_noticias(self):
        segs = guion.armar([], "Radio", AHORA, 200)
        self.assertIn("No encontré noticias", segs[-1].texto)


class VozTest(unittest.TestCase):
    def test_limpiar(self):
        self.assertEqual(voz.limpiar("🧠 两小时 Train your LLM."), "Train your LLM.")

    def test_fichas_respetan_el_texto_y_marcan_palabras(self):
        t = voz.Tramo("es", "texto", "Hola, mundo: 3,5 GB.", 1000, 3000,
                      [(1100, "Hola"), (1500, "mundo"), (1900, "tres coma cinco"), (2400, "GB")])
        fichas = voz.fichas(t)
        self.assertEqual("".join(x for _, x in fichas), t.texto)  # el texto queda igual
        self.assertEqual([m for m, x in fichas if m >= 0], [1100, 1500, 2400])  # lo que no está tal cual, no se marca

    def test_duracion(self):
        self.assertEqual(voz.duracion_segundos(1_210_464), 202)


class PodcastTest(unittest.TestCase):
    def test_episodios_feed_y_vistos(self):
        cfg = {"titulo": "Radio & Co", "descripcion": "d", "idioma": "es"}
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            for dia in range(1, 5):
                ep = {"id": f"radio-tecno-2026-11-0{dia}", "titulo": f"Día {dia}", "publicado": f"2026-11-0{dia}T06:00:00-03:00",
                      "archivo": f"episodios/2026-11-0{dia}.mp3", "bytes": 3, "segundos": 61, "notas": "<ul></ul>"}
                episodios = podcast.agregar_episodio(carpeta, b"mp3", ep, guardar=3)
            self.assertEqual([e["id"][-2:] for e in episodios], ["04", "03", "02"])
            self.assertFalse((carpeta / "episodios/2026-11-01.mp3").exists())  # el viejo se borró
            self.assertTrue(podcast.hay_episodio(carpeta, "2026-11-04"))
            self.assertFalse(podcast.hay_episodio(carpeta, "2026-11-01"))

            podcast.escribir_feed(carpeta, episodios, cfg, "https://x.github.io/radio/")
            raiz = ET.parse(carpeta / "feed.xml").getroot()
            items = raiz.findall("channel/item")
            self.assertEqual(len(items), 3)
            self.assertEqual(items[0].find("enclosure").get("url"), "https://x.github.io/radio/episodios/2026-11-04.mp3")
            self.assertEqual(raiz.find("channel/title").text, "Radio & Co")
            self.assertIsNone(items[0].find("{https://podcastindex.org/namespace/1.0}transcript"))

            tramo = voz.Tramo("es", "texto", "Hola, mundo.", 0, 1500, [(100, "Hola"), (600, "mundo")])
            podcast.guardar_transcripcion(carpeta, "2026-11-04", [tramo])
            self.assertIn("00:00:00.100 --> 00:00:01.500\nHola, mundo.", (carpeta / "episodios/2026-11-04.vtt").read_text())
            datos = json.loads((carpeta / "episodios/2026-11-04.json").read_text())
            self.assertEqual(datos["tramos"][0]["fichas"], [[100, "Hola"], [-1, ", "], [600, "mundo"], [-1, "."]])
            episodios[0]["vtt"] = "episodios/2026-11-04.vtt"
            podcast.escribir_feed(carpeta, episodios, cfg, "https://x.github.io/radio/")
            item = ET.parse(carpeta / "feed.xml").getroot().find("channel/item")
            self.assertEqual(item.find("{https://podcastindex.org/namespace/1.0}transcript").get("url"),
                             "https://x.github.io/radio/episodios/2026-11-04.vtt")
            podcast.escribir_pagina(carpeta, episodios, cfg)
            self.assertIn("escuchar.html?e=2026-11-04", (carpeta / "index.html").read_text())
            self.assertIn("Radio &amp; Co", (carpeta / "escuchar.html").read_text())

            hoy = datetime(2026, 11, 21)
            podcast.guardar_vistos(carpeta, {"viejo": "2026-11-01", "reciente": "2026-11-20"}, ["nuevo"], hoy)
            vistos = json.loads((carpeta / "vistos.json").read_text())
            self.assertEqual(vistos, {"reciente": "2026-11-20", "nuevo": "2026-11-21"})


if __name__ == "__main__":
    unittest.main()
