# Radio Tecno

Un podcast diario de noticias de programación, IA, Python, Linux y repos de GitHub, armado
con Python. Lee los feeds RSS de `feeds.toml`, elige las noticias nuevas y las pasa a voz
con [edge-tts](https://github.com/rany2/edge-tts): voz de mujer en español para las fuentes
en castellano y voz de mujer en inglés para las demás.

- **No usa IA ni claves:** lee el título y la bajada que trae cada fuente.
- **No llena el celular:** se escucha por streaming desde AntennaPod y el sitio guarda solo los
  últimos 7 episodios (unos 1 a 4 MB cada uno).
- **No usa la PC:** GitHub Actions lo arma todos los días a las 06:00 (hora de Argentina) y lo
  publica en GitHub Pages.

## Cómo está hecho

| Archivo | Qué hace |
|---------|----------|
| `feeds.toml` | Configuración: fuentes por sección, voces y topes. Para cambiar las noticias, se toca solo esto |
| `radio/feeds.py` | Baja los feeds y lee RSS 2.0 y Atom con `urllib` y `xml.etree` (librería estándar) |
| `radio/guion.py` | Elige las noticias (últimas 36 h, sin repetir) y arma el guion en segmentos con su idioma |
| `radio/voz.py` | Pasa cada segmento a MP3 con edge-tts (`asyncio`) y los pega en un solo archivo |
| `radio/podcast.py` | Guarda el episodio, borra los viejos y escribe `feed.xml` (podcast) e `index.html` |
| `radio/__main__.py` | El programa: `python -m radio` |
| `.github/workflows/episodio.yml` | La corrida diaria en GitHub y la publicación en la rama `gh-pages` |

## Usarlo en la PC

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m radio --dry-run        # muestra el guion, sin audio
.venv/bin/python -m radio                  # arma publico/episodios/AAAA-MM-DD.mp3
.venv/bin/python -m http.server -d publico # escucharlo en http://localhost:8000
.venv/bin/python -m unittest discover tests
```

## Escucharlo en el celular

1. Instalá **AntennaPod** (gratis, de código abierto; F-Droid o Play Store).
2. **Agregar podcast → Agregar podcast por dirección RSS**:
   `https://the-heimdallr.github.io/radio-tecno/feed.xml`
3. En la configuración del podcast, dejá **Descarga automática** apagada: con el botón ▶ se escucha
   por streaming, sin ocupar memoria.

## Ideas para seguir experimentando

- Sumar un feed nuevo en `feeds.toml` y ver el resultado con `--dry-run`.
- Cambiar las voces (`edge-tts --list-voices`; siempre de mujer).
- Agregar una música de entrada (pegar un MP3 corto al principio, con el mismo formato: 24 kHz mono).
- Leer el resumen de cada noticia de la página original cuando el feed trae poco texto.
