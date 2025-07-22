# Telegram Auto Post Bot

Un bot avanzado de Telegram para auto-publicación de contenido con programación y eliminación automática.

## Características

- ✅ **Auto-publicación** de posts (texto, foto, video, audio, documentos)
- ⏰ **Programación flexible** por hora y días de la semana
- 🗑️ **Eliminación automática** después de horas configuradas
- 📺 **Gestión de canales** (añadir/eliminar múltiples canales)
- 🎯 **Asignación por post** (canales específicos para cada post)
- 📊 **Estadísticas** y monitoreo
- 🔐 **Panel de administración** con botones interactivos
- 📱 **Soporte para hasta 5 posts** con configuraciones individuales

## Instalación

1. Clona el repositorio:
```bash
git clone <url-del-repositorio>
cd telegram_auto_post_bot
```

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. Configura el archivo `.env`:
```bash
cp .env.example .env
# Edita .env con tu token y configuraciones
```

4. Ejecuta el bot:
```bash
python bot.py
```

## Uso

### Comandos Principales
- `/start` - Inicia el bot (solo administrador)

### Funcionalidades

#### Crear un Post
1. Ve al canal fuente
2. Reenvía el mensaje al bot
3. El bot detectará automáticamente el contenido

#### Configurar Posts
- **Hora de envío**: Programa cuándo enviar el post
- **Tiempo de eliminación**: Horas hasta eliminar automáticamente
- **Días de publicación**: Selecciona días específicos
- **Canales destino**: Asigna canales específicos para cada post

#### Gestión de Canales
- Añadir canales por @username o ID
- Eliminar canales en masa
- Ver lista de canales registrados
- Asignar canales a posts específicos

## Configuración del Bot

### Variables de Entorno
- `BOT_TOKEN`: Token del bot de Telegram
- `ADMIN_ID`: ID del administrador
- `DATABASE_URL`: URL de la base de datos (SQLite por defecto)

### Límites
- Máximo 5 posts activos
- Máximo 50 canales por post
- Programación diaria disponible

## Estructura del Proyecto

```
telegram_auto_post_bot/
├── bot.py              # Archivo principal
├── config.py           # Configuración
├── database.py         # Modelos de base de datos
├── handlers.py         # Manejadores de comandos
├── scheduler.py        # Sistema de programación
├── channel_manager.py  # Gestión de canales
├── requirements.txt    # Dependencias
├── .env.example        # Ejemplo de configuración
└── README.md          # Este archivo
```

## Solución de Problemas

### El bot no responde
1. Verifica que el token esté correcto
2. Asegúrate de que el bot esté agregado al canal como administrador
3. Revisa los logs del bot

### Los posts no se envían
1. Verifica que los canales estén correctamente asignados
2. Asegúrate de que el bot tenga permisos en los canales
3. Comprueba la configuración de horarios

### Errores de eliminación
1. El bot debe ser administrador en los canales
2. Los mensajes solo pueden eliminarse dentro de las 48 horas
3. Verifica los permisos de eliminación

## Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT.
