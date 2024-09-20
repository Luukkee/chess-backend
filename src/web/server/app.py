from dataBase import *
from flask_cors import CORS
CORS(app)

# Initialize the database every time the app starts
#with app.app_context():
#    app.logger.info("Initializing the database...")
#    db.create_all()  # This ensures the tables are created
#    app.logger.info(f"Database file should be located at: {app.config['SQLALCHEMY_DATABASE_URI']}")
#    app.logger.info("Database initialized.")

# Run application (only when run locally)
if __name__ == '__main__':
    app.run(debug=True, port=5001)