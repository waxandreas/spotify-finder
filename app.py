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

        # Funktion für Tracks bleibt gecached (spart Zeit bei Wiederholung)
        @st.cache_data(ttl=3600)
        def get_tracks_cached(_sp, pl_id, pl_name):
            tracks = []
            res = _sp.playlist_items(pl_id, limit=100, fields='items(track(id, name, external_urls, artists(name))), next')
            for item in res['items']:
                t = item.get('track')
                if t:
                    tracks.append({"Song": t['name'], "Artists": [a['name'] for a in t['artists']], "Link": t['external_urls']['spotify'], "Playlist": pl_name})
            return tracks

        st.write("---")
        
        # 1. Playlists laden OHNE Cache, damit wir sehen was passiert
        with st.status("Verbinde mit Spotify und lade Playlist-Verzeichnis...", expanded=True) as status:
            all_playlists = []
            results = sp.current_user_playlists(limit=50)
            all_playlists.extend(results['items'])
            while results['next']:
                status.write(f"Bereits {len(all_playlists)} Playlists gefunden...")
                results = sp.next(results)
                all_playlists.extend(results['items'])
            status.update(label=f"✅ {len(all_playlists)} Playlists geladen!", state="complete")

        # 2. Der eigentliche Scan
        if "all_songs" not in st.session_state:
            if st.button(f"🔍 Scan starten ({len(all_playlists)} Playlists durchsuchen)"):
                all_songs = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, pl in enumerate(all_playlists):
                    status_text.text(f"Lese Playlist {i+1}/{len(all_playlists)}: {pl['name']}")
                    try:
                        songs = get_tracks_cached(sp, pl['id'], pl['name'])
                        all_songs.extend(songs)
                    except:
                        continue
                    progress_bar.progress((i + 1) / len(all_playlists))
                
                st.session_state.all_songs = all_songs
                status_text.success(f"Fertig! {len(all_songs)} Songs im Speicher.")
                st.rerun()

        # 3. Suchmaske (nur wenn Daten da sind)
        if "all_songs" in st.session_state:
            artist_query = st.text_input("Künstler suchen:", placeholder="z.B. Queen")
            if artist_query:
                q = artist_query.lower()
                results = [s for s in st.session_state.all_songs if any(q in a.lower() for a in s['Artists'])]
                st.dataframe(results, use_container_width=True)
                
            if st.button("🗑️ Cache löschen & neu scannen"):
                del st.session_state.all_songs
                st.cache_data.clear()
                st.rerun()

    except Exception as e:
        st.error("Fehler beim Laden")
        st.exception(e)
        if st.button("Sitzung zurücksetzen"):
            st.query_params.clear()
            st.rerun()
