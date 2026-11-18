def tribonacci(n: int) -> int:
    if n == 0:
        return 0
    if n in (1, 2):
        return 1

    a, b, c = 0, 1, 1
    for _ in range(3, n + 1):
        a, b, c = b, c, a + b + c
    return c


print(tribonacci(15))  