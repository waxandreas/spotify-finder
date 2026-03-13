import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os

st.set_page_config(page_title="Spotify Artist Finder")
st.title("🎵 Artist Playlist Finder")

# Login-Bereich
# WICHTIG: Die Keys holen wir uns später aus den "Secrets"
client_id = st.secrets["SPOTIPY_CLIENT_ID"]
client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]

auth_manager = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope="playlist-read-private",
    open_browser=False # Wichtig für Web-Server!
)

# Authentifizierungs-Link anzeigen
auth_url = auth_manager.get_authorize_url()
st.sidebar.markdown(f'[In Spotify einloggen]({auth_url})')

# URL-Parameter abfangen (nach dem Login)
query_params = st.experimental_get_query_params()
if "code" in query_params:
    token = auth_manager.get_access_token(query_params["code"])
    sp = spotipy.Spotify(auth=token["access_token"])
    
    artist_name = st.text_input("Welchen Künstler suchst du?")
    
    if artist_name and st.button("Suchen"):
        with st.spinner('Durchsuche Playlists...'):
            # Hier die Logik von oben einfügen (Playlists loopen)
            # ... (gekürzt zur Übersicht)
            st.success(f"Suche abgeschlossen für {artist_name}!")
else:
    st.info("Bitte klicke links auf den Login-Link, um zu starten.")
