# t2n | v2.0
\- This program lets you encode and decode any text into numbers (text2numbers), with flexible customization of the translation through alphabets.

## Usage examples:
> ttn default Hello World!
> 
> *245435647671742280114323*

> ntt tiny 141724270202268934
> 
> this is t2n

## Important
This algorithm is not a 100% way to protect your data. If someone has a single pair of source+result data, there is a way to decode other data as well. It's better to use the algorithm in combination with something else.

## Installation
### Via cmd / terminal:

1. Navigate to the directory you want using the command
```bash
cd /where/you/want/
```
2. Clone the repository with git
```bash
git clone https://github.com/qpikzz/t2n.git
```
3. Create the virtual environment
```bash
python -m venv venv
```
Then activate it:  
- windows: `venv\Scripts\activate`  
- mac/linux: `source venv/bin/activate`  
4. Run the program:
```bash
python run.py
```

## Project structure
- `/alphabets/` - directory containing the alphabets.  
There are 6 by default: `default`, `tiny`, `utiny`, `oneword`, `hex`, `russian`.  
You can add your own alphabets to this directory, using `[name].txt`, to use them in run.py.  
The alphabet should be written on a single line; line breaks will not be read.

- `.gitignore`, `LICENSE`, `README.md` - service files

- `help.txt` - text printed when the help command is sent. It contains examples and a description of all commands.

- `run.py` - runs the program and handles commands. Also, if a command isn't recognized, the code is passed to exec, and the result is printed to the console.

- `t2n.py` - holds the 4 main functions. If you want to add t2n to your project, copy this file specifically.

## Using t2n.py
Here I'll go into more detail about the functions - what data they take and return.

### text_to_number(text: str, alp: str) -> int  
> Takes as input:
> 1. text (string) - the message you want to encode
> 2. alp (string) - the alphabet used for encoding  

> Returns:
>1. result (int) - the message translated into a number

> Usage example
> ```py
> textToNumber("qwerty", "0123qwertyuiop") # >> 2361333
> ```

### numberToText(number: int, alp: str) -> str
> Takes as input:
> 1. number (int) - the number you want to decode into text
> 2. alp (string) - the alphabet used for decoding  

> Returns:
>1. result (string) - the resulting text

> Usage example
> ```py
> numberToText(1234567890, "0123qwertyuiop") # >> iypeiwuu
> ```

### average_to_number(texts: list, alp: str) -> int  
> Takes as input:
> 1. texts (list) - the list of messages you want to encode. The texts are separated by `;` in the command
> 2. alp (string) - the alphabet used for encoding  

> Returns:
>1. result (int) - each text is translated into a number, then their arithmetic mean is returned

> Usage example
> ```py
> average_to_number(["hello", "world"], "helo wrd") # >> 11541
> ```

### average_to_text(texts: list, alp: str) -> str
> Takes as input:
> 1. texts (list) - the list of messages you want to encode. The texts are separated by `;` in the command
> 2. alp (string) - the alphabet used for encoding  

> Returns:
>1. result (string) - each text is translated into a number, then their arithmetic mean is returned, translated back into text

> Usage example
> ```py
> average_to_text(["hello", "world"], "helo wrd") # >> lr lw
> ```

### class T2N

> Allows you to set the alphabet once at creation instead of passing it to every function call.  
>Provides 2 methods: `t2n` (equivalent to `text_to_number`) and `n2t` (equivalent to `number_to_text`).

> Usage example
> ```py
> from t2n import T2N
> 
> converter = T2N("helo wrd")
> 
> print(converter.t2n("hello"))   # >> 659
> print(converter.n2t(22423))     # >> world
> ```
