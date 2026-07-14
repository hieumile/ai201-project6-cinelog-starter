"""
services/watchlist_service.py — CineLog

Business logic for managing a user's watchlist (films they want to watch later).
All functions follow the project's verb_to_noun naming convention.
"""

from app import db
from models import Film, WatchlistEntry


class FilmNotFoundError(Exception):
    """Raised when a film_id does not exist in the database."""
    pass


class AlreadyInWatchlistError(Exception):
    """Raised when a film is already in the user's watchlist."""
    pass


def add_to_watchlist(user_id, film_id):
    """
    Add a film to a user's watchlist (i.e., mark it to watch later).

    Args:
        user_id (str): ID of the user.
        film_id: ID of the film.

    Returns:
        WatchlistEntry: The newly created entry.

    Raises:
        FilmNotFoundError: If film_id does not exist.
        AlreadyInWatchlistError: If the film is already in the user's watchlist.
    """
    film = Film.query.get(film_id)
    if film is None:
        raise FilmNotFoundError(f"No film found with id '{film_id}'")

    existing = WatchlistEntry.query.filter_by(
        user_id=user_id, film_id=film_id
    ).first()
    if existing:
        raise AlreadyInWatchlistError(
            f"Film '{film_id}' is already in this user's watchlist"
        )

    entry = WatchlistEntry(user_id=user_id, film_id=film_id)
    db.session.add(entry)
    db.session.commit()
    return entry


def get_watchlist(user_id):
    """
    Return all films in a user's watchlist, sorted alphabetically by title.

    Args:
        user_id (str): ID of the user.

    Returns:
        list[dict]: List of film dicts (not WatchlistEntry objects) with the
                    date_added and public flag from the entry attached.
    """
    entries = (
        WatchlistEntry.query
        .filter_by(user_id=user_id)
        .join(Film)
        .order_by(Film.title.asc())
        .all()
    )

    result = []
    for entry in entries:
        film_dict = entry.film.to_dict()
        film_dict["date_added"] = entry.date_added.isoformat()
        film_dict["public"] = entry.public
        result.append(film_dict)

    return result
