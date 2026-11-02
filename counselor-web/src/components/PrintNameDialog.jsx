// 인쇄 · 내보내기 전에 이름 표시 방식(실명 그대로 / 이름 가리기)을 고르는 창(10/29 · 10/30 디자인 out-*).
// 내담자 정보 탭 브리핑 '인쇄 · PDF' 와 종결보고서 'PDF · HWP로 내보내기' 가 같이 쓴다.
// printMasked: 이름 가리기면 인쇄하는 동안만 root 안 글자를 바꾸고(data/maskName — 사례 별칭) 되돌린다.
// bodyClass 를 주면 인쇄 동안 body 에 붙인다(브리핑만 인쇄하는 print-brief).
import { useState } from 'react';
import { maskExample, maskName } from '../data/maskName';
import './PrintNameDialog.css';

export function printMasked({ root, name, mask, bodyClass }) {
  const changed = [];
  const target = root || document.body;
  if (mask && name) {
    const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const next = maskName(node.nodeValue, name);
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

export default function PrintNameDialog({ title, goLabel, name, onClose, onRun }) {
  const [mask, setMask] = useState(true);
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
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button type="button" className="btn btn-s" onClick={onClose}>
            취소
          </button>
          <button type="button" className="btn btn-p" onClick={() => onRun(mask)}>
            {goLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
