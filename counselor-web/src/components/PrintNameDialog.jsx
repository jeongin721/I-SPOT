// 인쇄 · 내보내기 전에 이름 표시 방식(실명 그대로 / 이름 가리기)을 고르는 창(10/29 · 10/30 디자인 out-*).
// 내담자 정보 탭 브리핑 '인쇄 · PDF' 와 종결보고서 'PDF · HWP로 내보내기' 가 같이 쓴다.
// printMasked: 이름 가리기면 인쇄하는 동안만 root 안 글자를 바꾸고(data/maskName) 되돌린다. names(그 사례의 등록 이름 전부와
// 별칭 — 사례 상세)를 주면 그것을 모두, 없으면 name 하나(사례 별칭 — 종결보고서)를 가린다.
// maskReady=false(사례 상세에서 등록 이름 목록을 아직 못 받음)면 '이름 가리기' 로는 내보내지 않는다(Codex #129 R3).
// bodyClass 를 주면 인쇄 동안 body 에 붙인다(브리핑만 인쇄하는 print-brief).
import { useState } from 'react';
import { maskExample, maskNames } from '../data/maskName';
import './PrintNameDialog.css';

export function printMasked({ root, name, names, mask, bodyClass }) {
  const changed = [];
  const target = root || document.body;
  const list = names ?? (name ? [name] : []);
  if (mask && list.length) {
    const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const next = maskNames(node.nodeValue, list);
      if (next !== node.nodeValue) {
        changed.push([node, node.nodeValue]);
        node.nodeValue = next;
      }
    }
  }
  if (bodyClass) document.body.classList.add(bodyClass);
  try {
    window.print();
  } finally {
    if (bodyClass) document.body.classList.remove(bodyClass);
    changed.forEach(([node, value]) => {
      node.nodeValue = value;
    });
  }
}

export default function PrintNameDialog({ title, goLabel, name, maskReady = true, onClose, onRun }) {
  const [mask, setMask] = useState(true);
  const blocked = mask && !maskReady;
  const shown = name || '이서윤';
  return (
    <div className="out-ov">
      <div className="out-dlg" role="dialog" aria-modal="true" aria-labelledby="out-t">
        <b id="out-t" style={{ fontSize: '18px' }}>
          {title}
        </b>
        <span className="note" style={{ marginTop: '-6px' }}>
          출력물에 들어갈 이름 표시 방식을 고르세요.
        </span>
        <div role="radiogroup" aria-label="이름 표시 방식" className="out-opts">
          {[
            [false, '실명 그대로', `예) ${shown}`],
            [true, '이름 가리기', `예) ${maskExample(shown)}`],
          ].map(([m, label, ex]) => (
            <button
              key={label}
              type="button"
              role="radio"
              aria-checked={mask === m ? 'true' : 'false'}
              className={`out-opt ${mask === m ? 'on' : ''}`}
              onClick={() => setMask(m)}
            >
              <span className="out-rd" aria-hidden="true"></span>
              <span style={{ flex: '1', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <b style={{ fontSize: '14px' }}>{label}</b>
                <span className="note">{ex}</span>
              </span>
            </button>
          ))}
        </div>
        {blocked ? (
          <span className="note" role="alert" style={{ color: '#A33B2E' }}>
            등록된 이름 목록을 아직 받지 못해 이름을 가릴 수 없습니다. 실명 정보를 다시 불러온 뒤 {goLabel}해 주세요.
          </span>
        ) : null}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button type="button" className="btn btn-s" onClick={onClose}>
            취소
          </button>
          <button
            type="button"
            className="btn btn-p"
            disabled={blocked}
            onClick={() => {
              // 등록 이름 전부를 받기 전에는 가린 출력을 내지 않는다(위 안내).
              if (blocked) return;
              onRun(mask);
            }}
          >
            {goLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
