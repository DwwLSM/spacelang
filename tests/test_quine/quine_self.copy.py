def __spacelang_quine_hook_0():
    import os
    source = __file__
    root, extension = os.path.splitext(source)
    with open(source, 'rb') as source_file:
        contents = source_file.read()
    with open(root + '.copy' + extension, 'wb') as copy_file:
        copy_file.write(contents)
__spacelang_quine_hook_0()
del __spacelang_quine_hook_0
print("Hello from the SpaceLang quine demo.")
