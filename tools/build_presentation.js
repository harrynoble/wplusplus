/* Build docs/WPP_Presentation.pptx - the deck for presenting W++.
 *
 * The palette is the playground's own: near-black ground, one blue accent, and
 * the editor's syntax colours for code. The deck should look like the product.
 *
 *   node tools/build_presentation.js
 *
 * Needs node and pptxgenjs. W++ itself still has no dependencies; this is a
 * build tool for the deck, like docs/build_guide.py is for the PDF.
 */

const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.join(__dirname, "..");
const IMAGES = path.join(ROOT, "docs", "images");
const TARGET = path.join(ROOT, "docs", "WPP_Presentation.pptx");

// --- the playground's palette
const BG = "0B0E13";
const CARD = "141920";
const EDGE = "2B343F";
const TEXT = "DEE3EA";
const MUTED = "8A95A3";
const FAINT = "626D7B";
const ACCENT = "3B82F6";
const KEYWORD = "B48EAD";   // the editor's keyword colour
const STRING = "97B982";
const OK = "7FAE86";

const SANS = "Calibri";
const MONO = "Courier New";

const W = 13.3;
const H = 7.5;
const M = 0.7;              // page margin

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "The Mavericks";
pres.title = "W++";

/* Every slide starts from the same dark ground. */
function newSlide() {
  const slide = pres.addSlide();
  slide.background = { color: BG };
  return slide;
}

/* Section title, used on every content slide. */
function heading(slide, text, sub) {
  slide.addText(text, {
    x: M, y: 0.45, w: W - M * 2, h: 0.7,
    fontFace: SANS, fontSize: 34, bold: true, color: TEXT,
    align: "left", isTextBox: true, margin: 0,
  });
  if (sub) {
    slide.addText(sub, {
      x: M, y: 1.18, w: W - M * 2, h: 0.42,
      fontFace: SANS, fontSize: 15, color: MUTED,
      align: "left", isTextBox: true, margin: 0,
    });
  }
}

/* A rounded panel. The deck's one repeated motif. */
function card(slide, opts) {
  slide.addShape(pres.ShapeType.roundRect, {
    x: opts.x, y: opts.y, w: opts.w, h: opts.h,
    rectRadius: 0.06,
    fill: { color: opts.fill || CARD },
    line: { color: opts.line || EDGE, width: 0.75 },
  });
}

/* A block of code on a panel, in the editor's colours. */
function codeCard(slide, opts) {
  card(slide, { x: opts.x, y: opts.y, w: opts.w, h: opts.h });
  slide.addText(opts.runs, {
    x: opts.x + 0.22, y: opts.y + 0.18, w: opts.w - 0.44, h: opts.h - 0.36,
    fontFace: MONO, fontSize: opts.fontSize || 13, color: TEXT,
    align: "left", valign: "top", isTextBox: true, margin: 0,
    lineSpacingMultiple: 1.18,
  });
}

/* Syntax-coloured runs from a tiny W++ highlighter. */
const KEYWORDS = ["cook", "spill", "yap", "dm", "bodycount", "bet", "plotwist",
  "nah", "spam", "grind", "dip", "skrrt", "nocap", "cap", "npc", "squad",
  "tea", "cult", "range"];

function wpp(source) {
  const runs = [];
  const lines = source.split("\n");
  lines.forEach((line, index) => {
    const pieces = line.split(/("(?:[^"\\]|\\.)*"|\b\w+\b)/g);
    pieces.forEach((piece) => {
      if (!piece) return;
      let color = TEXT;
      if (/^".*"$/.test(piece)) color = STRING;
      else if (KEYWORDS.includes(piece)) color = KEYWORD;
      else if (/^\d+$/.test(piece)) color = "D0A67D";
      runs.push({ text: piece, options: { color: color } });
    });
    if (index < lines.length - 1) {
      runs.push({ text: "", options: { breakLine: true } });
    }
  });
  return runs;
}

function plain(source, color) {
  const runs = [];
  source.split("\n").forEach((line, index, all) => {
    runs.push({
      text: line,
      options: {
        color: color || MUTED,
        breakLine: index < all.length - 1,
      },
    });
  });
  return runs;
}

/* A big number with a label under it. */
function stat(slide, x, y, w, value, label) {
  slide.addText(value, {
    x: x, y: y, w: w, h: 0.85,
    fontFace: SANS, fontSize: 46, bold: true, color: ACCENT,
    align: "left", isTextBox: true, margin: 0,
  });
  slide.addText(label, {
    x: x, y: y + 0.9, w: w, h: 0.7,
    fontFace: SANS, fontSize: 13, color: MUTED,
    align: "left", isTextBox: true, margin: 0,
  });
}

