Chialisp Dev Utility
=======

Install (Windows only atm)
-------

```
git clone https://github.com/Quexington/chialisp_dev_utlity.git
cd chialisp_dev_utility
.\chialisp install
#Optionally add chialisp.ps1 to PATH
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
chialisp run helloworld.py
```

All current commands
-------
```
chialisp install #grab necessary packages for the utility to work
chialisp init #creates a 'Hello World' script in the current directory
chialisp activate #activate the venv
chialisp deactivate #deactivate the venv
chialisp build <optional clvm filename> #build all .clvm files into .hex files or just the specified one
chialisp exec <filename> #run a python file without building any clvm
```
