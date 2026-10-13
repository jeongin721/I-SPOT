// 화면 위 한 줄 안내(불러오는 중 · 오류 · 대상 없음). 값은 src/data/screens/common.ts 의 screenNotice 가 만든다.
import A from './A';

export default function Notice({ value, style }) {
  if (!value) return null;
  return (
    <p className="note" role={value.alert ? 'alert' : 'status'} style={{ margin: 0, ...style }}>
      {value.text}
      {value.retry ? (
        <>
          {' '}
          <button type="button" className="btn btn-s btn-sm" onClick={value.retry}>
            다시 시도
          </button>
        </>
      ) : null}
      {value.href ? (
        <>
          {' '}
          <A to={value.href}>{value.hrefLabel}</A>
        </>
      ) : null}
    </p>
  );
}
