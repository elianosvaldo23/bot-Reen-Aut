from flask import Flask, jsonify
import threading
import logging
from datetime import datetime
from config import TIMEZONE
import pytz

logger = logging.getLogger(__name__)

class HealthServer:
    def __init__(self, port=8000):
        self.app = Flask(__name__)
        self.port = port
        self.setup_routes()
    
    def setup_routes(self):
        @self.app.route('/')
        def health_check():
            return "Bot is running!"
        
        @self.app.route('/health')
        def detailed_health():
            cuba_time = datetime.now(pytz.timezone(TIMEZONE))
            return jsonify({
                'status': 'healthy',
                'timestamp': cuba_time.isoformat(),
                'timezone': TIMEZONE,
                'message': 'Auto Post Bot is running'
            })
        
        @self.app.route('/ping')
        def ping():
            return "pong"
    
    def start(self):
        """Inicia el servidor en un hilo separado"""
        def run_server():
            try:
                self.app.run(host='0.0.0.0', port=self.port, debug=False)
            except Exception as e:
                logger.error(f"Error en health server: {e}")
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        logger.info(f"Health server iniciado en puerto {self.port}")

# Instancia global
health_server = HealthServer()
