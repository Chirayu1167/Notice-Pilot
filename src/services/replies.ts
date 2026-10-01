import type { ReplyDraft } from "../types";
import { getReplyDraft, listReplyDrafts, saveReplyDraft } from "./agent";

export async function getReplyDraftForNotice(noticeId: string): Promise<ReplyDraft | null> {
  const drafts = await listReplyDrafts(noticeId);
  return drafts[0] ?? null;
}

export async function fetchReplyDraft(draftId: string): Promise<ReplyDraft> {
  return getReplyDraft(draftId);
}

export async function saveReplyDraftContent(
  draftId: string,
  content: string
): Promise<ReplyDraft> {
  return saveReplyDraft(draftId, { content });
}
