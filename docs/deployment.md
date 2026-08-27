# Deployment

## Backend: Render

Create a Render Web Service from this repository. Render uses `render.yaml`. Set real `MONGODB_URI`, `GROQ_API_KEY`, and `CORS_ORIGINS` values in Render environment settings. The API start command is `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

## Frontend: Vercel

Import the same repository, set Root Directory to `frontend`, and set `VITE_API_URL` to the deployed Render API URL. Once Vercel gives you a public URL, add that URL to the backend `CORS_ORIGINS` setting and redeploy the backend.

Secrets belong only in Render environment variables and local `backend/.env`. Never place database, JWT, or Groq secrets in any Vercel `VITE_` variable.
