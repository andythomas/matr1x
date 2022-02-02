# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
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
