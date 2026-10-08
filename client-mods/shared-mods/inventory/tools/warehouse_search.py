"""Native Search/Clear handlers for the two Aion 4.8 warehouse lists.

Search dims nonmatching items in their original slots, so storage positions and
item actions remain the client's own. The hook runs only when one of four named
warehouse buttons is clicked. The existing Inventory search draw path remains
the fallback for every other item list.
"""

import struct
import xml.etree.ElementTree as ET

from warehouse_patch import ACCOUNT_SLOTS, CHARACTER_SLOTS


EVENT_SITE = 0x948150
DRAW_SITE = 0x4F2079
INVENTORY_DRAW = 0x144EB00
MATCH = 0x144E100
CODE = 0xE8F800
STATE_CHARACTER = 0xE93000
STATE_ACCOUNT = 0xE93400
STRINGS = 0xE93A00
END = 0xE95000


class Assembler:
    def __init__(self, base):
        self.base = base
        self.code = bytearray()
        self.labels = {}
        self.fixups = []

    def emit(self, value):
        self.code.extend(value)

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
        for pos, label in self.fixups:
            self.code[pos:pos + 4] = struct.pack('<i', self.labels[label] - pos - 4)
        return bytes(self.code)


def emit(a, value):
    a.emit(bytes.fromhex(value))


NAMES = (
    'warehouse_character_search', 'warehouse_character_clear',
    'warehouse_account_search', 'warehouse_account_clear',
    'warehouse_character_query', 'warehouse_account_query',
)
TEXT = {}
string_bytes = bytearray()
for name in NAMES:
    TEXT[name] = STRINGS + len(string_bytes)
    string_bytes.extend(name.encode('ascii') + b'\0')
if len(string_bytes) & 1:
    string_bytes.append(0)
TEXT['empty'] = STRINGS + len(string_bytes)
string_bytes.extend(b'\0\0')


def search_widgets(dialog):
    """Add native editboxes and explicit Search/Clear buttons to each panel."""
    personal = dialog.find("Widget[@name='personal_container']")
    account = personal.find("Widget[@name='account_container']")
    personal.find("Widget[@name='personal_warehouse']").set('frame', '15,58,560,240')
    account.find("Widget[@name='account_warehouse']").set('frame', '15,60,560,210')
    for parent, label in [(personal, 'character'), (account, 'account')]:
        # Rebuilding a combined package must also accept our installed layout.
        for suffix in ('query', 'search', 'clear'):
            for existing in parent.findall("Widget[@name='warehouse_" + label + '_' + suffix + "']"):
                parent.remove(existing)
        ET.SubElement(parent, 'Widget', dict(type='editbox', name='warehouse_' + label + '_query', frame='15,30,330,24',
                     preset='v5_editbox', font='ui_editbox', h_padding='4', v_padding='4',
                     alphanumeric='False', tabstop='1', max_length='63'))
        ET.SubElement(parent, 'Widget', dict(type='button', name='warehouse_' + label + '_search', frame='350,30,95,24',
                     preset='v5_button', font='ui_default', text='STR_WHO_DIALOG__SEARCH'))
        ET.SubElement(parent, 'Widget', dict(type='button', name='warehouse_' + label + '_clear', frame='450,30,95,24',
                     preset='v5_button', font='ui_default', text='STR_PARTY_MATCH_DIALOG__SEARCH_CANCEL'))
    # The account panel's coordinates are relative to its own container.
    return dialog


def _lookup(a, name, kind):
    emit(a, '4c89e1498b0424')  # rcx=r12 dialog, rax=dialog vtable
    a.relative(b'\x48\x8d\x15', TEXT[name])
    a.emit(b'\x41\xb8' + struct.pack('<I', kind))
    emit(a, 'ff9038030000')  # FindWidget(name, kind)


