import os
from flask import Flask

from config import config
from core.storage import boot
from routes import register_blueprints


def create_app():
    app = Flask(__name__)
    app.secret_key = config['secret_key']
    app.logger.setLevel('INFO')

    boot()                    # create data/, photos/, JSON files
    register_blueprints(app)

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)