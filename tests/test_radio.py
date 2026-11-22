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


class GuionTest(unittest.TestCase):
    def test_elegir_respeta_topes_fecha_y_vistos(self):
        fuente = {"nombre": "F", "max": 2}
        lista = [noticia("vieja", "e/0", horas=50), noticia("ya leída", "e/1"),
                 noticia("nueva uno", "e/2"), noticia("sin fecha", "e/3", horas=None), noticia("sobra", "e/4")]
        elegidas = guion.elegir([(fuente, lista)], {"e/1"}, AHORA, horas=36, max_por_fuente=5, max_noticias=10)
        self.assertEqual([n.titulo for n in elegidas], ["nueva uno", "sin fecha"])

    def test_elegir_saca_titulos_repetidos_entre_fuentes(self):
        a = ({"nombre": "A"}, [noticia("Llega GPT-9", "a/1")])
        b = ({"nombre": "B"}, [noticia("llega gpt 9", "b/1"), noticia("Otra", "b/2")])
        elegidas = guion.elegir([a, b], set(), AHORA, 36, 2, 10)
        self.assertEqual([n.enlace for n in elegidas], ["a/1", "b/2"])

    def test_recortar_en_fin_de_oracion(self):
        texto = "Primera oración bastante larga. Segunda oración que no entra en el límite."
        self.assertEqual(guion.recortar(texto, 40), "Primera oración bastante larga.")
        self.assertTrue(guion.recortar("palabra " * 20, 30).endswith("…"))

    def test_armar_con_voces_y_repos(self):
        notas = [
            noticia("Nuevo Debian", "1", fuente="MuyLinux", idioma="es", seccion="Linux", resumen="Sale Debian."),
            noticia("Big release", "2", fuente="Blog", idioma="en", seccion="Linux", resumen="Details."),
            noticia("dueño/mi-repo_genial", "3", fuente="Trending", idioma="en", seccion="GitHub", resumen="A tool."),
            noticia("Título HN", "4", fuente="HN", idioma="en", seccion="GitHub", resumen="Points: 30"),
        ]
        segs = guion.armar(notas, "Radio", AHORA, 200, {"GitHub/HN"}, {"GitHub/Trending"})
        textos = [(s.idioma, s.texto) for s in segs]
        self.assertIn(("es", "Linux."), textos)
        self.assertIn(("es", "De MuyLinux: Nuevo Debian. Sale Debian."), textos)
        self.assertIn(("en", "Big release. Details."), textos)
        self.assertIn(("es", "Repositorio mi repo genial, de dueño."), textos)
        self.assertIn(("en", "A tool."), textos)
        self.assertIn(("en", "Título HN."), textos)  # sin resumen
        self.assertEqual(sum(1 for s in segs if s.texto == "Linux."), 1)  # la sección se anuncia una vez
        self.assertIn("sábado 21 de noviembre", segs[0].texto)

    def test_armar_sin_noticias(self):
        segs = guion.armar([], "Radio", AHORA, 200, set(), set())
        self.assertIn("No encontré noticias", segs[-1].texto)


class VozTest(unittest.TestCase):
    def test_limpiar(self):
        self.assertEqual(voz.limpiar("🧠 两小时 Train your LLM."), "Train your LLM")

    def test_duracion(self):
        self.assertEqual(voz.duracion_segundos(1_210_464), 202)


class PodcastTest(unittest.TestCase):
    def test_episodios_feed_y_vistos(self):
        cfg = {"titulo": "Radio & Co", "descripcion": "d", "idioma": "es"}
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            for dia in range(1, 5):
                ep = {"id": f"ep-{dia}", "titulo": f"Día {dia}", "publicado": f"2026-11-0{dia}T06:00:00-03:00",
                      "archivo": f"episodios/2026-11-0{dia}.mp3", "bytes": 3, "segundos": 61, "notas": "<ul></ul>"}
                episodios = podcast.agregar_episodio(carpeta, b"mp3", ep, guardar=3)
            self.assertEqual([e["id"] for e in episodios], ["ep-4", "ep-3", "ep-2"])
            self.assertFalse((carpeta / "episodios/2026-11-01.mp3").exists())  # el viejo se borró

            podcast.escribir_feed(carpeta, episodios, cfg, "https://x.github.io/radio/")
            raiz = ET.parse(carpeta / "feed.xml").getroot()
            items = raiz.findall("channel/item")
            self.assertEqual(len(items), 3)
            self.assertEqual(items[0].find("enclosure").get("url"), "https://x.github.io/radio/episodios/2026-11-04.mp3")
            self.assertEqual(raiz.find("channel/title").text, "Radio & Co")

            hoy = datetime(2026, 11, 21)
            podcast.guardar_vistos(carpeta, {"viejo": "2026-11-01", "reciente": "2026-11-20"}, ["nuevo"], hoy)
            vistos = json.loads((carpeta / "vistos.json").read_text())
            self.assertEqual(vistos, {"reciente": "2026-11-20", "nuevo": "2026-11-21"})


if __name__ == "__main__":
    unittest.main()
