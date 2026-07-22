// GENERATED — DO NOT EDIT. Source: scripts/build-adapters.py
// Regenerate with: python3 scripts/build-adapters.py

import type { ExtensionAPI, Theme } from "@earendil-works/pi-coding-agent";
import {
  Editor,
  type EditorTheme,
  Key,
  matchesKey,
  Text,
  truncateToWidth,
  wrapTextWithAnsi,
  type Component,
  type TUI,
} from "@earendil-works/pi-tui";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { Type, type Static } from "typebox";

const TOOL_NAME = "AskUserQuestion";
const OTHER_LABEL = "Other";

const OptionSchema = Type.Object({
  label: Type.String({ description: "Option label shown to the user and returned when selected" }),
  description: Type.Optional(Type.String({ description: "Optional explanation or trade-off shown under the label" })),
  preview: Type.Optional(Type.String({ description: "Optional markdown/plain preview shown when the option is focused" })),
});

const QuestionSchema = Type.Object({
  question: Type.String({ description: "Full question text to display" }),
  header: Type.Optional(Type.String({ description: "Optional short tab/header label" })),
  multiSelect: Type.Optional(Type.Boolean({ description: "Allow the user to select more than one option" })),
  options: Type.Array(OptionSchema, {
    minItems: 2,
    maxItems: 4,
    description: "2-4 options. A custom/Other row is added automatically unless an explicit Other/custom option is present.",
  }),
});

const ParamsSchema = Type.Object({
  questions: Type.Array(QuestionSchema, { minItems: 1, maxItems: 4, description: "Questions to ask the user" }),
  metadata: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
});

type Params = Static<typeof ParamsSchema>;
type RawQuestion = Static<typeof QuestionSchema>;
type RawOption = Static<typeof OptionSchema>;

type Question = Omit<RawQuestion, "header" | "multiSelect" | "options"> & {
  header: string;
  multiSelect: boolean;
  options: RawOption[];
  customOption?: RawOption;
};

type AnswerDetail = {
  question: string;
  header?: string;
  selections: string[];
  selectedOptions: RawOption[];
  customAnswer?: string;
  cancelled?: boolean;
};

type Details = {
  questions: RawQuestion[];
  answers: Record<string, string | string[]>;
  answerDetails: AnswerDetail[];
  metadata: Record<string, unknown>;
  cancelled: boolean;
};

type State = {
  cursor: number;
  selectedIndex: number | null;
  selectedIndices: Set<number>;
  customText: string | null;
  confirmed: boolean;
  editing: boolean;
};

type RenderOption = RawOption & { isOther?: boolean };

