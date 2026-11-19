// 사례 상세 › 문서함(탭 5) 기관 서식 '열기' 읽기 전용 보기 창(11/10 디자인 CaseDocs.dc.html).
// 공용 문서함(DocBox)과 같은 서식 모양(components/BlankForm 의 Paper)에 이 사례에 저장한 값을 채워 보인다.
// 창 위 '수정' → 원래 작성 화면(CaseForm ?form=A~D). 값은 data/screens/caseForm.ts blankViewValues.
// 스타일은 DocBox.css(.pg-DocBox 안) 그대로 쓴다.
import { useEffect, useRef } from 'react';
import A from './A';
import { Paper } from './BlankForm';
import { blankFormPages } from '../data/blankForms';
import { useTheme } from '../theme';
import '../pages/DocBox.css';

export default function CaseFormView({ name, formId, values, editHref, status, onClose }) {
  const theme = useTheme();
  const opener = useRef(document.activeElement);
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  useEffect(() => () => opener.current?.focus?.(), []);

  return (
    <div className="pg-DocBox">
      <div className={theme.cls}>
        <div className="fm-ov" role="dialog" aria-modal="true" aria-label={`${name} 보기`}>
          <div className="fm-bar">
            <b className="fm-t">{name}</b>
            <span className="note fm-st" role="status">
              내용 보기 · 읽기 전용{status ? ` · ${status}` : ''}
            </span>
            {editHref ? (
              <A className="btn btn-sm btn-p" to={editHref}>
                수정
              </A>
            ) : null}
            <button type="button" className="btn btn-sm btn-s" onClick={onClose} autoFocus>
              닫기
            </button>
          </div>
          <div className="fm-body">
            {blankFormPages(formId).map((page, i) => (
              <Paper key={i} page={page} values={values} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
