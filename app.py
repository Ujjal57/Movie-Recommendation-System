from flask import Flask, render_template, request, jsonify
import pickle, pandas as pd, ast, requests, urllib.parse
from datetime import datetime

app = Flask(__name__)

TMDB_API_KEY = "8265bd1679663a7ea12ac168da84d2e8"

# Load data
movies_df = pd.read_csv("model/movies.csv")
credits_df = pd.read_csv("model/credits.csv")
movies_df = movies_df.merge(credits_df, on="title", how="left")

def extract_genres(genre_str):
    try:
        return [genre["name"] for genre in ast.literal_eval(genre_str)]
    except:
        return []

movies_df["genres"] = movies_df["genres"].apply(extract_genres)
movies_df["genres"] = movies_df["genres"].apply(lambda x: ", ".join(x) if isinstance(x, list) else "")

db_movies = pickle.load(open("model/movie_list.pkl", "rb"))
similarity = pickle.load(open("model/similarity.pkl", "rb"))

def get_greeting():
    hour = datetime.now().hour
    return "Good Morning ☀️" if hour < 12 else "Good Afternoon 🌤️" if hour < 18 else "Good Evening 🌙"

def fetch_movie_details(movie_title):
    encoded = urllib.parse.quote(movie_title)
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={encoded}"
    try:
        res = requests.get(url).json()
        if res["results"]:
            movie_id = res["results"][0]["id"]
            return fetch_poster_and_trailer_by_id(movie_id)
    except:
        pass
    return "https://via.placeholder.com/500x750?text=No+Image", None

def fetch_poster_and_trailer_by_id(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=videos"
    try:
        res = requests.get(url).json()
        poster_path = res.get("poster_path")
        poster = f"https://image.tmdb.org/t/p/w500/{poster_path}" if poster_path else "https://via.placeholder.com/500x750?text=No+Image"
        trailer = None
        for vid in res["videos"]["results"]:
            if vid["type"] == "Trailer" and vid["site"] == "YouTube":
                trailer = f"https://www.youtube.com/watch?v={vid['key']}"
                break
        return poster, trailer
    except:
        return "https://via.placeholder.com/500x750?text=No+Image", None

@app.route('/')
def home():
    genres = sorted(set(g for gs in movies_df["genres"].dropna().str.split(", ") for g in gs))
    return render_template('index.html', greeting=get_greeting(), movies=list(db_movies['title']), genres=genres)

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    movie = data.get('movie')
    num = int(data.get('num'))
    index = db_movies[db_movies['title'] == movie].index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
    
    results = []
    for i in distances[:num]:
        title = db_movies.iloc[i[0]].title
        poster, trailer = fetch_movie_details(title)
        results.append({'title': title, 'poster': poster, 'trailer': trailer})
    return jsonify(results)

@app.route('/genre', methods=['POST'])
def genre():
    data = request.json
    genre = data.get('genre')
    num = int(data.get('num'))
    filtered = movies_df[movies_df['genres'].str.contains(genre, na=False)]
    sampled = filtered.sample(min(num, len(filtered)))
    
    results = []
    for title in sampled["title"]:
        poster, trailer = fetch_movie_details(title)
        results.append({'title': title, 'poster': poster, 'trailer': trailer})
    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)
