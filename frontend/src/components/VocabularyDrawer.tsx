import {
  deleteVocabulary,
  updateVocabulary,
  type VocabularyItem,
} from "../api";

export function VocabularyDrawer({
  items,
  open,
  onClose,
  onChange,
}: {
  items: VocabularyItem[];
  open: boolean;
  onClose: () => void;
  onChange: (items: VocabularyItem[]) => void;
}) {
  if (!open) return null;

  const patch = async (
    item: VocabularyItem,
    updates: Partial<Pick<VocabularyItem, "mastery_status" | "note">>,
  ) => {
    const updated = await updateVocabulary(item.id, updates);
    onChange(items.map((candidate) => candidate.id === item.id ? updated : candidate));
  };

  const remove = async (item: VocabularyItem) => {
    await deleteVocabulary(item.id);
    onChange(items.filter((candidate) => candidate.id !== item.id));
  };

  return (
    <aside className="vocabulary-drawer" aria-label="个人词汇栏">
      <header>
        <div><p className="eyebrow">VOCABULARY</p><h2>我的词汇</h2></div>
        <button className="icon-button" aria-label="关闭词汇栏" onClick={onClose}>×</button>
      </header>
      <p className="drawer-hint">这里只保存你主动划选的词汇，不会自动提取术语。</p>
      <div className="vocabulary-list">
        {items.map((item) => (
          <article className="vocabulary-card" key={item.id}>
            <div className="vocabulary-title">
              <span className="color-dot" style={{ backgroundColor: item.color }} />
              <strong>{item.display_text}</strong>
              <button aria-label={`删除 ${item.display_text}`} onClick={() => void remove(item)}>删除</button>
            </div>
            <p className="vocabulary-translation">{item.contextual_translation}</p>
            <blockquote>{item.source_sentence}</blockquote>
            <div className="vocabulary-meta">
              {item.page_number && <span>第 {item.page_number} 页</span>}
              <select
                aria-label={`${item.display_text} 掌握状态`}
                value={item.mastery_status}
                onChange={(event) => void patch(item, { mastery_status: event.target.value as VocabularyItem["mastery_status"] })}
              >
                <option value="new">陌生</option>
                <option value="learning">学习中</option>
                <option value="mastered">已掌握</option>
              </select>
            </div>
            <textarea
              defaultValue={item.note}
              placeholder="添加个人备注"
              onBlur={(event) => void patch(item, { note: event.target.value })}
            />
          </article>
        ))}
        {!items.length && <div className="empty-drawer">在阅读区划选文字并右键收藏。</div>}
      </div>
    </aside>
  );
}