// ============================================================ 1. title

{
  const slide = newSlide();
  slide.addText("W++", {
    x: M, y: 1.95, w: 7, h: 1.9,
    fontFace: SANS, fontSize: 96, bold: true, color: TEXT,
    align: "left", isTextBox: true, margin: 0,
  });
  slide.addText("A programming language that reads like group chat\nand runs like Python.", {
    x: M, y: 3.95, w: 8, h: 1.0,
    fontFace: SANS, fontSize: 20, color: MUTED,
    align: "left", isTextBox: true, margin: 0, lineSpacingMultiple: 1.25,
  });

  slide.addText([
    { text: "The Mavericks", options: { color: TEXT, bold: true, breakLine: true } },
    { text: "Harry Noble  ·  Jinoy Fredy", options: { color: MUTED, breakLine: true } },
    { text: "Muthoot Institute of Technology & Science, Kochi", options: { color: FAINT } },
  ], {
    x: M, y: 5.3, w: 7, h: 1.1,
    fontFace: SANS, fontSize: 14, align: "left", isTextBox: true, margin: 0,
    lineSpacingMultiple: 1.3,
  });

  card(slide, { x: 8.6, y: 2.35, w: 4.0, h: 2.2 });
  slide.addText(wpp('cook greet(name):\n    yap("gm, " + name)\n\ngreet("world")'), {
    x: 8.85, y: 2.6, w: 3.5, h: 1.7,
    fontFace: MONO, fontSize: 13, align: "left", valign: "top",
    isTextBox: true, margin: 0, lineSpacingMultiple: 1.2,
  });

  slide.addText("wplusplus.vercel.app", {
    x: 8.6, y: 5.55, w: 4.0, h: 0.4,
    fontFace: MONO, fontSize: 13, color: ACCENT,
    align: "left", isTextBox: true, margin: 0,
  });

  slide.addNotes("W++ is a programming language where every keyword is Gen Z slang. "
    + "It is a real language implementation - it has its own lexer, parser and AST - "
    + "that happens to be completely unserious. There is a live playground you can try.");
}

// ============================================================ 2. the problem

{
  const slide = newSlide();
  heading(slide, "The problem that doesn't exist");

  slide.addText([
    { text: "Programming languages are written in the vocabulary of 1970s computer science.",
      options: { color: TEXT, breakLine: true } },
  ], {
    x: M, y: 1.7, w: 7.2, h: 0.9,
    fontFace: SANS, fontSize: 20, align: "left", isTextBox: true, margin: 0,
    lineSpacingMultiple: 1.25,
  });

  slide.addText([
    { text: "Nobody talks like that. An entire generation is asked to write ", options: { color: MUTED } },
    { text: "return", options: { color: KEYWORD, fontFace: MONO } },
    { text: " when they mean ", options: { color: MUTED } },
    { text: "spill", options: { color: KEYWORD, fontFace: MONO } },
    { text: ", and to type ", options: { color: MUTED } },
    { text: "False", options: { color: KEYWORD, fontFace: MONO } },
    { text: " when they clearly mean ", options: { color: MUTED } },
    { text: "cap", options: { color: KEYWORD, fontFace: MONO } },
    { text: ".", options: { color: MUTED } },
  ], {
    x: M, y: 2.95, w: 7.2, h: 1.0,
    fontFace: SANS, fontSize: 16, align: "left", isTextBox: true, margin: 0,
    lineSpacingMultiple: 1.3,
  });

  slide.addText("And when your code breaks, Python hands you a wall of traceback "
    + "instead of simply telling you it is a skill issue.", {
    x: M, y: 4.1, w: 7.2, h: 0.9,
    fontFace: SANS, fontSize: 16, color: MUTED,
    align: "left", isTextBox: true, margin: 0, lineSpacingMultiple: 1.3,
  });

  card(slide, { x: 8.5, y: 1.75, w: 4.1, h: 3.5 });
  slide.addText(plain(
    "Traceback (most recent call last):\n"
    + '  File "grades.py", line 12,\n'
    + "    in average\n"
    + "    return total / len(marks)\n"
    + "           ~~~~~~^~~~~~~~~~~~\n"
    + "ZeroDivisionError: division by\n"
    + "zero", FAINT), {
    x: 8.72, y: 2.0, w: 3.7, h: 3.0,
    fontFace: MONO, fontSize: 11, align: "left", valign: "top",
    isTextBox: true, margin: 0, lineSpacingMultiple: 1.25,
  });

  slide.addNotes("Set up the joke. The premise is that programming vocabulary is dated, "
    + "and that Python's error messages are unhelpfully verbose.");
}

