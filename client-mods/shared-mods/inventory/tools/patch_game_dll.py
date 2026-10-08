"""Small native-code assembler; no menu or shop hooks."""
import struct

class Assembler:
    def __init__(self, base):
        self.base = base
        self.code = bytearray()
        self.labels = {}
        self.fixups = []

    def emit(self, data):
        self.code.extend(data)

    def label(self, name):
        self.labels[name] = len(self.code)

    def branch(self, opcode, label):
        self.emit(opcode)
        self.fixups.append((len(self.code), label))
        self.emit(bytes(4))

    def relative(self, opcode, target):
        self.emit(opcode)
        self.emit(struct.pack('<i', target - self.base - len(self.code) - 4))

    def finish(self):
        for pos, name in self.fixups:
            self.code[pos:pos + 4] = struct.pack('<i', self.labels[name] - pos - 4)
        return bytes(self.code)
