// 문서함 빈 양식의 카드 · 미리보기 · 열람/입력 창(11/09 디자인 DocBox.dc.html). 값과 문구는 src/data/blankForms.ts.
//
// 저장(2026-11-19, 디자인 '저장 → 제목 · 폴더를 정해 별도 문서로'): 작성 중 '저장' → 제목 · 저장할 폴더 · '아이 정보 없음' 확인 →
// 작성 양식 파일(.ispotform, JSON)로 문서함에 올린다(onSave). 저장한 파일을 열면 initialValues 로 이어 쓴다(다시 저장하면 새 문서).
// 공용 보관함이라 아이를 알아볼 수 있는 정보는 넣지 않게 확인을 받는다 — 사례 서식은 사례 상세 › 문서함에서 쓴다.
// 내려받기는 지금 적은 내용이 든 HTML 이다(빈 칸이면 빈 양식).
// 스타일은 DocBox.css 에 있다(.pg-DocBox 안에서만 쓴다).
import { memo, useEffect, useRef, useState } from 'react';
import { blankFormPages, clampScore } from '../data/blankForms';

// 읽기 칸. values 를 주면(사례 문서함 '열기' 보기 창) 저장한 값을 칸에 적고, 고른 항목은 ☑ 로 보인다.
function ReadSeg({ g, values }) {
  const val = values ? values[g.key] : undefined;
  switch (g.t) {
    case 'i':
      return g.fill ? (
        <span className="fv" style={{ flex: '1 1 90px', minWidth: '60px' }}>
          {val || null}
        </span>
      ) : (
        <span className="fv" style={{ flex: '0 0 auto', minWidth: g.width }}>
          {val || null}
        </span>
      );
    case 'n':
      return (
        <span className="fv" style={{ flex: '0 0 auto', minWidth: '56px' }}>
          {val || null}
        </span>
      );
    case 'ta':
      return (
        <span className="fvt" style={{ minHeight: `${g.rows * 22 + 14}px` }}>
          {val || null}
        </span>
      );
    default: {
      const on = values ? (g.group ? val === g.text : !!val) : false;
      return (
        <span className={`${g.cls} fvc`}>
          <span className="fbox" aria-hidden="true">
            {on ? '☑' : '☐'}
          </span>
          <span className="fcl-t" style={on ? { fontWeight: 700 } : undefined}>
            {g.text}
          </span>
          {on ? <span style={{ position: 'absolute', left: '-9999px' }}>(선택됨)</span> : null}
        </span>
      );
    }
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

export function Paper({ page, values, onSet }) {
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
                return editing ? (
                  <EditSeg key={gi} g={g} values={values} onSet={onSet} />
                ) : (
                  <ReadSeg key={gi} g={g} values={values} />
                );
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

// 저장 창(디자인 sv): 제목 · 저장할 폴더 · 아이 정보 없음 확인.
function SaveDialog({ defaultTitle, folders, defaultFolder, onCancel, onSave }) {
  const [title, setTitle] = useState(defaultTitle);
  const [folder, setFolder] = useState(defaultFolder ?? '');
  const [noChild, setNoChild] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const go = async () => {
    const t = title.trim();
    if (!t) return setErr('문서 제목을 입력해 주세요.');
    if (!noChild) return setErr('아이를 알아볼 수 있는 정보가 없는지 확인해 주세요.');
    setBusy(true);
    setErr('');
    const ok = await onSave({ title: t, folderId: folder || null });
    setBusy(false);
    if (!ok) setErr('저장하지 못했어요. 위 안내 줄을 확인해 주세요.');
  };
  return (
    <div className="sv-ov" onClick={() => !busy && onCancel()}>
      <section className="sv" role="dialog" aria-modal="true" aria-label="문서로 저장" onClick={(e) => e.stopPropagation()}>
        <b style={{ fontSize: '17px' }}>문서로 저장</b>
        <label className="sv-f">
          <span className="sv-l">문서 제목</span>
          <input className="inp" type="text" maxLength={80} value={title} onChange={(e) => setTitle(e.target.value)} aria-label="문서 제목" style={{ height: '40px' }} />
        </label>
        <label className="sv-f">
          <span className="sv-l">저장할 폴더</span>
          <select className="inp" value={folder} onChange={(e) => setFolder(e.target.value)} aria-label="저장할 폴더" style={{ height: '40px' }}>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', fontSize: '13px', lineHeight: 1.5 }}>
          <input type="checkbox" checked={noChild} onChange={(e) => setNoChild(e.target.checked)} style={{ marginTop: '3px' }} />
          <span>
            아동 이름 · 생년월일 · 주소 등 <b>아이를 알아볼 수 있는 정보가 없습니다.</b> 문서함은 모든 상담원이 봅니다 — 사례 서식은 사례 상세 ›
            문서함에서 작성해 주세요.
          </span>
        </label>
        {err ? (
          <span className="note" role="alert" style={{ color: '#A33B2E' }}>
            {err}
          </span>
        ) : null}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button type="button" className="btn btn-sm btn-s" onClick={onCancel} disabled={busy}>
            취소
          </button>
          <button type="button" className="btn btn-sm btn-p" onClick={go} disabled={busy}>
            {busy ? '저장하는 중…' : '저장'}
          </button>
        </div>
      </section>
    </div>
  );
}

export function BlankFormDialog({
  formId,
  name,
  editing,
  onEdit,
  onClose,
  onDownload,
  initialValues,
  savedTitle,
  folders,
  defaultFolder,
  onSave,
}) {
  const [values, setValues] = useState(() => ({ ...(initialValues || {}) }));
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const opener = useRef(document.activeElement);
  // 저장한 뒤로 바뀐 칸이 있는가(처음 연 값 · 마지막 저장 값과 비교).
  const [base, setBase] = useState(() => JSON.stringify(initialValues || {}));
  const dirty = JSON.stringify(values) !== base && Object.values(values).some(Boolean);
  const set = (key, value) => setValues((cur) => ({ ...cur, [key]: value }));

  // 저장하지 않은 내용이 있으면 Esc 로 잘못 닫히지 않게 한다(닫기 단추로는 닫힌다).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && !dirty && !saving) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dirty, saving, onClose]);
  useEffect(() => () => opener.current?.focus?.(), []);

  return (
    <div className="fm-ov" role="dialog" aria-modal="true" aria-label={`${name} ${editing ? '작성' : '보기'}`}>
      <div className="fm-bar">
        <b className="fm-t">{name}</b>
        <span className="note fm-st" role="status">
          {editing
            ? savedAt
              ? `저장했어요(${savedAt}) · 이어서 고친 뒤 다시 저장하면 새 문서로 남아요`
              : `${savedTitle ? `‘${savedTitle}’ 이어 쓰기 · ` : ''}'저장'을 눌러야 남아요 · 아이를 알아볼 수 있는 정보는 적지 마세요 · 사례 서식은 사례 상세 › 문서함에서`
            : '내용 보기 · 읽기 전용'}
        </span>
        {editing ? (
          <>
            <button type="button" className="btn btn-sm btn-s" onClick={() => setValues({})}>
              모두 지우기
            </button>
            {onSave ? (
              <button type="button" className="btn btn-sm btn-p" onClick={() => setSaving(true)} disabled={!Object.values(values).some(Boolean)}>
                저장
              </button>
            ) : null}
          </>
        ) : (
          <button type="button" className="btn btn-sm btn-p" onClick={onEdit}>
            작성하기
          </button>
        )}
        <button type="button" className="btn btn-sm btn-s" onClick={() => onDownload(values)}>
          {Object.values(values).some(Boolean) ? '↓ 내려받기' : '↓ 빈 양식 내려받기'}
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
      {saving ? (
        <SaveDialog
          defaultTitle={savedTitle || name}
          folders={folders || [{ id: '', name: '폴더 없음' }]}
          defaultFolder={defaultFolder}
          onCancel={() => setSaving(false)}
          onSave={async ({ title, folderId }) => {
            const ok = await onSave({ title, folderId, values });
            if (ok) {
              setSaving(false);
              setBase(JSON.stringify(values));
              setSavedAt(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
            }
            return ok;
          }}
        />
      ) : null}
    </div>
  );
}
