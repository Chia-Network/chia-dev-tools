Chialisp Dev Utility
=======

Install (Windows only atm)
-------

```
git clone https://github.com/Quexington/chialisp_dev_utlity.git
cd chialisp_dev_utility
.\venv\Scripts\activate #Optionally add this to PATH, you will need it every time you are using the utility
pip install -e .
```

Initialize a hello world project
-------
```
mkdir My-Chia-Project
cd My-Chia-Project
chialisp init
```

Run the hello world project
-------
```
chialisp build
py helloworld.py
```

All current commands
-------
```
chialisp init #creates a 'Hello World' script in the current directory
chialisp build <optional clvm filename> #build all .clvm files into .hex files or just the specified one
```
