from pymongo import MongoClient
from datetime import datetime
import logging
from config import MONGODB_URL, DATABASE_NAME

logger = logging.getLogger(__name__)

class MongoDB:
    _instance = None
    _client = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDB, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            try:
                self._client = MongoClient(MONGODB_URL)
                self._db = self._client[DATABASE_NAME]
                
                # Crear índices
                self._create_indexes()
                logger.info("Conectado a MongoDB exitosamente")
            except Exception as e:
                logger.error(f"Error conectando a MongoDB: {e}")
                raise
    
    def _create_indexes(self):
        """Crear índices para optimizar consultas"""
        try:
            # Índices para posts
            self._db.posts.create_index("is_active")
            
            # Índices para canales
            self._db.channels.create_index("channel_id", unique=True)
            
            # Índices para post_channels
            self._db.post_channels.create_index([("post_id", 1), ("channel_id", 1)])
            
            # Índices para post_schedules
            self._db.post_schedules.create_index("post_id")
            
            # Índices para scheduled_jobs
            self._db.scheduled_jobs.create_index([("post_id", 1), ("is_completed", 1)])
            
            # Nuevos índices para notificaciones
            self._db.sent_messages.create_index([("post_id", 1), ("deleted", 1)])
            self._db.deletion_stats.create_index([("post_id", 1), ("send_time", 1)])
            
        except Exception as e:
            logger.error(f"Error creando índices: {e}")
    
    @property
    def db(self):
        return self._db
    
    def close(self):
        if self._client:
            self._client.close()

# Instancia global
mongodb = MongoDB()
db = mongodb.db

class Post:
    def __init__(self, name, source_channel, source_message_id, content_type, 
                 content_text="", file_id=None, is_active=True, _id=None):
        self.name = name
        self.source_channel = source_channel
        self.source_message_id = source_message_id
        self.content_type = content_type
        self.content_text = content_text or ""
        self.file_id = file_id
        self.is_active = is_active
        self.created_at = datetime.utcnow()
        self._id = _id
    
    def to_dict(self):
        doc = {
            'name': self.name,
            'source_channel': self.source_channel,
            'source_message_id': self.source_message_id,
            'content_type': self.content_type,
            'content_text': self.content_text,
            'file_id': self.file_id,
            'is_active': self.is_active,
            'created_at': self.created_at
        }
        if self._id:
            doc['_id'] = self._id
        return doc
    
    @classmethod
    def from_dict(cls, doc):
        return cls(
            name=doc['name'],
            source_channel=doc['source_channel'],
            source_message_id=doc['source_message_id'],
            content_type=doc['content_type'],
            content_text=doc.get('content_text', ''),
            file_id=doc.get('file_id'),
            is_active=doc.get('is_active', True),
            _id=doc.get('_id')
        )
    
    def save(self):
        try:
            if self._id:
                db.posts.update_one({'_id': self._id}, {'$set': self.to_dict()})
            else:
                result = db.posts.insert_one(self.to_dict())
                self._id = result.inserted_id
            return True
        except Exception as e:
            logger.error(f"Error guardando post: {e}")
            return False
    
    @classmethod
    def find_by_id(cls, post_id):
        try:
            from bson import ObjectId
            doc = db.posts.find_one({'_id': ObjectId(post_id)})
            return cls.from_dict(doc) if doc else None
        except Exception as e:
            logger.error(f"Error buscando post: {e}")
            return None
    
    @classmethod
    def find_active(cls):
        try:
            docs = db.posts.find({'is_active': True})
            return [cls.from_dict(doc) for doc in docs]
        except Exception as e:
            logger.error(f"Error buscando posts activos: {e}")
            return []
    
    @classmethod
    def count_active(cls):
        try:
            return db.posts.count_documents({'is_active': True})
        except Exception as e:
            logger.error(f"Error contando posts: {e}")
            return 0
    
    def delete(self):
        try:
            if self._id:
                # Eliminar registros relacionados
                from bson import ObjectId
                post_id_str = str(self._id)
                
                db.post_channels.delete_many({'post_id': post_id_str})
                db.post_schedules.delete_many({'post_id': post_id_str})
                db.scheduled_jobs.delete_many({'post_id': post_id_str})
                db.sent_messages.delete_many({'post_id': post_id_str})
                db.deletion_stats.delete_many({'post_id': post_id_str})
                db.posts.delete_one({'_id': self._id})
                return True
        except Exception as e:
            logger.error(f"Error eliminando post: {e}")
            return False

