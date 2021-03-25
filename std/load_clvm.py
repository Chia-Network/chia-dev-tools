import hashlib
from lib.std.program import Program

def load_clvm(filename):
    filehash = ""
    hasher = hashlib.sha256()
    with open(filename, 'rb') as standard_file:
        buf = standard_file.read()
        hasher.update(buf)
        filehash = hasher.hexdigest()
        standard_file.close()
    hex_filename = filename+"."+filehash+".hex"
    with open(hex_filename, 'rb') as hex_file:
        buf = hex_file.read()
        hex_file.close()
        return Program.from_bytes(bytes.fromhex(buf.decode('utf8')))
