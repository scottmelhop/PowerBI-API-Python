from typing import List, Any


def partition(lst: List[Any], n: int) -> List[List[Any]]:
    """
    Splits the list into chunks with size n,
    except last chunks that has size <= n
    """
    return [lst[i:i+n] for i in range(0, len(lst), n)]
