# 本动画基于 DwwLSM/spacelang 仓库的实际 README 与源码生成；Phase 3 空白语义已核实。
# Phase 3 的八个换行在 .sp 中解码为八条 NOP，VM.run() 返回 None。
# C++ 基准仅报告本机测量结果，动画不声称 computed-goto 必然更快。

from manim import *
from manim import Text as ManimText


BG = "#071318"
PANEL = "#10232A"
PANEL_EDGE = "#28505A"
CYAN = "#63D8E8"
GREEN = "#75E0A2"
GOLD = "#F4C66A"
ALERT = "#FF5968"
TEXT = "#EDF5F4"
MUTED = "#9AB1B5"


def Text(*args, **kwargs):
    kwargs.setdefault("font", "Noto Sans CJK SC")
    return ManimText(*args, **kwargs)


class SpacelangIntroWithSubtitle(Scene):
    show_subtitles = True
    language = "en"

    def localized(self, chinese, english):
        return chinese if self.language == "zh" else english

    def caption(self, chinese, english):
        background = RoundedRectangle(
            corner_radius=0.06,
            width=13.0,
            height=0.78,
            stroke_width=0,
            fill_color="#081317",
            fill_opacity=0.96,
        ).move_to(DOWN * 3.34)
        subtitle = Text(
            self.localized(chinese, english),
            font="Noto Sans CJK SC",
            font_size=17,
            line_spacing=0.9,
            color=TEXT,
        ).move_to(DOWN * 3.34)
        caption_group = VGroup(background, subtitle)
        if not self.show_subtitles:
            caption_group.set_opacity(0)
        return caption_group

    def show_real_program_demo(self, previous_scene):
        title = Text(
            self.localized("真实程序：2 + 3 = 5", "Real Program: 2 + 3 = 5"),
            font_size=30,
            color=TEXT,
        ).to_edge(UP, buff=0.35)
        self.play(FadeOut(previous_scene), FadeIn(title), run_time=0.8)

        panel_width = 4.05
        panel_height = 4.7

        def make_panel(label, center, color):
            frame = RoundedRectangle(
                corner_radius=0.08,
                width=panel_width,
                height=panel_height,
                stroke_color=color,
                fill_color="#0B171C",
                fill_opacity=1,
            ).move_to(center)
            header = Rectangle(
                width=panel_width - 0.02,
                height=0.48,
                stroke_width=0,
                fill_color="#172A30",
                fill_opacity=1,
            ).move_to(frame.get_top() + DOWN * 0.24)
            label_text = Text(
                label,
                font="DejaVu Sans Mono",
                font_size=12,
                color=MUTED,
            ).move_to(header.get_center() + LEFT * 1.35)
            return VGroup(frame, header, label_text), frame, header

        source_group, source_panel, source_header = make_panel(
            "example.sp",
            LEFT * 4.55 + UP * 0.05,
            CYAN,
        )
        assembly_group, assembly_panel, _ = make_panel(
            "example.spasm",
            UP * 0.05,
            GOLD,
        )
        stack_group, stack_panel, _ = make_panel(
            self.localized("VM 栈", "VM Stack"),
            RIGHT * 4.55 + UP * 0.05,
            GREEN,
        )

        run_button = RoundedRectangle(
            corner_radius=0.05,
            width=0.78,
            height=0.28,
            stroke_color=GREEN,
            fill_color="#18352B",
            fill_opacity=1,
        ).move_to(source_header.get_center() + RIGHT * 1.4)
        run_label = Text(
            self.localized("运行", "RUN"),
            font="DejaVu Sans Mono",
            font_size=9,
            color=GREEN,
        ).move_to(run_button)

        space_counts = [7, 4, 7, 6, 5, 1, 29]
        space_lines = VGroup(
            *[
                Text("·" * count, font="DejaVu Sans Mono", font_size=11, color=TEXT)
                for count in space_counts
            ]
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.13)
        space_lines.move_to(source_panel.get_center() + UP * 0.16)
        space_note = Text(
            self.localized("· 代表一个空格", "· represents one space"),
            font_size=11,
            color=MUTED,
        ).move_to(source_panel.get_bottom() + UP * 0.4)
        typing_cursor = Rectangle(
            width=0.025,
            height=0.2,
            stroke_width=0,
            fill_color=GREEN,
            fill_opacity=1,
        ).move_to(space_lines[0].get_left() + LEFT * 0.1)

        assembly_mnemonics = ("PUSH_INT 2", "PUSH_INT 3", "OP 1", "HALT")
        assembly_lines = VGroup(
            *[
                Text(line, font="DejaVu Sans Mono", font_size=15, color=TEXT)
                for line in assembly_mnemonics
            ]
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        assembly_lines.move_to(assembly_panel.get_center() + UP * 0.35)
        assemble_note = Text(
            "spacelang asm example.spasm example.sp",
            font="DejaVu Sans Mono",
            font_size=8.5,
            color=MUTED,
        ).move_to(assembly_panel.get_bottom() + UP * 0.4)
        stack_state = Text("[]", font="DejaVu Sans Mono", font_size=30, color=GREEN)
        stack_state.move_to(stack_panel.get_center())
        result_panel = RoundedRectangle(
            corner_radius=0.06,
            width=12.4,
            height=0.62,
            stroke_color=GREEN,
            fill_color="#10261D",
            fill_opacity=1,
        ).move_to(DOWN * 2.66)
        result_text = Text(
            "VM(program).run() -> 5",
            font="DejaVu Sans Mono",
            font_size=15,
            color=GREEN,
        ).move_to(result_panel)
        result_text.set_opacity(0)

        self.play(
            FadeIn(source_group),
            FadeIn(assembly_group),
            FadeIn(stack_group),
            FadeIn(run_button),
            FadeIn(run_label),
            FadeIn(space_note),
            FadeIn(assemble_note),
            FadeIn(stack_state),
            FadeIn(result_panel),
            FadeIn(result_text),
            FadeIn(typing_cursor),
            run_time=1.0,
        )

        instruction_for_token = {1: 0, 3: 1, 5: 2, 6: 3}
        for token_index, space_line in enumerate(space_lines):
            animations = [Write(space_line)]
            if token_index > 0:
                animations.append(
                    typing_cursor.animate.move_to(space_line.get_left() + LEFT * 0.1)
                )
            if token_index in instruction_for_token:
                instruction_index = instruction_for_token[token_index]
                animations.append(Write(assembly_lines[instruction_index]))
            self.play(*animations, run_time=0.38)

        # Execute each disassembled instruction and update the live stack.
        self.play(run_button.animate.set_fill(GREEN, opacity=0.85), run_time=0.25)
        for line_index, value in enumerate(("[2]", "[2, 3]", "[5]")):
            self.play(
                Indicate(assembly_lines[line_index], color=GOLD),
                Transform(
                    stack_state,
                    Text(value, font="DejaVu Sans Mono", font_size=30, color=GREEN).move_to(stack_state),
                ),
                run_time=0.7,
            )
        self.play(
            Indicate(assembly_lines[3], color=GOLD),
            result_text.animate.set_opacity(1),
            run_time=0.7,
        )
        subtitle = self.caption(
            "点号只用于显示空格：.sp 的 7 个 token 解码为 4 条指令，运行结果是 5。",
            "Dots visualize spaces: seven .sp tokens decode to four instructions; execution returns 5.",
        )
        self.play(FadeIn(subtitle), run_time=0.8)
        self.wait(8.0)

        return VGroup(
            title,
            source_group,
            assembly_group,
            stack_group,
            run_button,
            run_label,
            space_lines,
            space_note,
            typing_cursor,
            assembly_lines,
            assemble_note,
            stack_state,
            result_panel,
            result_text,
            subtitle,
        )

    def show_large_integer_demo(self):
        title = Text(
            self.localized("大整数：别堆 10 万个空格", "Large Integers: Don't Count 100,000 Spaces"),
            font_size=28,
            color=TEXT,
        ).to_edge(UP, buff=0.35)
        self.play(FadeIn(title), run_time=0.8)

        panel_width = 4.05
        panel_height = 4.55

        def make_panel(label, center, color):
            frame = RoundedRectangle(
                corner_radius=0.08,
                width=panel_width,
                height=panel_height,
                stroke_color=color,
                fill_color="#0B171C",
                fill_opacity=1,
            ).move_to(center)
            header = Rectangle(
                width=panel_width - 0.02,
                height=0.48,
                stroke_width=0,
                fill_color="#172A30",
                fill_opacity=1,
            ).move_to(frame.get_top() + DOWN * 0.24)
            header_text = Text(
                label,
                font="DejaVu Sans Mono",
                font_size=11,
                color=MUTED,
            ).move_to(header.get_center() + LEFT * 1.25)
            return VGroup(frame, header, header_text), frame

        raw_group, raw_panel = make_panel(
            self.localized("直接编码", "DIRECT TOKEN"),
            LEFT * 4.55 + UP * 0.05,
            ALERT,
        )
        factor_group, factor_panel = make_panel(
            "--compress-source",
            UP * 0.05,
            GOLD,
        )
        stack_group, stack_panel = make_panel(
            self.localized("运行时栈", "VM STACK"),
            RIGHT * 4.55 + UP * 0.05,
            GREEN,
        )

        raw_rows = VGroup(
            Text("print(100000)", font="DejaVu Sans Mono", font_size=11, color=TEXT),
            Text("PUSH_INT 100000", font="DejaVu Sans Mono", font_size=11, color=TEXT),
            Text(
                self.localized("参数: 200,000 个空格", "argument: 200,000 spaces"),
                font="Noto Sans Mono CJK SC",
                font_size=10,
                color=TEXT,
            ),
            Text("· × 200,000", font="DejaVu Sans Mono", font_size=15, color=ALERT),
            Text(
                self.localized("单 token 上限: 65,535", "per-token limit: 65,535"),
                font="Noto Sans Mono CJK SC",
                font_size=10,
                color=ALERT,
            ),
        ).arrange(DOWN, buff=0.22)
        raw_rows.move_to(raw_panel.get_center() + DOWN * 0.05)

        factor_rows = VGroup(
            Text("100000 = 2^5 * 5^5", font="DejaVu Sans Mono", font_size=12, color=GOLD),
            Text("PUSH_INT 2", font="DejaVu Sans Mono", font_size=11, color=TEXT),
            Text("(PUSH_INT 2; OP 3) x 4", font="DejaVu Sans Mono", font_size=10, color=TEXT),
            Text("(PUSH_INT 5; OP 3) x 5", font="DejaVu Sans Mono", font_size=10, color=TEXT),
            Text(
                self.localized("OP 3 = 乘法", "OP 3 = multiply"),
                font="Noto Sans Mono CJK SC",
                font_size=10,
                color=MUTED,
            ),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.22)
        factor_rows.move_to(factor_panel.get_center() + DOWN * 0.02)

        stack_state = Text("[]", font="DejaVu Sans Mono", font_size=25, color=GREEN)
        stack_state.move_to(stack_panel.get_center() + UP * 0.25)
        stdout_text = Text(
            "stdout: 100000",
            font="DejaVu Sans Mono",
            font_size=12,
            color=GREEN,
        ).move_to(stack_panel.get_center() + DOWN * 0.75)
        stdout_text.set_opacity(0)
        command = Text(
            "spacelang compile-py large.py large.sp --compress-source  &&  spacelang run large.sp",
            font="DejaVu Sans Mono",
            font_size=9,
            color=MUTED,
        ).move_to(DOWN * 2.58)

        self.play(
            FadeIn(raw_group),
            FadeIn(factor_group),
            FadeIn(stack_group),
            FadeIn(raw_rows[0]),
            FadeIn(raw_rows[1]),
            FadeIn(stack_state),
            FadeIn(command),
            run_time=1.0,
        )
        self.play(
            FadeIn(VGroup(*raw_rows[2:])),
            Indicate(raw_rows[3], color=ALERT),
            run_time=1.0,
        )
        self.play(Write(factor_rows[0]), run_time=0.8)
        self.play(FadeIn(VGroup(*factor_rows[1:])), run_time=1.0)
        for value, highlight in (
            ("[2]", factor_rows[1]),
            ("[32]", factor_rows[2]),
            ("[160]", factor_rows[3]),
            ("[800]", factor_rows[3]),
            ("[4,000]", factor_rows[3]),
            ("[20,000]", factor_rows[3]),
            ("[100,000]", factor_rows[3]),
        ):
            self.play(
                Indicate(highlight, color=GOLD),
                Transform(
                    stack_state,
                    Text(value, font="DejaVu Sans Mono", font_size=25, color=GREEN).move_to(stack_state),
                ),
                run_time=0.45,
            )
        self.play(stdout_text.animate.set_opacity(1), run_time=0.5)
        subtitle = self.caption(
            "100000 需要 200000 个空格，超过单 token 上限 65535。\n"
            "--compress-source 用小因数和乘法重建。",
            "100000 needs 200000 spaces, beyond the 65535 token limit.\n"
            "--compress-source rebuilds it from small factors and multiplies.",
        )
        self.play(FadeIn(subtitle), run_time=0.8)
        self.wait(4.0)
        self.play(
            FadeOut(
                VGroup(
                    title,
                    raw_group,
                    factor_group,
                    stack_group,
                    raw_rows,
                    factor_rows,
                    stack_state,
                    stdout_text,
                    command,
                    subtitle,
                )
            ),
            run_time=0.8,
        )

    def file_icon(self, label, color):
        frame = RoundedRectangle(
            corner_radius=0.08,
            width=1.4,
            height=1.65,
            stroke_color=color,
            stroke_width=2,
            fill_color=PANEL,
            fill_opacity=1,
        )
        fold = Line(
            frame.get_corner(UR) + LEFT * 0.38,
            frame.get_corner(UR) + LEFT * 0.38 + DOWN * 0.38,
            color=color,
            stroke_width=2,
        )
        label_size = 13 if len(label) <= 16 else 9.5
        label_text = Text(label, font="DejaVu Sans Mono", font_size=label_size, color=TEXT)
        label_text.next_to(frame, DOWN, buff=0.12)
        return VGroup(frame, fold, label_text)

    def construct(self):
        self.camera.background_color = BG

        # Part A 的神圣留白在此落到一个可追踪的程序状态。
        blank_mark = VGroup(
            Line(LEFT * 1.7, RIGHT * 1.7, color=CYAN, stroke_width=2),
            Line(LEFT * 1.7 + DOWN * 0.32, RIGHT * 1.7 + DOWN * 0.32, color=CYAN, stroke_width=2),
            Line(LEFT * 1.7 + DOWN * 0.64, RIGHT * 1.7 + DOWN * 0.64, color=CYAN, stroke_width=2),
        ).move_to(UP * 0.65)
        opening = Text(
            self.localized("空白之后，秩序开始运行", "After the blank, order begins to run"),
            font_size=34,
            color=TEXT,
        )
        opening.to_edge(DOWN, buff=1.2)
        self.play(FadeIn(blank_mark, lag_ratio=0.2), run_time=2.2)
        if self.show_subtitles:
            self.play(Write(opening), run_time=1.7)
        else:
            self.wait(1.7)
        self.wait(3.0)
        self.play(FadeOut(blank_mark), FadeOut(opening), run_time=1.2)

        # ===== Phase 1 =====
        title = Text(
            self.localized("SpaceLang：基于栈的语言", "SpaceLang: A Stack-Based Language"),
            font_size=34,
            color=TEXT,
        )
        title.to_edge(UP, buff=0.35)

        source_box = RoundedRectangle(
            corner_radius=0.08,
            width=4.35,
            height=4.75,
            stroke_color=PANEL_EDGE,
            fill_color=PANEL,
            fill_opacity=0.92,
        ).move_to(LEFT * 4.55 + DOWN * 0.1)
        source_heading = Text(
            self.localized("Python 子集源码", "Python-subset source"),
            font_size=18,
            color=CYAN,
        )
        source_heading.move_to(source_box.get_top() + DOWN * 0.36)
        source_code = Text(
            "def add(a, b):\n"
            "    return a + b\n"
            "i = 0\n"
            "while i < 3:\n"
            "    print(add(i, 2))\n"
            "    i = i + 1",
            font="DejaVu Sans Mono",
            font_size=14,
            color=TEXT,
            line_spacing=0.72,
        )
        source_code.move_to(source_box.get_center() + DOWN * 0.1)
        source_tag = Text(
            self.localized(
                "compile_py(source) | 输出: 2, 3, 4",
                "compile_py(source) | stdout: 2, 3, 4",
            ),
            font="DejaVu Sans Mono",
            font_size=12,
            color=MUTED,
        )
        source_tag.next_to(source_code, DOWN, buff=0.3)

        asm_box = RoundedRectangle(
            corner_radius=0.08,
            width=4.35,
            height=4.75,
            stroke_color=PANEL_EDGE,
            fill_color=PANEL,
            fill_opacity=0.92,
        ).move_to(RIGHT * 4.55 + DOWN * 0.1)
        asm_heading = Text(
            self.localized("真实字节码节选", "Actual bytecode excerpt"),
            font_size=18,
            color=GOLD,
        )
        asm_heading.move_to(asm_box.get_top() + DOWN * 0.36)
        instructions = [
            "LOAD_LOCAL 0",
            "LOAD_LOCAL 1",
            "OP 1",
            "RET",
            "PUSH_INT 3",
            "OP 7",
            "JZ while_exit_9",
            "PUSH_INT 2",
            "CALL 10000 2",
            "CALL 0 1",
            "STACK 3",
            "JMP while_loop_9",
        ]
        instruction_lines = VGroup(
            *[
                Text(line, font="DejaVu Sans Mono", font_size=12, color=TEXT)
                for line in instructions
            ]
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.1)
        instruction_lines.move_to(asm_box.get_center() + DOWN * 0.05)
        asm_note = Text(
            self.localized("OP 1 = 加法", "OP 1 = addition"),
            font="DejaVu Sans Mono",
            font_size=13,
            color=MUTED,
        )
        asm_note.next_to(instruction_lines, DOWN, buff=0.28)

        stack_slots = VGroup(
            *[
                Rectangle(width=1.5, height=0.66, stroke_color=CYAN, stroke_width=2)
                for _ in range(3)
            ]
        ).arrange(UP, buff=0.08).move_to(DOWN * 0.15)
        stack_heading = Text(
            self.localized("运行时栈", "Runtime stack"),
            font_size=18,
            color=CYAN,
        )
        stack_heading.next_to(stack_slots, UP, buff=0.4)
        stack_top = Text(self.localized("栈顶", "TOP"), font_size=14, color=GOLD)
        stack_top.next_to(stack_slots[2], RIGHT, buff=0.12)

        # 标题、源码、栈和指令同时建立，让三个视图彼此对应。
        self.play(
            Write(title),
            FadeIn(source_box),
            FadeIn(asm_box),
            Create(stack_slots),
            run_time=2.4,
        )
        self.play(
            FadeIn(source_heading),
            FadeIn(source_code),
            FadeIn(source_tag),
            FadeIn(asm_heading),
            FadeIn(instruction_lines),
            FadeIn(asm_note),
            FadeIn(stack_heading),
            FadeIn(stack_top),
            run_time=2.3,
        )
        self.wait(8.0)

        zero = Text("0", font="DejaVu Sans Mono", font_size=25, color=TEXT).move_to(stack_slots[0])
        two = Text("2", font="DejaVu Sans Mono", font_size=25, color=TEXT).move_to(stack_slots[1])
        # 函数体把两个局部参数依次压到栈上。
        self.play(FadeIn(zero), Indicate(instruction_lines[0]), run_time=1.2)
        self.play(
            FadeIn(two),
            Indicate(instruction_lines[1]),
            stack_top.animate.next_to(stack_slots[1], RIGHT, buff=0.12),
            run_time=1.2,
        )
        result = Text("2", font="DejaVu Sans Mono", font_size=25, color=GREEN).move_to(stack_slots[0])
        # OP 1 弹出两个操作数，把相加结果压回栈顶。
        self.play(
            FadeOut(zero),
            FadeOut(two),
            Indicate(instruction_lines[2], color=GOLD),
            run_time=1.4,
        )
        self.play(
            FadeIn(result),
            stack_top.animate.next_to(stack_slots[0], RIGHT, buff=0.12),
            run_time=1.1,
        )
        self.wait(1.0)
        self.play(Indicate(instruction_lines[3]), FadeOut(result), run_time=1.1)
        self.wait(6.0)
        self.play(Indicate(instruction_lines[8]), Indicate(instruction_lines[9]), run_time=1.4)
        self.play(Indicate(instruction_lines[10]), Indicate(instruction_lines[11]), run_time=1.0)
        phase_one_caption = self.caption(
            "所有运算都在栈顶完成：弹出操作数，再把结果压回栈顶。",
            "Every operation uses the stack top: pop the operands, then push the result back.",
        )
        self.play(FadeIn(phase_one_caption), run_time=1.0)
        self.wait(9.0)
        self.play(
            FadeOut(
                VGroup(
                    title,
                    source_box,
                    source_heading,
                    source_code,
                    source_tag,
                    asm_box,
                    asm_heading,
                    instruction_lines,
                    asm_note,
                    stack_slots,
                    stack_heading,
                    stack_top,
                    result,
                    phase_one_caption,
                )
            ),
            run_time=1.3,
        )

        # ===== Phase 2 =====
        phase_two_title = Text(
            self.localized("同一程序，两种执行引擎", "One Program, Two Engines"),
            font_size=32,
            color=TEXT,
        )
        phase_two_title.to_edge(UP, buff=0.45)
        program_file = self.file_icon("example.sp", CYAN).move_to(LEFT * 4.7 + UP * 0.45)
        py_box = RoundedRectangle(
            corner_radius=0.08,
            width=4.0,
            height=1.65,
            stroke_color=GREEN,
            fill_color=PANEL,
            fill_opacity=1,
        ).move_to(RIGHT * 1.7 + UP * 1.05)
        py_label = Text("Python VM", font_size=25, color=GREEN).move_to(py_box.get_center() + UP * 0.18)
        py_sub = Text(
            self.localized("参考实现", "Reference implementation"),
            font_size=17,
            color=TEXT,
        ).next_to(py_label, DOWN, buff=0.13)
        cpp_box = RoundedRectangle(
            corner_radius=0.08,
            width=4.0,
            height=1.65,
            stroke_color=CYAN,
            fill_color=PANEL,
            fill_opacity=1,
        ).move_to(RIGHT * 1.7 + DOWN * 1.05)
        cpp_label = Text("C++ VM", font_size=25, color=CYAN).move_to(cpp_box.get_center() + UP * 0.18)
        cpp_sub = Text(
            self.localized("实验性原生引擎", "Experimental native engine"),
            font_size=17,
            color=TEXT,
        ).next_to(cpp_label, DOWN, buff=0.13)
        py_arrow = Arrow(program_file.get_right(), py_box.get_left(), color=GREEN, buff=0.22)
        cpp_arrow = Arrow(program_file.get_right() + DOWN * 0.15, cpp_box.get_left(), color=CYAN, buff=0.22)
        dispatch = Text(
            "GCC / Clang: goto *dispatch_table[instr.op]",
            font="DejaVu Sans Mono",
            font_size=13,
            color=CYAN,
        ).move_to(DOWN * 2.28)
        fallback = Text(
            self.localized("其他编译器：switch 分发", "Other compilers: switch dispatch"),
            font_size=15,
            color=MUTED,
        )
        fallback.next_to(dispatch, DOWN, buff=0.14)

        # .sp 程序向两侧分流；C++ 路径展示源码中的分发实现。
        self.play(Write(phase_two_title), FadeIn(program_file), run_time=1.8)
        self.play(Create(py_arrow), Create(cpp_arrow), run_time=1.0)
        self.play(
            FadeIn(py_box), FadeIn(py_label), FadeIn(py_sub),
            FadeIn(cpp_box), FadeIn(cpp_label), FadeIn(cpp_sub),
            run_time=1.8,
        )
        self.play(FadeIn(dispatch), FadeIn(fallback), run_time=1.2)
        self.play(Indicate(dispatch, color=GOLD), run_time=2.0)
        phase_two_caption = self.caption(
            "Python VM 是行为参考；--engine cpp 选择实验性原生 VM。\n"
            "性能取决于本机基准测试，不代表普遍速度保证。",
            "Python VM is the reference; --engine cpp selects the experimental native VM.\n"
            "Performance depends on the local benchmark; there is no universal speed guarantee.",
        )
        self.play(FadeIn(phase_two_caption), run_time=1.0)
        self.wait(15.0)
        self.play(
            FadeOut(
                VGroup(
                    phase_two_title,
                    program_file,
                    py_arrow,
                    cpp_arrow,
                    py_box,
                    py_label,
                    py_sub,
                    cpp_box,
                    cpp_label,
                    cpp_sub,
                    dispatch,
                    fallback,
                    phase_two_caption,
                )
            ),
            run_time=1.4,
        )

        # ===== Phase 3 =====
        phase_three_title = Text(
            self.localized("空白输入，真实执行", "Blank Input, Real Execution"),
            font_size=32,
            color=TEXT,
        )
        phase_three_title.to_edge(UP, buff=0.4)
        editor = RoundedRectangle(
            corner_radius=0.08,
            width=6.1,
            height=4.65,
            stroke_color=PANEL_EDGE,
            fill_color="#0B171C",
            fill_opacity=1,
        ).move_to(LEFT * 3.15 + UP * 0.35)
        title_bar = Rectangle(width=6.08, height=0.52, stroke_width=0, fill_color="#172A30", fill_opacity=1)
        title_bar.move_to(editor.get_top() + DOWN * 0.26)
        editor_name = Text("example.sp", font="DejaVu Sans Mono", font_size=15, color=MUTED)
        editor_name.move_to(title_bar.get_center() + LEFT * 2.15)
        spasm_panel = RoundedRectangle(
            corner_radius=0.08,
            width=5.85,
            height=4.65,
            stroke_color=PANEL_EDGE,
            fill_color="#0B171C",
            fill_opacity=1,
        ).move_to(RIGHT * 3.2 + UP * 0.35)
        spasm_title_bar = Rectangle(width=5.83, height=0.52, stroke_width=0, fill_color="#172A30", fill_opacity=1)
        spasm_title_bar.move_to(spasm_panel.get_top() + DOWN * 0.26)
        spasm_name = Text("example.spasm", font="DejaVu Sans Mono", font_size=13, color=MUTED)
        spasm_name.move_to(spasm_title_bar.get_center() + LEFT * 1.65)
        spasm_lines = VGroup(
            *[
                Text(
                    f"NOP ; line={index + 1} spaces=0",
                    font="DejaVu Sans Mono",
                    font_size=11,
                    color=TEXT,
                )
                for index in range(8)
            ]
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.16)
        spasm_lines.move_to(spasm_panel.get_center() + DOWN * 0.12)
        spasm_lines.set_opacity(0)
        run_button = RoundedRectangle(
            corner_radius=0.06,
            width=1.45,
            height=0.36,
            stroke_color=GREEN,
            fill_color="#18352B",
            fill_opacity=1,
        )
        run_button.move_to(title_bar.get_center() + RIGHT * 2.15)
        run_text = Text(self.localized("▶ 运行", "▶ Run"), font_size=15, color=GREEN).move_to(run_button)
        code_area_top = editor.get_top()[1] - 0.88
        row_gap = 0.39
        blank_rows = VGroup(
            *[
                Line(
                    [editor.get_left()[0] + 0.42, code_area_top - index * row_gap, 0],
                    [editor.get_left()[0] + 3.3, code_area_top - index * row_gap, 0],
                    color="#1B3035",
                    stroke_width=1,
                )
                for index in range(8)
            ]
        )
        cursor = Rectangle(width=0.025, height=0.27, stroke_width=0, fill_color=GREEN, fill_opacity=1)
        cursor.move_to([editor.get_left()[0] + 0.48, code_area_top, 0])
        output_panel = RoundedRectangle(
            corner_radius=0.06,
            width=12.0,
            height=0.82,
            stroke_color=GREEN,
            fill_color="#10261D",
            fill_opacity=1,
        ).move_to(DOWN * 2.52)
        output_text = Text(
            self.localized(
                "8 条 NOP -> run() 返回 None | 无打印输出",
                "8 x NOP -> run() returns None | no printed output",
            ),
            font="Noto Sans Mono CJK SC",
            font_size=15,
            color=GREEN,
        )
        output_text.move_to(output_panel)

        # 纯换行在 .sp 中是零值 token，即 NOP；光标只下移，不伪造空格指令。
        self.play(
            Write(phase_three_title),
            FadeIn(editor),
            FadeIn(title_bar),
            FadeIn(spasm_panel),
            FadeIn(spasm_title_bar),
            run_time=1.8,
        )
        self.play(
            FadeIn(editor_name),
            FadeIn(run_button),
            FadeIn(run_text),
            FadeIn(spasm_name),
            FadeIn(spasm_lines),
            Create(blank_rows),
            FadeIn(cursor),
            run_time=1.4,
        )
        blink_clock = [0.0]

        def blink_cursor(mob, dt):
            blink_clock[0] += dt
            mob.set_opacity(1 if int(blink_clock[0] * 2) % 2 == 0 else 0.12)

        cursor.add_updater(blink_cursor)
        for index in range(8):
            # Reveal each disassembly row as the source cursor enters that line.
            animations = [spasm_lines[index].animate.set_opacity(1)]
            if index > 0:
                next_position = [editor.get_left()[0] + 0.48, code_area_top - index * row_gap, 0]
                animations.append(cursor.animate.move_to(next_position))
            self.play(*animations, run_time=0.32)
        self.wait(0.35)
        cursor.remove_updater(blink_cursor)
        # 点击运行；这一段来自 .sp lexer、parser 与参考 VM 的实测行为。
        self.play(cursor.animate.move_to(run_button.get_center()), run_time=0.65)
        self.play(run_button.animate.set_fill(GREEN, opacity=0.85), run_time=0.25)
        self.play(FadeIn(output_panel), FadeIn(output_text), run_time=0.9)
        flash = Rectangle(width=14.3, height=8.1, stroke_width=0, fill_color=GREEN, fill_opacity=0.12)
        self.play(FadeIn(flash), run_time=0.18)
        self.play(FadeOut(flash), run_time=0.3)
        phase_three_caption = self.caption(
            "每个换行编码一个零值 token，即 NOP。\n"
            "8 条 NOP 正常结束；VM.run() 返回 None。",
            "Each newline encodes a zero token: NOP.\n"
            "Eight NOPs finish normally; VM.run() returns None.",
        )
        self.play(FadeIn(phase_three_caption), run_time=1.0)
        self.wait(3.0)
        empty_program_scene = VGroup(
            phase_three_title,
            editor,
            title_bar,
            editor_name,
            spasm_panel,
            spasm_title_bar,
            spasm_name,
            spasm_lines,
            run_button,
            run_text,
            blank_rows,
            cursor,
            output_panel,
            output_text,
            phase_three_caption,
        )
        real_program_scene = self.show_real_program_demo(empty_program_scene)
        self.play(FadeOut(real_program_scene), run_time=1.0)
        self.show_large_integer_demo()

        # ===== Phase 4 =====
        phase_four_title = Text(
            self.localized("外星威胁与 quine", "The Alien Threat and the Quine"),
            font_size=32,
            color=TEXT,
        )
        phase_four_title.to_edge(UP, buff=0.45)
        source_file = self.file_icon("example.sp", GOLD).move_to(LEFT * 4.4 + UP * 0.7)
        generated_file = self.file_icon("example_quine.sp", CYAN).move_to(UP * 0.7)
        copied_file = self.file_icon("example_quine.copy.sp", GREEN).move_to(RIGHT * 4.4 + UP * 0.7)
        alien_slash = Line(
            generated_file[0].get_corner(UL) + RIGHT * 0.12 + DOWN * 0.12,
            generated_file[0].get_corner(DR) + LEFT * 0.12 + UP * 0.12,
            color=ALERT,
            stroke_width=7,
        )
        make_arrow = Arrow(source_file.get_right(), generated_file.get_left(), color=CYAN, buff=0.25)
        copy_arrow = Arrow(generated_file.get_right(), copied_file.get_left(), color=GREEN, buff=0.25)
        call_code = Text(
            'quine("example.sp", "example_quine.sp")',
            font="DejaVu Sans Mono",
            font_size=20,
            color=GOLD,
        ).move_to(DOWN * 1.25)
        run_code = Text(
            self.localized("运行生成文件", "Run the generated file"),
            font_size=17,
            color=MUTED,
        ).move_to(DOWN * 0.55)
        sidecar_note = Text(
            self.localized(
                ".sp / .spz quine 还会生成 .names.json 伴随文件",
                ".sp / .spz quines also create a .names.json sidecar",
            ),
            font_size=15,
            color=MUTED,
        )
        sidecar_note.move_to(DOWN * 2.05)

        # 运行 hook 在原程序指令之前写出副本，给故事里的抹除威胁留下一份可运行文件。
        self.play(Write(phase_four_title), FadeIn(source_file), run_time=1.8)
        self.play(Create(make_arrow), FadeIn(generated_file), run_time=1.4)
        self.play(FadeIn(call_code), run_time=1.0)
        self.wait(2.0)
        self.play(FadeIn(run_code), Create(copy_arrow), FadeIn(copied_file), run_time=1.4)
        self.play(Create(alien_slash), Indicate(copied_file[0], color=GREEN), run_time=1.0)
        self.play(
            FadeOut(generated_file),
            FadeOut(make_arrow),
            FadeOut(copy_arrow),
            run_time=0.8,
        )
        phase_four_caption = self.caption(
            "外星武器会在执行后抹除当前文件。quine hook 先复制程序，再运行原指令。\n"
            "因此 example_quine.copy.sp 留下一份可运行副本。",
            "The alien erases the active file after execution. The quine hook copies first.\n"
            "example_quine.copy.sp remains as a runnable copy.",
        )
        self.play(FadeIn(phase_four_caption), FadeIn(sidecar_note), run_time=1.0)
        self.wait(16.0)
        self.play(
            FadeOut(
                VGroup(
                    phase_four_title,
                    source_file,
                    generated_file,
                    alien_slash,
                    copied_file,
                    make_arrow,
                    copy_arrow,
                    call_code,
                    run_code,
                    sidecar_note,
                    phase_four_caption,
                )
            ),
            run_time=1.5,
        )
        self.wait(1.0)


class SpacelangIntroChineseWithSubtitle(SpacelangIntroWithSubtitle):
    language = "zh"


class SpacelangIntroChineseWithoutSubtitle(SpacelangIntroChineseWithSubtitle):
    show_subtitles = False


class SpacelangIntroEnglishWithSubtitle(SpacelangIntroWithSubtitle):
    language = "en"


class SpacelangIntroEnglishWithoutSubtitle(SpacelangIntroEnglishWithSubtitle):
    show_subtitles = False