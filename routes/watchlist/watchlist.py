"""
routes/watchlist/watchlist.py — CineLog

Endpoints for a user's watchlist (films they want to watch later).
"""

from flask import Blueprint, jsonify, request
from services.watchlist_service import (
    add_to_watchlist,
    get_watchlist,
    FilmNotFoundError,
)

watchlist_bp = Blueprint("watchlist", __name__)


@watchlist_bp.route("/<user_id>", methods=["GET"])
def view_watchlist(user_id):
    """
    GET /watchlist/<user_id>

    Returns all films in a user's watchlist, sorted alphabetically by title.
    """
    films = get_watchlist(user_id)
    return jsonify(films)


@watchlist_bp.route("/<user_id>/add", methods=["POST"])
def add_film(user_id):
    """
    POST /watchlist/<user_id>/add

    Body: { "film_id": "<id>" }
    """
    data = request.get_json()
    if not data or "film_id" not in data:
        return jsonify({"error": "film_id is required"}), 400

    entry = add_to_watchlist(user_id=user_id, film_id=data["film_id"])
    return jsonify(entry.to_dict()), 201