// ============================================================ 3. the solution

{
  const slide = newSlide();
  heading(slide, "The solution nobody asked for",
    "Nineteen keywords. That is the whole language.");

  const pairs = [
    ["cook", "def"], ["spill", "return"], ["yap", "print"], ["dm", "input"],
    ["bodycount", "len"], ["bet", "if"], ["plotwist", "elif"], ["nah", "else"],
    ["spam", "for"], ["grind", "while"], ["dip", "break"], ["skrrt", "continue"],
    ["nocap", "True"], ["cap", "False"], ["npc", "None"], ["squad", "list"],
    ["tea", "dict"], ["cult", "set"], ["range", "range"],
  ];

  const cols = 5;
  const gap = 0.14;
  // Sized from the usable width so the last column keeps a full margin.
  const cw = (W - M * 2 - gap * (cols - 1)) / cols;
  const ch = 0.78;
  const gapX = gap;
  const gapY = 0.16;
  const startY = 2.05;

  pairs.forEach((pair, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    const x = M + col * (cw + gapX);
    const y = startY + row * (ch + gapY);
    card(slide, { x: x, y: y, w: cw, h: ch });
    slide.addText([
      { text: pair[0], options: { color: KEYWORD, bold: true } },
      { text: "   " + pair[1], options: { color: FAINT } },
    ], {
      x: x + 0.16, y: y + 0.17, w: cw - 0.32, h: 0.45,
      fontFace: MONO, fontSize: 13, align: "left", valign: "middle",
      isTextBox: true, margin: 0,
    });
  });

  slide.addText("Everything else is ordinary Python - classes, generators, "
    + "f-strings, the whole standard library.", {
    x: M, y: 6.55, w: W - M * 2, h: 0.5,
    fontFace: SANS, fontSize: 14, color: MUTED,
    align: "left", isTextBox: true, margin: 0,
  });

  slide.addNotes("Read a few aloud - cook, yap, bet, dip. Then make the important point: "
    + "only these nineteen words changed. Everything else is Python, which is why real "
    + "programs work.");
}

// ============================================================ 4. a program

{
  const slide = newSlide();
  heading(slide, "A real program", "The same thing, before and after the compiler.");

  const half = (W - M * 2 - 0.5) / 2;

  slide.addText("W++", {
    x: M, y: 1.95, w: half, h: 0.3,
    fontFace: MONO, fontSize: 12, color: ACCENT, bold: true,
    align: "left", isTextBox: true, margin: 0,
  });
  codeCard(slide, {
    x: M, y: 2.35, w: half, h: 3.1,
    runs: wpp('cook check_vibe(name):\n'
      + '    bet name == "Claude":\n'
      + '        spill "W AI"\n'
      + '    nah:\n'
      + '        spill "Mid"\n\n'
      + 'username = dm("Who are you? ")\n'
      + 'yap(check_vibe(username))'),
  });

  slide.addText("generated Python", {
    x: M + half + 0.5, y: 1.95, w: half, h: 0.3,
    fontFace: MONO, fontSize: 12, color: FAINT, bold: true,
    align: "left", isTextBox: true, margin: 0,
  });
  codeCard(slide, {
    x: M + half + 0.5, y: 2.35, w: half, h: 3.1,
    runs: plain('def check_vibe(name):\n'
      + '    if name == "Claude":\n'
      + '        return "W AI"\n'
      + '    else:\n'
      + '        return "Mid"\n\n'
      + 'username = input("Who are you? ")\n'
      + 'print(check_vibe(username))', MUTED),
  });

  slide.addText("Python runs the result. W++ has no runtime of its own.", {
    x: M, y: 5.75, w: W - M * 2, h: 0.4,
    fontFace: SANS, fontSize: 14, color: MUTED,
    align: "left", isTextBox: true, margin: 0,
  });

  slide.addNotes("This is the official example from our language spec. Point out cook, "
    + "bet, nah, spill and dm on the left, and what each became on the right.");
}

// ============================================================ 5. demo

