#!/usr/bin/env python3
"""
Script de instalación para el Telegram Auto Post Bot
"""

import os
import sys
import subprocess
import platform

def check_python_version():
    """Verifica la versión de Python"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 o superior es requerido")
        sys.exit(1)
    print("✅ Python versión compatible")

def install_dependencies():
    """Instala las dependencias del proyecto"""
    print("📦 Instalando dependencias...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencias instaladas")
    except subprocess.CalledProcessError:
        print("❌ Error instalando dependencias")
        sys.exit(1)

def create_env_file():
    """Crea el archivo .env si no existe"""
    if not os.path.exists('.env'):
        print("📝 Creando archivo .env...")
        with open('.env', 'w') as f:
            f.write("""# Telegram Bot Configuration
BOT_TOKEN=8063509725:AAHsa32julaJ4fst2OWhgj7lkL_HdA5ALN4
ADMIN_ID=1742433244

# Database Configuration
DATABASE_URL=sqlite:///auto_post_bot.db

# Optional: Set timezone (default is UTC)
TIMEZONE=UTC
""")
        print("✅ Archivo .env creado")
    else:
        print("✅ Archivo .env ya existe")

def create_directories():
    """Crea directorios necesarios"""
    directories = ['logs', 'backups']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📁 Directorio {directory} creado")
        else:
            print(f"✅ Directorio {directory} ya existe")

def main():
    print("🚀 Instalando Telegram Auto Post Bot...\n")
    
    check_python_version()
    install_dependencies()
    create_env_file()
    create_directories()
    
    print("\n✅ Instalación completada!")
    print("\nPara iniciar el bot:")
    print("1. Edita el archivo .env con tu token real")
    print("2. Ejecuta: python bot.py")

if __name__ == "__main__":
    main()
