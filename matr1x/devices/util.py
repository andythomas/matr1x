def listToStr(floatList):
    """
    converts a list of numeric values to a comma separated string
    """
    return ",".join(str(r) for r in floatList)


def strToList(string, dtype=float):
    """
    converts a comma separated string of values into a list with of
    values corresponding cast to dtype
    """
    string = string.strip("[")
    string = string.strip("]")
    return [dtype(r) for r in string.split(",")]
