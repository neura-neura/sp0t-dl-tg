# sp0t-dl-tg

Bot de Telegram en Python para buscar contenido musical, procesar enlaces de Spotify y usar enlaces de YouTube Music como entrada de busqueda. El bot trabaja por polling, responde en chats privados y tambien puede operar en grupos cuando se le menciona.

> Uso responsable: este proyecto debe usarse solo con cuentas, archivos, sesiones y contenido para los que tengas autorizacion. No incluyas tokens, cookies, archivos de dispositivo ni datos personales en el repositorio.

## Que hace

- Recibe enlaces de Spotify de tracks, albums y playlists.
- Permite buscar con `/search` canciones, albums y playlists.
- Detecta enlaces de YouTube Music y los convierte en una busqueda equivalente.
- Presenta resultados con botones inline de Telegram.
- Procesa canciones una por una y las envia al chat como audio.
- Agrega metadatos ID3 al archivo final, incluyendo titulo, artista, album, fecha, copyright y portada.
- Limpia archivos temporales al terminar cada operacion.

## Estructura del proyecto

```text
.
|-- script.py            # Bot principal y logica de busqueda/procesamiento
|-- requirements.txt     # Dependencias Python
|-- .env.example         # Plantilla para variables de entorno
|-- .gitignore           # Archivos locales/sensibles excluidos del repo
```

Archivos locales esperados en ejecucion:

```text
.env                    # Token del bot de Telegram
cookies.txt             # Cookies locales de sesion, no versionar
device.wvd              # Archivo de dispositivo Widevine, no versionar
temp/                   # Carpeta temporal generada por el script
```

## Requisitos

- Python 3.10 o superior.
- Una cuenta de Telegram y un bot creado con BotFather.
- Una cuenta compatible con el flujo usado por el proyecto.
- `ffmpeg` disponible en el `PATH`.
- `mp4decrypt` disponible en el `PATH`.
- Los archivos locales requeridos por tu entorno de ejecucion:
  - `cookies.txt`
  - `device.wvd`

El proyecto no incluye tokens, cookies, dispositivos, sesiones ni credenciales. Esos archivos deben mantenerse fuera del control de versiones.

## Instalacion

1. Clona el repositorio:

```bash
git clone <url-del-repo>
cd sp0t-dl-tg
```

2. Crea y activa un entorno virtual:

```bash
python -m venv venv
```

En Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

En macOS/Linux:

```bash
source venv/bin/activate
```

3. Instala dependencias:

```bash
pip install -r requirements.txt
```

4. Verifica que las herramientas externas esten disponibles:

```bash
ffmpeg -version
mp4decrypt --version
```

Si alguno de esos comandos no existe, instala la herramienta correspondiente y agregala al `PATH`.

## Configuracion

1. Copia la plantilla de entorno:

```bash
cp .env.example .env
```

En Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Edita `.env` y agrega el token del bot:

```env
TELEGRAM_BOT_TOKEN=tu_token_de_telegram
```

3. Coloca los archivos privados requeridos en la raiz del proyecto:

```text
cookies.txt
device.wvd
```

No subas estos archivos al repositorio. Ya estan contemplados en `.gitignore`.

## Ejecucion

Con el entorno virtual activo:

```bash
python script.py
```

Si todo esta configurado correctamente, veras mensajes de inicializacion en consola y el bot empezara a escuchar updates mediante polling.

## Uso en Telegram

### Buscar contenido

Envia:

```text
/search nombre de cancion o album
```

El bot mostrara botones inline con resultados de tracks, albums y playlists. Al tocar un resultado, empezara el procesamiento.

### Enviar un enlace de Spotify

Puedes enviar enlaces de:

```text
https://open.spotify.com/track/...
https://open.spotify.com/album/...
https://open.spotify.com/playlist/...
```

El bot detecta el tipo de enlace y procesa el contenido correspondiente.

### Enviar un enlace de YouTube Music

