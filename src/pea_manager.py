"""
pea_manager.py - Gestion du Plan d'Epargne en Actions (PEA)
Suivi des positions, P&L, fiscalite, eligibilite EEE.
"""

import json
import os
from datetime import datetime
from typing import Optional

# Plafond PEA classique
PEA_PLAFOND = 150_000.0

# Prefixes ISIN eligibles PEA (Espace Economique Europeen)
ISIN_PREFIXES_PEA = {
    "FR", "DE", "IT", "ES", "NL", "BE", "PT", "AT", "FI", "IE",
    "LU", "GR", "SI", "SK", "EE", "LV", "LT", "MT", "CY",
    "NO", "IS", "LI",
}

# Suffixes tickers Euronext eligibles
TICKER_SUFFIXES_PEA = {".PA", ".AS", ".BR", ".LS", ".MI", ".DE", ".MC"}


class PEAManager:
    """Gestionnaire de portefeuille PEA."""

    def __init__(self):
        self.positions = {}
        self.date_ouverture = None
        self.total_versements = 0.0
        self._load()

    def _get_path(self) -> str:
        try:
            from android.storage import app_storage_path
            return os.path.join(app_storage_path(), "pea_portfolio.json")
        except ImportError:
            here = os.path.dirname(os.path.abspath(__file__))
            config_dir = os.path.join(os.path.dirname(here), "config")
            if os.path.isdir(config_dir):
                return os.path.join(config_dir, "pea_portfolio.json")
            return os.path.join(here, "pea_portfolio.json")

    def _load(self):
        path = self._get_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.positions = data.get("positions", {})
                self.date_ouverture = data.get("date_ouverture")
                self.total_versements = data.get("total_versements", 0.0)
            except (json.JSONDecodeError, IOError):
                pass

    def _save(self):
        path = self._get_path()
        data = {
            "positions": self.positions,
            "date_ouverture": self.date_ouverture,
            "total_versements": self.total_versements,
        }
        try:
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    @staticmethod
    def is_pea_eligible(ticker_or_isin: str) -> bool:
        """Verifie si un titre est eligible PEA (EEE)."""
        val = ticker_or_isin.strip().upper()
        # ISIN: 2 lettres pays + 9 alphanumeriques + 1 chiffre controle
        import re
        if re.match(r'^[A-Z]{2}[A-Z0-9]{9}\d$', val):
            return val[:2] in ISIN_PREFIXES_PEA
        # Ticker avec suffixe Euronext
        for suffix in TICKER_SUFFIXES_PEA:
            if val.endswith(suffix):
                return True
        return False

    def ouvrir_pea(self):
        """Ouvre le PEA (fixe la date d'ouverture)."""
        if not self.date_ouverture:
            self.date_ouverture = datetime.now().isoformat()
            self._save()

    def get_anciennete_annees(self) -> float:
        if not self.date_ouverture:
            return 0
        dt = datetime.fromisoformat(self.date_ouverture)
        return (datetime.now() - dt).days / 365.25

    def get_fiscalite(self) -> dict:
        """Retourne les infos fiscales selon l'anciennete du PEA."""
        annees = self.get_anciennete_annees()
        if annees >= 5:
            return {
                "regime": "Exonere (>5 ans)",
                "taux_ir": 0,
                "taux_ps": 17.2,
                "taux_total": 17.2,
                "detail": "Prelevements sociaux 17.2% uniquement",
            }
        elif annees >= 2:
            return {
                "regime": f"PFU 30% (2-5 ans, {annees:.1f} an(s))",
                "taux_ir": 12.8,
                "taux_ps": 17.2,
                "taux_total": 30.0,
                "detail": "Flat tax 30% (12.8% IR + 17.2% PS)",
            }
        else:
            return {
                "regime": f"PFU 30% (<2 ans, {annees:.1f} an(s))",
                "taux_ir": 12.8,
                "taux_ps": 17.2,
                "taux_total": 30.0,
                "detail": "Flat tax 30% + cloture PEA si retrait",
            }

    def versement_possible(self, montant: float) -> bool:
        return (self.total_versements + montant) <= PEA_PLAFOND

    def acheter(self, ticker: str, name: str, quantity: int, prix: float) -> dict:
        """Achete des actions dans le PEA."""
        if quantity <= 0 or prix <= 0:
            return {"success": False, "error": "Quantite et prix doivent etre positifs"}

        montant = quantity * prix

        if not self.versement_possible(montant):
            reste = PEA_PLAFOND - self.total_versements
            return {"success": False, "error": f"Plafond PEA depasse. Reste: {reste:.2f} EUR"}

        if not self.date_ouverture:
            self.ouvrir_pea()

        tx = {
            "type": "ACHAT",
            "date": datetime.now().isoformat(),
            "quantity": quantity,
            "prix": round(prix, 4),
            "montant": round(montant, 2),
        }

        if ticker in self.positions:
            pos = self.positions[ticker]
            ancien_total = pos["quantity"] * pos["pru"]
            nouveau_total = ancien_total + montant
            pos["quantity"] += quantity
            pos["pru"] = round(nouveau_total / pos["quantity"], 4)
            pos["total_invested"] = round(pos["total_invested"] + montant, 2)
            pos["transactions"].append(tx)
        else:
            self.positions[ticker] = {
                "name": name,
                "quantity": quantity,
                "pru": round(prix, 4),
                "total_invested": round(montant, 2),
                "transactions": [tx],
            }

        self.total_versements = round(self.total_versements + montant, 2)
        self._save()
        return {"success": True, "montant": round(montant, 2)}

    def vendre(self, ticker: str, quantity: int, prix: float) -> dict:
        """Vend des actions du PEA."""
        if quantity <= 0 or prix <= 0:
            return {"success": False, "error": "Quantite et prix doivent etre positifs"}

        if ticker not in self.positions:
            return {"success": False, "error": "Position inexistante"}

        pos = self.positions[ticker]
        if quantity > pos["quantity"]:
            return {"success": False, "error": f"Quantite insuffisante ({pos['quantity']} dispo)"}

        montant = quantity * prix
        pnl = (prix - pos["pru"]) * quantity

        tx = {
            "type": "VENTE",
            "date": datetime.now().isoformat(),
            "quantity": quantity,
            "prix": round(prix, 4),
            "montant": round(montant, 2),
            "pnl": round(pnl, 2),
        }

        pos["quantity"] -= quantity
        pos["transactions"].append(tx)

        if pos["quantity"] <= 0:
            del self.positions[ticker]

        self._save()
        return {"success": True, "montant": round(montant, 2), "pnl": round(pnl, 2)}

    def get_resume(self, prix_actuels: dict = None) -> dict:
        """Retourne un resume complet du portefeuille PEA."""
        total_invested = 0.0
        total_value = 0.0
        positions_detail = []

        for ticker, pos in self.positions.items():
            if pos["quantity"] <= 0:
                continue
            invested = pos["quantity"] * pos["pru"]
            total_invested += invested

            prix_actuel = (prix_actuels or {}).get(ticker, pos["pru"])
            value = pos["quantity"] * prix_actuel
            total_value += value
            pnl = value - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0

            positions_detail.append({
                "ticker": ticker,
                "name": pos["name"],
                "quantity": pos["quantity"],
                "pru": pos["pru"],
                "prix_actuel": round(prix_actuel, 2),
                "invested": round(invested, 2),
                "value": round(value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })

        pnl_total = total_value - total_invested
        pnl_total_pct = (pnl_total / total_invested * 100) if total_invested > 0 else 0

        fisc = self.get_fiscalite()
        impot = max(0, pnl_total) * fisc["taux_total"] / 100
        pnl_net = pnl_total - impot

        return {
            "total_versements": round(self.total_versements, 2),
            "plafond_restant": round(PEA_PLAFOND - self.total_versements, 2),
            "total_invested": round(total_invested, 2),
            "total_value": round(total_value, 2),
            "pnl_total": round(pnl_total, 2),
            "pnl_total_pct": round(pnl_total_pct, 2),
            "impot_estime": round(impot, 2),
            "pnl_net": round(pnl_net, 2),
            "fiscalite": fisc,
            "anciennete": round(self.get_anciennete_annees(), 2),
            "nb_positions": len(positions_detail),
            "positions": positions_detail,
        }
