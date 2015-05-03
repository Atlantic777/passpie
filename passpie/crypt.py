import errno
import os
import shutil
import tempfile
import gnupg

from ._compat import which, FileNotFoundError, FileExistsError
from .utils import mkdir_open


KEY_INPUT = """Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Name-Comment: Auto-generated by Passpie
Passphrase: {}
Name-Real: Passpie
Name-Email: passpie@local
Expire-Date: 0
%commit
"""


class Cryptor(object):

    def __init__(self, path):
        self.path = path
        self.keys_path = os.path.join(path, ".keys")
        self._binary = which("gpg")
        self._homedir = tempfile.mkdtemp()
        self._gpg = gnupg.GPG(binary=self._binary, homedir=self._homedir)

    def __enter__(self):
        return self

    def __exit__(self, exc_ty, exc_val, exc_tb):
        shutil.rmtree(self._homedir)

    def _import_keys(self):
        try:
            with open(self.keys_path) as keyfile:
                self._gpg.import_keys(keyfile.read())
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                raise FileNotFoundError("Keys not found in path")
            else:
                raise

    @property
    def current_key(self):
        keys = self._gpg.list_keys()
        return keys.curkey["fingerprint"]

    def create_keys(self, passphrase, overwrite=False):
        if overwrite is False and os.path.exists(self.keys_path):
            raise FileExistsError("Keys found in path")

        keys = self._gpg.gen_key(KEY_INPUT.format(passphrase))
        pubkey = self._gpg.export_keys(keys.fingerprint)
        seckey = self._gpg.export_keys(keys.fingerprint, secret=True)
        with mkdir_open(self.keys_path, "w") as keyfile:
            keyfile.write(pubkey + seckey)

    def encrypt(self, data):
        self._import_keys()
        encrypted = self._gpg.encrypt(data, self.current_key)
        return str(encrypted)

    def decrypt(self, data, passphrase):
        self._import_keys()
        self.check(passphrase, ensure=True)
        decrypted = self._gpg.decrypt(data, passphrase=passphrase)
        return str(decrypted)

    def check(self, passphrase, ensure=False):
        self._import_keys()
        sign = self._gpg.sign(
            "testing",
            default_key=self.current_key,
            passphrase=passphrase
        )
        if sign:
            return True
        else:
            if ensure:
                raise ValueError("Wrong passphrase")
