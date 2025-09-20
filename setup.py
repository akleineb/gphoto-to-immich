#!/usr/bin/env python3
"""
Setup-Script für Google Photos zu Immich Migration
"""

import subprocess
import sys
import os
from pathlib import Path


def install_requirements():
    """Installiert die erforderlichen Abhängigkeiten"""
    print("📦 Installiere Abhängigkeiten...")
    try:
        # Versuche verschiedene pip-Varianten
        pip_commands = [
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            ["pip3", "install", "-r", "requirements.txt"],
            ["pip", "install", "-r", "requirements.txt"]
        ]
        
        for cmd in pip_commands:
            try:
                subprocess.check_call(cmd)
                print("✅ Abhängigkeiten erfolgreich installiert")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        print("❌ Konnte pip nicht finden. Bitte installiere die Abhängigkeiten manuell:")
        print("   pip3 install requests urllib3")
        return False
        
    except Exception as e:
        print(f"❌ Fehler beim Installieren der Abhängigkeiten: {e}")
        print("Bitte installiere die Abhängigkeiten manuell:")
        print("   pip3 install requests urllib3")
        return False


def make_executable():
    """Macht die Scripts ausführbar"""
    scripts = ["gphoto_to_immich.py", "test_migration.py"]
    
    for script in scripts:
        if os.path.exists(script):
            try:
                os.chmod(script, 0o755)
                print(f"✅ {script} ist jetzt ausführbar")
            except Exception as e:
                print(f"⚠️  Konnte {script} nicht ausführbar machen: {e}")


def test_installation():
    """Testet die Installation"""
    print("\n🧪 Teste Installation...")
    
    # Teste Python-Version
    print(f"Python-Version: {sys.version}")
    
    # Teste Import der Module
    try:
        import requests
        print(f"✅ requests {requests.__version__} verfügbar")
    except ImportError as e:
        print(f"❌ requests nicht verfügbar: {e}")
        return False
    
    try:
        import urllib3
        print(f"✅ urllib3 {urllib3.__version__} verfügbar")
    except ImportError as e:
        print(f"❌ urllib3 nicht verfügbar: {e}")
        return False
    
    # Teste Script-Syntax
    try:
        with open("gphoto_to_immich.py", "r", encoding='utf-8') as f:
            compile(f.read(), "gphoto_to_immich.py", "exec")
        print("✅ Hauptscript-Syntax ist korrekt")
    except Exception as e:
        print(f"❌ Syntax-Fehler im Hauptscript: {e}")
        return False
    
    # Teste Test-Script
    try:
        with open("test_migration.py", "r", encoding='utf-8') as f:
            compile(f.read(), "test_migration.py", "exec")
        print("✅ Test-Script-Syntax ist korrekt")
    except Exception as e:
        print(f"❌ Syntax-Fehler im Test-Script: {e}")
        return False
    
    return True


def main():
    """Hauptfunktion"""
    print("🚀 Google Photos zu Immich Migration - Setup")
    print("=" * 50)
    
    # Prüfe Python-Version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 oder höher ist erforderlich")
        return 1
    
    print(f"✅ Python {sys.version.split()[0]} erkannt")
    
    # Installiere Abhängigkeiten
    if not install_requirements():
        return 1
    
    # Mache Scripts ausführbar
    make_executable()
    
    # Teste Installation
    if not test_installation():
        return 1
    
    print("\n" + "=" * 50)
    print("🎉 Setup erfolgreich abgeschlossen!")
    print("=" * 50)
    print("\nNächste Schritte:")
    print("1. Immich-Server starten")
    print("2. API-Key aus Immich kopieren")
    print("3. Test mit Beispieldateien:")
    print("   python test_migration.py --analyze")
    print("4. Migration starten:")
    print("   python gphoto_to_immich.py --api-key YOUR_KEY --takeout-path /path/to/Google\\ Photos")
    print("\nFür Hilfe:")
    print("   python gphoto_to_immich.py --help")
    
    return 0


if __name__ == "__main__":
    exit(main())
