BASE_WEB_URL = "http://localhost:3000/"


class POSTGRES:
    user = "postgres"
    password = "postgres password"
    host = "localhost"
    port = 5432
    name = "Sketyl"
    uri = f"postgres://{user}:{password}@{host}:{port}/{name}"


class SPOTIFY:
    client_id = "go to spotify dev portal and get"
    client_secret = "dito"
    redirect_uri = BASE_WEB_URL + "spotify/connect"  # Add this as redirect uri
