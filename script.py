import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.request import HTTPXRequest
from telegram.error import BadRequest, TimedOut
import asyncio
import os
import shutil
import tempfile
import json
import traceback
import time
from http.cookiejar import MozillaCookieJar
import requests
import math
import hmac
import hashlib
from mutagen.id3 import ID3, TIT2, TPE1, TPE2, TALB, TRCK, TPOS, TDRC, COMM, TCOP, APIC
import subprocess
import yt_dlp
from pathlib import Path
from pywidevine import PSSH, Cdm, Device
import re
from dotenv import load_dotenv

# Configuraciones de paths (igual al script original)
mp4decrypt_path = "mp4decrypt"  # Debe estar en PATH
ffmpeg_path = "ffmpeg"  # Debe estar en PATH
base_dir = Path(__file__).parent.resolve()
wvd_path = base_dir / "device.wvd"
cookies_path = base_dir / "cookies.txt"
temp_dir = base_dir / "temp"
temp_dir.mkdir(exist_ok=True)

class TOTP:
    def __init__(self) -> None:
        self.secret = b'376136387538459893883312310911992847112448894410210511297108'
        self.version = 61
        self.period = 30
        self.digits = 6

    def generate(self, timestamp: int) -> str:
        counter = math.floor(timestamp / 1000 / self.period)
        counter_bytes = counter.to_bytes(8, byteorder="big")
        h = hmac.new(self.secret, counter_bytes, hashlib.sha1)
        hmac_result = h.digest()
        offset = hmac_result[-1] & 0x0F
        binary = (
            (hmac_result[offset] & 0x7F) << 24
            | (hmac_result[offset + 1] & 0xFF) << 16
            | (hmac_result[offset + 2] & 0xFF) << 8
            | (hmac_result[offset + 3] & 0xFF)
        )
        return str(binary % (10 ** self.digits)).zfill(self.digits)