// Claude Code's AskUserQuestion schema/output shape is the compatibility contract.
// The TUI interaction model is inspired by ghoseb/pi-askuserquestion: explicit
// selection, multi-question tabs, a final Submit review, previews, and custom answers.
export default function askUserQuestion(pi: ExtensionAPI) {
  process.env.FEATURE_FORGE_ROOT ||= dirname(dirname(fileURLToPath(import.meta.url)));

  const tool = {
    name: TOOL_NAME,
    label: "Ask User Question",
    description:
      "Ask the user one to four structured multiple-choice questions. Use only for genuine user decisions; supports automatic Other/custom answers, per-question headings, previews, multi-select, and final review.",
    promptSnippet: "Ask the user structured multiple-choice questions and return Claude-shaped answers.",
    promptGuidelines: [
      "Use AskUserQuestion only for genuine user decisions or requirements clarification.",
      "AskUserQuestion accepts 1-4 questions with 2-4 options each; the UI provides Other/custom text automatically.",
      "Use AskUserQuestion multiSelect only when several options can validly apply together.",
    ],
    parameters: ParamsSchema,
    executionMode: "sequential" as const,

    async execute(_toolCallId: string, params: Params, _signal: AbortSignal | undefined, _onUpdate: unknown, ctx: any) {
      const validationError = validateInput(params);
      if (validationError) {
        return {
          content: [{ type: "text" as const, text: `Invalid AskUserQuestion input: ${validationError}` }],
          details: cancelledDetails(params.questions ?? [], params.metadata ?? {}),
        };
      }

      if (ctx.mode !== "tui") {
        return {
          content: [{ type: "text" as const, text: "AskUserQuestion requires interactive Pi TUI mode; the user did not see the questions." }],
          details: cancelledDetails(params.questions, params.metadata ?? {}),
        };
      }

      const normalized = normalizeQuestions(params.questions);
      const result = await ctx.ui.custom<Details | null>((tui: TUI, theme: Theme, _kb: unknown, done: (result: Details | null) => void) => {
        return new AskUserQuestionComponent(params.questions, normalized, params.metadata ?? {}, tui, theme, done);
      });

      const details = result ?? cancelledDetails(params.questions, params.metadata ?? {});
      if (details.cancelled) {
        return { content: [{ type: "text" as const, text: "User cancelled AskUserQuestion." }], details };
      }

      const lines = details.answerDetails.map((a, i) => `${i + 1}. ${a.question}: ${a.selections.join(", ")}`);
      return { content: [{ type: "text" as const, text: `User answered:\n${lines.join("\n")}` }], details };
    },

    renderCall(args: Partial<Params>, theme: Theme) {
      const count = Array.isArray(args.questions) ? args.questions.length : 0;
      return new Text(theme.fg("toolTitle", theme.bold("AskUserQuestion ")) + theme.fg("muted", `${count} question${count === 1 ? "" : "s"}`), 0, 0);
    },

    renderResult(result: { details?: Details; content?: Array<{ type: string; text?: string }> }, _options: unknown, theme: Theme) {
      const details = result.details;
      if (!details || details.cancelled) return new Text(theme.fg("warning", "AskUserQuestion cancelled/no UI"), 0, 0);
      return new Text(
        details.answerDetails
          .map((a) => `${theme.fg("success", "✓")} ${theme.fg("muted", a.header ?? a.question)}: ${theme.fg("accent", a.selections.join(", "))}`)
          .join("\n"),
        0,
        0,
      );
    },
  };

  pi.on("session_start", async () => {
    if (pi.getAllTools().some((existing) => existing.name === TOOL_NAME)) return;
    pi.registerTool(tool);
  });
}

function cancelledDetails(questions: RawQuestion[], metadata: Record<string, unknown>): Details {
  return {
    questions,
    answers: {},
    answerDetails: questions.map((q) => ({ question: q.question, header: q.header, selections: [], selectedOptions: [], cancelled: true })),
    metadata,
    cancelled: true,
  };
}

export function validateInput(params: Partial<Params>): string | undefined {
  if (!Array.isArray(params.questions) || params.questions.length < 1 || params.questions.length > 4) return "expected 1-4 questions";
  const seenQuestions = new Set<string>();
  for (const [qi, q] of params.questions.entries()) {
    if (!q.question?.trim()) return `question ${qi + 1} needs text`;
    if (seenQuestions.has(q.question)) return "question texts must be unique";
    seenQuestions.add(q.question);
    if (!Array.isArray(q.options) || q.options.length < 2 || q.options.length > 4) return `question ${qi + 1} needs 2-4 options`;
    const seenLabels = new Set<string>();
    for (const [oi, o] of q.options.entries()) {
      if (!o.label?.trim()) return `question ${qi + 1} option ${oi + 1} needs a label`;
      const key = o.label.trim().toLowerCase();
      if (seenLabels.has(key)) return `question ${qi + 1} option labels must be unique`;
      seenLabels.add(key);
    }
  }
}

function isCustomLabel(label: string): boolean {
  return /^(other|custom)(\b|\s*\/)/i.test(label.trim()) || /custom answer/i.test(label);
}

export function normalizeQuestions(raw: RawQuestion[]): Question[] {
  return raw.map((q, index) => {
    const customIndex = q.options.findIndex((o) => isCustomLabel(o.label));
    const options = customIndex >= 0 ? q.options.filter((_, i) => i !== customIndex) : q.options;
    const customOption = customIndex >= 0 ? q.options[customIndex] : undefined;
    return {
      question: q.question,
      header: (q.header?.trim() || `Q${index + 1}`).slice(0, 24),
      multiSelect: q.multiSelect ?? false,
      options,
      customOption,
    };
  });
}

