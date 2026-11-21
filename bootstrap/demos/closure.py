def make_adder(step):
    def add(value):
        return value + step

    return add


def make_counter():
    state = [0]

    def bump():
        state[0] = state[0] + 1
        return state[0]

    return bump


add_two = make_adder(2)
print(add_two(40))

add_seven = make_adder(7)
print(add_seven(35))

counter = make_counter()
print(counter())
print(counter())
print(counter())
