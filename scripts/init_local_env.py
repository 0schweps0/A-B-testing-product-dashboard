"""Create an ignored local development .env without exposing its password."""
from pathlib import Path
import secrets
import os

root = Path(__file__).resolve().parents[1]
path = root / '.env'
# O_EXCL preserves an existing user configuration. Restrict access at creation.
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as file:
    file.write('POSTGRES_DB=reactivation\nPOSTGRES_USER=analyst\n'
               f'POSTGRES_PASSWORD={secrets.token_urlsafe(24)}\n'
               'POSTGRES_HOST=127.0.0.1\nPOSTGRES_PORT=5433\n')
print('Created .env for the local development database. Keep it out of Git.')