class PostSchedule:
    def __init__(self, post_id, send_time="09:00", delete_after_hours=24, 
                 days_of_week="1,2,3,4,5,6,7", is_enabled=True, 
                 pin_message=False, forward_original=True, _id=None):
        self.post_id = str(post_id)
        self.send_time = send_time
        self.delete_after_hours = delete_after_hours
        self.days_of_week = days_of_week
        self.is_enabled = is_enabled
        self.pin_message = pin_message
        self.forward_original = forward_original
        self._id = _id
    
    def to_dict(self):
        doc = {
            'post_id': self.post_id,
            'send_time': self.send_time,
            'delete_after_hours': self.delete_after_hours,
            'days_of_week': self.days_of_week,
            'is_enabled': self.is_enabled,
            'pin_message': self.pin_message,
            'forward_original': self.forward_original
        }
        if self._id:
            doc['_id'] = self._id
        return doc
    
    @classmethod
    def from_dict(cls, doc):
        return cls(
            post_id=doc['post_id'],
            send_time=doc.get('send_time', '09:00'),
            delete_after_hours=doc.get('delete_after_hours', 24),
            days_of_week=doc.get('days_of_week', '1,2,3,4,5,6,7'),
            is_enabled=doc.get('is_enabled', True),
            pin_message=doc.get('pin_message', False),
            forward_original=doc.get('forward_original', True),
            _id=doc.get('_id')
        )
    
    def save(self):
        try:
            if self._id:
                db.post_schedules.update_one({'_id': self._id}, {'$set': self.to_dict()})
            else:
                result = db.post_schedules.insert_one(self.to_dict())
                self._id = result.inserted_id
            return True
        except Exception as e:
            logger.error(f"Error guardando horario: {e}")
            return False
    
    @classmethod
    def find_by_post_id(cls, post_id):
        try:
            doc = db.post_schedules.find_one({'post_id': str(post_id)})
            return cls.from_dict(doc) if doc else None
        except Exception as e:
            logger.error(f"Error buscando horario: {e}")
            return None
    
    @classmethod
    def count_enabled(cls):
        try:
            return db.post_schedules.count_documents({'is_enabled': True})
        except Exception as e:
            logger.error(f"Error contando horarios: {e}")
            return 0

class Channel:
    def __init__(self, channel_id, channel_name=None, channel_username=None, _id=None):
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.channel_username = channel_username
        self._id = _id
    
    def to_dict(self):
        doc = {
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'channel_username': self.channel_username
        }
        if self._id:
            doc['_id'] = self._id
        return doc
    
    @classmethod
    def from_dict(cls, doc):
        return cls(
            channel_id=doc['channel_id'],
            channel_name=doc.get('channel_name'),
            channel_username=doc.get('channel_username'),
            _id=doc.get('_id')
        )
    
    def save(self):
        try:
            if self._id:
                db.channels.update_one({'_id': self._id}, {'$set': self.to_dict()})
            else:
                result = db.channels.insert_one(self.to_dict())
                self._id = result.inserted_id
            return True
        except Exception as e:
            logger.error(f"Error guardando canal: {e}")
            return False
    
    @classmethod
    def find_all(cls):
        try:
            docs = db.channels.find()
            return [cls.from_dict(doc) for doc in docs]
        except Exception as e:
            logger.error(f"Error buscando canales: {e}")
            return []
    
    @classmethod
    def find_by_channel_id(cls, channel_id):
        try:
            doc = db.channels.find_one({'channel_id': channel_id})
            return cls.from_dict(doc) if doc else None
        except Exception as e:
            logger.error(f"Error buscando canal: {e}")
            return None
    
    @classmethod
    def count_all(cls):
        try:
            return db.channels.count_documents({})
        except Exception as e:
            logger.error(f"Error contando canales: {e}")
            return 0
    
    def delete(self):
        try:
            if self._id:
                # Eliminar asignaciones
                db.post_channels.delete_many({'channel_id': self.channel_id})
                db.channels.delete_one({'_id': self._id})
                return True
        except Exception as e:
            logger.error(f"Error eliminando canal: {e}")
            return False

