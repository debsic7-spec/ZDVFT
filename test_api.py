import pytest
import pandas as pd
from fastapi.testclient import TestClient
from unittest.mock import patch

# Importe l'application FastAPI depuis ton fichier serveur
from backend.server import app

# TestClient simule un navigateur qui requête ton API en mémoire
client = TestClient(app)

def test_health_endpoint():
    """Vérifie que l'API démarre et répond à la route de santé."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "cache_entries" in response.json()

def test_market_status():
    """Vérifie que la route des statuts du marché fonctionne."""
    response = client.get("/api/market-status")
    assert response.status_code == 200
    assert "open" in response.json()

def test_invalid_asset():
    """Vérifie que l'API gère bien un ISIN inconnu (Erreur 404)."""
    response = client.get("/api/asset/FAKE_ISIN")
    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"

@patch("backend.server.yf.Ticker")
def test_valid_asset(mock_ticker):
    """Vérifie la génération des données d'un actif en mockant Yahoo Finance."""
    
    # 1. On crée un faux jeu de données de bourse avec Pandas
    dates = pd.date_range(start="2023-01-01", periods=5)
    mock_df = pd.DataFrame({
        "Open": [10.0, 10.5, 11.0, 10.8, 11.2],
        "High": [10.5, 11.0, 11.5, 11.2, 11.8],
        "Low": [9.5, 10.0, 10.5, 10.2, 11.0],
        "Close": [10.2, 10.8, 10.9, 11.1, 11.5],
        "Volume": [1000, 1500, 1200, 1300, 2000]
    }, index=dates)
    
    # 2. On intercepte `.history()` pour qu'il renvoie toujours nos fausses données
    mock_ticker.return_value.history.return_value = mock_df

    # 3. On appelle notre API (elle croira interroger YFinance)
    response = client.get("/api/asset/FR0013341781?period=1d")
    
    # 4. On vérifie que la transformation FastAPI a bien marché
    assert response.status_code == 200
    data = response.json()
    assert data["isin"] == "FR0013341781"
    assert data["ticker"] == "AL2SI.PA"
    assert len(data["dataseries"]) == 5
    assert data["price"] == 11.5  # Le dernier prix 'Close' de notre mock