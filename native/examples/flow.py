score = 0
for i in range(10):
    if i == 3:
        score = score + 10
    elif i == 5:
        score = score + 100
    else:
        score = score + 1
print(score)

msg = "value: " + str(score)
print(msg)
print(not (score < 0))

n = 1
while n < 100:
    n = n * 2
print(n)

print(1 + 2 * 3 - 4 // 2)
print(10 % 3, 2 ** 8)