Puedes enviar un enlace de `music.youtube.com`. El bot extrae informacion del enlace con `yt-dlp` y la usa como termino de busqueda en Spotify.

### Uso en grupos

En chats que no sean privados, el bot solo responde si se le menciona. El nombre de usuario esperado esta definido en `script.py` dentro de `handle_message`:

```python
bot_username = 'sp0tdl_bot'
```

Si tu bot usa otro username, actualiza ese valor.

## Variables y rutas importantes

En `script.py` se definen estas rutas:

```python
mp4decrypt_path = "mp4decrypt"
ffmpeg_path = "ffmpeg"
wvd_path = base_dir / "device.wvd"
cookies_path = base_dir / "cookies.txt"
temp_dir = base_dir / "temp"
```

Si `ffmpeg` o `mp4decrypt` no estan en el `PATH`, puedes cambiar esas variables por rutas absolutas locales. Evita subir rutas personales al repositorio si contienen nombres de usuario o informacion privada.

## Seguridad

No versionar:

- `.env`
- `cookies.txt`
- `device.wvd`
- logs con respuestas de APIs, tokens o informacion de cuenta
- archivos temporales descargados o procesados

Buenas practicas:

- Usa un token de bot dedicado para este proyecto.
- Revoca y rota el token si alguna vez se expone.
- No compartas cookies ni archivos de dispositivo.
- Manten el bot en un entorno privado o controlado.
- Revisa permisos y politicas de las plataformas que uses con el bot.

## Solucion de problemas

### `TELEGRAM_BOT_TOKEN not defined`

El archivo `.env` no existe, no tiene la variable correcta o el entorno no esta cargando la configuracion.

Verifica:

```env
TELEGRAM_BOT_TOKEN=tu_token_de_telegram
```

### `ffmpeg` o `mp4decrypt` no se reconoce

La herramienta no esta instalada o no esta en el `PATH`.

Prueba:

```bash
ffmpeg -version
mp4decrypt --version
```

### `Account is not premium. Cannot proceed.`

El script valido el tipo de cuenta y detuvo el proceso porque no cumple el requisito esperado por el flujo.

### Errores de busqueda o respuestas inesperadas

Puede deberse a cambios en respuestas de APIs, rate limits, cookies vencidas o contenido no disponible para la cuenta/region.

### Timeouts al enviar audio

El script reintenta envios con backoff. Si el problema persiste, revisa la conectividad del servidor, el tamano del archivo y los limites vigentes de Telegram.

## Dependencias principales

- `python-telegram-bot`: integracion con Telegram.
- `requests`: llamadas HTTP.
- `yt-dlp`: extraccion y descarga de medios.
- `mutagen`: escritura de tags ID3.
- `pywidevine`: manejo de licencia/dispositivo en el flujo existente.
- `python-dotenv`: carga de variables desde `.env`.

## Despliegue

El bot usa polling, asi que no requiere webhook publico. Puede ejecutarse en:

- una PC local,
- un VPS,
- un contenedor,
- un servicio que mantenga procesos Python activos.

Recomendaciones para despliegue:

- Mantener `.env`, `cookies.txt` y `device.wvd` como secretos del entorno.
- Ejecutar con un usuario sin privilegios administrativos.
- Usar logs rotados si se corre 24/7.
- Reiniciar automaticamente el proceso con `systemd`, Docker, PM2 o el supervisor que uses.
- Asegurar que `ffmpeg` y `mp4decrypt` existan dentro del entorno de despliegue.

## Mantenimiento

Despues de actualizar dependencias o mover el proyecto:

```bash
pip install -r requirements.txt --upgrade
python script.py
```

Si cambias el username del bot, recuerda actualizar `bot_username` para que las menciones en grupos funcionen.

## Licencia

No se incluye una licencia en este repositorio. Agrega una antes de distribuir el proyecto si quieres definir permisos de uso, copia o modificacion.
