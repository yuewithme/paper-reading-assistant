import type { VocabularyItem } from "../api";
import { AcademicMarkdown } from "./AcademicMarkdown";

export function AnalysisMarkdown({
  text,
  vocabulary,
}: {
  text: string;
  vocabulary: VocabularyItem[];
}) {
  return (
    <div className="analysis-markdown">
      <AcademicMarkdown text={text} vocabulary={vocabulary} variant="analysis" />
    </div>
  );
}