class SpotifyClient:
    def __init__(self):
        self.session = requests.Session()
        self.clienttoken = None
        self.get_session()

    def get_session(self):
        totp = TOTP()
        if cookies_path.exists():
            cookies = MozillaCookieJar(str(cookies_path))
            cookies.load(ignore_discard=True, ignore_expires=True)
            self.session.cookies.update(cookies)
            for cookie in cookies:
                if cookie.name == "sp_t":
                    headerssp_t = {
                        "accept": "application/json",
                        "content-type": "application/json",
                        "origin": "https://open.spotify.com/",
                        "referer": "https://open.spotify.com/",
                        "user-agent": "Mozilla/5.0",
                        "spotify-app-version": "1.2.72.240.gf5884949",
                        "app-platform": "WebPlayer",
                        "cookie": f"sp_t={cookie.value};"
                    }
                    server_time = int(time.time() * 1000)
                    generated_totp = totp.generate(server_time)
                    session_info = requests.get(
                        "https://open.spotify.com/api/token",
                        params={
                            "reason": "init",
                            "productType": "web-player",
                            "totp": generated_totp,
                            "totpServer": generated_totp,
                            "totpVer": str(totp.version)
                        },
                        headers=headerssp_t,
                        timeout=9999
                    ).json()
                    response = requests.post(
                        "https://clienttoken.spotify.com/v1/clienttoken",
                        json={
                            "client_data": {
                                "client_version": "1.2.72.240.gf5884949",
                                "client_id": session_info["clientId"],
                                "js_sdk_data": {
                                    "device_id": cookie.value,
                                    "device_type": "computer"
                                }
                            }
                        },
                        headers=headerssp_t,
                        timeout=9999
                    )
                    self.clienttoken = response.json()["granted_token"]["token"]
        self.session.headers.update({
            "accept": "application/json",
            "content-type": "application/json",
            "origin": "https://open.spotify.com/",
            "referer": "https://open.spotify.com/",
            "user-agent": "Mozilla/5.0",
            "spotify-app-version": "1.2.72.240.gf5884949",
            "app-platform": "WebPlayer",
        })
        server_time = int(time.time() * 1000)
        generated_totp = totp.generate(server_time)
        session_info = self.session.get(
            "https://open.spotify.com/api/token",
            params={
                "reason": "init",
                "productType": "web-player",
                "totp": generated_totp,
                "totpServer": generated_totp,
                "totpVer": str(totp.version)
            },
            timeout=9999
        ).json()
        self.session.headers.update({
            "authorization": f"Bearer {session_info['accessToken']}",
            "client-token": self.clienttoken
        })

    def get_track(self, track_id: str) -> dict:
        url = "https://api-partner.spotify.com/pathfinder/v2/query"
        payload = {
            "variables": {
                "uri": f"spotify:track:{track_id}"
            },
            "operationName": "getTrack",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "612585ae06ba435ad26369870deaae23b5c8800a256cd8a57e08eddc25a37294"
                }
            }
        }
        response = self.session.post(url, json=payload, timeout=9999)
        return response.json()

    def get_album(self, album_id: str) -> dict:
        url = "https://api-partner.spotify.com/pathfinder/v2/query"
        payload = {
            "variables": {
                "uri": f"spotify:album:{album_id}",
                "offset": 0,
                "limit": 300
            },
            "operationName": "queryAlbumTracks",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "3ea563e1d68f486d8df30f69de9dcedae74c77e684b889ba7408c589d30f7f2e"
                }
            }
        }
        response = self.session.post(url, json=payload, timeout=9999)
        response = response.json()
        album_data = response['data']['album']
        tracks = [item['track']['uri'].split(':')[-1] for item in album_data['tracks']['items'] if 'track' in item and 'uri' in item['track']]
        artist_name = ''
        album_name = ''
        if tracks:
            first_track_tags = self.get_tags(tracks[0])
            artist_name = first_track_tags['artist']
            album_name = first_track_tags['album']
        return {
            'artist': artist_name,
            'album': album_name,
            'tracks': tracks
        }

    def get_playlist(self, playlist_id: str) -> dict:
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        tracks = []
        offset = 0
        limit = 100
        name = ''
        while True:
            payload = {
                "variables": {
                    "uri": f"spotify:playlist:{playlist_id}",
                    "offset": offset,
                    "limit": limit
                },
                "operationName": "fetchPlaylist",
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "91d4c2bc3e0cd1bc672281c4f1f59f43ff55ba726ca04a45810d99bd091f3f0e"
                    }
                }
            }
            response = self.session.post(url, json=payload, timeout=9999)
            try:
                json_response = response.json()
            except json.JSONDecodeError:
                print("[ERROR] Playlist API response not JSON:")
                print(response.text)
                raise ValueError("Playlist API response not JSON")
            if 'errors' in json_response:
                print("[ERROR] Playlist API errors:")
                print(json.dumps(json_response['errors']))
                raise ValueError(f"Playlist API returned errors: {json_response['errors']}")
            if 'data' not in json_response or 'playlistV2' not in json_response['data']:
                raise ValueError("Unexpected response structure")
            playlist_data = json_response['data']['playlistV2']
            if playlist_data.get('__typename') == 'NotFound':
                raise ValueError("Playlist not found or not accessible")
            if offset == 0:
                name = playlist_data.get('name', 'Unknown Playlist')
            items = playlist_data.get('content', {}).get('items', [])
            for item in items:
                item_v2 = item.get('itemV2')
                if item_v2 and item_v2.get('__typename') == 'TrackResponseWrapper':
                    track_data = item_v2.get('data')
                    if track_data and track_data.get('__typename') == 'Track' and 'uri' in track_data:
                        track_id = track_data['uri'].split(':')[-1]
                        tracks.append(track_id)
            total_count = playlist_data.get('content', {}).get('totalCount', 0)
            if offset + limit >= total_count:
                break
            offset += limit
            time.sleep(1)
        if not name:
            name = f"Playlist_{playlist_id}"
        return {
            'name': name,
            'tracks': tracks
        }

    def search(self, query, limit=10):
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = {
            "operationName": "searchDesktop",
            "variables": {
                "searchTerm": query,
                "offset": 0,
                "limit": limit,
                "numberOfTopResults": 5,
                "includeAudiobooks": False
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "75bbf6bfcfdf85b8fc828417bfad92b7cd66bf7f556d85670f4da8292373ebec"
                }
            }
        }
        response = self.session.post(url, json=payload, timeout=9999)
        if response.status_code == 429:
            raise ValueError("API rate limit exceeded. Try again later.")
        if response.status_code != 200:
            raise ValueError(f"Search API error: {response.text}")
        try:
            return response.json()
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in search response")

    def get_tags(self, track_id):
        album = self.get_track(track_id)
        track = album['data']['trackUnion']
        album_data = track['albumOfTrack']
        try:
            copyright = next(
                i['text']
                for i in album_data['copyright']['items']
                if i['type'] in ('P', 'C')
            )
        except StopIteration:
            copyright = ''
        date_info = album_data['date']
        if date_info['precision'] == 'YEAR':
            release_date = f"{date_info['year']}-01-01"
        else:
            release_date = date_info['isoString'][:10]
        total_tracks = album_data['tracks']['totalCount']
        total_discs = 1
        artist_name = track['firstArtist']['items'][0]['profile']['name']
        cover_url = max(
            album_data['coverArt']['sources'],
            key=lambda x: x['width']
        )['url']
        cover_data = requests.get(cover_url, timeout=9999).content
        tags = {
            'title': track['name'],
            'artist': artist_name,
            'album_artist': artist_name,
            'album': album_data['name'],
            'track_num': track.get('trackNumber', 1),
            'total_tracks': total_tracks,
            'disc_num': 1,
            'total_discs': total_discs,
            'date': f'{release_date}T00:00:00Z'[:4],
            'comment': '',
            'copyright': copyright,
            'cover_data': cover_data
        }
        return tags

    def audio_extracted(self, track_id):
        metamp4 = self.session.get(f'https://gue1-spclient.spotify.com/track-playback/v1/media/spotify:track:{track_id}?manifestFileFormat=file_ids_mp4', timeout=9999).json()
        bitrate_files = [
            (f.get("bitrate"), f["file_id"])
            for track in metamp4["media"].values()
            for files in track["item"]["manifest"].values()
            if isinstance(files, list)
            for f in files
            if isinstance(f, dict) and "bitrate" in f and f.get("bitrate")
        ]
        if not bitrate_files:
            raise ValueError("No audio files found")
        max_bitrate, file_id = max(bitrate_files)
        return file_id

    def get_sanizated_string(self, dirty_string, is_folder):
        for character in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ';']:
            dirty_string = dirty_string.replace(character, '_')
        if is_folder:
            dirty_string = dirty_string[:40]
            if dirty_string[-1:] == '.':
                dirty_string = dirty_string[:-1] + '_'
        else:
            dirty_string = dirty_string[:80]
        return dirty_string.strip()

    def get_final_location(self, tags, output_dir):
        artist = tags['artist']
        title = tags['title']
        base_name = f"{artist} - {title}"
        sanitized = self.get_sanizated_string(base_name, is_folder=False)
        return output_dir / f"{sanitized}.mp3"

    def get_pssh(self, file_id):
        url = f'https://seektables.scdn.co/seektable/{file_id}.json'
        response = requests.get(url, timeout=9999)
        if response.status_code != 200:
            raise ValueError(f"Failed to get seektable: status {response.status_code}")
        try:
            data = response.json()
            return data['pssh']
        except json.JSONDecodeError:
            raise

    def accountAttributes(self):
        url = "https://api-partner.spotify.com/pathfinder/v2/query"
        payload = {
            "variables": {},
            "operationName": "accountAttributes",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "24aaa3057b69fa91492de26841ad199bd0b330ca95817b7a4d6715150de01827"
                }
            }
        }
        response = self.session.post(url, json=payload, timeout=9999)
        account = response.json()['data']['me']['account']['product']
        country = response.json()['data']['me']['account']['country']
        url = "https://api-partner.spotify.com/pathfinder/v2/query"
        payload = {
            "variables": {},
            "operationName": "profileAttributes",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "53bcb064f6cd18c23f752bc324a791194d20df612d8e1239c735144ab0399ced"
                }
            }
        }
        response = self.session.post(url, json=payload, timeout=9999)
        UserName = response.json()['data']['me']['profile']['username']
        mode = 'Country: ' + country + '\n' + 'Account: ' + account + '\n' + 'UserName: ' + UserName + '\n'
        return mode, account

    def get_decryption_keys(self, pssh, wvd):
        cdm = Cdm.from_device(Device.load(wvd))
        cdm_session = cdm.open()
        pssh = PSSH(pssh)
        challenge = cdm.get_license_challenge(cdm_session, pssh)
        license = self.session.post("https://gue1-spclient.spotify.com/widevine-license/v1/audio/license", challenge, timeout=9999).content
        cdm.parse_license(cdm_session, license)
        return f'1:{next(i for i in cdm.get_keys(cdm_session) if i.type == "CONTENT").key.hex()}'

    def get_stream_url(self, file_id):
        final = self.session.get(
            f'https://gue1-spclient.spotify.com/storage-resolve/v2/files/audio/interactive/11/{file_id}?version=10000000&product=9&platform=39&alt=json', timeout=9999).json()[
            'cdnurl'][0]
        return final

    def decrypt(self, keys, encrypted_location, decrypted_location):
        subprocess.run(
            [
                mp4decrypt_path,
                str(encrypted_location),
                '--key',
                keys,
                str(decrypted_location)
            ],
            check=True,
            timeout=9999
        )

    def download(self, encrypted_location, stream_url):
        with yt_dlp.YoutubeDL({
            'quiet': True,
            'no_warnings': True,
            'no_progress': True,
            'outtmpl': str(encrypted_location),
            'allow_unplayable_formats': True,
            'fixup': 'never',
            'overwrites': False,
            'socket_timeout': 9999
        }) as ydl:
            ydl.download(stream_url)

    def get_encrypted_location(self, track_id, temp_dir):
        return temp_dir / f'{track_id}_encrypted.mp4'

    def get_decrypted_location(self, track_id, temp_dir):
        return temp_dir / f'{track_id}_decrypted.mp4'

    def get_fixed_location(self, track_id, temp_dir):
        return temp_dir / f'{track_id}_fixed.mp3'

    def fixup(self, decrypted_location, fixed_location):
        subprocess.run(
            [
                ffmpeg_path,
                '-loglevel',
                'error',
                '-y',
                '-i',
                str(decrypted_location),
                '-c:a',
                'libmp3lame',
                '-b:a',
                '320k',
                str(fixed_location)
            ],
            check=True,
            timeout=9999
        )

    def make_final(self, fixed_location, final_location, tags):
        shutil.copy(fixed_location, final_location)
        audio = ID3(str(final_location))
        audio.delete()
        audio.add(TIT2(encoding=3, text=tags['title']))
        audio.add(TPE1(encoding=3, text=tags['artist']))
        audio.add(TPE2(encoding=3, text=tags['album_artist']))
        audio.add(TALB(encoding=3, text=tags['album']))
        audio.add(TRCK(encoding=3, text=f"{tags['track_num']}/{tags['total_tracks']}"))
        audio.add(TPOS(encoding=3, text=f"{tags['disc_num']}/{tags['total_discs']}"))
        audio.add(TDRC(encoding=3, text=tags['date']))
        audio.add(COMM(encoding=3, lang='eng', desc='', text=tags['comment']))
        audio.add(TCOP(encoding=3, text=tags['copyright']))
        audio.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=tags['cover_data']))
        audio.save(v1=2)

    async def start(self, track_id, wvd, temp_dir, bot, chat_id, status_message_id, current=1, total=1):
        try:
            tags = self.get_tags(track_id)
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text=f"Descargando {tags['artist']} - {tags['title']} ({current}/{total})...")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    pass
                else:
                    raise e
            print(f"[INFO] Starting download for track ID: {track_id} ({current}/{total})")
            final_location = self.get_final_location(tags, temp_dir)
            try:
                file_id = self.audio_extracted(track_id)
            except ValueError as e:
                if "No audio files found" in str(e):
                    await bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text=f"Skipping track {track_id}: No audio files available")
                    print(f"[INFO] Skipping track {track_id}: No audio files available")
                    return True
                else:
                    raise e
            pssh = self.get_pssh(file_id)
            decryption_keys = self.get_decryption_keys(pssh, wvd)
            stream_url = self.get_stream_url(file_id)
            encrypted_location = self.get_encrypted_location(track_id, temp_dir)
            print(f"[INFO] Downloading encrypted file for {track_id}")
            self.download(encrypted_location, stream_url)
            decrypted_location = self.get_decrypted_location(track_id, temp_dir)
            print(f"[INFO] Decrypting file for {track_id}")
            self.decrypt(decryption_keys, encrypted_location, decrypted_location)
            fixed_location = self.get_fixed_location(track_id, temp_dir)
            print(f"[INFO] Fixing up audio for {track_id}")
            self.fixup(decrypted_location, fixed_location)
            print(f"[INFO] Applying tags and finalizing MP3 for {track_id}")
            self.make_final(fixed_location, final_location, tags)
            os.remove(str(encrypted_location))
            os.remove(str(decrypted_location))
            os.remove(str(fixed_location))
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text=f"Enviando {tags['artist']} - {tags['title']} ({current}/{total})...")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    pass
                else:
                    raise e
            print(f"[INFO] Sending audio file for {track_id}")
            retries = 5
            backoff = 5
            for attempt in range(retries):
                try:
                    with open(final_location, 'rb') as audio_file:
                        await bot.send_audio(
                            chat_id=chat_id,
                            audio=audio_file,
                            title=tags['title'],
                            performer=tags['artist'],
                            read_timeout=9999,
                            write_timeout=9999,
                            connect_timeout=9999,
                            pool_timeout=9999
                        )
                    break
                except TimedOut:
                    print(f"[WARNING] Upload timeout for {track_id}, retry {attempt + 1}/{retries}")
                    await asyncio.sleep(backoff)
                    backoff *= 2
            else:
                raise TimedOut("Max retries reached for upload")
            os.remove(str(final_location))
            print(f"[INFO] Download and send completed for {track_id}")
            await asyncio.sleep(2)  # Delay between tracks
            return True
        except Exception as e:
            print(f"[ERROR] For track: {track_id}")
            print(f"Error details: {e}")
            print("Traceback:")
            print(traceback.format_exc())
            await bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text=f"Error: {str(e)}")
            return False