function makeEditor(tui: TUI, theme: Theme): Editor {
  const editorTheme: EditorTheme = {
    borderColor: (s: string) => theme.fg("accent", s),
    selectList: {
      selectedPrefix: (s: string) => theme.fg("accent", s),
      selectedText: (s: string) => theme.fg("accent", s),
      description: (s: string) => theme.fg("muted", s),
      scrollInfo: (s: string) => theme.fg("dim", s),
      noMatch: (s: string) => theme.fg("warning", s),
    },
  };
  const editor = new Editor(tui, editorTheme);
  editor.disableSubmit = true;
  return editor;
}

export class AskUserQuestionComponent implements Component {
  private activeTab = 0;
  private states: State[];
  private editor: Editor;
  private cachedWidth?: number;
  private cachedLines?: string[];
  private resolved = false;

  constructor(
    private rawQuestions: RawQuestion[],
    private questions: Question[],
    private metadata: Record<string, unknown>,
    private tui: TUI,
    private theme: Theme,
    private done: (result: Details | null) => void,
  ) {
    this.states = questions.map(() => ({ cursor: 0, selectedIndex: null, selectedIndices: new Set(), customText: null, confirmed: false, editing: false }));
    this.editor = makeEditor(tui, theme);
    this.editor.onChange = () => this.refresh();
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }

  handleInput(data: string): void {
    if (this.resolved) return;

    if (this.onSubmitTab()) {
      if (matchesKey(data, Key.enter) && this.allConfirmed()) return this.submit();
      if (matchesKey(data, Key.escape)) return this.cancel();
      if (matchesKey(data, Key.right)) return this.goto(0);
      if (matchesKey(data, Key.left)) return this.goto(this.questions.length - 1);
      return;
    }

    const q = this.currentQuestion();
    const state = this.currentState();

    if (state.editing) {
      if (matchesKey(data, Key.escape)) {
        state.editing = false;
        this.editor.setText("");
        return this.refresh();
      }
      if (matchesKey(data, Key.enter)) {
        const text = this.editor.getText().trim();
        state.customText = text || null;
        state.editing = false;
        this.editor.setText("");
        if (!text && !this.hasAnyAnswer(q, state)) state.confirmed = false;
        if (text && !q.multiSelect) {
          state.selectedIndex = null;
          state.confirmed = true;
          return this.advance();
        }
        return this.refresh();
      }
      this.editor.handleInput(data);
      return this.refresh();
    }

    if (matchesKey(data, Key.escape)) return this.cancel();
    if (matchesKey(data, Key.right) && this.questions.length > 1) {
      this.autoConfirmAnswered();
      return this.goto((this.activeTab + 1) % (this.questions.length + 1));
    }
    if (matchesKey(data, Key.left) && this.questions.length > 1) {
      this.autoConfirmAnswered();
      return this.goto((this.activeTab - 1 + this.questions.length + 1) % (this.questions.length + 1));
    }
    if (matchesKey(data, Key.up)) return this.moveCursor(-1);
    if (matchesKey(data, Key.down)) return this.moveCursor(1);

    const customIndex = this.optionsFor(q).length - 1;
    const onCustom = state.cursor === customIndex;
    if (onCustom && (matchesKey(data, Key.enter) || matchesKey(data, Key.space) || matchesKey(data, Key.tab) || isPrintable(data))) {
      state.editing = true;
      this.editor.setText(isPrintable(data) ? data : (state.customText ?? ""));
      return this.refresh();
    }

    if (q.multiSelect) {
      if (matchesKey(data, Key.space)) {
        state.selectedIndices.has(state.cursor) ? state.selectedIndices.delete(state.cursor) : state.selectedIndices.add(state.cursor);
        if (!this.hasAnyAnswer(q, state)) state.confirmed = false;
        return this.refresh();
      }
      if (matchesKey(data, Key.enter) && this.hasAnyAnswer(q, state)) {
        state.confirmed = true;
        return this.advance();
      }
      return;
    }

    if (matchesKey(data, Key.enter)) {
      state.selectedIndex = state.cursor;
      state.customText = null;
      state.confirmed = true;
      return this.advance();
    }
  }

