# Full-Stack Run Guide

This project now supports:
- Model workflow in Jupyter notebook (`model_training.ipynb`)
- JavaScript backend API in `backend/`
- Vite + React frontend in `frontend/`

## 1) Train or refresh model artifacts in notebook
1. Open `model_training.ipynb`.
2. Run all cells.
3. Confirm `model/movies.pkl`, `model/knn_model.pkl`, and `model/tfidf_matrix.pkl` are updated.

## 2) Install dependencies
From the workspace root:

```powershell
npm install
npm --prefix backend install
npm --prefix frontend install
```

## 3) Run backend + frontend together
From the workspace root:

```powershell
npm run dev
```

- Backend: `http://localhost:4000`
- Frontend: `http://localhost:5173`

## 4) Useful API endpoints
- `POST /api/auth/register` with JSON body: `{ "username": "demo", "password": "demo1234" }`
- `POST /api/auth/login` with JSON body: `{ "username": "demo", "password": "demo1234" }`
- `GET /api/auth/me` with header: `Authorization: Bearer <token>`
- `GET /api/health`
- `GET /api/popular`
- `GET /api/personalized` (requires bearer token)
- `POST /api/recommend` with JSON body: `{ "movie_name": "Interstellar", "top_n": 18 }`
- `GET /api/autocomplete?q=inter`
- `GET /api/watched` (requires bearer token)
- `POST /api/watch` with JSON body: `{ "title": "Interstellar (2014)" }` (requires bearer token)
- `POST /api/unwatch` with JSON body: `{ "title": "Interstellar (2014)" }` (requires bearer token)

## 5) Production-readiness added
- JWT auth and user accounts (stored in `backend/data/users.json`)
- Per-user watch history (stored in `backend/data/watch_history.json`)
- API response caching for recommendation-heavy routes
- Rate limiting on `/api/*` and stricter limits on `/api/auth/*`

## 6) Optional: run services separately
```powershell
npm run dev:backend
npm run dev:frontend
```

## 7) Build frontend for production
```powershell
npm run build
```
