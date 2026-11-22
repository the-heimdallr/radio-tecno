# Radio Tecno

Un podcast diario de unos 30 minutos con noticias de IA, Google, Microsoft, NVIDIA,
programación, Python, Linux y repos de GitHub, armado con Python. Lee los feeds RSS de
`feeds.toml`, elige las noticias nuevas y las pasa a voz con
[edge-tts](https://github.com/rany2/edge-tts): **primero todas en español** (voz de Elena) y
**después todas en inglés** (voz de Aria, un 10 % más lenta), para practicar el idioma.

- **Escuchar leyendo:** `escuchar.html` muestra el texto del episodio y marca cada palabra
  mientras suena (sirve para aprender inglés). Tocar una palabra salta a ese momento; se puede
  bajar la velocidad a 0.8× y retoma donde quedó. AntennaPod también muestra la transcripción
  (subtítulos `.vtt` en el feed).

- **No usa IA ni claves:** lee el título y la bajada que trae cada fuente.
- **No llena el celular:** se escucha por streaming y el sitio guarda solo los últimos 7
  episodios (unos 13 MB cada uno: ojo con los datos móviles, mejor con wifi).
- **No usa la PC:** GitHub Actions lo arma todos los días a las 06:00 (hora de Argentina) y lo
  publica en GitHub Pages.

## Cómo está hecho

| Archivo | Qué hace |
|---------|----------|
| `feeds.toml` | Configuración: fuentes por sección, voces y topes. Para cambiar las noticias, se toca solo esto |
| `radio/feeds.py` | Baja los feeds y lee RSS 2.0 y Atom con `urllib` y `xml.etree` (librería estándar) |
| `radio/guion.py` | Elige las noticias hasta llenar unos 30 minutos (mitad por idioma, una por fuente por vuelta, sin repetir) y arma el guion |
| `radio/voz.py` | Pasa cada segmento a MP3 con edge-tts (`asyncio`), los pega y guarda el momento de cada palabra |
| `radio/podcast.py` | Guarda el episodio y su transcripción (JSON y VTT), borra los viejos y escribe `feed.xml` e `index.html` |
| `radio/escuchar.html` | La página que marca la palabra que suena (el único JavaScript: en el navegador no corre Python) |
| `radio/__main__.py` | El programa: `python -m radio` |
| `.github/workflows/episodio.yml` | La corrida diaria en GitHub y la publicación en la rama `gh-pages` |

## Usarlo en la PC

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m radio --dry-run        # muestra el guion, sin audio
.venv/bin/python -m radio                  # arma publico/episodios/AAAA-MM-DD.mp3
.venv/bin/python -m http.server -d publico # http://localhost:8000 (este servidor no deja saltar en el audio; GitHub Pages sí)
.venv/bin/python -m unittest discover tests
```

## Escucharlo en el celular

**Para leer mientras escuchás:** abrí https://the-heimdallr.github.io/radio-tecno/ en el navegador
del celular y tocá «📖 Escuchar leyendo el texto». Se puede agregar a la pantalla de inicio
(menú del navegador → Agregar a pantalla principal).

**Como podcast:**

1. Instalá **AntennaPod** (gratis, de código abierto; F-Droid o Play Store).
2. **Agregar podcast → Agregar podcast por dirección RSS**:
   `https://the-heimdallr.github.io/radio-tecno/feed.xml`
3. En la configuración del podcast, dejá **Descarga automática** apagada: con el botón ▶ se escucha
   por streaming, sin ocupar memoria.

## Ideas para seguir experimentando

- Sumar un feed nuevo en `feeds.toml` y ver el resultado con `--dry-run`.
- Cambiar las voces o la velocidad del inglés en `feeds.toml` (`edge-tts --list-voices`; siempre de mujer).
- Agregar una música de entrada (pegar un MP3 corto al principio, con el mismo formato: 24 kHz mono).
- Leer el resumen de cada noticia de la página original cuando el feed trae poco texto.
