F = 'server.py'
s = open(F).read()
if 'physics.register' in s:
    print('already patched')
else:
    open('server.py.bak_physics', 'w').write(s)
    s = s.replace("if __name__ == '__main__':",
                  "import physics\nphysics.register(app)\n\nif __name__ == '__main__':", 1)
    open(F, 'w').write(s)
    print('server.py patched (backup: server.py.bak_physics)')
