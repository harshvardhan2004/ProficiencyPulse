"""
WSGI entry point for the Skills Matrix application.
This file is used by both development and production servers.
It automatically chooses the appropriate server based on environment settings.
"""

import os
from dotenv import load_dotenv
from app import app

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    # Get environment settings
    env = os.getenv('FLASK_ENV', 'production')
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    
    if env == 'development':
        # Development mode: use Flask's built-in server
        app.run(
            host=host,
            port=port,
            debug=True
        )
    else:
        # Production mode: use Waitress
        from waitress import serve
        print(f"Starting Waitress server on {host}:{port}")
        serve(
            app,
            host=host,
            port=port,
            threads=int(os.getenv('WAITRESS_THREADS', 4)),
            connection_limit=int(os.getenv('WAITRESS_CONNECTION_LIMIT', 1000)),
            channel_timeout=int(os.getenv('WAITRESS_CHANNEL_TIMEOUT', 30))
        ) 