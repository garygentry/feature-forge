// GENERATED — DO NOT EDIT. Source: scripts/build-adapters.py
// Regenerate with: python3 scripts/build-adapters.py

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Key, matchesKey, Text, visibleWidth, wrapTextWithAnsi } from "@earendil-works/pi-tui";
import { Type } from "typebox";

interface QuestionOption {
  label: string;
  description?: string;
  preview?: string;
}

interface QuestionInput {
  question: string;
  header?: string;
  multiSelect?: boolean;
  options: QuestionOption[];
}

interface AskUserQuestionInput {
  questions: QuestionInput[];
  metadata?: Record<string, unknown>;
}

interface AnswerDetail {
  question: string;
  header?: string;
  selections: string[];
  selectedOptions: QuestionOption[];
  customAnswer?: string;
  cancelled?: boolean;
}

interface AskUserQuestionResult {
  questions: QuestionInput[];
  answers: Record<string, string | string[]>;
  answerDetails: AnswerDetail[];
  response?: string;
  metadata: Record<string, unknown>;
}

const OptionSchema = Type.Object({
  label: Type.String({ description: "Option label shown to the user" }),
  description: Type.Optional(Type.String({ description: "Optional explanation/trade-off shown below the label" })),
  preview: Type.Optional(Type.String({ description: "Optional preview text shown with the option" })),
});

const QuestionSchema = Type.Object({
  question: Type.String({ description: "Question to ask the user" }),
  header: Type.Optional(Type.String({ description: "Optional short section heading" })),
  multiSelect: Type.Optional(Type.Boolean({ description: "Allow multiple options" })),
  options: Type.Array(OptionSchema, { minItems: 2, maxItems: 4, description: "Multiple-choice options; Other/custom is added automatically" }),
});

const ParamsSchema = Type.Object({
  questions: Type.Array(QuestionSchema, { minItems: 1, maxItems: 4, description: "Questions to ask" }),
  metadata: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
});

export default function askUserQuestion(pi: ExtensionAPI) {
  const tool = {
    name: "AskUserQuestion",
    label: "Ask User Question",
    description:
      "Ask the user one to four structured multiple-choice questions. Use only for genuine user decisions; supports automatic Other/custom answers, per-question headings, previews, and multi-select.",
    parameters: ParamsSchema,
    executionMode: "sequential",
    async execute(_toolCallId, params: AskUserQuestionInput, _signal, _onUpdate, ctx) {
      const validationError = validateInput(params);
      if (validationError) {
        return { content: [{ type: "text", text: `Error: ${validationError}` }], details: { questions: params.questions ?? [], answers: {}, answerDetails: [] }, isError: true };
      }

      if (ctx.mode !== "tui") {
        const answerDetails = params.questions.map((q) => ({ question: q.question, header: q.header, selections: [], selectedOptions: [], cancelled: true }));
        return {
          content: [{ type: "text", text: "Error: AskUserQuestion requires interactive Pi TUI mode; UI is unavailable in this run." }],
          details: { questions: params.questions, answers: {}, answerDetails, metadata: params.metadata ?? {} },
          isError: true,
        };
      }

      const result = await ctx.ui.custom<AskUserQuestionResult | null>((tui: any, theme: any, _kb: any, done: any) =>
        createQuestionnaire(tui, theme, params, done),
      );

      if (!result) {
        const answerDetails = params.questions.map((q) => ({ question: q.question, header: q.header, selections: [], selectedOptions: [], cancelled: true }));
        return {
          content: [{ type: "text", text: "User cancelled AskUserQuestion." }],
          details: { questions: params.questions, answers: {}, answerDetails, metadata: params.metadata ?? {} },
          isError: true,
        };
      }

      const summary = result.answerDetails
        .map((a, i) => `${i + 1}. ${a.question}: ${Array.isArray(result.answers[a.question]) ? (result.answers[a.question] as string[]).join(", ") : result.answers[a.question]}`)
        .join("\n");
      return { content: [{ type: "text", text: `User answered:\n${summary}` }], details: result };
    },
    renderCall(args, theme) {
      const count = Array.isArray(args.questions) ? args.questions.length : 0;
      return new Text(theme.fg("toolTitle", theme.bold("AskUserQuestion ")) + theme.fg("muted", `${count} question${count === 1 ? "" : "s"}`), 0, 0);
    },
    renderResult(result, _options, theme) {
      const details = result.details as AskUserQuestionResult | undefined;
      const answerDetails = details?.answerDetails ?? [];
      const text = answerDetails
        .map((a) => (a.cancelled ? theme.fg("warning", `✕ ${a.question}: cancelled`) : theme.fg("success", "✓ ") + theme.fg("accent", `${a.question}: ${a.selections.join(", ")}`)))
        .join("\n");
      return new Text(text || (result.content[0]?.type === "text" ? result.content[0].text : ""), 0, 0);
    },
  };

  pi.on("session_start", async () => {
    if (pi.getAllTools().some((existing) => existing.name === "AskUserQuestion")) return;
    pi.registerTool(tool);
  });
}

