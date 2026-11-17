// 문서함 빈 양식의 카드 · 미리보기 · 열람/입력 창(11/09 디자인 DocBox.dc.html). 값과 문구는 src/data/blankForms.ts.
//
// 디자인에서 뺀 것: 저장(별도 문서로 저장 · 폴더 고르기), 폴더 옮기기. 입력값은 이 창의 상태에만 있어 창을 닫으면 사라진다.
// 내려받기는 입력값과 상관없이 빈 양식이다.
// 스타일은 DocBox.css 에 있다(.pg-DocBox 안에서만 쓴다).
import { memo, useEffect, useRef, useState } from 'react';
import { blankFormPages, clampScore } from '../data/blankForms';

function ReadSeg({ g }) {
  switch (g.t) {
    case 'i':
      return g.fill ? (
        <span className="fv" style={{ flex: '1 1 90px', minWidth: '60px' }} />
      ) : (
        <span className="fv" style={{ flex: '0 0 auto', minWidth: g.width }} />
      );
    case 'n':
      return <span className="fv" style={{ flex: '0 0 auto', minWidth: '56px' }} />;
    case 'ta':
      return <span className="fvt" style={{ minHeight: `${g.rows * 22 + 14}px` }} />;
    default:
      return (
        <span className={`${g.cls} fvc`}>
          <span className="fbox" aria-hidden="true">
            ☐
          </span>
          <span className="fcl-t">{g.text}</span>
        </span>
      );
  }
}

function EditSeg({ g, values, onSet }) {
  switch (g.t) {
    case 'i':
      return (
        <input
          className="fi"
          type="text"
          aria-label={g.aria}
          value={values[g.key] || ''}
          onChange={(e) => onSet(g.key, e.target.value)}
          style={g.fill ? { width: 'auto', flex: '1 1 90px' } : { width: g.width, flex: '0 0 auto' }}
        />
      );
    case 'n':
      return (
        <input
          className="fi fn"
          type="number"
          inputMode="numeric"
          min="1"
          max="10"
          step="1"
          aria-label={g.aria}
          value={values[g.key] || ''}
          onChange={(e) => onSet(g.key, clampScore(e.target.value))}
        />
      );
    case 'ta':
      return (
        <textarea
          className="fta"
          rows={g.rows}
          aria-label={g.aria}
          value={values[g.key] || ''}
          onChange={(e) => onSet(g.key, e.target.value)}
        />
      );
    default: {
      const on = g.group ? values[g.key] === g.text : !!values[g.key];
      const toggle = () => onSet(g.key, g.group ? (on ? '' : g.text) : !on);
      return (
        <label className={g.cls}>
          <input type="checkbox" checked={on} onChange={toggle} aria-label={g.aria} />
          <span className="fcl-t">{g.text}</span>
        </label>
      );
    }
  }
}

function Paper({ page, values, onSet }) {
  const editing = !!onSet;
  return (
    <div className="paper">
      {page.map((block, bi) => (
        <div key={bi} className="fg" style={{ gridTemplateColumns: block.cols }}>
          {block.cells.map((c, ci) => (
            <div key={ci} className={c.cls} style={{ gridColumn: `span ${c.colSpan}`, gridRow: `span ${c.rowSpan}` }}>
              {c.segs.map((g, gi) => {
                if (g.t === 's') return <span key={gi} className="fs">{g.text}</span>;
                if (g.t === 'g') return <span key={gi} className="fgd">{g.text}</span>;
                if (g.t === 'br') return <span key={gi} className="fbr" />;
                if (g.t === 'sp') return <span key={gi} className={`fsp ${g.q}`} />;
                return editing ? <EditSeg key={gi} g={g} values={values} onSet={onSet} /> : <ReadSeg key={gi} g={g} />;
              })}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// 카드 미리보기(첫 쪽). 입력칸 없이 그려 키보드 초점이 들어가지 않는다.
const Preview = memo(function Preview({ id }) {
  return (
    <div className="pv-form">
      <Paper page={blankFormPages(id)[0]} />
    </div>
  );
});

function onActivate(run) {
  return (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      run();
    }
  };
}

export function BlankFormCard({ doc }) {
  return (
    <article className="doc">
      <div
        className="pv pv-click"
        role="button"
        tabIndex={0}
        aria-label={doc.viewLabel}
        onClick={doc.view}
        onKeyDown={onActivate(doc.view)}
      >
        <Preview id={doc.formId} />
      </div>
      <div className="dname dname-click" onClick={doc.view}>
        {doc.name}
      </div>
      <div className="dmeta">{doc.meta}</div>
      <button type="button" className="btn btn-sm btn-p" onClick={doc.open}>
        작성하기
      </button>
      <div>
        <button type="button" className="btn btn-sm btn-s" onClick={doc.download}>
          ↓ 내려받기
        </button>
      </div>
    </article>
  );
}

export function BlankFormDialog({ formId, name, editing, onEdit, onClose, onDownload }) {
  const [values, setValues] = useState({});
  const opener = useRef(document.activeElement);
  const dirty = Object.values(values).some(Boolean);
  const set = (key, value) => setValues((cur) => ({ ...cur, [key]: value }));

  // 입력한 내용은 저장되지 않으므로, 내용이 있으면 Esc 로 잘못 닫히지 않게 한다(닫기 단추로는 닫힌다).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && !dirty) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dirty, onClose]);
  useEffect(() => () => opener.current?.focus?.(), []);

  return (
    <div className="fm-ov" role="dialog" aria-modal="true" aria-label={`${name} ${editing ? '작성' : '보기'}`}>
      <div className="fm-bar">
        <b className="fm-t">{name}</b>
        <span className="note fm-st" role="status">
          {editing
            ? '입력한 내용은 저장되지 않아요 · 닫으면 사라져요 · 사례에 남기려면 사례 상세 › 문서함에서 작성해 주세요'
            : '내용 보기 · 읽기 전용'}
        </span>
        {editing ? (
          <button type="button" className="btn btn-sm btn-s" onClick={() => setValues({})}>
            모두 지우기
          </button>
        ) : (
          <button type="button" className="btn btn-sm btn-p" onClick={onEdit}>
            작성하기
          </button>
        )}
        <button type="button" className="btn btn-sm btn-s" onClick={onDownload}>
          ↓ 빈 양식 내려받기
        </button>
        <button type="button" className="btn btn-sm btn-s" onClick={onClose} autoFocus>
          닫기
        </button>
      </div>
      <div className="fm-body">
        {blankFormPages(formId).map((page, i) => (
          <Paper key={i} page={page} values={values} onSet={editing ? set : undefined} />
        ))}
      </div>
    </div>
  );
}