def _scanner(base, state, list_offset, query, limit):
    a = Assembler(base)
    # Eight nonvolatile registers plus 0x28 bytes of aligned shadow space.
    emit(a, '5355565741544155415641574883ec28')
    emit(a, '4989cc')  # r12=dialog
    a.relative(b'\x4c\x8d\x2d', state)
    a.emit(bytes.fromhex('4d8bb4') + bytes([0x24]) + struct.pack('<I', list_offset))  # r14=[r12+offset]
    emit(a, '4d85f6')
    a.branch(b'\x0f\x84', 'done')
    emit(a, '4d897500')  # [state]=list pointer
    _lookup(a, query, 0x200B)
    emit(a, '4885c0')
    a.branch(b'\x0f\x84', 'done')
    emit(a, '4889c1488b00ff9098020000')  # editbox GetText
    emit(a, '4989c7')  # r15=query
    emit(a, '41c7450800000000')  # inactive until nonempty
    emit(a, '498d7d2031c0b9')
    a.emit(struct.pack('<I', limit))
    emit(a, 'f3aa')  # clear previous match flags
    emit(a, '4d85ff')
    a.branch(b'\x0f\x84', 'done')
    emit(a, '6641833f00')
    a.branch(b'\x0f\x84', 'done')
    emit(a, '41c7450801000000')  # active search
    emit(a, '498b9eb8030000498baec00300004829dd48c1ed03')
    emit(a, '31f6')  # index=0
    a.label('loop')
    emit(a, '81fe')
    a.emit(struct.pack('<I', limit))
    a.branch(b'\x0f\x83', 'done')
    emit(a, '4839ee')  # index compared with the native list vector length
    a.branch(b'\x0f\x83', 'done')
    emit(a, '488b3cf34885ff')  # slot=[rbx+rsi*8]
    a.branch(b'\x0f\x84', 'next')
    emit(a, '448b87940000004585c0')
    a.branch(b'\x0f\x84', 'next')
    a.relative(b'\x48\x8b\x0d', 0x12EDA48)
    emit(a, '4885c9')
    a.branch(b'\x0f\x84', 'next')
    emit(a, '8b97980000004531c9')
    a.relative(b'\xe8', 0x444030)
    emit(a, '4885c0')
    a.branch(b'\x0f\x84', 'next')
    emit(a, '488d48204883783808')
    a.branch(b'\x0f\x82', 'name')
    emit(a, '488b4820')
    a.label('name')
    emit(a, '4885c9')
    a.branch(b'\x0f\x84', 'next')
    emit(a, '4c89fa')
    a.relative(b'\xe8', MATCH)
    emit(a, '85c0')
    a.branch(b'\x0f\x84', 'next')
    emit(a, '4c89e84801f0c6402001')  # state[index+0x20]=1
    a.label('next')
    emit(a, 'ffc6')
    a.branch(b'\xe9', 'loop')
    a.label('done')
    emit(a, '4883c428415f415e415d415c5f5e5d5bc3')
    return a.finish()


def _clear(base, query, scanner):
    a = Assembler(base)
    emit(a, '5341544883ec284889cb4989cc')
    _lookup(a, query, 0x200B)
    emit(a, '4885c0')
    a.branch(b'\x0f\x84', 'scan')
    emit(a, '4889c1488b00')
    a.relative(b'\x48\x8d\x15', TEXT['empty'])
    emit(a, 'ff9090020000')
    a.label('scan')
    emit(a, '4889d9')
    a.relative(b'\xe8', scanner)
    emit(a, '4883c428415c5bc3')
    return a.finish()


def _dispatch(base, scanners, clears):
    a = Assembler(base)
    emit(a, '53564883ec284889cb488b32')  # rbx=dialog, rsi=clicked widget
    for index, name in enumerate(NAMES[:4]):
        emit(a, '488b034889d9')
        a.relative(b'\x48\x8d\x15', TEXT[name])
        emit(a, 'ff90400300004839f0')  # FindWidget(name), compare clicked
        a.branch(b'\x0f\x85', 'next' + str(index))
        emit(a, '4889d9')
        a.relative(b'\xe8', scanners[0 if index < 2 else 1] if index % 2 == 0 else clears[0 if index < 2 else 1])
        emit(a, 'b801000000')
        a.branch(b'\xe9', 'done')
        a.label('next' + str(index))
    emit(a, '31c0')
    a.label('done')
    emit(a, '4883c4285e5bc3')
    return a.finish()


def _event(base, dispatch):
    a = Assembler(base)
    emit(a, '4883ec4848894c242048895424284c894424304c894c2438')
    a.relative(b'\xe8', dispatch)
    emit(a, '488b4c2420488b5424284c8b4424304c8b4c24384883c44885c0')
    a.branch(b'\x0f\x85', 'handled')
    emit(a, '488bc44881ec88000000')
    a.relative(b'\xe9', EVENT_SITE + 10)
    a.label('handled')
    emit(a, '31c0c3')
    return a.finish()


