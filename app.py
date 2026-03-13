import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth

st.set_page_config(page_title="Spotify Finder", layout="centered")
st.title("🎵 Spotify Finder")

# 1. Zugriff auf die Secrets (müssen in Streamlit Cloud hinterlegt sein)
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

# NEU: Der moderne Weg, um URL-Parameter in Streamlit abzugreifen
query_params = st.query_params

# Falls kein "code" in der URL ist -> Login zeigen
if "code" not in query_params:
    auth_url = auth_manager.get_authorize_url()
    st.info("Willkommen! Bitte melde dich zuerst bei Spotify an.")
    
    # Dieser Button öffnet den Link automatisch korrekt
    st.link_button("Mit Spotify verbinden", auth_url, type="primary")
else:
    try:
        code = query_params["code"]
        token_info = auth_manager.get_access_token(code)
        sp = spotipy.Spotify(auth=token_info['access_token'])

        # 1. Funktion zum Laden der Playlist-LISTE (geht schnell)
        @st.cache_data(ttl=3600)
        def get_playlist_list(_sp):
            playlists = []
            results = _sp.current_user_playlists(limit=50)
            playlists.extend(results['items'])
            while results['next']:
                results = _sp.next(results)
                playlists.extend(results['items'])
            return playlists

        # 2. Funktion zum Laden der TRACKS einer einzelnen Playlist (wird einzeln gecached)
        @st.cache_data(ttl=3600)
        def get_tracks_from_playlist(_sp, playlist_id, playlist_name):
            tracks = []
            offset = 0
            while True:
                res = _sp.playlist_items(
                    playlist_id, 
                    offset=offset, 
                    limit=100, 
                    fields='items(track(id, name, external_urls, artists(name))), next'
                )
                for item in res['items']:
                    track = item.get('track')
                    if track and track.get('id'):
                        tracks.append({
                            "Song": track['name'],
                            "Artists": [a['name'] for a in track['artists']],
                            "Link": track['external_urls']['spotify'],
                            "Playlist": playlist_name
                        })
                if not res['next'] or offset > 500: break
                offset += 100
            return tracks

        # --- UI Logik ---
        st.write("---")
        
        all_playlists = get_playlist_list(sp)
        
        # Initialisiere den Speicher für alle Songs
        all_cached_songs = []
        
        # Button zum Starten/Aktualisieren
        if "data_loaded" not in st.session_state:
            st.session_state.data_loaded = False

        if not st.session_state.data_loaded:
            if st.button("🚀 Suche starten: Alle 143 Playlists scannen"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, pl in enumerate(all_playlists):
                    status_text.text(f"Scanne {i+1}/{len(all_playlists)}: {pl['name']}")
                    # Tracks laden (einzeln gecached)
                    playlist_songs = get_tracks_from_playlist(sp, pl['id'], pl['name'])
                    all_cached_songs.extend(playlist_songs)
                    progress_bar.progress((i + 1) / len(all_playlists))
                
                st.session_state.all_songs = all_cached_songs
                st.session_state.data_loaded = True
                st.rerun()
        else:
            # Wenn Daten bereits geladen sind
            if st.button("🔄 Bibliothek neu scannen"):
                st.cache_data.clear()
                st.session_state.data_loaded = False
                st.rerun()

            artist_query = st.text_input("Welchen Künstler suchst du?", placeholder="z.B. Queen").strip()

            if artist_query:
                query = artist_query.lower()
                # Suche in den Session State Daten
                results = [
                    s for s in st.session_state.all_songs 
                    if any(query in a.lower() for a in s['Artists'])
                ]
                
                if results:
                    st.write(f"### Gefundene Songs ({len(results)})")
                    st.dataframe(results, hide_index=True, use_container_width=True)
                else:
                    st.warning("Keine Treffer.")

    except Exception as e:
        st.error("🚨 Ein Fehler ist aufgetreten:")
        st.exception(e)
        if st.button("Sitzung zurücksetzen"):
            st.query_params.clear()
            st.rerun()