{
  const slide = newSlide();
  heading(slide, "The playground", "Write W++, press Run. In the browser, no install.");

  slide.addImage({
    path: path.join(IMAGES, "screenshot1-fizzbuzz.png"),
    x: M, y: 1.95, w: W - M * 2, h: (W - M * 2) * 430 / 1280,
  });

  slide.addText("wplusplus.vercel.app", {
    x: M, y: 6.35, w: 6, h: 0.4,
    fontFace: MONO, fontSize: 14, color: ACCENT,
    align: "left", isTextBox: true, margin: 0,
  });

  slide.addNotes("Switch to the live site here if the wifi allows. FizzBuzz is in the "
    + "Examples menu and runs in milliseconds.");
}

// ============================================================ 6. the challenge

{
  const slide = newSlide();

  slide.addText("“Isn't this just find-and-replace?”", {
    x: M, y: 2.25, w: W - M * 2, h: 1.0,
    fontFace: SANS, fontSize: 40, bold: true, color: TEXT,
    align: "left", isTextBox: true, margin: 0,
  });

  slide.addText("No. And here is how you can check.", {
    x: M, y: 3.4, w: W - M * 2, h: 0.5,
    fontFace: SANS, fontSize: 20, color: ACCENT,
    align: "left", isTextBox: true, margin: 0,
  });

  const items = [
    ["python wpp.py --tokens", "what the lexer saw"],
    ["python wpp.py --ast", "the syntax tree the parser built"],
    ["python wpp.py --emit", "the Python the backend generated"],
  ];
  items.forEach((item, index) => {
    const y = 4.25 + index * 0.72;
    slide.addText([
      { text: item[0], options: { color: TEXT, fontFace: MONO, bold: true } },
      { text: "    " + item[1], options: { color: MUTED, fontFace: SANS } },
    ], {
      x: M, y: y, w: W - M * 2, h: 0.45,
      fontSize: 15, align: "left", valign: "middle", isTextBox: true, margin: 0,
    });
  });

  slide.addNotes("This is the question every judge asks. Say it before they do. "
    + "The three commands are the answer: each stage of the compiler can be printed.");
}

// ============================================================ 7. architecture

{
  const slide = newSlide();
  heading(slide, "How it actually works");

  const imageW = 6.1;
  slide.addImage({
    path: path.join(IMAGES, "architecture.png"),
    x: M, y: 1.55, w: imageW, h: imageW * 796 / 900,
  });

  const notes = [
    ["Lexer", "W++ tokens, each with a line and column. A keyword inside a "
      + "string is never a keyword, because the scanner returns the whole "
      + "literal as one token."],
    ["Parser", "Recursive descent for statements, precedence climbing for "
      + "expressions. Produces a W++ syntax tree."],
    ["Semantic pass", "Is dip inside a loop? Is spill inside a cook? Errors "
      + "that need a view of the whole tree."],
    ["Code generator", "Walks the tree and emits Python, remembering which "
      + "W++ line produced each Python line."],
  ];

  notes.forEach((note, index) => {
    const y = 1.75 + index * 1.28;
    slide.addText(note[0], {
      x: 7.3, y: y, w: 5.3, h: 0.34,
      fontFace: SANS, fontSize: 16, bold: true, color: ACCENT,
      align: "left", isTextBox: true, margin: 0,
    });
    slide.addText(note[1], {
      x: 7.3, y: y + 0.34, w: 5.3, h: 0.86,
      fontFace: SANS, fontSize: 12.5, color: MUTED,
      align: "left", valign: "top", isTextBox: true, margin: 0,
      lineSpacingMultiple: 1.18,
    });
  });

  slide.addNotes("Four stages, each with one job. Python is the target we compile to, "
    + "not what W++ is.");
}

// ============================================================ 8. the AST

