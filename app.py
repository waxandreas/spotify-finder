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

        # Funktion zum Laden ALLER Daten (wird gecached)
        @st.cache_data(show_spinner=False, ttl=3600)
        def get_all_user_data(_sp):
            all_songs = []
            seen_track_ids = set() # Verhindert, dass wir denselben Song 10x laden
            
            # 1. Alle Playlists auf einmal holen (Limit 50)
            playlists = []
            results = _sp.current_user_playlists(limit=50)
            playlists.extend(results['items'])
            while results['next']:
                results = _sp.next(results)
                playlists.extend(results['items'])
            
            # Fortschrittsbalken in Streamlit
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, pl in enumerate(playlists):
                # Update Fortschritt
                percent = int((i + 1) / len(playlists) * 100)
                progress_bar.progress(percent)
                status_text.text(f"Scanne Playlist {i+1}/{len(playlists)}: {pl['name']}")
                
                try:
                    # WICHTIG: Wir holen NUR die Track-ID und den Namen, um Zeit zu sparen
                    # Wir nutzen playlist_items statt next-Paging innerhalb der Playlist für Speed
                    offset = 0
                    while True:
                        res = _sp.playlist_items(
                            pl['id'], 
                            offset=offset, 
                            limit=100, 
                            fields='items(track(id, name, external_urls, artists(name))), next'
                        )
                        
                        for item in res['items']:
                            track = item.get('track')
                            if not track or not track.get('id'): continue
                            
                            # Nur hinzufügen, wenn wir den Song in DIESER Playlist noch nicht haben
                            # (Oder global nicht haben, falls du Dubletten gar nicht willst)
                            track_key = f"{track['id']}-{pl['id']}" 
                            if track_key not in seen_track_ids:
                                all_songs.append({
                                    "Song": track['name'],
                                    "Artists": [a['name'] for a in track['artists']],
                                    "Link": track['external_urls']['spotify'],
                                    "Playlist": pl['name']
                                })
                                seen_track_ids.add(track_key)
                        
                        if not res['next'] or offset > 500: # Sicherheit: Max 500 Songs pro Playlist
                            break
                        offset += 100
                        
                except Exception as e:
                    continue # Bei Fehler (z.B. 403) zur nächsten Playlist
            
            progress_bar.empty()
            status_text.empty()
            return all_songs

        # --- Such-Interface ---
        st.write("---")
        if st.button("🚀 Musik-Bibliothek scannen / aktualisieren"):
            st.cache_data.clear() # Ermöglicht manuelles Refresh
            st.rerun()

        # Daten laden (beim ersten Mal langsam, danach blitzschnell)
        with st.spinner("Lade deine Playlists in den Zwischenspeicher (nur beim ersten Mal)..."):
            cached_songs = get_all_user_data(sp)
        
        st.success(f"{len(cached_songs)} Songs aus {len(set(s['Playlist'] for s in cached_songs))} Playlists bereit zum Durchsuchen!")

        artist_query = st.text_input("Welchen Künstler suchst du?", placeholder="z.B. Queen").strip()

        if artist_query:
            # Die eigentliche Suche passiert jetzt nur noch im lokalen Speicher (extrem schnell)
            query = artist_query.lower()
            results = [
                s for s in cached_songs 
                if any(query in a.lower() for a in s['Artists'])
            ]
            
            if results:
                st.write(f"### Gefundene Songs ({len(results)})")
                st.dataframe(
                    results,
                    column_config={"Link": st.column_config.LinkColumn("Anhören")},
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.warning("Keine Treffer.")
                    
    except Exception as e:
        st.error("🚨 Ein Fehler ist aufgetreten:")
        st.exception(e) # Das zeigt uns den VOLLSTÄNDIGEN Fehlercode an
        if st.button("Sitzung zurücksetzen"):
            st.query_params.clear()
            st.rerun()
