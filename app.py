import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voice_receptionist.settings")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    host = os.environ.get("HOST", "0.0.0.0")

    import django
    django.setup()

    from django.core.management import call_command
    call_command("migrate", interactive=False)
    call_command("seed_demo_data")

    try:
        import uvicorn
        from voice_receptionist.asgi import application
        print(f"Starting AI Receptionist Django Enterprise Server on http://{host}:{port} with Uvicorn ASGI...", flush=True)
        uvicorn.run(application, host=host, port=port)
    except ImportError:
        from django.core.management import execute_from_command_line
        print(f"Starting Django development server on http://{host}:{port}...", flush=True)
        execute_from_command_line([sys.argv[0], "runserver", f"{host}:{port}"])