{
  const slide = newSlide();
  heading(slide, "It really is parsed", "python wpp.py --ast");

  const half = (W - M * 2 - 0.5) / 2;

  codeCard(slide, {
    x: M, y: 2.0, w: half, h: 2.2, fontSize: 13,
    runs: wpp('cook check_vibe(name):\n'
      + '    bet name == "Claude":\n'
      + '        spill "W AI"'),
  });

  slide.addText("becomes a tree of W++ constructs, each remembering where it came from",
    {
      x: M, y: 4.45, w: half, h: 0.9,
      fontFace: SANS, fontSize: 14, color: MUTED,
      align: "left", valign: "top", isTextBox: true, margin: 0,
      lineSpacingMultiple: 1.2,
    });

  codeCard(slide, {
    x: M + half + 0.5, y: 2.0, w: half, h: 4.4, fontSize: 11,
    runs: [
      { text: "Program", options: { color: TEXT, breakLine: true } },
      { text: "  FunctionDeclaration", options: { color: ACCENT, breakLine: true } },
      { text: "    name='check_vibe'", options: { color: MUTED, breakLine: true } },
      { text: "    keyword='cook'  @1:0", options: { color: MUTED, breakLine: true } },
      { text: "    params: name", options: { color: MUTED, breakLine: true } },
      { text: "    body:", options: { color: MUTED, breakLine: true } },
      { text: "      IfStatement  @2:4", options: { color: ACCENT, breakLine: true } },
      { text: "        condition:", options: { color: MUTED, breakLine: true } },
      { text: "          Comparison  ==", options: { color: TEXT, breakLine: true } },
      { text: "            Identifier name", options: { color: MUTED, breakLine: true } },
      { text: '            Literal "Claude"', options: { color: STRING, breakLine: true } },
      { text: "        body:", options: { color: MUTED, breakLine: true } },
      { text: "          ReturnStatement", options: { color: ACCENT, breakLine: true } },
      { text: "            keyword='spill'", options: { color: MUTED } },
    ],
  });

  slide.addNotes("Every node knows the W++ keyword that created it and the line and "
    + "column it came from. That is what makes the next slide possible.");
}

// ============================================================ 9. errors

{
  const slide = newSlide();
  heading(slide, "Errors speak W++",
    "The Skill Issue Protocol - and it points at your line, not generated code.");

  slide.addImage({
    path: path.join(IMAGES, "screenshot2-skill-issue.png"),
    x: M, y: 2.0, w: W - M * 2, h: (W - M * 2) * 430 / 1280,
  });

  slide.addText([
    { text: "Line 5", options: { color: ACCENT, bold: true, fontFace: MONO } },
    { text: "  is the W++ line the author wrote. The compiler keeps a map from "
        + "generated Python back to the source, so no message ever mentions code "
        + "nobody typed.", options: { color: MUTED } },
  ], {
    x: M, y: 6.4, w: W - M * 2, h: 0.6,
    fontFace: SANS, fontSize: 13, align: "left", isTextBox: true, margin: 0,
  });

  slide.addNotes("Seven error types get their own message. The interesting part is not "
    + "the joke wording, it is that the line number is right: a runtime failure knows "
    + "only the generated Python line, and the source map turns it back.");
}

// ============================================================ 10. deployment

{
  const slide = newSlide();
  heading(slide, "It runs in two places",
    "One codebase. The interface cannot tell them apart.");

  const cw = (W - M * 2 - 0.5) / 2;

  card(slide, { x: M, y: 2.05, w: cw, h: 2.55 });
  slide.addText("Locally", {
    x: M + 0.3, y: 2.3, w: cw - 0.6, h: 0.4,
    fontFace: SANS, fontSize: 20, bold: true, color: TEXT,
    align: "left", isTextBox: true, margin: 0,
  });
  slide.addText("A small Python server runs each program in its own child process, "
    + "with a timeout.", {
    x: M + 0.3, y: 2.8, w: cw - 0.6, h: 1.5,
    fontFace: SANS, fontSize: 14, color: MUTED,
    align: "left", valign: "top", isTextBox: true, margin: 0,
    lineSpacingMultiple: 1.2,
  });

  card(slide, { x: M + cw + 0.5, y: 2.05, w: cw, h: 2.55 });
  slide.addText("In your browser", {
    x: M + cw + 0.8, y: 2.3, w: cw - 0.6, h: 0.4,
    fontFace: SANS, fontSize: 20, bold: true, color: ACCENT,
    align: "left", isTextBox: true, margin: 0,
  });
  slide.addText("The same compiler runs under Pyodide - CPython on WebAssembly - "
    + "inside a worker. No backend at all.", {
    x: M + cw + 0.8, y: 2.8, w: cw - 0.6, h: 1.5,
    fontFace: SANS, fontSize: 14, color: MUTED,
    align: "left", valign: "top", isTextBox: true, margin: 0,
    lineSpacingMultiple: 1.2,
  });

  slide.addText([
    { text: "So the playground deploys as static files, and it is safe to make public: ",
      options: { color: MUTED } },
    { text: "there is no server executing anyone's code.",
      options: { color: TEXT, bold: true } },
  ], {
    x: M, y: 5.0, w: W - M * 2, h: 0.6,
    fontFace: SANS, fontSize: 15, align: "left", isTextBox: true, margin: 0,
    lineSpacingMultiple: 1.2,
  });

  slide.addText("wplusplus.vercel.app", {
    x: M, y: 5.85, w: 6, h: 0.4,
    fontFace: MONO, fontSize: 14, color: ACCENT,
    align: "left", isTextBox: true, margin: 0,
  });

  slide.addNotes("The browser engine is why we can host it at all. Your own browser "
    + "runs your own code, so there is nothing of ours to attack.");
}