def extract_spotify_track_id(url):
    return url.split("/track/")[1].split("?")[0] if url and "/track/" in url else False

def extract_spotify_album_id(url):
    return url.split("/album/")[1].split("?")[0] if url and "/album/" in url else False

def extract_spotify_playlist_id(url):
    return url.split("/playlist/")[1].split("?")[0] if url and "/playlist/" in url else False

def is_youtube_music_link(text):
    return "music.youtube.com" in text

def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    for url in urls:
        if "music.youtube.com" in url:
            return url
    return None

async def extract_youtube_music_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if 'entries' in info:
        # Playlist or album
        first_entry = info['entries'][0] if info['entries'] else None
        if first_entry and 'album' in first_entry:
            # Assume album
            artist = first_entry.get('artist') or info.get('uploader', 'Unknown Artist')
            album = first_entry['album']
            return f"{artist} {album} album"
        else:
            # Playlist
            name = info.get('title', 'Unknown Playlist')
            return f"{name} playlist"
    else:
        # Single track
        artist = info.get('artist') or info.get('uploader', 'Unknown Artist')
        track = info.get('track') or info.get('title', 'Unknown Track')
        return f"{artist} {track}"

async def handle_message(update, context):
    if update.message is None:
        return
    if update.message.chat.type != 'private':
        bot_username = 'sp0tdl_bot'
        mentioned = any(
            entity.type == telegram.constants.MessageEntityType.MENTION and
            update.message.text[entity.offset:entity.offset + entity.length] == f'@{bot_username}'
            for entity in update.message.entities
        )
        if not mentioned:
            return
    message = update.message.text
    chat_id = update.message.chat_id
    print(f"[INFO] Received message: {message}")
    spotify = SpotifyClient()
    wvd = wvd_path
    mode, account_type = spotify.accountAttributes()
    if account_type.lower() != 'premium':
        await update.message.reply_text("Account is not premium. Cannot proceed.")
        print("[WARNING] Account is not premium. Aborting process.")
        return
    status_message = await update.message.reply_text("Buscando...")
    status_message_id = status_message.message_id
    print("[INFO] Sent status: Buscando...")
    success = True
    if is_youtube_music_link(message):
        print(f"[INFO] Processing YouTube Music link: {message}")
        url = extract_url(message)
        if url:
            try:
                query = await extract_youtube_music_info(url)
                context.args = query.split()
                await search_command(update, context, status_message_id=status_message_id)
                return  # Salir después de manejar la búsqueda
            except Exception as e:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text=f"Error processing YouTube Music link: {str(e)}")
                print(f"[ERROR] YouTube Music processing failed: {str(e)}")
                print("Traceback:")
                print(traceback.format_exc())
                success = False
        else:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text="No valid YouTube Music URL found.")
            success = False
    track_id = extract_spotify_track_id(message)
    if track_id:
        print(f"[INFO] Processing track ID: {track_id}")
        success = await spotify.start(track_id, wvd, temp_dir, context.bot, chat_id, status_message_id, current=1, total=1)
    album_id = extract_spotify_album_id(message)
    if album_id:
        print(f"[INFO] Processing album ID: {album_id}")
        try:
            album_info = spotify.get_album(album_id)
            total_tracks = len(album_info['tracks'])
            for i, t_id in enumerate(album_info['tracks'], 1):
                if not await spotify.start(t_id, wvd, temp_dir, context.bot, chat_id, status_message_id, i, total_tracks):
                    success = False
        except Exception as e:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text=f"Error: {str(e)}")
            print(f"[ERROR] Album processing failed: {str(e)}")
            print("Traceback:")
            print(traceback.format_exc())
            success = False
    playlist_id = extract_spotify_playlist_id(message)
    if playlist_id:
        print(f"[INFO] Processing playlist ID: {playlist_id}")
        try:
            playlist_info = spotify.get_playlist(playlist_id)
            total_tracks = len(playlist_info['tracks'])
            for i, t_id in enumerate(playlist_info['tracks'], 1):
                if not await spotify.start(t_id, wvd, temp_dir, context.bot, chat_id, status_message_id, i, total_tracks):
                    success = False
        except Exception as e:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text=f"Error: {str(e)}")
            print(f"[ERROR] Playlist processing failed: {str(e)}")
            print("Traceback:")
            print(traceback.format_exc())
            success = False
    if success:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text="Enviando...")
        print("[INFO] Updated status: Enviando...")
        await context.bot.delete_message(chat_id=chat_id, message_id=status_message_id)
        print("[INFO] Deleted status message. Process completed.")
    # Clean up temp directory
    for file in temp_dir.glob('*'):
        file.unlink()