def _draw(base):
    a = Assembler(base)
    emit(a, '5052488b13488d05')
    a.emit(struct.pack('<i', STATE_CHARACTER - (base + len(a.code) + 4)))
    emit(a, '483910')
    a.branch(b'\x0f\x85', 'account')
    emit(a, '83780800')
    a.branch(b'\x0f\x84', 'fallback')
    emit(a, '8b939000000081fa')
    a.emit(struct.pack('<I', CHARACTER_SLOTS))
    a.branch(b'\x0f\x83', 'fallback')
    emit(a, '807c102000')
    a.branch(b'\x0f\x84', 'dim')
    a.branch(b'\xe9', 'fallback')
    a.label('account')
    a.relative(b'\x48\x8d\x05', STATE_ACCOUNT)
    emit(a, '483910')
    a.branch(b'\x0f\x85', 'fallback')
    emit(a, '83780800')
    a.branch(b'\x0f\x84', 'fallback')
    emit(a, '8b939000000081fa')
    a.emit(struct.pack('<I', ACCOUNT_SLOTS))
    a.branch(b'\x0f\x83', 'fallback')
    emit(a, '807c102000')
    a.branch(b'\x0f\x85', 'fallback')
    a.label('dim')
    for reg in (10, 11, 12):
        a.branch(b'\xf3\x44\x0f\x59' + bytes([0x05 | ((reg & 7) << 3)]), 'factor')
    emit(a, '5a58f20f118c24c8000000')
    a.relative(b'\xe9', DRAW_SITE + 9)
    a.label('fallback')
    emit(a, '5a58')
    a.relative(b'\xe9', INVENTORY_DRAW)
    a.label('factor')
    a.emit(struct.pack('<f', 0.28))
    return a.finish()


def patch_search_dll(payload):
    data = bytearray(payload)
    event_original = bytes.fromhex('488bc44881ec88000000')
    if data[EVENT_SITE:EVENT_SITE + 10] != event_original:
        raise ValueError('Unsupported warehouse button handler')
    expected_draw = b'\xe9' + struct.pack('<i', INVENTORY_DRAW - DRAW_SITE - 5) + b'\x90' * 4
    if data[DRAW_SITE:DRAW_SITE + 9] != expected_draw:
        raise ValueError('Inventory search draw hook is required before warehouse search')
    if any(data[CODE:END]):
        raise ValueError('Warehouse search code/state region is not empty')
    blocks = {}
    cursor = CODE
    def add(name, build):
        nonlocal cursor
        cursor = (cursor + 15) & ~15
        result = build(cursor)
        blocks[name] = (cursor, result)
        cursor += len(result)
        if cursor >= STATE_CHARACTER:
            raise ValueError('Warehouse search code exceeds its reserved region')
    add('scan_char', lambda base: _scanner(base, STATE_CHARACTER, 0x540, NAMES[4], CHARACTER_SLOTS))
    add('scan_account', lambda base: _scanner(base, STATE_ACCOUNT, 0x548, NAMES[5], ACCOUNT_SLOTS))
    add('clear_char', lambda base: _clear(base, NAMES[4], blocks['scan_char'][0]))
    add('clear_account', lambda base: _clear(base, NAMES[5], blocks['scan_account'][0]))
    add('dispatch', lambda base: _dispatch(base, [blocks['scan_char'][0], blocks['scan_account'][0]],
                                           [blocks['clear_char'][0], blocks['clear_account'][0]]))
    add('event', lambda base: _event(base, blocks['dispatch'][0]))
    add('draw', _draw)
    for base, code in blocks.values():
        data[base:base + len(code)] = code
    data[STRINGS:STRINGS + len(string_bytes)] = string_bytes
    data[EVENT_SITE:EVENT_SITE + 10] = b'\xe9' + struct.pack('<i', blocks['event'][0] - EVENT_SITE - 5) + b'\x90' * 5
    data[DRAW_SITE:DRAW_SITE + 9] = b'\xe9' + struct.pack('<i', blocks['draw'][0] - DRAW_SITE - 5) + b'\x90' * 4
    return bytes(data)