  render(width: number): string[] {
    if (this.cachedWidth === width && this.cachedLines) return this.cachedLines;
    const w = Math.max(20, width);
    const lines: string[] = [];
    const add = (line = "") => lines.push(truncateToWidth(line, w));
    const t = this.theme;

    add(t.fg("accent", "─".repeat(w)));
    add(` ${t.fg("accent", t.bold("AskUserQuestion"))} ${t.fg("dim", `(${Math.min(this.activeTab + 1, this.questions.length)}/${this.questions.length})`)}`);
    if (this.questions.length > 1) add(` ${this.renderTabs(w - 2)}`);
    add();

    if (this.onSubmitTab()) this.renderSubmit(add, w);
    else this.renderQuestion(add, w);

    add(t.fg("accent", "─".repeat(w)));
    this.cachedWidth = width;
    this.cachedLines = lines;
    return lines;
  }

  private renderQuestion(add: (line?: string) => void, width: number): void {
    const t = this.theme;
    const q = this.currentQuestion();
    const state = this.currentState();
    for (const line of wrapTextWithAnsi(t.fg("text", q.question), width - 2)) add(` ${line}`);
    add();
    const opts = this.optionsFor(q);
    for (let i = 0; i < opts.length; i++) {
      const opt = opts[i];
      const focused = i === state.cursor;
      const prefix = focused ? t.fg("accent", "> ") : "  ";
      const selected = q.multiSelect ? state.selectedIndices.has(i) : state.selectedIndex === i;
      const marker = opt.isOther ? (state.customText ? t.fg("success", "✎") : " ") : q.multiSelect ? (selected ? t.fg("success", "[x]") : t.fg("dim", "[ ]")) : selected ? t.fg("success", "✓") : " ";
      add(`${prefix}${marker} ${t.fg(focused ? "accent" : opt.isOther ? "muted" : "text", `${i + 1}. ${opt.label}`)}`);
      if (opt.description) for (const line of wrapTextWithAnsi(t.fg("muted", opt.description), width - 7)) add(`      ${line}`);
      if (opt.isOther && state.customText) add(`      ${t.fg("dim", JSON.stringify(state.customText))}`);
    }
    const preview = opts[state.cursor]?.preview;
    if (preview) {
      add();
      add(t.fg("accent", " Preview"));
      for (const line of wrapTextWithAnsi(preview, width - 4).slice(0, 12)) add(` ${t.fg("dim", "│")} ${line}`);
    }
    if (state.editing) {
      add();
      add(t.fg("muted", " Custom answer:"));
      for (const line of this.editor.render(width - 2)) add(` ${line}`);
    }
    add();
    add(t.fg("dim", state.editing ? " Enter save • Esc back" : q.multiSelect ? " ↑↓ move • Space toggle • Enter next/submit • ←→ tabs • Esc cancel" : " ↑↓ move • Enter select/custom • ←→ tabs • Esc cancel"));
  }

  private renderSubmit(add: (line?: string) => void, width: number): void {
    const t = this.theme;
    add(this.allConfirmed() ? t.fg("success", t.bold(" Ready to submit")) : t.fg("warning", t.bold(" Unanswered questions")));
    add();
    for (let i = 0; i < this.questions.length; i++) {
      const q = this.questions[i];
      const answer = this.answerFor(q, this.states[i]);
      const label = truncateToWidth(q.header, 16);
      const answerWidth = Math.max(1, width - label.length - 4);
      add(` ${t.fg("muted", label + ":")} ${answer.length ? t.fg("text", truncateToWidth(answer.join(", "), answerWidth)) : t.fg("warning", "—")}`);
    }
    add();
    add(t.fg("dim", this.allConfirmed() ? " Enter submit • ←→ review/edit • Esc cancel" : " ←→ answer missing questions • Esc cancel"));
  }

