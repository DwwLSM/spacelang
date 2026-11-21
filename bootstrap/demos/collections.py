words = ["alpha", "beta", "gamma"]
total = 0
for word in words:
    total = total + len(word)
print(total)

counts = {}
for word in words:
    counts[word] = len(word)
print(counts)

text = "space"
print(text.upper())
print(text[1])
print(text[0:3])
print(text[::-1])

squares = [value * value for value in range(5)]
print(squares)

copied = {key: value for key, value in counts.items()}
print(copied)

pairs = []
for key, value in counts.items():
    pairs.append((key, value))
print(pairs)

letters = set("aab")
print(len(letters))
