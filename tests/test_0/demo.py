
from math import sqrt

def main(str):
    for i in range(10):
        print(f"Hello: {i}, {str}", 1, sep=" ,  ")

    a = [i for i in range(5)]

main("test")

sum = 0
for i in range(100000):
    sum += sqrt(i) * sqrt(2)

print(sum)