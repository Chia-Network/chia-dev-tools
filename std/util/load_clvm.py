from lib.std.util.hash import std_hash
from lib.std.types.program import Program

def load_clvm(filename):
    filehash = ""
    with open(filename, 'rb') as standard_file:
        buf = standard_file.read()
        filehash = std_hash(buf)
        standard_file.close()
    hex_filename = filename+"."+str(filehash)+".hex"
    with open(hex_filename, 'rb') as hex_file:
        buf = hex_file.read()
        hex_file.close()
        return Program.from_bytes(bytes.fromhex(buf.decode('utf8')))