function validateInput(params: AskUserQuestionInput): string | undefined {
  if (!Array.isArray(params.questions) || params.questions.length < 1 || params.questions.length > 4) return "AskUserQuestion requires 1-4 questions.";
  for (const [i, q] of params.questions.entries()) {
    if (!q || typeof q.question !== "string" || !q.question.trim()) return `Question ${i + 1} requires question text.`;
    if (q.header && visibleWidth(q.header) > 12) return `Question ${i + 1} header must be 12 characters or fewer.`;
    if (!Array.isArray(q.options) || q.options.length < 2 || q.options.length > 4) return `Question ${i + 1} requires 2-4 options.`;
    for (const [j, opt] of q.options.entries()) {
      if (!opt || typeof opt.label !== "string" || !opt.label.trim()) return `Question ${i + 1}, option ${j + 1} requires a label.`;
    }
  }
  return undefined;
}

function createQuestionnaire(tui: any, theme: any, params: AskUserQuestionInput, done: (result: AskUserQuestionResult | null) => void) {
  const questions = params.questions;
  const answers = new Map<number, AnswerDetail>();
  let qIndex = 0;
  let optIndex = 0;
  let customMode = false;
  let customDraft = "";
  let cachedLines: string[] | undefined;
  const selected = new Map<number, Set<number>>();

  const refresh = () => {
    cachedLines = undefined;
    tui.requestRender();
  };
  const current = () => questions[qIndex];
  const currentSelected = () => {
    if (!selected.has(qIndex)) selected.set(qIndex, new Set());
    return selected.get(qIndex)!;
  };
  const allOptions = (q: QuestionInput) => [...q.options, { label: "Other", description: "Type a custom response" }];
  const customIndex = (q: QuestionInput) => q.options.length;
  const isPrintableInput = (value: string) => value.length > 0 && !/[\x00-\x1F\x7F]/.test(value);
  const startCustom = (initial = "") => {
    customMode = true;
    customDraft = initial;
    refresh();
  };
  const saveAnswer = (detail: AnswerDetail) => {
    answers.set(qIndex, detail);
  };
  const advance = () => {
    if (qIndex < questions.length - 1) {
      qIndex += 1;
      optIndex = 0;
      customMode = false;
      customDraft = "";
      refresh();
      return;
    }
    finish();
  };
  const finish = () => {
    if (answers.size < questions.length) return;
    const answerDetails = questions.map((_q, i) => answers.get(i)!).filter(Boolean);
    const answerRecord: Record<string, string | string[]> = {};
    for (const detail of answerDetails) {
      answerRecord[detail.question] = detail.selections.length === 1 ? detail.selections[0]! : detail.selections;
    }
    done({ questions, answers: answerRecord, answerDetails, metadata: params.metadata ?? {} });
  };
  const submitCustom = () => {
    const q = current();
    const custom = customDraft.trim();
    if (!custom) return;
    saveAnswer({ question: q.question, header: q.header, selections: [custom], selectedOptions: [], customAnswer: custom });
    advance();
  };
  const submitOption = () => {
    const q = current();
    const opts = allOptions(q);
    if (optIndex === customIndex(q)) {
      startCustom();
      return;
    }
    if (q.multiSelect) {
      const set = currentSelected();
      set.has(optIndex) ? set.delete(optIndex) : set.add(optIndex);
      refresh();
      return;
    }
    const opt = opts[optIndex]!;
    saveAnswer({ question: q.question, header: q.header, selections: [opt.label], selectedOptions: [opt] });
    advance();
  };
  const submitMultiCurrent = () => {
    const q = current();
    const set = currentSelected();
    if (!set.size) return;
    const opts = q.options;
    const selectedOptions = [...set].sort((a, b) => a - b).map((i) => opts[i]).filter(Boolean) as QuestionOption[];
    saveAnswer({ question: q.question, header: q.header, selections: selectedOptions.map((o) => o.label), selectedOptions });
    advance();
  };

  return {
    invalidate: () => {
      cachedLines = undefined;
    },
    handleInput(data: string) {
      const q = current();
      const opts = allOptions(q);
      if (customMode) {
        if (matchesKey(data, Key.escape)) {
          customMode = false;
          customDraft = "";
          refresh();
          return;
        }
        if (matchesKey(data, Key.enter)) {
          submitCustom();
          return;
        }
        if (matchesKey(data, Key.backspace)) {
          customDraft = customDraft.slice(0, -1);
          refresh();
          return;
        }
        if (isPrintableInput(data)) {
          customDraft += data;
          refresh();
        }
        return;
      }
      if (matchesKey(data, Key.up)) {
        optIndex = Math.max(0, optIndex - 1);
        refresh();
        return;
      }
      if (matchesKey(data, Key.down)) {
        optIndex = Math.min(opts.length - 1, optIndex + 1);
        refresh();
        return;
      }
      if (matchesKey(data, Key.left) && qIndex > 0) {
        qIndex -= 1;
        optIndex = 0;
        refresh();
        return;
      }
      if (matchesKey(data, Key.space) && q.multiSelect && optIndex !== customIndex(q)) {
        submitOption();
        return;
      }
      if (matchesKey(data, Key.enter)) {
        if (q.multiSelect && optIndex !== customIndex(q) && currentSelected().size > 0) submitMultiCurrent();
        else submitOption();
        return;
      }
      if (matchesKey(data, Key.escape)) done(null);
      if (optIndex === customIndex(q) && isPrintableInput(data)) startCustom(data);
    },
    render(width: number) {
      if (cachedLines) return cachedLines;
      const lines: string[] = [];
      const w = Math.max(1, width);
      const add = (text: string) => lines.push(...wrapTextWithAnsi(text, w));
      const addPref = (prefix: string, text: string) => {
        const pw = visibleWidth(prefix);
        const wrapped = wrapTextWithAnsi(text, Math.max(1, w - pw));
        wrapped.forEach((line, i) => lines.push((i === 0 ? prefix : " ".repeat(pw)) + line));
      };
      const q = current();
      const opts = allOptions(q);
      const set = currentSelected();
      lines.push(theme.fg("accent", "─".repeat(w)));
      add(theme.fg("muted", `Question ${qIndex + 1} of ${questions.length}`));
      if (q.header) add(theme.fg("accent", theme.bold(q.header)));
      add(theme.fg("text", q.question));
      lines.push("");
      opts.forEach((opt, i) => {
        const cursor = i === optIndex ? theme.fg("accent", "> ") : "  ";
        const mark = q.multiSelect && i !== customIndex(q) ? (set.has(i) ? "[x] " : "[ ] ") : "";
        const suffix = i === customIndex(q) && customMode ? `: ${customDraft}▏` : "";
        addPref(cursor, theme.fg(i === optIndex ? "accent" : "text", `${i + 1}. ${mark}${opt.label}${suffix}`));
        if (opt.description) addPref("     ", theme.fg("muted", opt.description));
        if (opt.preview) addPref("     ", theme.fg("dim", `Preview: ${opt.preview}`));
      });
      lines.push("");
      const canSubmit = q.multiSelect && set.size > 0;
      addPref(" ", theme.fg(canSubmit ? "success" : "muted", canSubmit ? "Submit selected answers with Enter" : "Submit appears after selecting an option"));
      const help = customMode
        ? "Enter submit custom • Backspace edit • Esc back"
        : q.multiSelect
          ? "↑↓ navigate • Space toggle • Enter submit/select custom • ← previous • Esc cancel"
          : "↑↓ navigate • Enter select/custom • type on Other • ← previous • Esc cancel";
      addPref(" ", theme.fg("dim", help));
      lines.push(theme.fg("accent", "─".repeat(w)));
      cachedLines = lines;
      return lines;
    },
  };
}
