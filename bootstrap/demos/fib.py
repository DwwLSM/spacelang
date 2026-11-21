def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


total = 0
i = 0
while i < 10:
    value = fib(i)
    total = total + value
    print(f"fib({i}) = {value}")
    i = i + 1
print(f"sum = {total}")
