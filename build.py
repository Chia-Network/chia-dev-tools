import sys
import hashlib

from clvm_tools.clvmc import compile_clvm

outfile = sys.argv[1] + "." + sys.argv[2] + ".hex"
compile_clvm(sys.argv[1],outfile)
