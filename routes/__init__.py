def register_blueprints(app):
    from routes.spy import bp as spy_bp
    from routes.webhook import bp as webhook_bp
    from routes.admin import bp as admin_bp
    from routes.diagnostics import bp as diag_bp
    from routes.photos import bp as photos_bp

    app.register_blueprint(spy_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(diag_bp)
    app.register_blueprint(photos_bp)