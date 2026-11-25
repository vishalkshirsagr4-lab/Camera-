from flask import Blueprint, send_from_directory
from core.storage import PHOTO_DIR

bp = Blueprint('photos', __name__)


@bp.route('/photos/<filename>')
def photo(filename):
    return send_from_directory(PHOTO_DIR, filename)