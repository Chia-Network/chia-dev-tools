from lib.std.util.load_clvm import load_clvm

hello_world = load_clvm('./helloworld.clvm')
result = hello_world.run([])
print(result.as_python())