  private renderTabs(maxWidth: number): string {
    const parts = this.questions.map((q, i) => {
      const active = i === this.activeTab;
      const done = this.states[i].confirmed;
      const text = ` ${done ? "●" : "○"} ${q.header} `;
      return active ? this.theme.bg("selectedBg", this.theme.fg("text", text)) : this.theme.fg(done ? "success" : "muted", text);
    });
    const submit = ` ${this.allConfirmed() ? "✓" : "○"} Submit `;
    parts.push(this.onSubmitTab() ? this.theme.bg("selectedBg", this.theme.fg("text", submit)) : this.theme.fg(this.allConfirmed() ? "success" : "dim", submit));
    return truncateToWidth(parts.join(" "), maxWidth);
  }

  private optionsFor(q: Question): RenderOption[] {
    return [...q.options, { label: q.customOption?.label ?? OTHER_LABEL, description: q.customOption?.description ?? "Type a custom answer", preview: q.customOption?.preview, isOther: true }];
  }

  private currentQuestion(): Question { return this.questions[this.activeTab]; }
  private currentState(): State { return this.states[this.activeTab]; }
  private onSubmitTab(): boolean { return this.questions.length > 1 && this.activeTab === this.questions.length; }
  private allConfirmed(): boolean { return this.states.every((s, i) => s.confirmed && this.answerFor(this.questions[i], s).length > 0); }
  private refresh(): void { this.invalidate(); this.tui.requestRender(); }
  private goto(index: number): void { this.activeTab = index; this.refresh(); }
  private moveCursor(delta: -1 | 1): void { const max = this.optionsFor(this.currentQuestion()).length - 1; this.currentState().cursor = Math.max(0, Math.min(max, this.currentState().cursor + delta)); this.refresh(); }
  private hasAnyAnswer(q: Question, s: State): boolean { return this.answerFor(q, s).length > 0; }
  private autoConfirmAnswered(): void { const q = this.currentQuestion(); const s = this.currentState(); if (this.hasAnyAnswer(q, s)) s.confirmed = true; }
  private advance(): void { if (this.questions.length === 1) return this.submit(); const next = this.states.findIndex((s, i) => i > this.activeTab && !s.confirmed); this.activeTab = next >= 0 ? next : this.questions.length; this.refresh(); }
  private cancel(): void { this.resolved = true; this.done(null); }

  private answerFor(q: Question, s: State): string[] {
    if (q.multiSelect) {
      const selected = [...s.selectedIndices].sort((a, b) => a - b).map((i) => q.options[i]?.label).filter(Boolean) as string[];
      if (s.customText) selected.push(s.customText);
      return selected;
    }
    if (s.customText) return [s.customText];
    if (s.selectedIndex !== null) return [q.options[s.selectedIndex]?.label].filter(Boolean) as string[];
    return [];
  }

  private submit(): void {
    if (!this.allConfirmed() && this.questions.length > 1) return this.refresh();
    const answerDetails: AnswerDetail[] = this.questions.map((q, i) => {
      const s = this.states[i];
      const selectedOptions = q.multiSelect ? [...s.selectedIndices].sort((a, b) => a - b).map((idx) => q.options[idx]).filter(Boolean) as RawOption[] : s.selectedIndex !== null ? [q.options[s.selectedIndex]].filter(Boolean) as RawOption[] : [];
      return { question: q.question, header: q.header, selections: this.answerFor(q, s), selectedOptions, customAnswer: s.customText ?? undefined };
    });
    const answers: Record<string, string | string[]> = {};
    for (const detail of answerDetails) answers[detail.question] = detail.selections.length === 1 ? detail.selections[0] : detail.selections;
    this.resolved = true;
    this.done({ questions: this.rawQuestions, answers, answerDetails, metadata: this.metadata, cancelled: false });
  }
}

function isPrintable(data: string): boolean {
  return data.length === 1 && data >= " " && data !== "\x7f";
}