class PostChannel:
    def __init__(self, post_id, channel_id, _id=None):
        self.post_id = str(post_id)
        self.channel_id = channel_id
        self._id = _id
    
    def to_dict(self):
        doc = {
            'post_id': self.post_id,
            'channel_id': self.channel_id
        }
        if self._id:
            doc['_id'] = self._id
        return doc
    
    @classmethod
    def from_dict(cls, doc):
        return cls(
            post_id=doc['post_id'],
            channel_id=doc['channel_id'],
            _id=doc.get('_id')
        )
    
    def save(self):
        try:
            if self._id:
                db.post_channels.update_one({'_id': self._id}, {'$set': self.to_dict()})
            else:
                result = db.post_channels.insert_one(self.to_dict())
                self._id = result.inserted_id
            return True
        except Exception as e:
            logger.error(f"Error guardando asignación: {e}")
            return False
    
    @classmethod
    def find_by_post_id(cls, post_id):
        try:
            docs = db.post_channels.find({'post_id': str(post_id)})
            return [cls.from_dict(doc) for doc in docs]
        except Exception as e:
            logger.error(f"Error buscando asignaciones: {e}")
            return []
    
    @classmethod
    def count_by_post_id(cls, post_id):
        try:
            return db.post_channels.count_documents({'post_id': str(post_id)})
        except Exception as e:
            logger.error(f"Error contando asignaciones: {e}")
            return 0
    
    @classmethod
    def delete_by_post_id(cls, post_id):
        try:
            db.post_channels.delete_many({'post_id': str(post_id)})
            return True
        except Exception as e:
            logger.error(f"Error eliminando asignaciones: {e}")
            return False

class ScheduledJob:
    def __init__(self, post_id, job_type, scheduled_time, channel_id, 
                 message_id=None, is_completed=False, _id=None):
        self.post_id = str(post_id)
        self.job_type = job_type
        self.scheduled_time = scheduled_time
        self.channel_id = channel_id
        self.message_id = message_id
        self.is_completed = is_completed
        self._id = _id
    
    def to_dict(self):
        doc = {
            'post_id': self.post_id,
            'job_type': self.job_type,
            'scheduled_time': self.scheduled_time,
            'channel_id': self.channel_id,
            'message_id': self.message_id,
            'is_completed': self.is_completed
        }
        if self._id:
            doc['_id'] = self._id
        return doc
    
    @classmethod
    def from_dict(cls, doc):
        return cls(
            post_id=doc['post_id'],
            job_type=doc['job_type'],
            scheduled_time=doc['scheduled_time'],
            channel_id=doc['channel_id'],
            message_id=doc.get('message_id'),
            is_completed=doc.get('is_completed', False),
            _id=doc.get('_id')
        )
    
    def save(self):
        try:
            if self._id:
                db.scheduled_jobs.update_one({'_id': self._id}, {'$set': self.to_dict()})
            else:
                result = db.scheduled_jobs.insert_one(self.to_dict())
                self._id = result.inserted_id
            return True
        except Exception as e:
            logger.error(f"Error guardando trabajo: {e}")
            return False
