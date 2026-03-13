import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import time

st.set_page_config(page_title="Spotify Finder", layout="centered")
st.title("🎵 Spotify Finder")

# 1. Zugriff auf die Secrets
try:
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]
except Exception:
    st.error("Fehler: Secrets nicht gefunden! Hast du sie in den Streamlit-Einstellungen eingetragen?")
    st.stop()

# 2. Authentifizierungs-Setup
auth_manager = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope="playlist-read-private user-library-read",
    show_dialog=True
)

query_params = st.query_params

# Falls kein "code" in der URL ist -> Login zeigen
if "code" not in query_params:
    auth_url = auth_manager.get_authorize_url()
    st.info("Willkommen! Bitte melde dich zuerst bei Spotify an.")
    st.link_button("Mit Spotify verbinden", auth_url, type="primary")
else:
    # 1. Token extrahieren
    if 'access_token' not in st.session_state:
        try:
            code = query_params["code"]
            token_info = auth_manager.get_access_token(code)
            st.session_state.access_token = token_info['access_token']
            st.success("✅ Token erhalten!")
        except Exception as e:
            st.error(f"Login fehlgeschlagen: {e}")
            st.stop()

    token = st.session_state.access_token
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Schritt 1: Katalog laden (mit Geduld-Logik)
    st.write("### Schritt 1: Bibliothek erfassen")
    
    if 'all_playlists' not in st.session_state:
        if st.button("Katalog mit Geduld laden"):
            all_p = []
            url = "https://api.spotify.com/v1/me/playlists?limit=50"
            
            with st.status("Verbinde mit Spotify...", expanded=True) as status:
                try:
                    while url:
                        response = requests.get(url, headers=headers, timeout=10)
                        
                        if response.status_code == 200:
                            data = response.json()
                            all_p.extend(data['items'])
                            url = data.get('next')
                            status.write(f"✅ {len(all_p)} Playlists gefunden...")
                            time.sleep(0.3) # Kurze Pause zur Sicherheit
                        elif response.status_code == 429:
                            wait_time = int(response.headers.get("Retry-After", 30))
                            status.write(f"⏳ Rate Limit! Pause für {wait_time} Sek...")
                            time.sleep(wait_time + 1)
                        else:
                            st.error(f"Fehler {response.status_code}: {response.text}")
                            st.stop()
                    
                    st.session_state.all_playlists = all_p
                    status.update(label="Katalog fertig!", state="complete")
                    st.rerun()
                except Exception as e:
                    st.error(f"Netzwerk-Fehler: {e}")
        st.stop()

    # 3. Schritt 2: Sichtbarer Scan
    if 'all_songs' not in st.session_state:
        st.write(f"✅ {len(st.session_state.all_playlists)} Playlists gefunden.")
        
        if st.button("🚀 Jetzt Songs scannen"):
            all_songs = []
            progress_bar = st.progress(0)
            playlist_name_display = st.empty()
            counter_display = st.empty()
            
            total = len(st.session_state.all_playlists)
            
            for i, pl in enumerate(st.session_state.all_playlists):
                current_num = i + 1
                playlist_name_display.markdown(f"Aktuelle Playlist: **{pl['name']}**")
                counter_display.info(f"Fortschritt: {current_num} von {total}")
                progress_bar.progress(current_num / total)
                
                # Request für Songs dieser Playlist
                pl_url = f"https://api.spotify.com/v1/playlists/{pl['id']}/tracks?limit=100&fields=items(track(name,external_urls,artists(name))),next"
                
                while pl_url:
                    res = requests.get(pl_url, headers=headers, timeout=10)
                    
                    if res.status_code == 200:
                        data = res.json()
                        for item in data.get('items', []):
                            t = item.get('track')
                            if t:
                                all_songs.append({
                                    "Song": t['name'], 
                                    "Artists": ", ".join([a['name'] for a in t['artists']]), 
                                    "Playlist": pl['name'],
                                    "Link": t['external_urls']['spotify']
                                })
                        pl_url = data.get('next')
                        time.sleep(0.1) # Minimale Pause zwischen Song-Paketen
                    elif res.status_code == 429:
                        wait = int(res.headers.get("Retry-After", 30))
                        counter_display.warning(f"⏳ Rate Limit! Warte {wait}s...")
                        time.sleep(wait + 1)
                    else:
                        pl_url = None # Fehler -> Diese Playlist abbrechen
                
            st.session_state.all_songs = all_songs
            st.success(f"✅ Scan abgeschlossen! {len(all_songs)} Songs gefunden.")
            st.rerun()
        st.stop()

    # 4. Schritt: Die Suche
    st.write("### 🔍 Künstler suchen")
    artist_query = st.text_input("Name eingeben (z.B. Queen):").strip().lower()

    if artist_query:
        matches = [s for s in st.session_state.all_songs if artist_query in s['Artists'].lower()]
        if matches:
            st.write(f"Gefundene Songs: {len(matches)}")
            st.dataframe(matches, use_container_width=True, hide_index=True, column_config={
                "Link": st.column_config.LinkColumn("In Spotify öffnen")
            })
        else:
            st.warning("Kein Treffer in deiner Bibliothek.")

    if st.button("🗑️ Daten löschen / Neu scannen"):
        st.session_state.clear()
        st.rerun()
