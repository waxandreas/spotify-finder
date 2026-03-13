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
    # 1. AUTHENTIFIZIERUNG (Nur einmal pro Sitzung)
    if 'sp' not in st.session_state:
        try:
            code = query_params["code"]
            token_info = auth_manager.get_access_token(code)
            st.session_state.sp = spotipy.Spotify(auth=token_info['access_token'])
            st.success("✅ Authentifizierung erfolgreich!")
        except Exception as e:
            st.error("Login-Fehler. Bitte Seite neu laden.")
            st.stop()

    sp = st.session_state.sp

    # 2. PLAYLISTS LADEN (Nur auf Knopfdruck!)
    if 'all_playlists' not in st.session_state:
        st.info("Klicke auf den Button, um deine Playlist-Übersicht zu laden.")
        if st.button("📁 Playlist-Verzeichnis abrufen"):
            with st.status("Kontaktiere Spotify...") as status:
                try:
                    results = sp.current_user_playlists(limit=50)
                    all_p = results['items']
                    while results['next']:
                        results = sp.next(results)
                        all_p.extend(results['items'])
                    st.session_state.all_playlists = all_p
                    status.update(label=f"Fertig! {len(all_p)} Playlists gefunden.", state="complete")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler beim Abrufen: {e}")
        st.stop() # Hier stoppen, bis Playlists geladen sind

    # 3. SCAN STARTEN
    if 'all_songs' not in st.session_state:
        st.success(f"Gefunden: {len(st.session_state.all_playlists)} Playlists.")
        if st.button("🚀 Jetzt alle Songs tiefenscannen (Dauert ca. 1-2 Min)"):
            all_songs = []
            prog = st.progress(0)
            status_msg = st.empty()
            
            for i, pl in enumerate(st.session_state.all_playlists):
                status_msg.text(f"Scanne ({i+1}/{len(st.session_state.all_playlists)}): {pl['name']}")
                try:
                    # Wir holen nur die ersten 100 Tracks pro Playlist für den Speed-Test
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
                prog.progress((i + 1) / len(st.session_state.all_playlists))
            
            st.session_state.all_songs = all_songs
            status_msg.success(f"Scan abgeschlossen! {len(all_songs)} Songs bereit.")
            st.rerun()
        st.stop()

    # 4. SUCHE (Wird erst angezeigt, wenn alles geladen ist)
    st.write("### 🔍 Suche in deiner Bibliothek")
    artist_query = st.text_input("Künstler-Name eingeben:").strip().lower()

    if artist_query:
        matches = [s for s in st.session_state.all_songs if artist_query in s['Artists'].lower()]
        if matches:
            st.dataframe(matches, use_container_width=True)
        else:
            st.warning("Keine Treffer gefunden.")

    if st.button("🔄 Alles zurücksetzen"):
        st.session_state.clear()
        st.rerun()
