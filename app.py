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
    # 3. Token abrufen und Spotify-Client starten
    try:
        code = query_params["code"]
        token_info = auth_manager.get_access_token(code)
        sp = spotipy.Spotify(auth=token_info['access_token'])
        st.success("✅ Verbunden!")

        # Suchmaske
        artist_query = st.text_input("Welchen Künstler suchst du?", placeholder="z.B. Queen").strip()

        if artist_query:
            found_tracks = []
            
            with st.status("Durchsuche deine Bibliothek...", expanded=True) as status:
                # 1. Alle Playlists des Nutzers abrufen (Paging für Playlists)
                all_playlists = []
                results = sp.current_user_playlists(limit=50)
                all_playlists.extend(results['items'])
                while results['next']:
                    results = sp.next(results)
                    all_playlists.extend(results['items'])
                
                status.write(f"{len(all_playlists)} Playlists gefunden. Starte Tiefensuche...")

                # 2. Jede Playlist einzeln durchsuchen
                for pl in all_playlists:
                    try:
                        pl_name = pl['name']
                        pl_id = pl['id']
                        
                        # Paging für Tracks innerhalb der Playlist
                        track_results = sp.playlist_items(pl_id, fields='items(track(name, external_urls, artists)), next')
                        
                        while track_results:
                            for item in track_results['items']:
                                track = item.get('track')
                                if not track: continue
                                
                                # Prüfen, ob der Künstler im Track vorkommt
                                artists = [a['name'].lower() for a in track['artists']]
                                if artist_query.lower() in artists:
                                    found_tracks.append({
                                        "Song": track['name'],
                                        "Playlist": pl_name,
                                        "Link": track['external_urls']['spotify']
                                    })
                            
                            # Nächste Seite der Playlist laden, falls vorhanden
                            if track_results['next']:
                                track_results = sp.next(track_results)
                            else:
                                track_results = None
                                
                    except spotipy.exceptions.SpotifyException as e:
                        # 403 Fehler (Forbidden) einfach überspringen
                        if e.http_status == 403:
                            status.write(f"⚠️ Überspringe '{pl['name']}' (Kein Zugriff)")
                            continue
                        else:
                            status.write(f"❌ Fehler bei '{pl['name']}': {e}")
                
                status.update(label="Suche beendet!", state="complete", expanded=False)

            # 3. Ergebnisse anzeigen
            if found_tracks:
                st.write(f"### 🎵 Gefundene Songs ({len(found_tracks)})")
                
                # Tabelle mit Klick-Links
                st.dataframe(
                    found_tracks,
                    column_config={
                        "Link": st.column_config.LinkColumn("In Spotify öffnen")
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.warning(f"Keine Songs von '{artist_query}' in deinen Playlists gefunden.")
                    
    except Exception as e:
        st.error("🚨 Ein Fehler ist aufgetreten:")
        st.exception(e) # Das zeigt uns den VOLLSTÄNDIGEN Fehlercode an
        if st.button("Sitzung zurücksetzen"):
            st.query_params.clear()
            st.rerun()
