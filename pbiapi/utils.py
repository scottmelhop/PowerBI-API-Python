from typing import List, Any


def partition(lst: List[Any], n: int) -> List[List[Any]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]


def partition2(lst: List[Any], n: int) -> List[List[Any]]:
    return [lst[i:i+n] for i in range(len(lst), n)]
