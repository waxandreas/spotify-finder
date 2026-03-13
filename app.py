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
        @st.cache_data(show_spinner=False, ttl=3600)  # Speichert Daten für 1 Stunde
        def get_all_user_data(_sp):
            all_data = []
            playlists = []
            
            # 1. Alle Playlists laden
            results = _sp.current_user_playlists(limit=50)
            playlists.extend(results['items'])
            while results['next']:
                results = _sp.next(results)
                playlists.extend(results['items'])
            
            # 2. Tracks für jede Playlist laden
            for pl in playlists:
                try:
                    pl_tracks = []
                    # Wir holen nur die nötigsten Felder, um die Antwort klein zu halten
                    results = _sp.playlist_items(
                        pl['id'], 
                        fields='items(track(name, external_urls, artists(name))), next'
                    )
                    
                    while results:
                        for item in results['items']:
                            if item.get('track'):
                                track = item['track']
                                pl_tracks.append({
                                    "Song": track['name'],
                                    "Artists": [a['name'] for a in track['artists']],
                                    "Link": track['external_urls']['spotify'],
                                    "Playlist": pl['name']
                                })
                        results = _sp.next(results) if results['next'] else None
                    
                    all_data.extend(pl_tracks)
                except Exception:
                    continue # Playlists ohne Zugriff überspringen
            return all_data

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