// ============================================================ 11. testing

{
  const slide = newSlide();
  heading(slide, "How we know it works");

  stat(slide, M, 1.9, 3.0, "252", "automated tests, standard\nlibrary only");
  stat(slide, M + 3.4, 1.9, 3.0, "19", "keywords, each tested in\nits own context");
  stat(slide, M + 6.8, 1.9, 3.0, "0", "dependencies for the\nlanguage itself");

  card(slide, { x: M, y: 3.9, w: W - M * 2, h: 2.2 });
  slide.addText("The check that made the rewrite safe", {
    x: M + 0.35, y: 4.15, w: W - M * 2 - 0.7, h: 0.4,
    fontFace: SANS, fontSize: 18, bold: true, color: ACCENT,
    align: "left", isTextBox: true, margin: 0,
  });
  slide.addText("W++ started as a single regular-expression pass. When we replaced it "
    + "with the compiler, we kept the old translator as a test oracle. Both target "
    + "Python, so for any program they both accept, the two must generate Python that "
    + "parses to the same tree. They agree on every one - and the check found two real "
    + "bugs in the rewrite that we would otherwise have shipped.", {
    x: M + 0.35, y: 4.62, w: W - M * 2 - 0.7, h: 1.3,
    fontFace: SANS, fontSize: 13.5, color: MUTED,
    align: "left", valign: "top", isTextBox: true, margin: 0,
    lineSpacingMultiple: 1.22,
  });

  slide.addNotes("If you have time for one engineering detail, make it this one. "
    + "We used the old implementation as an oracle for the new one, comparing parsed "
    + "Python rather than text. It caught a bug where a nah attached to a loop was "
    + "being claimed by an inner bet, which silently changed what programs meant.");
}

// ============================================================ 12. close

{
  const slide = newSlide();

  slide.addText("W++", {
    x: M, y: 2.0, w: 6, h: 1.1,
    fontFace: SANS, fontSize: 64, bold: true, color: TEXT,
    align: "left", isTextBox: true, margin: 0,
  });
  slide.addText("A real compiler frontend, for a language whose\n"
    + "break statement is called dip.", {
    x: M, y: 3.2, w: 7.4, h: 1.0,
    fontFace: SANS, fontSize: 19, color: MUTED,
    align: "left", isTextBox: true, margin: 0, lineSpacingMultiple: 1.25,
  });

  const links = [
    ["Try it", "wplusplus.vercel.app"],
    ["Code", "github.com/harrynoble/wplusplus"],
    ["Learn it", "docs/WPP_Guide.pdf - 57 pages"],
  ];
  links.forEach((link, index) => {
    const y = 4.6 + index * 0.55;
    slide.addText(link[0], {
      x: M, y: y, w: 1.3, h: 0.4,
      fontFace: SANS, fontSize: 14, color: FAINT,
      align: "left", valign: "middle", isTextBox: true, margin: 0,
    });
    slide.addText(link[1], {
      x: M + 1.4, y: y, w: 7, h: 0.4,
      fontFace: MONO, fontSize: 14, color: index === 0 ? ACCENT : TEXT,
      align: "left", valign: "middle", isTextBox: true, margin: 0,
    });
  });

  card(slide, { x: 9.1, y: 2.2, w: 3.5, h: 2.6 });
  slide.addText(wpp('spam vibe in range(3):\n'
    + '    yap("thank you")\n\n'
    + 'bet questions:\n'
    + '    spill "ask away"'), {
    x: 9.35, y: 2.45, w: 3.0, h: 2.1,
    fontFace: MONO, fontSize: 12, align: "left", valign: "top",
    isTextBox: true, margin: 0, lineSpacingMultiple: 1.2,
  });

  slide.addNotes("Close on the live link. Offer to run anything they want to see.");
}

pres.writeFile({ fileName: TARGET }).then(() => {
  console.log("wrote " + TARGET);
});