async def search_command(update, context, status_message_id=None):
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text("Please provide search terms after /search.")
        print("[WARNING] No search query provided.")
        return
    print(f"[INFO] Received search command with query: {query}")
    spotify = SpotifyClient()
    chat_id = update.message.chat_id
    if status_message_id is None:
        status_message = await update.message.reply_text("Buscando...")
        status_message_id = status_message.message_id
        print("[INFO] Sent status: Buscando...")
    try:
        search_results = spotify.search(query, limit=10)
        keyboard = []
        tracks_list = []
        albums_list = []
        playlists_list = []
        if 'data' in search_results and 'search' in search_results['data']:
            search_data = search_results['data']['search']
            for type_key in ['tracks', 'albums', 'playlists']:
                if type_key in search_data:
                    items = search_data[type_key].get('items', [])
                    for item in items:
                        if type_key == 'tracks':
                            track = item.get('track', {})
                            name = track.get('name')
                            artist = track.get('artists', {}).get('items', [{}])[0].get('profile', {}).get('name', 'Unknown Artist')
                            uri = track.get('uri')
                            if uri and name:
                                tracks_list.append({'name': name, 'artist': artist, 'uri': uri})
                        elif type_key == 'albums':
                            name = item.get('name')
                            artist = item.get('artists', {}).get('items', [{}])[0].get('profile', {}).get('name', 'Unknown Artist')
                            uri = item.get('uri')
                            if uri and name:
                                albums_list.append({'name': name, 'artist': artist, 'uri': uri})
                        elif type_key == 'playlists':
                            name = item.get('name')
                            owner = item.get('owner', {}).get('data', {}).get('name', 'Unknown Owner') if 'data' in item.get('owner', {}) else 'Unknown Owner'
                            uri = item.get('uri')
                            if uri and name:
                                playlists_list.append({'name': name, 'owner': owner, 'uri': uri})
        # Botones para tracks 1-4
        for i in range(1, 5):
            if i <= len(tracks_list):
                track = tracks_list[i-1]
                label = f"Track: {track['name']} by {track['artist']}"
                data = json.dumps({'type': 'track', 'id': track['uri'].split(':')[2]})
                keyboard.append([InlineKeyboardButton(label, callback_data=data)])
            else:
                label = f"Track: No result"
                keyboard.append([InlineKeyboardButton(label, callback_data='none')])
        # Botones para albums 5-8
        for i in range(5, 9):
            if i - 4 <= len(albums_list):
                album = albums_list[i-5]
                album_info = spotify.get_album(album['uri'].split(':')[2])
                track_count = len(album_info['tracks'])
                label = f"Album: {album['name']} by {album['artist']} ({track_count} tracks)"
                data = json.dumps({'type': 'album', 'id': album['uri'].split(':')[2]})
                keyboard.append([InlineKeyboardButton(label, callback_data=data)])
            else:
                label = f"Album: No result"
                keyboard.append([InlineKeyboardButton(label, callback_data='none')])
        # Botones para playlists 9-10
        for i in range(9, 11):
            if i - 8 <= len(playlists_list):
                playlist = playlists_list[i-9]
                playlist_info = spotify.get_playlist(playlist['uri'].split(':')[2])
                track_count = len(playlist_info['tracks'])
                label = f"Playlist: {playlist['name']} by {playlist['owner']} ({track_count} tracks)"
                data = json.dumps({'type': 'playlist', 'id': playlist['uri'].split(':')[2]})
                keyboard.append([InlineKeyboardButton(label, callback_data=data)])
            else:
                label = f"Playlist: No result"
                keyboard.append([InlineKeyboardButton(label, callback_data='none')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text="Select an item:", reply_markup=reply_markup)
        print("[INFO] Presented search results with inline buttons.")
    except Exception as e:
        print("[ERROR] Search failed:")
        print(f"Error details: {e}")
        print("Traceback:")
        print(traceback.format_exc())
        await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message_id, text=f"Error: {str(e)}")

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = json.loads(query.data) if query.data != 'none' else None
    if data is None:
        await query.delete_message()
        print("[INFO] No selection made; deleted message.")
        return
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    print(f"[INFO] Received button callback: {data}")
    spotify = SpotifyClient()
    wvd = wvd_path
    mode, account_type = spotify.accountAttributes()
    if account_type.lower() != 'premium':
        await query.edit_message_text(text="Account is not premium. Cannot proceed.")
        print("[WARNING] Account is not premium. Aborting process.")
        return
    await query.edit_message_text(text="Buscando...")
    print("[INFO] Updated status: Buscando...")
    success = True
    if data['type'] == 'track':
        success = await spotify.start(data['id'], wvd, temp_dir, context.bot, chat_id, message_id, current=1, total=1)
    elif data['type'] == 'album':
        try:
            album_info = spotify.get_album(data['id'])
            total_tracks = len(album_info['tracks'])
            for i, t_id in enumerate(album_info['tracks'], 1):
                if not await spotify.start(t_id, wvd, temp_dir, context.bot, chat_id, message_id, i, total_tracks):
                    success = False
        except Exception as e:
            await query.edit_message_text(text=f"Error: {str(e)}")
            print(f"[ERROR] Album processing failed: {str(e)}")
            print("Traceback:")
            print(traceback.format_exc())
            success = False
    elif data['type'] == 'playlist':
        try:
            playlist_info = spotify.get_playlist(data['id'])
            total_tracks = len(playlist_info['tracks'])
            for i, t_id in enumerate(playlist_info['tracks'], 1):
                if not await spotify.start(t_id, wvd, temp_dir, context.bot, chat_id, message_id, i, total_tracks):
                    success = False
        except Exception as e:
            await query.edit_message_text(text=f"Error: {str(e)}")
            print(f"[ERROR] Playlist processing failed: {str(e)}")
            print("Traceback:")
            print(traceback.format_exc())
            success = False
    if success:
        await query.edit_message_text(text="Enviando...")
        print("[INFO] Updated status: Enviando...")
    await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    print("[INFO] Deleted status message. Process completed.")
    # Clean up temp directory
    for file in temp_dir.glob('*'):
        file.unlink()

async def set_bot_commands(application):
    commands = [
        telegram.BotCommand("search", "Search for songs, albums, or playlists")
    ]
    await application.bot.set_my_commands(commands)

def main():
    print("[INFO] Initializing bot with token...")
    load_dotenv()  # read .env
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("[INFO] TELEGRAM_BOT_TOKEN not defined in environment variables.")
    
    request = HTTPXRequest(
        read_timeout=9999,
        write_timeout=9999,
        connect_timeout=9999,
        pool_timeout=9999
    )
    application = Application.builder().token(token).request(request).build()
    print("[INFO] Adding handlers...")
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.post_init = set_bot_commands
    print("[INFO] Starting polling... Bot is now listening for updates.")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()