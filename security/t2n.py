def text_to_number(text: str, alp: str) -> int:
    result = 0
    revText = text[::-1]
    for i in range(len(text)):
        result += alp.index(revText[i]) * len(alp) ** i
    return result


def number_to_text(number: int, alp: str) -> str:
    if number == 0:
        return alp[0]
    result = ""
    while number:
        result = alp[number % len(alp)] + result
        number //= len(alp)
    return result

def average_to_number(texts: list, alp: str) -> str:
    numbers = [text_to_number(text, alp) for text in texts]
    average = round(sum(numbers) / len(numbers)) # !!!

    return average

def average_to_text(texts: list, alp: str) -> str:
    numbers = [text_to_number(text, alp) for text in texts]
    average = round(sum(numbers) / len(numbers)) # !!!

    return number_to_text(average, alp)


class T2N:

    def __init__(self, alphabet: str):
        self.alphabet = alphabet

    def t2n(self, text: str) -> int:
        return text_to_number(text, self.alphabet)

    def n2t(self, number: int) -> str:
        return number_to_text(number, self.alphabet)