import pickle
import streamlit as st
import requests
import pandas as pd
import ast
import urllib.parse
from datetime import datetime

# TMDB API Key
TMDB_API_KEY = "8265bd1679663a7ea12ac168da84d2e8"

# Load datasets
movies_df = pd.read_csv("model/movies.csv")
credits_df = pd.read_csv("model/credits.csv")
movies_df = movies_df.merge(credits_df, on="title", how="left")

# Extract genres
def extract_genres(genre_str):
    try:
        genre_list = ast.literal_eval(genre_str)
        return [genre["name"] for genre in genre_list]
    except (ValueError, SyntaxError):
        return []

movies_df["genres"] = movies_df["genres"].apply(extract_genres)
movies_df["genres"] = movies_df["genres"].apply(lambda x: ", ".join(x) if isinstance(x, list) else "")

# Fetch movie poster and trailer
def fetch_movie_details(movie_title):
    try:
        encoded_title = urllib.parse.quote(movie_title)
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={encoded_title}"
        response = requests.get(search_url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("results"):
            movie_id = data["results"][0].get("id")
            if movie_id:
                return fetch_poster_and_trailer_by_id(movie_id)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching movie details: {e}")
    return "https://via.placeholder.com/500x750?text=No+Image", None

# Fetch poster and trailer by movie ID
def fetch_poster_and_trailer_by_id(movie_id):
    try:
        details_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=videos"
        response = requests.get(details_url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        poster_path = data.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500/{poster_path}" if poster_path else "https://via.placeholder.com/500x750?text=No+Image"
        
        trailer_url = None
        for video in data.get("videos", {}).get("results", []):
            if video["type"] == "Trailer" and video["site"] == "YouTube":
                trailer_url = f"https://www.youtube.com/watch?v={video['key']}"
                break
        
        return poster_url, trailer_url
    except requests.exceptions.RequestException as e:
        print(f"Error fetching poster and trailer by ID: {e}")
    return "https://via.placeholder.com/500x750?text=No+Image", None

# Load model
db_movies = pickle.load(open('model/movie_list.pkl', 'rb'))
similarity = pickle.load(open('model/similarity.pkl', 'rb'))

# Extract unique genres
unique_genres = ["All"] + sorted(set(
    genre for sublist in movies_df["genres"].dropna().astype(str).str.split(", ") for genre in sublist
))

# Generate real-time greeting
def get_greeting():
    current_hour = datetime.now().hour
    if current_hour < 12:
        return "Good Morning! ☀️"
    elif current_hour < 18:
        return "Good Afternoon! 🌤️"
    else:
        return "Good Evening! 🌙"

# Recommend movies
def recommend(movie, num_recommendations):
    recommended_names, recommended_posters, recommended_trailers = [], [], []
    
    if movie:
        index = db_movies[db_movies["title"] == movie].index[0]
        distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
        
        for i in distances[:num_recommendations]:
            movie_title = db_movies.iloc[i[0]].title
            poster, trailer = fetch_movie_details(movie_title)
            recommended_names.append(movie_title)
            recommended_posters.append(poster)
            recommended_trailers.append(trailer)
    
    return recommended_names, recommended_posters, recommended_trailers

# Streamlit UI
st.markdown(
    f"""
    <h1 style='text-align: center;'>🎬 Movie Recommender System</h1>
    <h3 style='text-align: center;'>{get_greeting()}</h3>
    <h4 style='text-align: center;'>🔥 Get movie recommendations with their trailers!</h4>
    """,
    unsafe_allow_html=True
)


search_type = st.radio("Search by:", ("Movie Name", "Genre"))
num_recommendations = st.slider("Number of recommendations:", min_value=1, max_value=10, value=5)

if search_type == "Movie Name":
    selected_movie = st.selectbox("Select a movie", db_movies["title"].values)
    if st.button("🎥 Show Recommendation"):
        names, posters, trailers = recommend(selected_movie, num_recommendations)
        
        if names:
            st.subheader("Recommended Movies:")
            cols = st.columns(len(names))
            for col, name, poster, trailer in zip(cols, names, posters, trailers):
                with col:
                    st.image(poster, use_container_width=True)
                    st.markdown(f"**{name}**")
                    if trailer:
                        st.markdown(f"[🎬 Watch Trailer]({trailer})", unsafe_allow_html=True)
        else:
            st.warning("No recommendations found. Try another movie.")

elif search_type == "Genre":
    selected_genre = st.selectbox("Select Genre", unique_genres)
    
    if st.button("🎥 Show Recommendation"):
        filtered_movies = movies_df[movies_df["genres"].str.contains(selected_genre, na=False)]
        
        if not filtered_movies.empty:
            sampled_movies = filtered_movies.sample(min(num_recommendations, len(filtered_movies)))
            names, posters, trailers = [], [], []
            
            for title in sampled_movies["title"].values:
                poster, trailer = fetch_movie_details(title)
                names.append(title)
                posters.append(poster)
                trailers.append(trailer)
            
            st.subheader("Recommended Movies:")
            cols = st.columns(len(names))
            for col, name, poster, trailer in zip(cols, names, posters, trailers):
                with col:
                    st.image(poster, use_container_width=True)
                    st.markdown(f"**{name}**")
                    if trailer:
                        st.markdown(f"[🎬 Watch Trailer]({trailer})", unsafe_allow_html=True)
        else:
            st.warning("No movies found for this genre. Try another genre.")
