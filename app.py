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
        sp = spotipy.Spotify(auth=token_info['access_token'], requests_timeout=10)

        # 1. Playlists SCHNELL laden (ohne Paging-Schleife als Test)
        st.write("### 🔍 Scan-Zentrale")
        
        if "all_playlists" not in st.session_state:
            with st.status("Suche Playlists...", expanded=True) as status:
                try:
                    # Wir holen erst mal nur die ersten 50, um zu sehen, ob es geht
                    results = sp.current_user_playlists(limit=50)
                    all_p = results['items']
                    
                    # Falls mehr da sind, holen wir den Rest schnell nach
                    while results['next'] and len(all_p) < 200: # Sicherheitslimit 200
                        results = sp.next(results)
                        all_p.extend(results['items'])
                        status.write(f"{len(all_p)} Playlists gefunden...")
                    
                    st.session_state.all_playlists = all_p
                    status.update(label="✅ Playlists geladen!", state="complete")
                    st.rerun()
                except Exception as e:
                    st.error(f"Spotify antwortet nicht schnell genug: {e}")
                    st.stop()

        # 2. Wenn Playlists da sind, zeige den Scan-Button
        if "all_playlists" in st.session_state and "all_songs" not in st.session_state:
            p_list = st.session_state.all_playlists
            st.success(f"Bereit! {len(p_list)} Playlists im Verzeichnis.")
            
            if st.button(f"🚀 Jetzt alle {len(p_list)} Playlists nach Songs scannen"):
                all_songs = []
                prog = st.progress(0)
                info = st.empty()
                
                # Wir scannen jetzt nur die ersten 100 Songs pro Playlist für Speed
                for i, pl in enumerate(p_list):
                    info.text(f"Scanne: {pl['name']}")
                    try:
                        # Direkter Abruf ohne Paging innerhalb der Playlist für den ersten Test
                        res = sp.playlist_items(pl['id'], limit=100, fields='items(track(name, external_urls, artists(name)))')
                        for item in res['items']:
                            t = item.get('track')
                            if t:
                                all_songs.append({
                                    "Song": t['name'], 
                                    "Artists": ", ".join([a['name'] for a in t['artists']]), 
                                    "Playlist": pl['name'],
                                    "Link": t['external_urls']['spotify']
                                })
                    except:
                        continue
                    prog.progress((i + 1) / len(p_list))
                
                st.session_state.all_songs = all_songs
                st.rerun()

        # 3. Suchmaske
        if "all_songs" in st.session_state:
            st.success(f"Scan fertig! {len(st.session_state.all_songs)} Songs gefunden.")
            query = st.text_input("Künstler suchen:").lower()
            if query:
                res = [s for s in st.session_state.all_songs if query in s['Artists'].lower()]
                st.dataframe(res, use_container_width=True)
            
            if st.button("🗑️ App zurücksetzen"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.cache_data.clear()
                st.rerun()

    except Exception as e:
        st.error("Ein Fehler ist aufgetreten")
        st.exception(e)
        if st.button("Sitzung zurücksetzen"):
            st.query_params.clear()
            st.rerun()
