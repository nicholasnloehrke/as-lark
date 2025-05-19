from lark import Tree, Visitor, Token
from enum import Enum
import difflib
from errors import Formatter
from exceptions import UnknownLabelException, ImmediateOutOfRangeException


class Assembler(Visitor):
    class OpCode(Enum):
        ADD = 0b0000
        SUB = 0b0001
        SLT = 0b0010
        LI = 0b0011
        LW = 0b0100
        SW = 0b0101
        BEQ = 0b0110
        BNE = 0b0111
        PUSH = 0b1000
        POP = 0b1001
        J = 0b1010
        JAL = 0b1011
        JR = 0b1100
        NOP = 0b1101

    def __init__(self, text, file_name):
        self._statement_counter = 0
        self._data_counter = 0
        self._labels = {}
        self._data_decls = {}
        self._identifiers = []
        self._instructions = []
        self._data = []
        self._machine_code = []
        self._text = text
        self._file_name = file_name

    def statement(self, tree: Tree):
        """
        Processes a statement node from the parse tree.
        Extracts any label and maps it to the current instruction index.
        Extracts and stores the instruction opcode and its tokens.
        """
        label = list(tree.find_data("label"))
        if len(label) > 0:
            label = label[0].children[0].value
            self._labels[label] = self._statement_counter
        instr = next(tree.find_data("instruction")).children[0]
        op = self.OpCode[instr.data.upper()]
        tokens = instr.scan_values(lambda v: isinstance(v, Token))
        self._instructions.append((op, tokens))
        self._statement_counter += 1

    def data_decl(self, tree: Tree):
        """
        Processes a data declaration node from the parse tree.
        Maps the label to the current data counter.
        """
        label = tree.children[0].children[0].value
        token = tree.children[1].children[0]
        self._data_decls[label] = self._data_counter
        self._data.append((self.OpCode.NOP, token))
        self._data_counter += 1

    def identifier(self, tree: Tree):
        self._identifiers.append(tree.children[0].value)

    def visit(self, tree):
        """
        Walks parse tree and resolves labels to absolute addresses.
        """
        new_tree = super().visit(tree)

        # Move data section after instructions in memory
        self._data_decls = {k: v + self._statement_counter for k, v in self._data_decls.items()}

        # Resolve labels
        for op, tokens in self._instructions:
            args = []
            for token in tokens:
                value = -1
                match token.type:
                    case "REGISTER":
                        value = int(token[1:])
                    case "CNAME":
                        value = self._find_label_addr(token)
                    case "NUMBER":
                        value = int(token, 0)
                    case _:
                        raise ValueError(token)

                if not 0 <= value <= 31:
                    e = ImmediateOutOfRangeException()
                    e.token = token
                    raise e

                args.append(value)

            self._machine_code.append((self._opcode_to_machine(op, args), (op, args)))

        # Fill data section
        for op, token in self._data:
            value = int(token)
            if not 0 <= value <= 31:
                e = ImmediateOutOfRangeException()
                e.token = token
                raise e
            self._machine_code.append((self._opcode_to_machine(op, args), (op, args)))

        # Warn for unused data
        declared = set(self._data_decls.keys())
        used = set(self._identifiers)
        unused = declared - used
        for item in unused:
            print(
                Formatter.fmt(
                    self._file_name,
                    self._text,
                    f"unused data '{item}'.",
                    -1,
                    -1,
                    -1,
                    level=Formatter.Level.WARNING,
                )
            )

        return new_tree

    def _find_closest_label(self, token):
        all_keys = list(self._labels.keys()) + list(self._data_decls.keys())
        closest_matches = difflib.get_close_matches(token, all_keys, n=1)

        return closest_matches[0] if closest_matches else None

    def _find_label_addr(self, token):
        try:
            return self._labels[token]
        except KeyError:
            try:
                return self._data_decls[token]
            except KeyError:
                e = UnknownLabelException()
                e.closest = self._find_closest_label(token)
                e.token = token
                raise e

    def _opcode_to_machine(self, op: OpCode, args: list[int]):
        """
        Converts an opcode and its arguments into a machine code instruction.

        Instruction encoding format:
        The instruction is encoded into an 11-bit binary format. The first 4 bits
        represent the opcode, followed by operand bits depending on the instruction type.

        R-Type Format (used for register operations: ADD, SUB, SLT):
            [ 4 bits opcode | 2 bits reg1 | 3 bits reg2 | 2 bits reg3 ]
            Total: 11 bits
            - reg1: Destination register
            - reg2: Source register 1
            - reg3: Source register 2

        I-Type Format (used for immediate and memory operations: LI, LW, SW, BEQ, BNE, PUSH, POP):
            [ 4 bits opcode | 2 bits reg | 5 bits immediate ]
            Total: 11 bits
            - reg: Target register
            - immediate: Immediate value or offset

        J-Type Format (used for jumps: J, JAL, JR):
            [ 4 bits opcode | 7 bits address ]
            Total: 11 bits
            - address: Target address or label

        NOP (No Operation):
            Encoded as the opcode with the remaining bits set to zero:
            [ 4 bits opcode | 7 bits zero ]

        """

        def r_type(op, args):
            return op.value << 7 | args[0] << 5 | args[1] << 2 | args[2] & 0b11111111111

        def i_type(op, args):
            machine = op.value << 7 | args[0] << 5
            if len(args) > 1:
                machine |= args[1]
            return machine & 0b11111111111

        def j_type(op, args):
            machine = op.value << 7
            if args:
                machine |= args[0]
            return machine & 0b11111111111

        match op:
            case self.OpCode.ADD | self.OpCode.SUB | self.OpCode.SLT:
                return r_type(op, args)
            case (
                self.OpCode.LI
                | self.OpCode.LW
                | self.OpCode.SW
                | self.OpCode.BEQ
                | self.OpCode.BNE
                | self.OpCode.PUSH
                | self.OpCode.POP
            ):
                return i_type(op, args)
            case self.OpCode.J | self.OpCode.JAL | self.OpCode.JR:
                return j_type(op, args)
            case self.OpCode.NOP:
                if args:
                    return self.OpCode.NOP.value << 7 | args[0] & 0b11111111111
                return self.OpCode.NOP.value << 7 & 0b11111111111

    @property
    def machine_code(self):
        return self._machine_code
