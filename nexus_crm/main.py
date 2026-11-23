import os
import sys

from django.core.management import execute_from_command_line


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus.settings")
    arguments = sys.argv[1:] or ["runserver"]
    execute_from_command_line(["manage.py", *arguments])
